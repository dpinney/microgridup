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

#Input data.
# BASE_NAME = 'lehigh_base_phased.dss'
# LOAD_NAME = 'lehigh_load.csv'
# REOPT_INPUTS = {}
# microgrids = {
# 	'm1': {
# 		'loads': ['634a_supermarket','634b_supermarket','634c_supermarket'],
# 		'switch': '632633',
# 		'gen_bus': '634'
# 	},
# 	'm2': {
# 		'loads': ['675a_hospital','675b_residential1','675c_residential1'],
# 		'switch': '671692',
# 		'gen_bus': '675'
# 	},
# 	'm3': {
# 		'loads': ['671_hospital','652_med_apartment'],
# 		'switch': '671684',
# 		'gen_bus': '684'
# 	},
# 	'm4': {
# 		'loads': ['645_warehouse1','646_med_office'],
# 		'switch': '632645',
# 		'gen_bus': '646'
# 	}
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
	"outageDuration": "120",
	"fuelAvailable": "50000",
	"genExisting": 0,
	"minGenLoading": "0.3"
}
# gen_objects include all generator objects in the microgrid, preselected from base.dss
microgrids = {
	'm1': {
		'loads': ['634a_supermarket','634b_supermarket','634c_supermarket','675a_hospital','675b_residential1','675c_residential1','671_hospital','652_med_apartment','645_warehouse1','646_med_office'],
		'switch': '650632',
		'gen_bus': '670',
		'gen_objects': ['solar_634', 'diesel_634']
	}
}

# Output paths.
GEN_NAME = 'lehigh_gen.csv'
FULL_NAME = 'lehigh_full.dss'
OMD_NAME = 'lehigh.dss.omd'
ONELINE_NAME = 'lehigh.oneline.html'
MAP_NAME = 'lehigh_map'

# Generate an OMD.
if not os.path.isfile(OMD_NAME):
	tree = dssConvert.dssToTree(BASE_NAME)
	evil_glm = dssConvert.evilDssTreeToGldTree(tree)
	add_coords = json.load(open('additional_coords.json'))
	# Injecting additional coordinates.
	for ob in evil_glm.values():
		ob_name = ob.get('name','')
		ob_type = ob.get('object','')
		for ob2 in add_coords:
			ob2_name = ob2.get('name','')
			ob2_type = ob2.get('object','')
			if ob_name == ob2_name and ob_type == ob2_type:
				ob['latitude'] = ob2.get('latitude',0)
				ob['longitude'] = ob2.get('longitude',0)
	dssConvert.evilToOmd(evil_glm, OMD_NAME)

# Draw the circuit oneline.
if not os.path.isfile(ONELINE_NAME):
	distNetViz.viz(OMD_NAME, forceLayout=False, outputPath='.', outputName=ONELINE_NAME, open_file=False)

# Draw the map.
if not os.path.isdir(MAP_NAME):
	geo.mapOmd(OMD_NAME, MAP_NAME, 'html', openBrowser=False, conversion=False, offline=True)

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
	# requires pre-selection of all objects in a given microgrid in microgrids[key]['gen_objects']
	solar_gen = [] # TODO: Refactor will need one list per microgrid if running a single pass of REopt (named solar_gen_{mg_num} for example)
	diesel_gen = [] # TODO: Refactor will need one list per microgrid if running a single pass of REopt (named diesel_gen_{mg_num} for example)
	for key in microgrids:
		gen_obs = microgrids[key]['gen_objects'] 
		for gen_ob in gen_obs: # gen_ob is a name of an object from base.dss
			for ob in evil_glm.values(): # TODO: Change the syntax to match to the "tree" structure; See shpae insertions at line 270 for an example
				ob_name = ob.get('name','')
				#print(ob_name)
				ob_type = ob.get('object','')
				if ob_name == gen_ob and ob_type == "generator" and re.search('solar.+', ob_name):
						solar_gen.append(float(ob.get('kw')))
				elif ob_name == gen_ob and ob_type == "generator" and re.search('diesel.+', ob_name):
						diesel_gen.append(float(ob.get('kw')))
	#print("solar_gen:", solar_gen)
	#print("diesel_gen:", diesel_gen)
	allInputData['solarExisting'] = str(sum(solar_gen))
	allInputData['genExisting'] = str(sum(diesel_gen))

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
	solar_size_total = reopt_out.get(f'sizePV{mg_num}', 0.0)
	solar_size_existing = reopt_out.get(f'sizePVExisting{mg_num}', 0.0)
	solar_size_new = solar_size_total - solar_size_existing
	wind_size = reopt_out.get(f'sizeWind{mg_num}', 0.0) # TO DO: Update size of wind based on existing generation
	diesel_size_total = reopt_out.get(f'sizeDiesel{mg_num}', 0.0)
	diesel_size_existing = reopt_out.get(f'sizeDieselExisting{mg_num}', 0.0)
	diesel_size_new = diesel_size_total - diesel_size_existing
	battery_cap = reopt_out.get(f'capacityBattery{mg_num}', 0.0) # TO DO: Update size of battery based on existing generation
	battery_pow = reopt_out.get(f'powerBattery{mg_num}', 0.0) # TO DO: Update power of battery based on existing generation

	if solar_size_total > 0:
		gen_obs.append({
			'!CMD': 'new',
			'object':f'generator.solar_{gen_bus_name}',
			'bus1':f'{gen_bus_name}.1.2.3',
			'phases':'3', #todo: what about multiple smaller phases?
			'kv':'4.16', #todo: fix, make non-generic
			'kw':f'{solar_size_new}',
			'pf':'1'
		})
		gen_df_builder[f'solar_{gen_bus_name}'] = reopt_out.get(f'powerPV{mg_num}')
		# 0-1 scale the power output loadshape to the total generation kw of that type of generator
		gen_df_builder[f'solar_{gen_bus_name}'] = gen_df_builder[f'solar_{gen_bus_name}']/solar_size_total
	if wind_size > 0:
		gen_obs.append({
			'!CMD': 'new',
			'object':f'generator.wind_{gen_bus_name}',
			'bus1':f'{gen_bus_name}.1.2.3',
			'phases':'3', #todo: what about multiple smaller phases?
			'kv':'4.16', #todo: fix, make non-generic
			'kw':f'{wind_size}',
			'pf':'1'
		})
		gen_df_builder[f'wind_{gen_bus_name}'] = reopt_out.get(f'powerWind{mg_num}')
		# 0-1 scale the power output loadshape to the total generation kw of that type of generator
		gen_df_builder[f'wind_{gen_bus_name}'] = gen_df_builder[f'wind_{gen_bus_name}']/wind_size # TODO: 0-1 scale this to wind_size_total
	if diesel_size_total > 0:
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
		gen_df_builder[f'diesel_{gen_bus_name}'] = reopt_out.get(f'powerDiesel{mg_num}')
		# 0-1 scale the power output loadshape to the total generation kw of that type of generator
		gen_df_builder[f'diesel_{gen_bus_name}'] = gen_df_builder[f'diesel_{gen_bus_name}']/diesel_size_total
	if battery_cap > 0:
		gen_obs.append({
			'!CMD': 'new',
			'object':f'storage.battery_{gen_bus_name}',
			'bus1':f'{gen_bus_name}.1.2.3',
			'kv':'4.16', #todo: fix, make non-generic
			'kw':f'{battery_pow}',
			'phases':'3',
			'kwhstored':f'{battery_cap}',
			'kwhrated':f'{battery_cap}',
			'kva':f'{battery_pow}',
			'kvar':f'{battery_pow}',
			'%charge':'100',
			'%discharge':'100',
			'%effcharge':'100',
			'%effdischarge':'100',
			'%idlingkw':'1',
			'%r':'0',
			'%x':'50'
		})
		gen_df_builder[f'battery_{gen_bus_name}'] = reopt_out.get(f'powerBatteryToLoad{mg_num}')
		# 0-1 scale the power output loadshape to the total generation kw of that type of generator in pandas
		gen_df_builder[f'battery_{gen_bus_name}'] = gen_df_builder[f'battery_{gen_bus_name}']/battery_pow
		#print(gen_obs)

# insert generation objects into dss
tree = dssConvert.dssToTree(BASE_NAME)
# for col in gen_df_builder.columns:
# 	# zero-one scale the generator shapes. Already done in reference to the total reference size in loop above
# 	gen_df_builder[col] = gen_df_builder[col] / gen_df_builder[col].max() #TO DO: the 0-1 should be relative to the specified total kw of the generator
gen_df_builder.to_csv(GEN_NAME, index=False)
bus_list_pos = -1
for i, ob in enumerate(tree):
	if ob.get('!CMD','') == 'makebuslist':
		bus_list_pos = i
print("gen_obs after all new gen is built:", gen_obs)
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
	elif ob_string.startswith('generator.') or ob_string.startswith('battery.'):
		ob_name = ob_string[10:] #To Do: check if this grabs the full name of the battery gen objects; if not, add an elif statement or start after the '.' using regex
		print('ob_name:', ob_name)
		shape_data = gen_df[ob_name]
		shape_name = ob_name + '_shape'
		print('shape_name:', shape_name)
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

# Powerflow outputs.
opendss.newQstsPlot(FULL_NAME,
	stepSizeInMinutes=60, 
	numberOfSteps=24*20,
	keepAllFiles=False,
	actions={
		#24*5:'open object=line.671692 term=1',
		#24*8:'new object=fault.f1 bus1=670.1.2.3 phases=3 r=0 ontime=0.0'
	}
)
# opendss.voltagePlot(FULL_NAME, PU=True)
# opendss.currentPlot(FULL_NAME)

# Generate a report on each microgrid
def microgrid_report(inputName, outputCsvName):
    reopt_out = json.load(open(reopt_folder + inputName))

    with open(outputCsvName, 'w', newline='') as outcsv:
        writer = csv.writer(outcsv)
        writer.writerow(["Microgrid Name", "Generation Bus", "Minimum Load (kWh)", "Average Load (kWh)", "Average Daytime Load (kWh)", "Maximum Load (kWh)", "Recommended Diesel (kW)", "Diesel Fuel Used During Outage (gal)", "Recommended Solar (kW)", "Recommended Battery Power (kW)", "Recommended Battery Capacity (kWh)", "Recommended Wind (kW)", "NPV ($)", "CapEx ($)", "CapEx after Incentives ($)", "Average Outage Survived (h)"])

        for i, mg_ob in enumerate(microgrids.values()):
            mg_num = i + 1
            gen_bus_name = mg_ob['gen_bus']
            load = reopt_out.get(f'load{mg_num}', 0.0)
            min_load = min(load)
            ave_load = sum(load)/len(load)
            np_load = np.array_split(load, 365)
            np_load = np.array(np_load) #an array of 365 arrays of 24 hours each
            daytime_kwh = np_load[:,9:17] #365 8-hour daytime arrays
            avg_daytime_load = np.average(np.average(daytime_kwh, axis=1))
            max_load = max(load)
            diesel_size = reopt_out.get(f'sizeDiesel{mg_num}', 0.0)
            diesel_used_gal =reopt_out.get(f'fuelUsedDiesel{mg_num}', 0.0)
            solar_size = reopt_out.get(f'sizePV{mg_num}', 0.0)
            battery_cap = reopt_out.get(f'capacityBattery{mg_num}', 0.0)
            battery_pow = reopt_out.get(f'powerBattery{mg_num}', 0.0)
            wind_size = reopt_out.get(f'sizeWind{mg_num}', 0.0)
            npv = reopt_out.get(f'savings{mg_num}', 0.0)
            cap_ex = reopt_out.get(f'initial_capital_costs{mg_num}', 0.0)
            cap_ex_after_incentives = reopt_out.get(f'initial_capital_costs_after_incentives{mg_num}', 0.0)
            ave_outage = reopt_out.get(f'avgOutage{mg_num}', 0.0)
            row =[mg_num, gen_bus_name, round(min_load,0), round(ave_load,0), round(avg_daytime_load,1), round(max_load,0), round(diesel_size,1), round(solar_size,1), round(battery_pow,1), round(battery_cap,1), round(wind_size,1), int(round(npv)), int(round(cap_ex)), int(round(cap_ex_after_incentives)), round(ave_outage,1)]
            writer.writerow(row)

microgrid_report('/allOutputData.json','microgrid_report.csv')

# Charting outputs.
def make_chart(csvName, category_name, x, y_list):
	gen_data = pd.read_csv(csvName)
	data = []
	for ob_name in set(gen_data[category_name]):
		for y_name in y_list:
			this_series = gen_data[gen_data[category_name] == ob_name]
			trace = plotly.graph_objs.Scatter(
				x = this_series[x],
				y = this_series[y_name],
				name = ob_name + '_' + y_name
			)
			data.append(trace)
	layout = plotly.graph_objs.Layout(
		title = f'{csvName} Output',
		xaxis = dict(title = x),
		yaxis = dict(title = str(y_list))
	)
	fig = plotly.graph_objs.Figure(data, layout)
	plotly.offline.plot(fig, filename=f'{csvName}.plot.html', auto_open=False)
make_chart('timeseries_gen.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'])
make_chart('timeseries_load.csv', 'Name', 'hour', ['V1(PU)','V2(PU)','V3(PU)'])
make_chart('timeseries_source.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'])
make_chart('timeseries_control.csv', 'Name', 'hour', ['Tap(pu)'])

#TODO: enable this when we're good with control.
#import opendss_playground
#opendss_playground.play('lehigh.dss.omd', 'lehigh_full.dss', None, microgrids, '670671', False)

# Create giant consolidated report.
template = j2.Template(open('output_template.html').read())
out = template.render(
	x='David',
	y='Matt',
	summary=open('microgrid_report.csv').read(),
	inputs={'circuit':BASE_NAME,'loads':LOAD_NAME,'REopt inputs':REOPT_INPUTS,'microgrids':microgrids}
)
#TODO: have an option where we make the template <iframe srcdoc="{{X}}"> to embed the html and create a single file.
BIG_OUT_NAME = 'output_full_analysis_lehigh.html'
with open(BIG_OUT_NAME,'w') as outFile:
	outFile.write(out)
os.system(f'open {BIG_OUT_NAME}')