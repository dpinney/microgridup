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

# Input data.
# BASE_NAME = 'lehigh_base_phased.dss'
# LOAD_NAME = 'lehigh_load.csv'
# REOPT_INPUTS = {
# 	"solar" : "on",
# 	"wind" : "off",
# 	"battery" : "on",
# 	"year" : '2017',
# 	"energyCost" : "0.12",
# 	"demandCost" : '20',
# 	"solarCost" : "1600",
# 	"windCost" : "4989",
# 	"batteryPowerCost" : "840",
# 	"batteryCapacityCost" : "420",
# 	"dieselGenCost": "500",
# 	"solarMin": 0,
# 	"windMin": 0,
# 	"batteryPowerMin": 0,
# 	"batteryCapacityMin": 0,
# 	"solarMax": "100000",
# 	"windMax": "100000",
# 	"batteryPowerMax": "1000000",
# 	"batteryCapacityMax": "1000000",
# 	"solarExisting": 0,
# 	"criticalLoadFactor": "1",
# 	"outage_start_hour": "200",
# 	"outageDuration": "48",
# 	"fuelAvailable": "50000",
# 	"genExisting": 0,
# 	"minGenLoading": "0.3",
# 	"batteryKwExisting": 0,
# 	"batteryKwhExisting": 0,
# 	"windExisting": 0,
# 	"value_of_lost_load": "100",
# 	"solarCanCurtail": True,
# 	"solarCanExport": True
# }
# microgrids = {
	# 'm1': {
	# 	'loads': ['634a_data_center','634b_radar','634c_atc_tower'],
	# 	'switch': '632633',
	# 	'gen_bus': '634',
	# 	'gen_obs_existing': ['solar_634_existing']
	# },
	# 'm2': {
	# 	'loads': ['675a_hospital','675b_residential1','675c_residential1'],
	# 	'switch': '671692',
	# 	'gen_bus': '675',
	# 	'gen_obs_existing': []
	# },
	# 'm3': {
	# 	'loads': ['671_command_center','652_residential'],
	# 	'switch': '671684',
	# 	'gen_bus': '684',
	# 	'gen_obs_existing': ['diesel_684_existing']
	# },
	# 'm4': {
	# 	'loads': ['645_hangar','646_office'],
	# 	'switch': '632645',
	# 	'gen_bus': '646',
	# 	'gen_obs_existing': []
	# }
# }

#Second input set.
BASE_NAME = 'lehigh_base_phased.dss'
LOAD_NAME = 'lehigh_load.csv'
REOPT_INPUTS = {
	"solar" : "on",
	"wind" : "off",
	"battery" : "on",
	"year" : '2017',
	"energyCost" : "0.12",
	"demandCost" : '20',
	"solarCost" : "1600",
	"windCost" : "4989",
	"batteryPowerCost" : "840",
	"batteryCapacityCost" : "420",
	"dieselGenCost": "500",
	"solarMin": 0,
	"windMin": 0,
	"batteryPowerMin": 0,
	"batteryCapacityMin": 0,
	"solarMax": "100000",
	"windMax": "100000",
	"batteryPowerMax": "1000000",
	"batteryCapacityMax": "1000000",
	"solarExisting": 0,
	"criticalLoadFactor": "1",
	"outage_start_hour": "200",
	"outageDuration": "48",
	"fuelAvailable": "50000",
	"genExisting": 0,
	"minGenLoading": "0.3",
	"batteryKwExisting": 0,
	"batteryKwhExisting": 0,
	"windExisting": 0,
	"value_of_lost_load": "100",
	"solarCanCurtail": True,
	"solarCanExport": True
}
# gen_obs_existing include all generator objects already in the microgrid, preselected from base.dss
microgrids = {
	'm1': {
		'loads': ['634a_data_center','634b_radar','634c_atc_tower','675a_hospital','675b_residential1','675c_residential1','671_command_center','652_residential','645_hangar','646_office'],
		'switch': '650632',
		'gen_bus': '670',
		'gen_obs_existing': ['solar_634_existing', 'diesel_684_existing']
	}
}

# Output paths.
GEN_NAME = 'lehigh_gen.csv'
FULL_NAME = 'lehigh_full.dss'
OMD_NAME = 'lehigh.dss.omd'
ONELINE_NAME = 'lehigh.oneline.html'
MAP_NAME = 'lehigh_map'

def _name_to_key(glm):
	''' Make fast lookup map by name in a glm. '''
	mapping = {}
	for key, val in glm.items():
		if 'name' in val:
			mapping[val['name']] = key
	return mapping

# Generate the microgrid specs with REOpt.
reopt_folder = './lehigh_reopt'
load_df = pd.read_csv(LOAD_NAME)
if not os.path.isdir(reopt_folder):
	import omf.models
	shutil.rmtree(reopt_folder, ignore_errors=True)
	omf.models.microgridDesign.new(reopt_folder)
	
	# Get the microgrid total loads
	mg_load_df = pd.DataFrame()
	for key in microgrids:
		loads = microgrids[key]['loads']
		mg_load_df[key] = [0 for x in range(8760)]
		for load_name in loads:
			mg_load_df[key] = mg_load_df[key] + load_df[load_name]
	mg_load_df.to_csv(reopt_folder + '/loadShape.csv', header=False, index=False)
	
	# Default inputs.
	allInputData = json.load(open(reopt_folder + '/allInputData.json'))
	allInputData['loadShape'] = open(reopt_folder + '/loadShape.csv').read()
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
	solar_kw_exist = [] # TODO: Refactor will need one list per microgrid if running a single pass of REopt (named solar_gen_exist_{mg_num} for example)
	diesel_kw_exist = [] # TODO: Refactor will need one list per microgrid if running a single pass of REopt (named diesel_gen_exist_{mg_num} for example)
	battery_kw_exist = []
	battery_kwh_exist = []
	wind_kw_exist = []
	for key in microgrids:
		gen_obs = microgrids[key]['gen_obs_existing'] 
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
	with open(reopt_folder + '/allInputData.json','w') as outfile:
		json.dump(allInputData, outfile, indent=4)
	omf.models.__neoMetaModel__.runForeground(reopt_folder)
	omf.models.__neoMetaModel__.renderTemplateToFile(reopt_folder)

# Get generator objects and shapes from REOpt.
reopt_out = json.load(open(reopt_folder + '/allOutputData.json'))
gen_df_builder = pd.DataFrame()
gen_obs = []
for i, mg_ob in enumerate(microgrids.values()):
	mg_num = i + 1
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
			'kv':'4.16', #todo: fix, make non-generic
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
			'kv':'4.16', #todo: fix, make non-generic
			'kw':f'{diesel_size_new}',
			'phases':'3', #todo: what about multiple smaller phases?
			'pf':'1',
			'xdp':'0.27',
			'xdpp':'0.2',
			'h':'2',
			'conn':'delta'
		})
		# 0-1 scale the power output loadshape to the total generation kw of that type of generator
		gen_df_builder[f'diesel_{gen_bus_name}'] = pd.Series(reopt_out.get(f'powerDiesel{mg_num}'))/diesel_size_total

	# build loadshapes for existing generation from BASE_NAME, inputting the 0-1 diesel generation loadshape 
	if diesel_size_existing > 0:	
		for gen_ob_existing in gen_obs_existing:
			if gen_ob_existing.startswith('diesel_'):
				gen_df_builder[f'{gen_ob_existing}'] = pd.Series(reopt_out.get(f'powerDiesel{mg_num}'))/diesel_size_total

	# insert loadshapes for new Wind
	if wind_size_new > 0:
		gen_obs.append({
			'!CMD': 'new',
			'object':f'generator.wind_{gen_bus_name}',
			'bus1':f'{gen_bus_name}.1.2.3',
			'phases':'3', #todo: what about multiple smaller phases?
			'kv':'4.16', #todo: fix, make non-generic
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

	# insert DSS objects and loadshapes for new battery
	if battery_cap_new > 0: 
		gen_obs.append({
			'!CMD': 'new',
			'object':f'storage.battery_{gen_bus_name}',
			'bus1':f'{gen_bus_name}.1.2.3',
			'kv':'4.16', #todo: fix, make non-generic
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
			'%x':'50'
		})
		gen_df_builder[f'battery_{gen_bus_name}'] = battery_load_0_1

	# build loadshapes for existing battery generation from BASE_NAME
	if battery_cap_existing > 0:	
		for gen_ob_existing in gen_obs_existing:
			if gen_ob_existing.startswith('battery_'):
				gen_df_builder[f'{gen_ob_existing}'] = battery_load_0_1

# insert generation objects into dss
tree = dssConvert.dssToTree(BASE_NAME)
gen_df_builder.to_csv(GEN_NAME, index=False)
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
for i, ob in enumerate(tree):
	ob_string = ob.get('object','')
	if ob_string.startswith('load.'):
		ob_name = ob_string[5:]
		shape_data = load_df[ob_name] #load_df built in line 86 using load_df = pd.read_csv(LOAD_NAME)
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

# Do shape insertions at proper places
for key in shape_insert_list:
	min_pos = min(shape_insert_list.keys())
	tree.insert(min_pos, shape_insert_list[key])

# Write new DSS file.
dssConvert.treeToDss(tree, FULL_NAME)

# Generate an OMD.
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

# Draw the circuit oneline.
distNetViz.viz(OMD_NAME, forceLayout=False, outputPath='.', outputName=ONELINE_NAME, open_file=False)

# Draw the map.
geo.mapOmd(OMD_NAME, MAP_NAME, 'html', openBrowser=False, conversion=False, offline=True)

# Powerflow outputs.
opendss.newQstsPlot(FULL_NAME,
	stepSizeInMinutes=60, 
	numberOfSteps=24*365,
	keepAllFiles=False,
	actions={
		#24*5:'open object=line.671692 term=1',
		#24*8:'new object=fault.f1 bus1=670.1.2.3 phases=3 r=0 ontime=0.0'
	}
)
# opendss.voltagePlot(FULL_NAME, PU=True)
# opendss.currentPlot(FULL_NAME)

# Charting outputs.
def make_chart(csvName, category_name, x, y_list, year):
	gen_data = pd.read_csv(csvName)
	data = [] 
	for ob_name in set(gen_data[category_name]):
		for y_name in y_list:
			this_series = gen_data[gen_data[category_name] == ob_name]
			trace = plotly.graph_objs.Scatter(
				x = pd.to_datetime(this_series[x], unit = 'h', origin = pd.Timestamp(f'{year}-01-01')), #TODO: make this datetime convert arrays other than hourly or with a different startdate than Jan 1 if needed
				y = round(this_series[y_name],3),
				name = ob_name + '_' + y_name,
				hoverlabel = dict(namelength = -1)
			)
			data.append(trace)
	layout = plotly.graph_objs.Layout(
		title = f'{csvName} Output',
		xaxis = dict(title = x),
		yaxis = dict(title = str(y_list))
	)
	fig = plotly.graph_objs.Figure(data, layout)
	plotly.offline.plot(fig, filename=f'{csvName}.plot.html', auto_open=False)

make_chart('timeseries_gen.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], REOPT_INPUTS['year']) #TODO: pull year using reopt_out.get(f'year{mg_num}', 0.0) from allOutputData.json after refactor
make_chart('timeseries_load.csv', 'Name', 'hour', ['V1(PU)','V2(PU)','V3(PU)'], REOPT_INPUTS['year'])
make_chart('timeseries_source.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], REOPT_INPUTS['year'])
make_chart('timeseries_control.csv', 'Name', 'hour', ['Tap(pu)'], REOPT_INPUTS['year'])

#TODO: enable this when we're good with control.
#import opendss_playground
#opendss_playground.play('lehigh.dss.omd', 'lehigh_full.dss', None, microgrids, '670671', False)

# Generate a report on each microgrid
def microgrid_report_csv(inputName, outputCsvName):
	reopt_out = json.load(open(reopt_folder + inputName))

	with open(outputCsvName, 'w', newline='') as outcsv:
		writer = csv.writer(outcsv)
		writer.writerow(["Microgrid Name", "Generation Bus", "Minimum Load (kWh)", "Average Load (kWh)",
							"Average Daytime Load (kWh)", "Maximum Load (kWh)", "Existing Diesel (kW)", "Recommended New Diesel (kW)",
							"Diesel Fuel Used During Outage (gal)", "Existing Solar (kW)", "Recommended New Solar (kW)", 
							"Existing Battery Power (kW)", "Recommended New Battery Power (kW)", "Existing Battery Capacity (kWh)", 
							"Recommended New Battery Capacity (kWh)", "Existing Wind (kW)", "Recommended New Wind (kW)", 
							"Total Generation on Grid (kW)", "NPV ($)", "CapEx ($)", "CapEx after Incentives ($)", 
							"Average Outage Survived (h)"])

		for i, mg_ob in enumerate(microgrids.values()):
			mg_num = i + 1
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

			#TO DO: FIX THE TABBING ERROR IN THIS CODE SO IT PULLS THE VARIABELS FROM THIS LOOP INTO THE SUMMARY REPORT
			solar_size_total = reopt_out.get(f'sizePV{mg_num}', 0.0)
			solar_size_existing = reopt_out.get(f'sizePVExisting{mg_num}', 0.0)
			solar_size_new = solar_size_total - solar_size_existing
			wind_size_total = reopt_out.get(f'sizeWind{mg_num}', 0.0)# TO DO: Update size of wind based on existing generation once we find a way to get a loadshape for that wind if REopt recommends no wind
			wind_size_existing = reopt_out.get(f'windExisting{mg_num}', 0.0)
			if wind_size_total - wind_size_existing > 0:
				wind_size_new = wind_size_total - wind_size_existing
			else:
				wind_size_new = 0# TO DO: update logic here to make run more robust to oversized existing wind gen
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
			
			row =[mg_num, gen_bus_name, round(min_load,0), round(ave_load,0), round(avg_daytime_load,1), round(max_load,0),
			round(diesel_size_existing,1), round(diesel_size_new,1), round(diesel_used_gal, 0), round(solar_size_existing,1), 
			round(solar_size_new,1), round(battery_pow_existing,1), round(battery_pow_new,1), round(battery_cap_existing,1), 
			round(battery_cap_new,1), round(wind_size_existing,1), round(wind_size_new,1), round(total_gen,1),
			int(round(npv_existing_gen_adj)), int(round(cap_ex_existing_gen_adj)), int(round(cap_ex_after_incentives_existing_gen_adj)), 
			round(ave_outage,1)]
			
			writer.writerow(row)

microgrid_report_csv('/allOutputData.json','microgrid_report.csv') #TO DO: output as json or dict and convert report to list info in columns to reduce clutter in html output


#https://stackoverflow.com/questions/42847877/jinja2-list-of-dictionaries-into-html-table
def microgrid_report_list_of_dicts(inputName):
	reopt_out = json.load(open(reopt_folder + inputName))
	list_of_mg_dict = []
	for i, mg_ob in enumerate(microgrids.values()):
		mg_dict = {}
		mg_dict["Microgrid Name"] = i + 1
		mg_dict["Generation Bus"] = mg_ob['gen_bus']

		load = reopt_out.get(f'load{mg_num}', 0.0)
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


# Create giant consolidated report.
#summary_rdr= csv.reader( open('microgrid_report.csv', "r" ) )
#summary_data = [row for row in summary_rdr]

mg_list_of_dicts_full = microgrid_report_list_of_dicts('/allOutputData.json')

# mg_dict_of_lists_full = {}

# mg_num = 0
# for mg in mg_list_of_dicts_full:
# 	mg_num += 1
# 	value_list = []
# 	for key in mg.keys():
# 		value_list.append(mg[key])
# 	else:
# 		mg_dict_of_lists_full[mg_num] = value_list

mg_dict_of_lists_full = {key: [dic[key] for dic in mg_list_of_dicts_full] for key in mg_list_of_dicts_full[0]}

#print(mg_dict_of_lists_full)



#print(mg_dict_full)
# for key in mg_dict_full[0]:
# 	print(key)

template = j2.Template(open('output_template.html').read())
out = template.render(
	x='David',
	y='Matt',
	summary=mg_dict_of_lists_full,
	#summary=summary_data, # enable for using csv formatted print
	inputs={'circuit':BASE_NAME,'loads':LOAD_NAME,'REopt inputs':REOPT_INPUTS,'microgrids':microgrids}
)

#TODO: have an option where we make the template <iframe srcdoc="{{X}}"> to embed the html and create a single file.
BIG_OUT_NAME = 'output_full_analysis_lehigh.html'
with open(BIG_OUT_NAME,'w') as outFile:
	outFile.write(out)
os.system(f'open {BIG_OUT_NAME}')