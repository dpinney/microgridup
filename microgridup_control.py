import random, re, datetime, json, os, tempfile, shutil, csv, math, base64
from os.path import join as pJoin
import subprocess
import pandas as pd
import numpy as np
import scipy
import collections
from scipy import spatial
import scipy.stats as st
from sklearn.preprocessing import LabelEncoder
import matplotlib.pyplot as plt
import plotly
import plotly.graph_objects as go
from plotly.tools import make_subplots

# OMF imports
import omf
from omf import geo
from omf import distNetViz
from omf.models import __neoMetaModel__
from omf.models.__neoMetaModel__ import *
from omf.models import flisr
from omf.solvers.opendss import dssConvert
from omf.solvers import opendss

def make_chart(csvName, category_name, x, y_list, year, microgrids, tree, chart_name, y_axis_name, ansi_bands=False, batt_cycle_chart=False, fossil_loading_chart=False, vsource_ratings=None):
	# print("vsource_ratings",vsource_ratings)
	gen_data = pd.read_csv(csvName)
	data = []
	unreasonable_voltages = {}
	batt_cycles = {}
	fossil_kwh_output = 0
	batt_kwh_ratings = {}
	fossil_kw_ratings = {}
	fossil_traces = []
	
	# info we need from tree: every battery by name with corresponding kwhrated, every fossil gen by name with corresponding kw 
	if batt_cycle_chart == True or fossil_loading_chart == True:
		for item in tree:
			if "generator.fossil" in item.get("object","x.x"):
				fossil_kw_ratings[item.get("object").split(".")[1]] = item.get("kw")
			if "storage.battery" in item.get("object","x.x"):
				batt_kwh_ratings[item.get("object").split(".")[1]] = item.get("kwhrated")
		# print("fossil_kw_ratings",fossil_kw_ratings)
		# print("batt_kwh_ratings",batt_kwh_ratings)

	# loop through objects in circuit
	for ob_name in set(gen_data[category_name]): 

		# set appropriate legend group based on microgrid 
		for key in microgrids:
			if microgrids[key]['gen_bus'] in ob_name:
				legend_group = key
				break
			legend_group = "Not_in_MG"

		# loop through phases
		for y_name in y_list: 
			this_series = gen_data[gen_data[category_name] == ob_name]

			# if lead_gen_ and not null values, add total output to running tally 
			if "lead_gen_" in ob_name and not this_series[y_name].isnull().values.any(): 
				fossil_kwh_output += sum(this_series[y_name])
				# if lead_gen_ and not null values, divide by provided kw rating to create loading percentage series
				fossil_kw_rating = vsource_ratings[ob_name.split("-")[1]]
				# print("ob_name",ob_name,"y_name",y_name,"vsource_ratings",vsource_ratings,"fossil_kw_rating",fossil_kw_rating)  
				fossil_percent_loading = [(x / float(fossil_kw_rating)) * 100 for x in this_series[y_name]]
				# add traces for fossil loading percentages to graph variable
				fossil_trace = go.Scatter(
					x = pd.to_datetime(this_series[x], unit = 'h', origin = pd.Timestamp(f'{year}-01-01')), #TODO: make this datetime convert arrays other than hourly or with a different startdate than Jan 1 if needed
					y = fossil_percent_loading,
					legendgroup=legend_group,
					legendgrouptitle_text=legend_group,
					showlegend=True,
					name=ob_name + '_' + y_name,
					hoverlabel = dict(namelength = -1)
					)
				fossil_traces.append(fossil_trace)
				# print("ob_name",ob_name,"y_name",y_name,"this_series[y_name][58:62]",this_series[y_name][58:62],"fossil_kw_rating",fossil_kw_rating,"fossil_percent_loading[58:62]",fossil_percent_loading[58:62])

			# if fossil_ and not null values, add total output to running tally
			if "fossil_" in ob_name and not this_series[y_name].isnull().values.any():
				fossil_kwh_output += sum(abs(this_series[y_name]))
				# if fossil_ and not null values, divide by kw rating to create loading percentage series  
				fossil_kw_rating = fossil_kw_ratings[ob_name.split("-")[1]]
				fossil_percent_loading = [(x / float(fossil_kw_rating)) * -100 for x in this_series[y_name]]
				# add traces for fossil loading percentages to graph variable
				fossil_trace = go.Scatter(
					x = pd.to_datetime(this_series[x], unit = 'h', origin = pd.Timestamp(f'{year}-01-01')), #TODO: make this datetime convert arrays other than hourly or with a different startdate than Jan 1 if needed
					y = fossil_percent_loading,
					legendgroup=legend_group,
					legendgrouptitle_text=legend_group,
					showlegend=True,
					name=ob_name + '_' + y_name,
					hoverlabel = dict(namelength = -1)
					)
				fossil_traces.append(fossil_trace)

			# if battery_ and not null values, count battery cycles 
			if "battery_" in ob_name and not this_series[y_name].isnull().values.any():
				batt_kwh_input_output = sum(abs(this_series[y_name]))
				batt_kwh_rating = batt_kwh_ratings[ob_name.split("-")[1]]
				cycles = batt_kwh_input_output / (2 * float(batt_kwh_rating)) 
				batt_cycles[f"{ob_name}_{y_name}"] = cycles
				# print("batt_kwh_input_output",batt_kwh_input_output,"batt_kwh_rating",batt_kwh_rating,"cycles",cycles)

			# flag loads that don't fall within ansi bands
			if "_load" in csvName:
				if (this_series[y_name] > 1.1).any() or (this_series[y_name] < 0.9).any():
					unreasonable_voltages[f"{ob_name}_{y_name}"] = ob_name

			# traces for gen, load, source, control
			name = ob_name + '_' + y_name
			if name in unreasonable_voltages:
				name = '[BAD]_' + name
			trace = go.Scatter(
				x = pd.to_datetime(this_series[x], unit = 'h', origin = pd.Timestamp(f'{year}-01-01')), #TODO: make this datetime convert arrays other than hourly or with a different startdate than Jan 1 if needed
				y = this_series[y_name],
				legendgroup=legend_group,
				legendgrouptitle_text=legend_group,
				showlegend = True,
				name = name,
				hoverlabel = dict(namelength = -1)
			)
			data.append(trace)
	
	# make fossil genset loading plot
	if fossil_loading_chart == True:
		new_layout = go.Layout(
			title = f"Fossil Genset Loading Percentage ({csvName})",
			xaxis = dict(title = 'Date'),
			yaxis = dict(title = 'Fossil Percent Loading')
			)
		fossil_fig = plotly.graph_objs.Figure(fossil_traces, new_layout)
		plotly.offline.plot(fossil_fig, filename=f'{csvName}_fossil_loading.plot.html', auto_open=False)

	# make battery cycles bar chart
	if batt_cycle_chart == True:
		# print("csvName",csvName, "batt_cycles",batt_cycles)
		new_trace = go.Bar(
			x = list(batt_cycles.keys()), 
			y = list(batt_cycles.values()) 
		)
		new_layout = go.Layout(
			title = "Battery Cycles",
			xaxis = dict(title = 'Battery'),
			yaxis = dict(title = 'Cycles')
			)
		new_fig = plotly.graph_objs.Figure(new_trace, new_layout)
		plotly.offline.plot(new_fig, filename=f'{csvName}_battery_cycles.plot.html', auto_open=False)

	# calculate total fossil genset consumption
	fuel_consumption_rate_gallons_per_kwh = 1 # <-- TO DO: is this a preset or an input?
	total_fossil = fuel_consumption_rate_gallons_per_kwh * fossil_kwh_output
	# add total fossil genset consumption to source plot title 
	if "_source" in csvName or "_gen" in csvName:
		title = f'{chart_name}. Fossil consumption of gensets = {total_fossil}'
	else:
		title = f'{chart_name}'

	# plots for gen, load, source, control
	layout = go.Layout(
		title = title,
		xaxis = dict(title = 'Date'),
		yaxis = dict(title = y_axis_name)
	)
	fig = plotly.graph_objs.Figure(data, layout)
	if ansi_bands == True:
		line_style = {'color':'Red', 'width':3, 'dash':'dashdot'}
		fig.add_hline(y=0.9, line=line_style)
		fig.add_hline(y=1.1, line=line_style)
	plotly.offline.plot(fig, filename=f'{csvName}.plot.html', auto_open=False)


def microgridTimeline(outputTimeline, workDir):
	# check to see if work directory is specified; otherwise, create a temporary directory
	if not workDir:
		workDir = tempfile.mkdtemp()
		print('@@@@@@', workDir)
	
	# TODO: update table after calculating outage stats
	def timelineStats(outputTimeline):
		new_html_str = """
			<table class="sortable" cellpadding="0" cellspacing="0">
				<thead>
					<tr>
						<th>Device</th>
						<th>Time</th>
						<th>Action</th>
						<th>Before</th>
						<th>After</th>
					</tr>
				</thead>
				<tbody>"""
		
		row = 0
		while row < len(outputTimeline):
			loadBeforeStr = outputTimeline.loc[row, 'loadBefore']
			loadAfterStr = outputTimeline.loc[row, 'loadAfter']
			loadStringDict = ["open", "closed", "online", "offline"]
			if str(loadBeforeStr) not in loadStringDict:
				loadBeforeStr = '{0:.3f}'.format(float(loadBeforeStr))
			if str(loadAfterStr) not in loadStringDict:
				loadAfterStr = '{0:.3f}'.format(float(loadAfterStr))
			new_html_str += '<tr><td>' + str(outputTimeline.loc[row, 'device']) + '</td><td>' + str(outputTimeline.loc[row, 'time']) + '</td><td>' + str(outputTimeline.loc[row, 'action']) + '</td><td>' + loadBeforeStr + '</td><td>' + loadAfterStr + '</td></tr>'
			row += 1

		new_html_str +="""</tbody></table>"""

		return new_html_str

	# print all intermediate and final costs
	timelineStatsHtml = timelineStats(
		outputTimeline = outputTimeline)
	with open(pJoin(workDir, 'timelineStats.html'), 'w') as timelineFile:
		timelineFile.write(timelineStatsHtml)

	return timelineStatsHtml


def graphMicrogrid(pathToOmd, pathToJson, pathToCsv, outputFile, useCache, workDir, maxTime, stepSize, outageDuration, profit_on_energy_sales, restoration_cost, hardware_cost):
	''' Run full microgrid control process. '''

	# Setup ONM if it hasn't been done already.
	if not PowerModelsONM.check_instantiated():
		PowerModelsONM.instantiate()

	# read in the OMD file as a tree and create a geojson map of the system
	if not workDir:
		workDir = tempfile.mkdtemp()
		print('@@@@@@', workDir)

	useCache = 'True' # Force cache invalidation.
	# Run ONM.
	if  useCache == 'True':
		shutil.copyfile(outputFile,f'{workDir}/output.json')
	else:
		PowerModelsONM.run(f'{workDir}/circuit.dss', f'{workDir}/output.json',f'{workDir}/events.json')

	# Gather output data.
	with open(f'{workDir}/output.json') as inFile:
		data = json.load(inFile)
		genProfiles = data['Generator profiles']
		simTimeSteps = []
		for i in data['Simulation time steps']:
			simTimeSteps.append(float(i))
		voltages = data['Voltages']
		loadServed = data['Load served']
		storageSOC = data['Storage SOC (%)']
		switchLoadAction = data['Device action timeline']
		powerflow = data['Powerflow output']
	actionTime = []
	actionDevice = []
	actionAction = []
	actionLoadBefore = []
	actionLoadAfter = []
	loadsShed = []

	timestep = 1
	for key in switchLoadAction:
		if timestep == 1:
			switchActionsOld = key['Switch configurations']
		else:
			switchActionsNew = key['Switch configurations']
			for entry in switchActionsNew:
				if switchActionsNew[entry] != switchActionsOld[entry]:
					actionDevice.append(entry)
					actionTime.append(str(timestep))
					if switchActionsNew[entry] == 'open':
						actionAction.append('Switch Opening')
					else:
						actionAction.append('Switch Closing')
					actionLoadBefore.append(switchActionsOld[entry])
					actionLoadAfter.append(switchActionsNew[entry])
			switchActionsOld = key['Switch configurations']
		loadShed = key['Shedded loads']
		if len(loadShed) != 0:
			for entry in loadShed:
				if entry not in loadsShed:
					actionDevice.append(entry)
					actionTime.append(str(timestep))
					actionAction.append('Load Shed')
					actionLoadBefore.append('online')
					actionLoadAfter.append('offline')
					loadsShed.append(entry)
				else:
					actionDevice.append(entry)
					actionTime.append(str(timestep))
					actionAction.append('Load Pickup')
					actionLoadBefore.append('offline')
					actionLoadAfter.append('online')
					loadsShed.remove(entry)
		timestep += 1
	timestep = 0
	while timestep < 24:
		if timestep == 0:
			powerflowOld = powerflow[timestep]
		else:
			powerflowNew = powerflow[timestep]
			for generator in list(powerflowNew['generator'].keys()):
				entryNew = powerflowNew['generator'][generator]['real power setpoint (kW)'][0]
				if generator in list(powerflowOld['generator'].keys()):
					entryOld = powerflowOld['generator'][generator]['real power setpoint (kW)'][0]
				else:
					entryOld = 0.0
				if math.sqrt(((entryNew - entryOld)/(entryOld + 0.0000001))**2) > 0.5:
					actionDevice.append(generator)
					actionTime.append(str(timestep + 1))
					actionAction.append('Generator Control')
					actionLoadBefore.append(str(entryOld))
					actionLoadAfter.append(str(entryNew))
			for battery in list(powerflowNew['storage'].keys()):
				entryNew = powerflowNew['storage'][battery]['real power setpoint (kW)'][0]
				if battery in list(powerflowOld['storage'].keys()):
					entryOld = powerflowOld['storage'][battery]['real power setpoint (kW)'][0]
				else:
					entryOld = 0.0
				if math.sqrt(((entryNew - entryOld)/(entryOld + 0.0000001))**2) > 0.5:
					actionDevice.append(battery)
					actionTime.append(str(timestep + 1))
					actionAction.append('Battery Control')
					actionLoadBefore.append(str(entryOld))
					actionLoadAfter.append(str(entryNew))
			powerflowOld = powerflow[timestep]
		timestep += 1

	line = {'time': actionTime,
			'device': actionDevice,
			'action': actionAction,
			'loadBefore': actionLoadBefore,
			'loadAfter': actionLoadAfter
			}

	outputTime = pd.DataFrame(line, columns = ['time','device','action','loadBefore','loadAfter'])
	outputTimeline = outputTime.sort_values('time')

	# Create traces
	gens = go.Figure()
	gens.add_trace(go.Scatter(x=simTimeSteps, y=genProfiles['Diesel DG (kW)'],
							mode='lines',
							name='Diesel DG',
							hovertemplate=
							'<b>Time Step</b>: %{x}<br>' +
							'<b>Diesel DG</b>: %{y:.3f}kW'))
	gens.add_trace(go.Scatter(x=simTimeSteps, y=genProfiles['Energy storage (kW)'],
							mode='lines',
							name='Energy Storage',
							hovertemplate=
							'<b>Time Step</b>: %{x}<br>' +
							'<b>Energy Storage</b>: %{y:.3f}kW'))
	gens.add_trace(go.Scatter(x=simTimeSteps, y=genProfiles['Solar DG (kW)'],
							mode='lines',
							name='Solar DG',
							hovertemplate=
							'<b>Time Step</b>: %{x}<br>' +
							'<b>Solar DG</b>: %{y:.3f}kW'))
	gens.add_trace(go.Scatter(x=simTimeSteps, y=genProfiles['Grid mix (kW)'],
							mode='lines',
							name='Grid Mix',
							hovertemplate=
							'<b>Time Step</b>: %{x}<br>' +
							'<b>Grid Mix</b>: %{y:.3f}kW'))
	# Edit the layout
	gens.update_layout(xaxis_title='Hours',
						yaxis_title='Power (kW)',
						legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

	volts = go.Figure()
	volts.add_trace(go.Scatter(x=simTimeSteps, y=voltages['Min voltage (p.u.)'],
							mode='lines',
							name='Minimum Voltage',
							hovertemplate=
							'<b>Time Step</b>: %{x}<br>' +
							'<b>Minimum Voltage</b>: %{y:.4f}'))
	volts.add_trace(go.Scatter(x=simTimeSteps, y=voltages['Max voltage (p.u.)'],
							mode='lines',
							name='Maximum Voltage',
							hovertemplate=
							'<b>Time Step</b>: %{x}<br>' +
							'<b>Maximum Voltage</b>: %{y:.4f}'))
	volts.add_trace(go.Scatter(x=simTimeSteps, y=voltages['Mean voltage (p.u.)'],
							mode='lines',
							name='Mean Voltage',
							hovertemplate=
							'<b>Time Step</b>: %{x}<br>' +
							'<b>Mean Voltage</b>: %{y:.4f}'))
	# Edit the layout
	volts.update_layout(xaxis_title='Hours',
						yaxis_title='Power (p.u.)',
						legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

	loads = go.Figure()
	loads.add_trace(go.Scatter(x=simTimeSteps, y=loadServed['Feeder load (%)'],
							mode='lines',
							name='Feeder Load',
							hovertemplate=
							'<b>Time Step</b>: %{x}<br>' +
							'<b>Feeder Load</b>: %{y:.2f}%'))
	loads.add_trace(go.Scatter(x=simTimeSteps, y=loadServed['Microgrid load (%)'],
							mode='lines',
							name='Microgrid Load',
							hovertemplate=
							'<b>Time Step</b>: %{x}<br>' +
							'<b>Microgrid Load</b>: %{y:.2f}%'))
	loads.add_trace(go.Scatter(x=simTimeSteps, y=loadServed['Bonus load via microgrid (%)'],
							mode='lines',
							name='Bonus Load via Microgrid',
							hovertemplate=
							'<b>Time Step</b>: %{x}<br>' +
							'<b>Bonus Load via Microgrid</b>: %{y:.2f}%'))
	# Edit the layout
	loads.update_layout(xaxis_title='Hours',
						yaxis_title='Load (%)',
						legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

	timelineStatsHtml = microgridTimeline(outputTimeline, workDir)

	with open(pathToOmd) as inFile:
		tree = json.load(inFile)['tree']
	feederMap = geo.omdGeoJson(pathToOmd, conversion = False)

	# generate a list of substations
	busNodes = []
	for key in tree.keys():
		if tree[key].get('bustype','') == 'SWING':
			busNodes.append(tree[key]['name'])

	row = 0
	row_count_timeline = outputTimeline.shape[0]
	while row < row_count_timeline:
		full_data = pullDataForGraph(tree, feederMap, outputTimeline, row)
		device, coordLis, coordStr, time, action, loadBefore, loadAfter = full_data
		dev_dict = {}
		try:
			if len(coordLis) == 2:
				dev_dict['geometry'] = {'type': 'Point', 'coordinates': [coordLis[0], coordLis[1]]}
				dev_dict['type'] = 'Feature'
				dev_dict['properties'] = {'device': device, 
									  'time': time,
									  'action': action,
									  'loadBefore': loadBefore,
									  'loadAfter': loadAfter,
									  'pointColor': '#' + str(colormap(action)), 
									  'popupContent': 'Location: <b>' + str(coordStr) + '</b><br>Device: <b>' + str(device) + '</b><br>Time: <b>' + str(time) + '</b><br>Action: <b>' + str(action) + '</b><br>Before: <b>' + str(loadBefore) + '</b><br>After: <b>' + str(loadAfter) + '</b>.'}
				feederMap['features'].append(dev_dict)
			else:
				dev_dict['geometry'] = {'type': 'LineString', 'coordinates': [[coordLis[0], coordLis[1]], [coordLis[2], coordLis[3]]]}
				dev_dict['type'] = 'Feature'
				dev_dict['properties'] = {'device': device, 
									  'time': time,
									  'action': action,
									  'loadBefore': loadBefore,
									  'loadAfter': loadAfter,
									  'edgeColor': '#' + str(colormap(action)),
									  'popupContent': 'Location: <b>' + str(coordStr) + '</b><br>Device: <b>' + str(device) + '</b><br>Time: <b>' + str(time) + '</b><br>Action: <b>' + str(action) + '</b><br>Before: <b>' + str(loadBefore) + '</b><br>After: <b>' + str(loadAfter) + '</b>.'}
				feederMap['features'].append(dev_dict)
		except:
			print('MESSED UP MAPPING on', device, full_data)
		row += 1
	if not os.path.exists(workDir):
		os.makedirs(workDir)
	shutil.copy(omf.omfDir + '/templates/geoJsonMap.html', workDir)
	with open(pJoin(workDir,'geoJsonFeatures.js'),'w') as outFile:
		outFile.write('var geojson =')
		json.dump(feederMap, outFile, indent=4)

	#Save geojson dict to then read into outdata in work function below
	with open(pJoin(workDir,'geoDict.js'),'w') as outFile:
		json.dump(feederMap, outFile, indent=4)

	customerOutageData = pd.read_csv(pathToCsv)
	numberRows = math.ceil(customerOutageData.shape[0]/2)
	fig, axs = plt.subplots(numberRows, 2)
	row = 0
	average_lost_kwh = []
	outageCost = []
	globalMax = 0
	fig = go.Figure()
	while row < customerOutageData.shape[0]:
		customerName = str(customerOutageData.loc[row, 'Customer Name'])
		duration = str(customerOutageData.loc[row, 'Duration'])
		season = str(customerOutageData.loc[row, 'Season'])
		averagekWperhr = str(customerOutageData.loc[row, 'Average kW/hr'])
		businessType = str(customerOutageData.loc[row, 'Business Type'])
		loadName = str(customerOutageData.loc[row, 'Load Name'])

		customerOutageCost, kWperhrEstimate, times, localMax = customerCost1(workDir, customerName, duration, season, averagekWperhr, businessType, loadName)
		average_lost_kwh.append(float(averagekWperhr))
		outageCost.append(customerOutageCost)
		if localMax > globalMax:
			globalMax = localMax
  
		# creating series
		timesSeries = pd.Series(times)
		kWperhrSeries = pd.Series(kWperhrEstimate)

		trace = py.graph_objs.Scatter(
			x = timesSeries,
			y = kWperhrSeries,
			name = customerName,
			hoverlabel = dict(namelength = -1),
			hovertemplate = 
			'<b>Duration</b>: %{x} h<br>' +
			'<b>Cost</b>: $%{y:.2f}'
		)
		fig.add_trace(trace)
		row += 1
	fig.update_layout(xaxis_title = 'Duration (hours)',
		yaxis_title = 'Cost ($)',
		legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

	customerOutageHtml = customerOutageTable(customerOutageData, outageCost, workDir)

	profit_on_energy_sales = float(profit_on_energy_sales)
	restoration_cost = int(restoration_cost)
	hardware_cost = int(hardware_cost)
	outageDuration = int(outageDuration)

	utilityOutageHtml = utilityOutageTable(average_lost_kwh, profit_on_energy_sales, restoration_cost, hardware_cost, outageDuration, workDir)

	return {'utilityOutageHtml': utilityOutageHtml, 'customerOutageHtml': customerOutageHtml, 'timelineStatsHtml': timelineStatsHtml, 'gens': gens, 'loads': loads, 'volts': volts, 'fig': fig, 'customerOutageCost': customerOutageCost}


def play(pathToDss, workDir, microgrids, faultedLine):
	# TODO: do we need non-default outage timing?
	(outageStart, lengthOfOutage, switchingTime) = 60, 120, 30
	outageEnd = outageStart + lengthOfOutage
	actions = {}
	print('CONTROLLING ON', microgrids)
	# microgridup.py changes our directory to the one containing the currently running analysis. This is to help opendss run. If we're running this function by itself, we need to chdir into the workDir argument.
	curr_dir = os.getcwd()
	workDir = os.path.abspath(workDir)
	if curr_dir != workDir:
		os.chdir(workDir)
	# Read in the circuit information.
	dssTree = dssConvert.dssToTree(pathToDss)
	# Add the fault, modeled as a 3 phase open, to the actions.
	actions[outageStart] = f'''
		open object=line.{faultedLine} term=1
		open object=line.{faultedLine} term=2
		open object=line.{faultedLine} term=3
	'''
	actions[outageEnd] = f'''
		close object=line.{faultedLine} term=1
		close object=line.{faultedLine} term=2
		close object=line.{faultedLine} term=3
	'''
	actions[1] = ''

	# initialize dict of vsource ratings 
	big_gen_ratings = {}

	# Add per-microgrid objects, edits and actions.
	for mg_key, mg_values in microgrids.items():
		# Add load shed.
		load_list = mg_values['loads']
		crit_list = mg_values['critical_load_kws']
		load_crit_pairs = zip(load_list, crit_list)
		for load_name, load_kw in load_crit_pairs:
			try:
				this_load = opendss._getByName(dssTree, load_name)
				old_kw = this_load['kw']
				this_load['kw'] = str(load_kw)
				print(f'reduced {load_name} from {old_kw} to {load_kw}')
			except:
				pass
		# Have all microgrids switch out of the circuit during fault.
		switch_name = mg_values['switch']
		actions[outageStart] += f'''
			open object=line.{switch_name} term=1
			open object=line.{switch_name} term=2
			open object=line.{switch_name} term=3
		'''
		actions[outageEnd] += f'''
			close object=line.{switch_name} term=1
			close object=line.{switch_name} term=2
			close object=line.{switch_name} term=3
		'''
		# Get all microgrid fossil units, sorted by size
		gen_bus = mg_values['gen_bus']
		all_mg_fossil = [
			ob for ob in dssTree
			if ob.get('bus1','x.x').split('.')[0] == gen_bus
			and 'fossil' in ob.get('object')
		]
		all_mg_fossil.sort(key=lambda x:x.get('kw'))
		# Insert a vsource for the largest fossil unit in each microgrid.
		if len(all_mg_fossil) > 0: # i.e. if we have a fossil generator
			# vsource variables.
			big_gen_ob = all_mg_fossil[-1]
			big_gen_bus = big_gen_ob.get('bus1')
			big_gen_index = dssTree.index(big_gen_ob)
			safe_busname = big_gen_bus.replace('.','_')
			vsource_ob_and_name = f'vsource.lead_gen_{safe_busname}'
			line_name = f'line.line_for_lead_gen_{safe_busname}'
			new_bus_name = f'bus_for_lead_gen_{safe_busname}.1.2.3'
			#TO DO: update default kv assignment to match max kv on grid
			base_kv = big_gen_ob.get('kv','3.14')

			# Before removing fossil unit, grab kW rating 
			big_gen_ratings[f"lead_gen_{safe_busname}"] = big_gen_ob.get("kw")

			# Remove fossil unit, add new gen and line
			del dssTree[big_gen_index]
			dssTree.insert(big_gen_index, {'!CMD':'new', 'object':vsource_ob_and_name, 'bus1':new_bus_name, 'basekv':base_kv})
			dssTree.insert(big_gen_index, {'!CMD':'new', 'object':line_name, 'bus1':big_gen_bus, 'bus2':new_bus_name, 'switch':'yes'})
			# Disable the new lead gen by default.
			actions[1] += f'''
				open {line_name}
				calcv
			'''
			#Enable/disable the diesel vsources during the outage via actions.
			actions[outageStart] += f'''
				close {line_name}
				calcv
			'''
			actions[outageEnd] += f'''
				open {line_name}
				calcv
			'''

		# Do vector subtraction to figure out battery loadshapes. 
		# First get all loads.
		all_mg_loads = [
			ob for ob in dssTree
			if ob.get('bus1','x.x').split('.')[0] == gen_bus
			and 'load.' in ob.get('object')
		]
		if len(all_mg_loads) > 0: # i.e. if we have loads
			load_loadshapes = []
			for load_idx in range(len(all_mg_loads)):
				# Get loadshapes of all renewable generation.
				load_loadshape_name = all_mg_loads[load_idx].get('yearly')
				load_loadshape = [ob.get("mult") for ob in dssTree if ob.get("object") and load_loadshape_name in ob.get("object")]
				list_load_loadshape = [float(shape) for shape in load_loadshape[0][1:-1].split(",")]
				load_loadshapes.append(list_load_loadshape)
			data = np.array(load_loadshapes)
			cum_load_loadshapes = np.sum(data,0)

		# Second, get all renewable generation.
		all_mg_rengen = [
			ob for ob in dssTree
			if ob.get('bus1','x.x').split('.')[0] == gen_bus
			and ('generator.solar' in ob.get('object') or 'generator.wind' in ob.get('object'))
		]
		if len(all_mg_rengen) > 0: # i.e. if we have rengen
			rengen_loadshapes = []
			for gen_idx in range(len(all_mg_rengen)):
				# Get loadshapes of all renewable generation.
				rengen_loadshape_name = all_mg_rengen[gen_idx].get('yearly')
				rengen_loadshape = [ob.get("mult") for ob in dssTree if ob.get("object") and rengen_loadshape_name in ob.get("object")]
				list_rengen_loadshape = [float(shape) for shape in rengen_loadshape[0][1:-1].split(",")]
				rengen_loadshapes.append(list_rengen_loadshape)
			data = np.array(rengen_loadshapes)
			cum_rengen_loadshapes = np.sum(data,0)
		
		# Third, get battery sizes.
		batt_obj = [
			ob for ob in dssTree
			if ob.get('bus1','x.x').split('.')[0] == gen_bus
			and 'storage' in ob.get('object')
		]
		if len(batt_obj) > 1:
			print("ERROR: MORE THAN ONE BATTERY AT BUS")
		batt_kw = float(batt_obj[0].get("kwrated"))
		batt_kwh = float(batt_obj[0].get("kwhrated"))

		# Subtract vectors.
		new_batt_loadshape = cum_load_loadshapes - cum_rengen_loadshapes # NOTE: <-- load – rengen. 3 cases: above 0, 0, less than 0

		# Slice to outage length.
		new_batt_loadshape = new_batt_loadshape[outageStart:outageEnd]

		# Set starting battery capacity. starting_capacity will then be modified to represent dischargeable generation.
		starting_capacity = batt_kwh

		# Unneccessary variable for tracking unsupported load in kwh.
		unsupported_load_kwh = 0

		# Discharge battery (allowing for negatives that recharge (until hitting capacity)) until battery reaches 0 charge. Allow starting charge to be configurable. 
		hour = 0
		while starting_capacity > 0 and hour < len(new_batt_loadshape):
			# Reduce each value in DS until 0, batt_kw, or starting_capacity reaches 0
			if starting_capacity < batt_kw:
				batt_kw = starting_capacity
			indicator = new_batt_loadshape[hour] - batt_kw 
			# There is more rengen than load and we can charge our battery (up until reaching batt_kwh).
			if new_batt_loadshape[hour] < 0:
				starting_capacity += abs(new_batt_loadshape[hour])
				if starting_capacity > batt_kwh:
					starting_capacity = batt_kwh
				new_batt_loadshape[hour] = starting_capacity - new_batt_loadshape[hour]
			# There is load left to cover and we can discharge the battery to cover it in its entirety. 
			elif indicator < 0:
				starting_capacity -= new_batt_loadshape[hour]
				new_batt_loadshape[hour] *= -1 
			# There is load left to cover after discharging as much battery as possible for the hour. Load isn't supported.
			else:
				new_batt_loadshape[hour] = -1 * batt_kw
				starting_capacity -= batt_kw
				unsupported_load_kwh += indicator
			hour += 1

		# If there are remaining values in loadshape, set them to 0.
		if hour < lengthOfOutage:
			new_batt_loadshape[hour:] = [0 for x in new_batt_loadshape[hour:]]
		new_batt_loadshape = list(new_batt_loadshape)

		# Get existing battery loadshape. 
		batt_loadshape_name = batt_obj[0].get("yearly")
		full_loadshape = [ob.get("mult") for ob in dssTree if ob.get("object") and batt_loadshape_name in ob.get("object")]
		list_full_loadshape = [float(shape) for shape in full_loadshape[0][1:-1].split(",")]

		# Replace outage of existing battery loadshape with outage loadshape.
		final_batt_loadshape = list_full_loadshape[:outageStart] + new_batt_loadshape + list_full_loadshape[outageEnd:]

		# Get index of battery in tree.
		batt_loadshape_idx = dssTree.index([ob for ob in dssTree if ob.get("object") and batt_loadshape_name in ob.get("object")][0])

		# Replace mult with new loadshape and reinsert into tree.
		dssTree[batt_loadshape_idx]['mult'] = str(list_full_loadshape).replace(" ","")

	# print("big_gen_ratings",big_gen_ratings)

	# Additional calcv to make sure the simulation runs.
	actions[outageStart] += f'calcv\n'
	actions[outageEnd] += f'calcv\n'
	# Write the adjusted opendss file with new kw, generators.
	dssConvert.treeToDss(dssTree, 'circuit_control.dss')
	# Run the simulation
	FPREFIX = 'timezcontrol'
	opendss.newQstsPlot(
		'circuit_control.dss',
		stepSizeInMinutes=60, 
		numberOfSteps=300,
		keepAllFiles=False,
		actions=actions,
		filePrefix=FPREFIX
	)

	# Merge gen and source csvs for plotting fossil loading percentages
	inputs = [f'{FPREFIX}_gen.csv', f'{FPREFIX}_source.csv']

	# First determine the field names from the top line of each input file
	fieldnames = []
	for filename in inputs:
		with open(filename, "r", newline="") as f_in:
			reader = csv.reader(f_in)
			headers = next(reader)
			for h in headers:
				if h not in fieldnames:
					fieldnames.append(h)

	# Then copy the data
	with open(f"{FPREFIX}_source_and_gen.csv", "w", newline="") as f_out:
		writer = csv.DictWriter(f_out, fieldnames=fieldnames)
		writer.writeheader()
		for filename in inputs:
			with open(filename, "r", newline="") as f_in:
				reader = csv.DictReader(f_in)  # Uses the field names in this file
				for line in reader:
					writer.writerow(line)
	
	# Generate the output charts.
	make_chart(f'{FPREFIX}_gen.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], 2019, microgrids, dssTree, "Generator Output", "Average hourly kW", batt_cycle_chart=True)
	make_chart(f'{FPREFIX}_load.csv', 'Name', 'hour', ['V1(PU)','V2(PU)','V3(PU)'], 2019, microgrids, dssTree, "Load Voltage", "PU", ansi_bands=True)
	make_chart(f'{FPREFIX}_source.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], 2019, microgrids, dssTree, "Voltage Source Output", "Average hourly kW", vsource_ratings=big_gen_ratings)
	make_chart(f'{FPREFIX}_control.csv', 'Name', 'hour', ['Tap(pu)'], 2019, microgrids, dssTree, "Tap Position", "PU")
	make_chart(f'{FPREFIX}_source_and_gen.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], 2019, microgrids, dssTree, "None", "None", fossil_loading_chart=True, vsource_ratings=big_gen_ratings)

	# Undo directory change.
	os.chdir(curr_dir)