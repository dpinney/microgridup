from omf.solvers import opendss
from omf.solvers.opendss import dssConvert
from omf import distNetViz
from omf import geo
import shutil
import os
from pprint import pprint as pp
import json
import pandas as pd
import numpy as np
import plotly
import csv
import jinja2 as j2
import re
import math
import random
import datetime

def _name_to_key(glm):
	''' Make fast lookup map by name in a glm.
	WARNING: if the glm changes, the map will no longer be valid.'''
	mapping = {}
	for key, val in glm.items():
		if 'name' in val:
			mapping[val['name']] = key
	return mapping

def reopt_gen_mg_specs(BASE_NAME, LOAD_NAME, REOPT_INPUTS, REOPT_FOLDER, microgrid):
	''' Generate the microgrid specs with REOpt.
	SIDE-EFFECTS: generates REOPT_FOLDER'''
	load_df = pd.read_csv(LOAD_NAME)
	if not os.path.isdir(REOPT_FOLDER):
		import omf.models
		shutil.rmtree(REOPT_FOLDER, ignore_errors=True)
		omf.models.microgridDesign.new(REOPT_FOLDER)
		# Get the microgrid total loads
		mg_load_df = pd.DataFrame()
		loads = microgrid['loads']
		mg_load_df['load'] = [0 for x in range(8760)]
		for load_name in loads:
			mg_load_df['load'] = mg_load_df['load'] + load_df[load_name]
		mg_load_df.to_csv(REOPT_FOLDER + '/loadShape.csv', header=False, index=False)
		# Default inputs.
		allInputData = json.load(open(REOPT_FOLDER + '/allInputData.json'))
		allInputData['loadShape'] = open(REOPT_FOLDER + '/loadShape.csv').read()
		allInputData['fileName'] = 'loadShape.csv'
		# Pulling user defined inputs from REOPT_INPUTS.
		for key in REOPT_INPUTS:
			allInputData[key] = REOPT_INPUTS[key]
		# Pulling coordinates and existing generation from BASE_NAME.dss into REopt allInputData.json:
		tree = dssConvert.dssToTree(BASE_NAME) #TO DO: For Accuracy and slight efficiency gain, refactor all search parameters to search through the "tree" (list of OrderedDicts, len(list)= # lines in base.dss)
		#print(tree)
		evil_glm = dssConvert.evilDssTreeToGldTree(tree)
		#print(evil_glm)
		for ob in evil_glm.values():
			ob_name = ob.get('name','')
			ob_type = ob.get('object','')
			# pull out long and lat; When running one microgrid per REopt run, ob_name should be updated to the gen_bus from microgrids
			if ob_type == "bus" and ob_name == "sourcebus":
				ob_lat = ob.get('latitude','')
				ob_long = ob.get('longitude','')
				#print('lat:', float(ob_lat), 'long:', float(ob_long))
				allInputData['latitude'] = float(ob_lat)
				allInputData['longitude'] = float(ob_long)
		# Pull out and add up kw of all solar and diesel generators in the microgrid
		# requires pre-selection of all objects in a given microgrid in microgrids[key]['gen_obs_existing']
		solar_kw_exist = []
		diesel_kw_exist = []
		battery_kw_exist = []
		battery_kwh_exist = []
		wind_kw_exist = []
		gen_obs = microgrid['gen_obs_existing']
		for gen_ob in gen_obs: # gen_ob is a name of an object from base.dss
			for ob in evil_glm.values(): # TODO: Change the syntax to match to the "tree" structure; See shape insertions at line 270 for an example
				ob_name = ob.get('name','')
				#print(ob_name)
				ob_type = ob.get('object','')
				if ob_name == gen_ob and ob_type == "generator" and re.search('solar.+', ob_name):
					solar_kw_exist.append(float(ob.get('kw')))
				elif ob_name == gen_ob and ob_type == "generator" and re.search('wind.+', ob_name):
					wind_kw_exist.append(float(ob.get('kw')))
				elif ob_name == gen_ob and ob_type == "generator" and re.search('diesel.+', ob_name):
					diesel_kw_exist.append(float(ob.get('kw')))
				elif ob_name == gen_ob and ob_type == "storage" and re.search('battery.+', ob_name):
					battery_kw_exist.append(float(ob.get('kwrated')))
					battery_kwh_exist.append(float(ob.get('kwhrated')))
		allInputData['genExisting'] = str(sum(diesel_kw_exist))
		if sum(solar_kw_exist) > 0:
			allInputData['solarExisting'] = str(sum(solar_kw_exist))
			allInputData['solar'] = 'on'
		if sum(battery_kwh_exist) > 0:
			allInputData['batteryKwExisting'] = str(sum(battery_kw_exist))
			allInputData['batteryPowerMin'] = str(sum(battery_kw_exist))
			allInputData['batteryKwhExisting'] = str(sum(battery_kwh_exist))
			allInputData['batteryCapacityMin'] = str(sum(battery_kwh_exist))
			allInputData['battery'] = 'on'
		if sum(wind_kw_exist) > 0:
			allInputData['windExisting'] = str(sum(wind_kw_exist))
			allInputData['windMin'] = str(sum(wind_kw_exist))
			allInputData['wind'] = 'on' #failsafe to include wind if found in base_dss
			 # To Do: update logic if windMin, windExisting and other generation variables are enabled to be set by the user as inputs
		# run REopt via microgridDesign
		with open(REOPT_FOLDER + '/allInputData.json','w') as outfile:
			json.dump(allInputData, outfile, indent=4)
		omf.models.__neoMetaModel__.runForeground(REOPT_FOLDER)
		omf.models.__neoMetaModel__.renderTemplateToFile(REOPT_FOLDER)

def get_gen_ob_and_shape_from_reopt(REOPT_FOLDER, GEN_NAME, microgrid):
	''' Get generator objects and shapes from REOpt.
	SIDE EFFECTS: creates GEN_NAME generator shape, returns gen_obs'''
	reopt_out = json.load(open(REOPT_FOLDER + '/allOutputData.json'))
	gen_df_builder = pd.DataFrame()
	gen_obs = []
	mg_num = 1
	mg_ob = microgrid
	gen_bus_name = mg_ob['gen_bus']
	gen_obs_existing = mg_ob['gen_obs_existing']
	''' calculate size of new generators at gen_bus based on REopt and existing gen from BASE_NAME for each microgrid.
		Existing solar and diesel are supported natively in REopt.
		Existing wind and batteries require setting the minimimum generation threshold (windMin, batteryPowerMin, batteryCapacityMin)'''
	solar_size_total = reopt_out.get(f'sizePV{mg_num}', 0.0)
	solar_size_existing = reopt_out.get(f'sizePVExisting{mg_num}', 0.0)
	solar_size_new = solar_size_total - solar_size_existing
	wind_size_total = reopt_out.get(f'sizeWind{mg_num}', 0.0) # TO DO: Update size of wind based on existing generation once we find a way to get a loadshape for that wind if REopt recommends no wind
	wind_size_existing = reopt_out.get(f'windExisting{mg_num}', 0.0)
	if wind_size_total - wind_size_existing > 0:
		wind_size_new = wind_size_total - wind_size_existing 
	else:
		wind_size_new = 0 #TO DO: update logic here to make run more robust to oversized existing wind gen	
	diesel_size_total = reopt_out.get(f'sizeDiesel{mg_num}', 0.0)
	diesel_size_existing = reopt_out.get(f'sizeDieselExisting{mg_num}', 0.0)
	diesel_size_new = diesel_size_total - diesel_size_existing
	battery_cap_total = reopt_out.get(f'capacityBattery{mg_num}', 0.0) 
	battery_cap_existing = reopt_out.get(f'batteryKwhExisting{mg_num}', 0.0)
	if battery_cap_total - battery_cap_existing > 0:
		battery_cap_new = battery_cap_total - battery_cap_existing 
	else:
		battery_cap_new = 0 #TO DO: update logic here to make run more robust to oversized existing battery generation
	battery_pow_total = reopt_out.get(f'powerBattery{mg_num}', 0.0) 
	battery_pow_existing = reopt_out.get(f'batteryKwExisting{mg_num}', 0.0)
	if battery_pow_total - battery_pow_existing > 0:
		battery_pow_new = battery_pow_total - battery_pow_existing 
	else:
		battery_pow_new = 0 #TO DO: Fix logic so that new batteries cannot add kwh without adding kw
	# Build new solar gen objects and loadshapes as recommended by REopt
	if solar_size_new > 0:
		gen_obs.append({
			'!CMD': 'new',
			'object':f'generator.solar_{gen_bus_name}',
			'bus1':f'{gen_bus_name}.1.2.3',
			'phases':'3', #todo: what about multiple smaller phases?
			'kv':'2.4', #todo: fix, make non-generic
			'kw':f'{solar_size_new}',
			'pf':'1'
		})
		# 0-1 scale the power output loadshape to the total generation kw of that type of generator using pandas
		gen_df_builder[f'solar_{gen_bus_name}'] = pd.Series(reopt_out.get(f'powerPV{mg_num}'))/solar_size_total
	# build loadshapes for existing generation from BASE_NAME, inputting the 0-1 solar generation loadshape 
	if solar_size_existing > 0:
		for gen_ob_existing in gen_obs_existing:
			if gen_ob_existing.startswith('solar_'):
				gen_df_builder[f'{gen_ob_existing}'] = pd.Series(reopt_out.get(f'powerPV{mg_num}'))/solar_size_total
	if diesel_size_new > 0:
		gen_obs.append({
			'!CMD': 'new',
			'object':f'generator.diesel_{gen_bus_name}',
			'bus1':f'{gen_bus_name}.1.2.3',
			'kv':'2.4', #todo: fix, make non-generic
			'kw':f'{diesel_size_new}',
			'phases':'3', #todo: what about multiple smaller phases?
			'pf':'1',
			'xdp':'0.27',
			'xdpp':'0.2',
			'h':'2',
			'conn':'delta'
		})
		# 0-1 scale the power output loadshape to the total generation kw of that type of generator
		#bgen_df_builder[f'diesel_{gen_bus_name}'] = pd.Series(reopt_out.get(f'powerDiesel{mg_num}'))/diesel_size_total # insert the 0-1 diesel generation shape provided by REopt to simulate the outage specified in REopt
		gen_df_builder[f'diesel_{gen_bus_name}'] = pd.DataFrame(np.zeros(8760)) # insert an array of zeros for the diesel generation shape to simulate no outage
	# build loadshapes for existing generation from BASE_NAME, inputting the 0-1 diesel generation loadshape 
	if diesel_size_existing > 0:	
		for gen_ob_existing in gen_obs_existing:
			if gen_ob_existing.startswith('diesel_'):
				# gen_df_builder[f'{gen_ob_existing}'] = pd.Series(reopt_out.get(f'powerDiesel{mg_num}'))/diesel_size_total # insert the 0-1 diesel generation shape provided by REopt to simulate the outage specified in REopt
				gen_df_builder[f'{gen_ob_existing}'] = pd.DataFrame(np.zeros(8760)) # insert an array of zeros for the diesel generation shape to simulate no outage
	# get loadshapes for new Wind
	if wind_size_new > 0:
		gen_obs.append({
			'!CMD': 'new',
			'object':f'generator.wind_{gen_bus_name}',
			'bus1':f'{gen_bus_name}.1.2.3',
			'phases':'3', #todo: what about multiple smaller phases?
			'kv':'2.4', #todo: fix, make non-generic
			'kw':f'{wind_size_new}',
			'pf':'1'
		})
		# 0-1 scale the power output loadshape to the total generation kw of that type of generator
		gen_df_builder[f'wind_{gen_bus_name}'] = pd.Series(reopt_out.get(f'powerWind{mg_num}'))/wind_size_total
	# build loadshapes for existing Wind generation from BASE_NAME
	if wind_size_existing > 0:	
		for gen_ob_existing in gen_obs_existing:
			if gen_ob_existing.startswith('wind_'):
				gen_df_builder[f'{gen_ob_existing}'] = pd.Series(reopt_out.get(f'powerWind{mg_num}'))/wind_size_total
	# calculate battery loadshape (serving load - charging load)
	if battery_cap_total > 0:	
		batToLoad = pd.Series(reopt_out.get(f'powerBatteryToLoad{mg_num}'))
		gridToBat = np.zeros(8760)
		# TO DO: add logic to update insertion of grid charging when Daniel's islanding framework is complete 	
		gridToBat = pd.Series(reopt_out.get(f'powerGridToBattery{mg_num}'))
		pVToBat = np.zeros(8760)
		if solar_size_total > 0:
			pVToBat = pd.Series(reopt_out.get(f'powerPVToBattery{mg_num}'))
		dieselToBat = np.zeros(8760)
		if diesel_size_total > 0:
			dieselToBat = pd.Series(reopt_out.get(f'powerDieselToBattery{mg_num}'))
		windToBat = np.zeros(8760)
		if wind_size_total > 0:
			windToBat = pd.Series(reopt_out.get(f'powerWindToBattery{mg_num}'))
		battery_load = batToLoad - gridToBat - pVToBat - dieselToBat - windToBat
		# 0-1 scale the full battery loadshape to the total battery power kw
		battery_load_0_1 = battery_load/battery_pow_total
	# get DSS objects and loadshapes for new battery
	if battery_cap_new > 0: 
		gen_obs.append({
			'!CMD': 'new',
			'object':f'storage.battery_{gen_bus_name}',
			'bus1':f'{gen_bus_name}.1.2.3',
			'kv':'2.4', #todo: fix, make non-generic
			'kwrated':f'{battery_pow_new}',
			'phases':'3',
			'dispmode':'follow',
			'kwhstored':f'{battery_cap_new}',
			'kwhrated':f'{battery_cap_new}',
			# 'kva':f'{battery_pow_total}',
			# 'kvar':f'{battery_pow_total}',
			'%charge':'100',
			'%discharge':'100',
			'%effcharge':'100',
			'%effdischarge':'100',
			'%idlingkw':'0',
			'%r':'0',
			'%x':'50',
			'%stored':'50'
		})
		gen_df_builder[f'battery_{gen_bus_name}'] = battery_load_0_1
	# build loadshapes for existing battery generation from BASE_NAME
	if battery_cap_existing > 0:	
		for gen_ob_existing in gen_obs_existing:
			if gen_ob_existing.startswith('battery_'):
				gen_df_builder[f'{gen_ob_existing}'] = battery_load_0_1
	gen_df_builder.to_csv(GEN_NAME, index=False)
	return gen_obs

def make_full_dss(BASE_NAME, GEN_NAME, LOAD_NAME, FULL_NAME, gen_obs):
	''' insert generation objects into dss.
	SIDE EFFECTS: writes FULL_NAME dss'''
	tree = dssConvert.dssToTree(BASE_NAME)
	bus_list_pos = -1
	for i, ob in enumerate(tree):
		if ob.get('!CMD','') == 'makebuslist':
			bus_list_pos = i
	#print("gen_obs after all new gen is built:", gen_obs)
	for ob in gen_obs:
		tree.insert(bus_list_pos, ob)
	# Gather loadshapes and generator duties.
	gen_df = pd.read_csv(GEN_NAME)
	shape_insert_list = {}
	load_df = pd.read_csv(LOAD_NAME)
	for i, ob in enumerate(tree):
		try:
			ob_string = ob.get('object','')
			if ob_string.startswith('load.'):
				ob_name = ob_string[5:]
				shape_data = load_df[ob_name]
				shape_name = ob_name + '_shape'
				ob['yearly'] = shape_name
				shape_insert_list[i] = {
					'!CMD': 'new',
					'object': f'loadshape.{shape_name}',
					'npts': f'{len(shape_data)}',
					'interval': '1',
					'useactual': 'yes', #todo: move back to [0,1] shapes?
					'mult': f'{list(shape_data)}'.replace(' ','')
				}
			elif ob_string.startswith('generator.'):
				ob_name = ob_string[10:]
				#print('ob_name:', ob_name)
				shape_data = gen_df[ob_name]
				shape_name = ob_name + '_shape'
				#print('shape_name:', shape_name)
				ob['yearly'] = shape_name
				shape_insert_list[i] = {
					'!CMD': 'new',
					'object': f'loadshape.{shape_name}',
					'npts': f'{len(shape_data)}',
					'interval': '1',
					'useactual': 'no',
					'mult': f'{list(shape_data)}'.replace(' ','')
				}
			elif ob_string.startswith('storage.'):
				ob_name = ob_string[8:]
				#print('ob_name:', ob_name)
				shape_data = gen_df[ob_name]
				shape_name = ob_name + '_shape'
				#print('shape_name:', shape_name)
				ob['yearly'] = shape_name
				shape_insert_list[i] = {
					'!CMD': 'new',
					'object': f'loadshape.{shape_name}',
					'npts': f'{len(shape_data)}',
					'interval': '1',
					'useactual': 'no',
					'mult': f'{list(shape_data)}'.replace(' ','')
				}
		except:
			pass #Old existing gen, ignore.
	# Do shape insertions at proper places
	for key in shape_insert_list:
		min_pos = min(shape_insert_list.keys())
		tree.insert(min_pos, shape_insert_list[key])
	# Write new DSS file.
	dssConvert.treeToDss(tree, FULL_NAME)

def gen_omd(FULL_NAME, OMD_NAME):
	''' Generate an OMD.
	SIDE-EFFECTS: creates the OMD'''
	tree = dssConvert.dssToTree(FULL_NAME)
	evil_glm = dssConvert.evilDssTreeToGldTree(tree)
	# Injecting additional coordinates.
	RADIUS = 0.0002 #TODO: derive sensible RADIUS from lat/lon numbers.
	tree = dssConvert.dssToTree(FULL_NAME)
	evil_glm = dssConvert.evilDssTreeToGldTree(tree)
	name_map = _name_to_key(evil_glm)
	for ob in evil_glm.values():
		ob_name = ob.get('name','')
		ob_type = ob.get('object','')
		if 'parent' in ob:
			parent_loc = name_map[ob['parent']]
			parent_ob = evil_glm[parent_loc]
			parent_lat = parent_ob.get('latitude', None)
			parent_lon = parent_ob.get('longitude', None)
			# place randomly on circle around parent.
			angle = random.random()*3.14159265*2;
			x = math.cos(angle)*RADIUS;
			y = math.sin(angle)*RADIUS;
			ob['latitude'] = str(float(parent_lat) + x)
			ob['longitude'] = str(float(parent_lon) + y)
			# print(ob)
	dssConvert.evilToOmd(evil_glm, OMD_NAME)

def make_chart(csvName, category_name, x, y_list, year, qsts_steps, ansi_bands=False):
	''' Charting outputs. '''
	gen_data = pd.read_csv(csvName)
	data = [] 
	for ob_name in set(gen_data[category_name]):
		for y_name in y_list:
			this_series = gen_data[gen_data[category_name] == ob_name]
			trace = plotly.graph_objs.Scatter(
				x = pd.to_datetime(this_series[x], unit = 'h', origin = pd.Timestamp(f'{year}-01-01')), #TODO: make this datetime convert arrays other than hourly or with a different startdate than Jan 1 if needed
				y = this_series[y_name], # ToDo: rounding to 3 decimals here would be ideal, but doing so does not accept Inf values 
				name = ob_name + '_' + y_name,
				hoverlabel = dict(namelength = -1)
			)
			data.append(trace)

	layout = plotly.graph_objs.Layout(
		title = f'{csvName} Output',
		# xaxis = dict(title = x),
		xaxis = dict(title="Time"),
		yaxis = dict(title = str(y_list))
	)
	fig = plotly.graph_objs.Figure(data, layout)

	if ansi_bands == True:
		date = pd.Timestamp(f'{year}-01-01')
		fig.add_shape(type="line",
 			x0=date, y0=.95, x1=date+datetime.timedelta(hours=qsts_steps), y1=.95,
 			line=dict(color="Red", width=3, dash="dashdot")
		)
		fig.add_shape(type="line",
 			x0=date, y0=1.05, x1=date+datetime.timedelta(hours=qsts_steps), y1=1.05,
 			line=dict(color="Red", width=3, dash="dashdot")
		)

	plotly.offline.plot(fig, filename=f'{csvName}.plot.html', auto_open=False)

def microgrid_report_csv(inputName, outputCsvName, REOPT_FOLDER, microgrid): #naming oon this piece needs to be updated to output
	''' Generate a report on each microgrid '''
	reopt_out = json.load(open(REOPT_FOLDER + inputName))
	with open(outputCsvName, 'w', newline='') as outcsv:
		writer = csv.writer(outcsv)
		writer.writerow(["Microgrid Name", "Generation Bus", "Minimum Load (kWh)", "Average Load (kWh)",
							"Average Daytime Load (kWh)", "Maximum Load (kWh)", "Existing Diesel (kW)", "Recommended New Diesel (kW)",
							"Diesel Fuel Used During Outage (gal)", "Existing Solar (kW)", "Recommended New Solar (kW)", 
							"Existing Battery Power (kW)", "Recommended New Battery Power (kW)", "Existing Battery Capacity (kWh)", 
							"Recommended New Battery Capacity (kWh)", "Existing Wind (kW)", "Recommended New Wind (kW)", 
							"Total Generation on Grid (kW)", "NPV ($)", "CapEx ($)", "CapEx after Incentives ($)", 
							"Average Outage Survived (h)"])
		mg_num = 1
		mg_ob = microgrid
		gen_bus_name = mg_ob['gen_bus']
		load = reopt_out.get(f'load{mg_num}', 0.0)
		min_load = min(load)
		ave_load = sum(load)/len(load)
		np_load = np.array_split(load, 365)
		np_load = np.array(np_load) #a flattened array of 365 arrays of 24 hours each
		daytime_kwh = np_load[:,9:17] #365 8-hour daytime arrays
		avg_daytime_load = np.average(np.average(daytime_kwh, axis=1))
		max_load = max(load)
		diesel_used_gal =reopt_out.get(f'fuelUsedDiesel{mg_num}', 0.0)
		solar_size_total = reopt_out.get(f'sizePV{mg_num}', 0.0)
		solar_size_existing = reopt_out.get(f'sizePVExisting{mg_num}', 0.0)
		solar_size_new = solar_size_total - solar_size_existing
		wind_size_total = reopt_out.get(f'sizeWind{mg_num}', 0.0)
		wind_size_existing = reopt_out.get(f'windExisting{mg_num}', 0.0)
		if wind_size_total - wind_size_existing > 0:
			wind_size_new = wind_size_total - wind_size_existing
		else:
			wind_size_new = 0
		diesel_size_total = reopt_out.get(f'sizeDiesel{mg_num}', 0.0)
		diesel_size_existing = reopt_out.get(f'sizeDieselExisting{mg_num}', 0.0)
		diesel_size_new = diesel_size_total - diesel_size_existing
		battery_cap_total = reopt_out.get(f'capacityBattery{mg_num}', 0.0)
		battery_cap_existing = reopt_out.get(f'batteryKwhExisting{mg_num}', 0.0)
		if battery_cap_total - battery_cap_existing > 0:
			battery_cap_new = battery_cap_total - battery_cap_existing
		else:
			battery_cap_new = 0

		battery_pow_total = reopt_out.get(f'powerBattery{mg_num}', 0.0)
		battery_pow_existing = reopt_out.get(f'batteryKwExisting{mg_num}', 0.0)
		if battery_pow_total - battery_pow_existing > 0:
			battery_pow_new = battery_pow_total - battery_pow_existing
		else:
			battery_pow_new = 0

		total_gen = diesel_size_total + solar_size_total + battery_pow_total + wind_size_total

		npv = reopt_out.get(f'savings{mg_num}', 0.0) # overall npv against the business as usual case from REopt
		cap_ex = reopt_out.get(f'initial_capital_costs{mg_num}', 0.0) # description from REopt: Up-front capital costs for all technologies, in present value, excluding replacement costs and incentives
		cap_ex_after_incentives = reopt_out.get(f'initial_capital_costs_after_incentives{mg_num}', 0.0) # description from REopt: Up-front capital costs for all technologies, in present value, excluding replacement costs, including incentives
		# economic outcomes with the capital costs of existing wind and batteries deducted:
		npv_existing_gen_adj = npv \
								+ wind_size_existing * reopt_out.get(f'windCost{mg_num}', 0.0) \
								+ battery_cap_existing * reopt_out.get(f'batteryCapacityCost{mg_num}', 0.0) \
								+ battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0)
		cap_ex_existing_gen_adj = cap_ex \
								+ wind_size_existing * reopt_out.get(f'windCost{mg_num}', 0.0) \
								+ battery_cap_existing * reopt_out.get(f'batteryCapacityCost{mg_num}', 0.0) \
								+ battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0)
		cap_ex_after_incentives_existing_gen_adj = cap_ex_after_incentives \
								+ wind_size_existing * reopt_out.get(f'windCost{mg_num}', 0.0) \
								+ battery_cap_existing * reopt_out.get(f'batteryCapacityCost{mg_num}', 0.0) \
								+ battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0)
		ave_outage = reopt_out.get(f'avgOutage{mg_num}', 0.0)
		
		row =[str(REOPT_FOLDER[-1]), gen_bus_name, round(min_load,0), round(ave_load,0), round(avg_daytime_load,1), round(max_load,0),
		round(diesel_size_existing,1), round(diesel_size_new,1), round(diesel_used_gal, 0), round(solar_size_existing,1), 
		round(solar_size_new,1), round(battery_pow_existing,1), round(battery_pow_new,1), round(battery_cap_existing,1), 
		round(battery_cap_new,1), round(wind_size_existing,1), round(wind_size_new,1), round(total_gen,1),
		int(round(npv_existing_gen_adj)), int(round(cap_ex_existing_gen_adj)), int(round(cap_ex_after_incentives_existing_gen_adj)), 
		round(ave_outage,1)]
		writer.writerow(row)

def microgrid_report_list_of_dicts(inputName, REOPT_FOLDER, microgrid):
	''' Generate a dictionary reports fr each key for all microgrids. '''
	reopt_out = json.load(open(REOPT_FOLDER + inputName))
	list_of_mg_dict = []
	mg_dict = {}
	mg_num = 1
	mg_ob = microgrid
	mg_dict["Microgrid Name"] = str(REOPT_FOLDER[-1])
	mg_dict["Generation Bus"] = mg_ob['gen_bus']
	load = reopt_out.get(f'load1', 0.0)
	mg_dict["Minimum Load (kWh)"] = round(min(load),0)
	mg_dict["Average Load (kWh)"] = round(sum(load)/len(load),0)
	# build the average daytime load
	np_load = np.array_split(load, 365)
	np_load = np.array(np_load) #a flattened array of 365 arrays of 24 hours each
	daytime_kwh = np_load[:,9:17] #365 8-hour daytime arrays
	mg_dict["Average Daytime Load (kWh)"] = round(np.average(np.average(daytime_kwh, axis=1)),0)
	mg_dict["Maximum Load (kWh)"] = round(max(load),0)
	diesel_size_total = reopt_out.get(f'sizeDiesel{mg_num}', 0.0)
	diesel_size_existing = reopt_out.get(f'sizeDieselExisting{mg_num}', 0.0)
	mg_dict["Existing Diesel (kW)"] = round(diesel_size_existing,0)
	mg_dict["Recommended New Diesel (kW)"] = round(diesel_size_total - diesel_size_existing,0)
	mg_dict["Diesel Fuel Used During Outage (gal)"] = round(reopt_out.get(f'fuelUsedDiesel{mg_num}', 0.0),0)
	solar_size_total = reopt_out.get(f'sizePV{mg_num}', 0.0)
	solar_size_existing = reopt_out.get(f'sizePVExisting{mg_num}', 0.0)
	mg_dict["Existing Solar (kW)"] = round(solar_size_existing ,0)
	mg_dict["Recommended New Solar (kW)"] = round(solar_size_total - solar_size_existing,0)
	battery_pow_total = reopt_out.get(f'powerBattery{mg_num}', 0.0)
	battery_pow_existing = reopt_out.get(f'batteryKwExisting{mg_num}', 0.0)
	mg_dict["Existing Battery Power (kW)"] = round(battery_pow_existing,0)
	if battery_pow_total - battery_pow_existing > 0:
		mg_dict["Recommended New Battery Power (kW)"] = round(battery_pow_total - battery_pow_existing,0)
	else:
		mg_dict["Recommended New Battery Power (kW)"] = 0.0
	battery_cap_total = reopt_out.get(f'capacityBattery{mg_num}', 0.0)
	battery_cap_existing = reopt_out.get(f'batteryKwhExisting{mg_num}', 0.0)
	mg_dict["Existing Battery Capacity (kWh)"] = round(battery_cap_existing,0)
	if battery_cap_total - battery_cap_existing > 0:
		mg_dict["Recommended New Battery Capacity (kWh)"] = round(battery_cap_total - battery_cap_existing,0)
	else:
		mg_dict["Recommended New Battery Capacity (kWh)"] = 0.0
	wind_size_total = reopt_out.get(f'sizeWind{mg_num}', 0.0)
	wind_size_existing = reopt_out.get(f'windExisting{mg_num}', 0.0)
	mg_dict["Existing Wind (kW)"] = round(wind_size_existing,0)
	if wind_size_total - wind_size_existing > 0:
		mg_dict["Recommended New Wind (kW)"] = round(wind_size_total - wind_size_existing,0)
	else:
		mg_dict["Recommended New Wind (kW)"] = 0.0
	total_gen = diesel_size_total + solar_size_total + battery_pow_total + wind_size_total
	mg_dict["Total Generation on Grid (kW)"] = round(total_gen,0)
	npv = reopt_out.get(f'savings{mg_num}', 0.0) # overall npv against the business as usual case from REopt
	cap_ex = reopt_out.get(f'initial_capital_costs{mg_num}', 0.0) # description from REopt: Up-front capital costs for all technologies, in present value, excluding replacement costs and incentives
	cap_ex_after_incentives = reopt_out.get(f'initial_capital_costs_after_incentives{mg_num}', 0.0) # description from REopt: Up-front capital costs for all technologies, in present value, excluding replacement costs, including incentives
	# economic outcomes with the capital costs of existing wind and batteries deducted:
	npv_existing_gen_adj = npv \
							+ wind_size_existing * reopt_out.get(f'windCost{mg_num}', 0.0) \
							+ battery_cap_existing * reopt_out.get(f'batteryCapacityCost{mg_num}', 0.0) \
							+ battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0)
	mg_dict["Net Present Value ($)"] = f'{round(npv_existing_gen_adj):,}'
	cap_ex_existing_gen_adj = cap_ex \
							+ wind_size_existing * reopt_out.get(f'windCost{mg_num}', 0.0) \
							+ battery_cap_existing * reopt_out.get(f'batteryCapacityCost{mg_num}', 0.0) \
							+ battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0)
	mg_dict["CapEx ($)"] = f'{round(cap_ex_existing_gen_adj):,}'
	cap_ex_after_incentives_existing_gen_adj = cap_ex_after_incentives \
							+ wind_size_existing * reopt_out.get(f'windCost{mg_num}', 0.0) \
							+ battery_cap_existing * reopt_out.get(f'batteryCapacityCost{mg_num}', 0.0) \
							+ battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0)
	mg_dict["CapEx after Incentives ($)"] = f'{round(cap_ex_after_incentives_existing_gen_adj):,}'
	mg_dict["Average Outage Survived (h)"] = round(reopt_out.get(f'avgOutage{mg_num}', 0.0),0)
	list_of_mg_dict.append(mg_dict)
	#print(list_of_mg_dict)
	return(list_of_mg_dict)

def main(BASE_NAME, LOAD_NAME, REOPT_INPUTS, microgrid, playground_microgrids, GEN_NAME, FULL_NAME, OMD_NAME, ONELINE_NAME, MAP_NAME, REOPT_FOLDER, BIG_OUT_NAME, QSTS_STEPS):
	reopt_gen_mg_specs(BASE_NAME, LOAD_NAME, REOPT_INPUTS, REOPT_FOLDER, microgrid)
	gen_obs = get_gen_ob_and_shape_from_reopt(REOPT_FOLDER, GEN_NAME, microgrid)
	make_full_dss(BASE_NAME, GEN_NAME, LOAD_NAME, FULL_NAME, gen_obs)
	gen_omd(FULL_NAME, OMD_NAME)
	# Draw the circuit oneline.
	distNetViz.viz(OMD_NAME, forceLayout=False, outputPath='.', outputName=ONELINE_NAME, open_file=False)
	# Draw the map.
	geo.mapOmd(OMD_NAME, MAP_NAME, 'html', openBrowser=False, conversion=False, offline=True)
	# Powerflow outputs.
	opendss.newQstsPlot(FULL_NAME,
		stepSizeInMinutes=60, 
		numberOfSteps=QSTS_STEPS,
		keepAllFiles=False,
		actions={
			#24*5:'open object=line.671692 term=1',
			#24*8:'new object=fault.f1 bus1=670.1.2.3 phases=3 r=0 ontime=0.0'
		}
	)
	# opendss.voltagePlot(FULL_NAME, PU=True)
	# opendss.currentPlot(FULL_NAME)
	#TODO!!!! we're clobbering these outputs each time we run the full workflow. Consider keeping them separate.
	make_chart('timeseries_gen.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], REOPT_INPUTS['year'], QSTS_STEPS) #TODO: pull year using reopt_out.get(f'year{mg_num}', 0.0) from allOutputData.json after refactor
	# for timeseries_load, output ANSI Range A service bands (2,520V - 2,340V for 2.4kV and 291V - 263V for 0.277kV)
	make_chart('timeseries_load.csv', 'Name', 'hour', ['V1(PU)','V2(PU)','V3(PU)'], REOPT_INPUTS['year'], QSTS_STEPS, ansi_bands = True)
	make_chart('timeseries_source.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], REOPT_INPUTS['year'], QSTS_STEPS)
	make_chart('timeseries_control.csv', 'Name', 'hour', ['Tap(pu)'], REOPT_INPUTS['year'], QSTS_STEPS)
	# Perform control sim.
	import opendss_playground
	# opendss_playground.play('./lehigh.dss.omd', './lehigh_base_phased_playground.dss', './tiedata.csv', None, opendss_playground.microgrids, '670671', False, 120, 30) #TODO: unify the microgrids data structure.
	opendss_playground.play(OMD_NAME, BASE_NAME, None, None, playground_microgrids, '670671', False, 120, 30) #TODO: unify the microgrids data structure.
	microgrid_report_csv('/allOutputData.json', f'ultimate_rep_{FULL_NAME}.csv', REOPT_FOLDER, microgrid)
	mg_list_of_dicts_full = microgrid_report_list_of_dicts('/allOutputData.json', REOPT_FOLDER, microgrid)
	# convert to dict of lists for columnar output in output_template.html
	mg_dict_of_lists_full = {key: [dic[key] for dic in mg_list_of_dicts_full] for key in mg_list_of_dicts_full[0]}
	# Create giant consolidated report.
	template = j2.Template(open('output_template.html').read())
	out = template.render(
		x='David',
		y='Matt',
		summary=mg_dict_of_lists_full,
		inputs={'circuit':BASE_NAME,'loads':LOAD_NAME,'REopt inputs':REOPT_INPUTS,'microgrid':microgrid},
		reopt_folder=REOPT_FOLDER
	)
	#TODO: have an option where we make the template <iframe srcdoc="{{X}}"> to embed the html and create a single file.
	with open(BIG_OUT_NAME,'w') as outFile:
		outFile.write(out)
	os.system(f'open {BIG_OUT_NAME}')

if __name__ == '__main__':
	print('No Inputs Received')