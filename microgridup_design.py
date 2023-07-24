import os, json, shutil
import jinja2 as j2
import plotly.graph_objects as go
import pandas as pd
from omf.solvers.opendss import dssConvert
from omf.models.__neoMetaModel__ import csvValidateAndLoad

MGU_FOLDER = os.path.abspath(os.path.dirname(__file__))
if MGU_FOLDER == '/':
	MGU_FOLDER = '' #workaround for docker root installs
PROJ_FOLDER = f'{MGU_FOLDER}/data/projects'

def set_critical_load_percent(LOAD_NAME, microgrid, mg_name):
	''' Set the critical load percent input for REopt by finding the ratio of max critical load kws to the max kw of the loadshape of that mg'''
	load_df = pd.read_csv(LOAD_NAME)
	mg_load_df = pd.DataFrame()
	loads = microgrid['loads']
	mg_load_df['load'] = [0 for x in range(8760)]
	for load_name in loads:
		try:
			mg_load_df['load'] = mg_load_df['load'] + load_df[load_name]
		except:
			print('ERROR: loads in Load Data (.csv) do not match loads in circuit.')
	max_load = float(mg_load_df.max())
	# add up all max kws from critical loads to support during an outage
	max_crit_load = sum(microgrid['critical_load_kws'])
	if max_crit_load > max_load:
		warning_message = f'The critical loads specified for microgrid {mg_name} are larger than the max kw of the total loadshape.\n'
		print(warning_message)
		with open("user_warnings.txt", "a") as myfile:
			myfile.write(warning_message)
	critical_load_percent = max_crit_load/max_load
	if critical_load_percent > 2:
		print(f'This critical load percent of {critical_load_percent} is over 2.0, the maximum allowed. Setting critical load percent to 2.0.\n')
		critical_load_percent = 2.0
	return critical_load_percent, max_crit_load

def reopt_gen_mg_specs(BASE_NAME, LOAD_NAME, REOPT_INPUTS, REOPT_FOLDER, microgrid, critical_load_percent, INVALIDATE_CACHE=False):
	''' Generate the microgrid specs with REOpt.
	SIDE-EFFECTS: generates REOPT_FOLDER'''
	with open(LOAD_NAME, "r") as file:
		file_input = file.read()
		first_line = file_input.splitlines()[0]
		csv_width = len(first_line.split(','))
	cwd = os.getcwd()
	modelDir = cwd
	dtypes = [float if i > 0 else False for i in range(csv_width)]
	load_df = csvValidateAndLoad(file_input, modelDir, header=0, nrows=8760, ncols=csv_width, dtypes=dtypes, return_type='df', ignore_nans=True, save_file=None)
	if os.path.isdir(REOPT_FOLDER) and INVALIDATE_CACHE == False:
		# Cached results detected, user does not want to invalidate them, exit.
		return None
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
	# Insert loadshape into /allInputData.json
	allInputData = json.load(open(REOPT_FOLDER + '/allInputData.json'))
	allInputData['loadShape'] = open(REOPT_FOLDER + '/loadShape.csv').read()
	allInputData['fileName'] = 'loadShape.csv'
	# Pulling user defined inputs from REOPT_INPUTS.
	for key in REOPT_INPUTS:
		allInputData[key] = REOPT_INPUTS[key]
	# Set the REopt outage to be centered around the max load in the loadshape
	max_load = mg_load_df.max()
	max_load_index = int(mg_load_df.idxmax())
	# reset the outage timing such that the length of REOPT_INPUTS falls half before and half after the hour of max load
	outage_duration = int(REOPT_INPUTS["outageDuration"])
	if max_load_index + outage_duration/2 > 8760:
		outage_start_hour = 8760 - outage_duration
		# REopt seems not to allow an outage on the last hour of the year
	elif max_load_index - outage_duration/2 < 1:
		outage_start_hour = 2
	else:
		outage_start_hour = max_load_index - outage_duration/2
	allInputData['outage_start_hour'] = str(int(outage_start_hour))
	allInputData['criticalLoadFactor'] = str(critical_load_percent)
	# Pulling coordinates from BASE_NAME.dss into REopt allInputData.json:
	tree = dssConvert.dssToTree(BASE_NAME)
	evil_glm = dssConvert.evilDssTreeToGldTree(tree)
	# using evil_glm to get around the fact that buses in openDSS are created in memory and do not exist in the BASE_NAME dss file
	for ob in evil_glm.values():
		ob_name = ob.get('name','')
		ob_type = ob.get('object','')
		# pull out long and lat of the gen_bus
		if ob_type == "bus" and ob_name == microgrid['gen_bus']:
			ob_lat = ob.get('latitude','')
			ob_long = ob.get('longitude','')
			allInputData['latitude'] = float(ob_lat)
			allInputData['longitude'] = float(ob_long)
	# enable following 5 lines when using gen_existing_ref_shapes()
	# force REopt to optimize on wind and solar even if not recommended by REopt optimization
	if allInputData['wind'] == 'on':
		allInputData['windMin'] = '1'
	if allInputData['solar'] == 'on':
		allInputData['solarMin'] = '1'
	# Workflow to deal with existing generators in the microgrid and analyze for these in REopt
	# This workflow requires pre-selection of all objects in a given microgrid in microgrids['gen_obs_existing']
	# Multiple existing gens of any type except batteries are permitted
	# Pull out and add up kw of all existing generators in the microgrid
	load_map = {x.get('object',''):i for i, x in enumerate(tree)}
	solar_kw_exist = []
	fossil_kw_exist = []
	battery_kw_exist = []
	battery_kwh_exist = []
	wind_kw_exist = []
	gen_obs_existing = microgrid['gen_obs_existing']
	for gen_ob in gen_obs_existing:
		if gen_ob.startswith('solar_'):
			solar_kw_exist.append(float(tree[load_map[f'generator.{gen_ob}']].get('kw')))
		elif gen_ob.startswith('fossil_'):
			fossil_kw_exist.append(float(tree[load_map[f'generator.{gen_ob}']].get('kw')))
		elif gen_ob.startswith('wind_'):
			wind_kw_exist.append(float(tree[load_map[f'generator.{gen_ob}']].get('kw')))
		elif gen_ob.startswith('battery_'):
			battery_kw_exist.append(float(tree[load_map[f'storage.{gen_ob}']].get('kwrated')))
			battery_kwh_exist.append(float(tree[load_map[f'storage.{gen_ob}']].get('kwhrated')))
	allInputData['genExisting'] = str(sum(fossil_kw_exist))
	if sum(solar_kw_exist) > 0:
		allInputData['solarExisting'] = str(sum(solar_kw_exist))
		allInputData['solar'] = 'on'
	# do not analyze existing batteries if multiple existing batteries exist
	if len(battery_kwh_exist) > 1:
		allInputData['batteryKwExisting'] = 0
		allInputData['batteryKwhExisting'] = 0
		# multiple_existing_battery_message = f'More than one existing battery storage asset is specified on microgrid {mg_name}. Configuration of microgrid controller is not assumed to control multiple existing batteries, and thus all existing batteries will be removed from analysis of {mg_name}.\n'
		# print(multiple_existing_battery_message)
		# if path.exists("user_warnings.txt"):
		# 	with open("user_warnings.txt", "r+") as myfile:
		# 		if multiple_existing_battery_message not in myfile.read():
		# 			myfile.write(multiple_existing_battery_message)
		# else:
		# 	with open("user_warnings.txt", "a") as myfile:
		# 		myfile.write(multiple_existing_battery_message)
	elif sum(battery_kwh_exist) > 0:
		allInputData['batteryKwExisting'] = str(sum(battery_kw_exist))
		allInputData['batteryPowerMin'] = str(sum(battery_kw_exist))
		allInputData['batteryKwhExisting'] = str(sum(battery_kwh_exist))
		allInputData['batteryCapacityMin'] = str(sum(battery_kwh_exist))
		allInputData['battery'] = 'on'
	if sum(wind_kw_exist) > 0:
		allInputData['windExisting'] = str(sum(wind_kw_exist))
		allInputData['windMin'] = str(sum(wind_kw_exist))
		allInputData['wind'] = 'on' #failsafe to include wind if found in base_dss
		 #TODO: update logic if windMin, windExisting and other generation variables are enabled to be set by the user as inputs
	# enable following 9 lines when using gen_existing_ref_shapes()
	# if not already turned on, set solar and wind on to 1 kw to provide loadshapes for existing gen in make_full_dss()
	if allInputData['wind'] == 'off':
		allInputData['wind'] = 'on'
		allInputData['windMax'] = '1'
		allInputData['windMin'] = '1'
	if allInputData['solar'] == 'off':
		allInputData['solar'] = 'on'
		allInputData['solarMax'] = '1'
		allInputData['solarMin'] = '1'
	# run REopt via microgridDesign
	with open(REOPT_FOLDER + '/allInputData.json','w') as outfile:
		json.dump(allInputData, outfile, indent=4)
	omf.models.__neoMetaModel__.runForeground(REOPT_FOLDER)

def microgrid_design_output(allOutDataPath, allInputDataPath, outputPath):
	''' Generate a clean microgridDesign output with edge-to-edge design. '''
	all_html = ''
	legend_spec = {'orientation':'h', 'xanchor':'left'}#, 'x':0, 'y':-0.2}
	with open(allOutDataPath) as file:
		allOutData = json.load(file)
	# Make timeseries charts
	plotlyData = {
		'Generation Serving Load':'powerGenerationData1',
		'Solar Generation Detail':'solarData1',
		'Wind Generation Detail':'windData1',
		'Fossil Generation Detail':'dieselData1',
		'Storage Charge Source':'batteryData1',
		'Storage State of Charge':'batteryChargeData1'}
	# Sometimes missing, so only add if available.
	if 'resilienceData1' in allOutData:
		plotlyData['Resilience Overview'] = 'resilienceData1'
	if 'resilienceProbData1' in allOutData:
		plotlyData['Outage Survival Probability'] = 'resilienceProbData1'
	for k,v in plotlyData.items():
		chart_data = json.loads(allOutData[v])
		fig = go.Figure(chart_data)
		fig.update_layout(
			title = k,
			legend = legend_spec
		)
		fig_html = fig.to_html(default_height='600px')
		all_html = all_html + fig_html
	# Make generation overview chart
	gen_data = {
		"Average Load (kWh)": allOutData["avgLoad1"],
		"Solar Total (kW)": allOutData["sizePVRounded1"],
		"Wind Total (kW)": allOutData["sizeWindRounded1"],
		"Storage Total (kW)": allOutData["powerBatteryRounded1"],
		"Storage Total (kWh)": allOutData["capacityBatteryRounded1"],
		"Fossil Total (kW)": allOutData["sizeDieselRounded1"],
		"Fossil Fuel Used in Outage (kGal diesel equiv.)": allOutData["fuelUsedDieselRounded1"] / 1000.0}
	generation_fig = go.Figure(
		data=[
			go.Bar(
				name = 'Without Microgrid',
				x=list(gen_data.keys()),
				y=list(gen_data.values()),
			)
		]
	)
	generation_fig.update_layout(
		title = 'Generation Overview',
		legend = legend_spec
	)
	generation_fig_html = generation_fig.to_html(default_height='600px')
	all_html = generation_fig_html + all_html
	# Make financial overview chart
	fin_data_bau = {
		'Demand Cost ($)':allOutData["demandCostBAU1"],
		'Energy Cost ($)':allOutData["energyCostBAU1"],
		'Total Cost ($)':allOutData["totalCostBAU1"],
		'Avg. Outage Survived (H)': None}
	fin_data_microgrid = {
		'Demand Cost ($)':allOutData["demandCost1"],
		'Energy Cost ($)':allOutData["energyCost1"],
		'Total Cost ($)':allOutData["totalCost1"],
		'Avg. Outage Survived (H)': allOutData.get("avgOutage1",None) }
	fin_fig = go.Figure(
		data=[
			go.Bar(
				name = 'Business as Usual',
				x=list(fin_data_bau.keys()),
				y=list(fin_data_bau.values()),
			),
			go.Bar(
				name = 'With Microgrid',
				x=list(fin_data_microgrid.keys()),
				y=list(fin_data_microgrid.values()),
			)
		]
	)
	fin_fig.update_layout(
		title = 'Lifetime Financial Comparison Overview',
		legend = legend_spec
	)
	fin_fig_html = fin_fig.to_html(default_height='600px')
	all_html = fin_fig_html + all_html
	# Nice input display
	with open(allInputDataPath) as inFile:
		allInputData = json.load(inFile)
	allInputData['loadShape'] = 'From File'
	allInputData['criticalLoadShape'] = 'From File'
	# Templating.
	with open(f'{MGU_FOLDER}/templates/template_microgridDesign.html') as inFile:
		mgd_template = j2.Template(inFile.read())
	mgd = mgd_template.render(
		chart_html=all_html,
		allInputData=allInputData
	)
	with open(outputPath, 'w') as outFile:
		outFile.write(mgd)

def run(LOAD_FILE_PATH, MICROGRID_DICT, MG_NAME, DSS_FILE_PATH, REOPT_INPUTS, REOPT_FOLDER_FINAL, INVALIDATE_CACHE=False):
	''' Generate full microgrid design for given microgrid spec dictionary and circuit file (used to gather distribution assets).'''
	critical_load_percent, max_crit_load = set_critical_load_percent(LOAD_FILE_PATH, MICROGRID_DICT, MG_NAME)
	reopt_gen_mg_specs(DSS_FILE_PATH, LOAD_FILE_PATH, REOPT_INPUTS, REOPT_FOLDER_FINAL, MICROGRID_DICT, critical_load_percent, INVALIDATE_CACHE)
	microgrid_design_output(f'{REOPT_FOLDER_FINAL}/allOutputData.json', f'{REOPT_FOLDER_FINAL}/allInputData.json', f'{REOPT_FOLDER_FINAL}/cleanMicrogridDesign.html')

def _tests():
	# Load arguments from JSON.
	with open('testfiles/test_params.json') as file:
		test_params = json.load(file)
	control_test_args = test_params['control_test_args']
	REOPT_INPUTS = test_params['REOPT_INPUTS']
	# Testing directory.
	_dir = 'lehigh4mgs' # Change to test on different directory.
	MODEL_DIR = f'{PROJ_FOLDER}/{_dir}'
	# HACK: work in directory because we're very picky about the current dir.
	curr_dir = os.getcwd()
	workDir = os.path.abspath(MODEL_DIR)
	if curr_dir != workDir:
		os.chdir(workDir)
	microgrids = control_test_args[_dir]
	for run_count in range(len(microgrids)):
		LOAD_NAME = 'loads.csv'
		microgrid = microgrids[f'mg{run_count}']
		mg_name = f'mg{run_count}'
		BASE_NAME = 'circuit.dss' if run_count == 0 else f'circuit_plusmg_{run_count - 1}.dss'
		REOPT_FOLDER_FINAL = f'reopt_final_{run_count}'
		run(LOAD_NAME, microgrid, mg_name, BASE_NAME, REOPT_INPUTS, REOPT_FOLDER_FINAL)
	os.chdir(curr_dir)
	return

if __name__ == '__main__':
	_tests()