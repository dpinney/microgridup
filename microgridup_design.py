import os, json, shutil
import jinja2 as j2
import plotly.graph_objects as go
import pandas as pd
from omf.solvers.opendss import dssConvert
import microgridup
import microgridup_hosting_cap
from omf.solvers.REopt import REOPT_API_KEYS

MGU_FOLDER = os.path.abspath(os.path.dirname(__file__))
if MGU_FOLDER == '/':
	MGU_FOLDER = '' #workaround for docker root installs
PROJ_FOLDER = f'{MGU_FOLDER}/data/projects'

def run(MODEL_DIR, REOPT_FOLDER, microgrid, logger, REOPT_INPUTS, mg_name, lat, lon, existing_generation_dict, api_key, INVALIDATE_CACHE):
	'''
	Generate full microgrid design for given microgrid spec dictionary and circuit file (used to gather distribution assets) Generate the microgrid
	specs for REOpt. SIDE-EFFECTS: generates REOPT_FOLDER

	- MODEL_DIR: the outermost model directory
	- REOPT_FOLDER: a inner directory within the outermost model directory for running REopt on a particular microgrid
	- microgrid: a microgrid dict
	- logger: a logger instance
	- REOPT_INPUTS: arbitrarily set user input parameters
	- mg_name: the name of the microgrid
	- lat: latitude
	- lon: longitude
	- existing_generation_dict: a dict that contains generation information from the circuit
	- INVALIDATE_CACHE: whether to reuse existing REopt results
	'''
	assert isinstance(INVALIDATE_CACHE, bool)
	if os.path.isdir(REOPT_FOLDER) and INVALIDATE_CACHE == False:
		# - The cache is only for testing purposes
		print('**************************************************')
		print(f'** Using cached REopt results for {REOPT_FOLDER} **')
		print('**************************************************')
		logger.warning('**************************************************')
		logger.warning(f'** Using cached REopt results for {REOPT_FOLDER} **')
		logger.warning('**************************************************')
		return
	import omf.models
	shutil.rmtree(REOPT_FOLDER, ignore_errors=True)
	omf.models.microgridDesign.new(REOPT_FOLDER)
	set_allinputdata_load_shape_parameters(REOPT_FOLDER, f'loads.csv', microgrid, logger)
	set_allinputdata_outage_parameters(REOPT_FOLDER, f'{REOPT_FOLDER}/loadShape.csv', REOPT_INPUTS["outageDuration"])
	critical_load_percent = get_critical_load_percent(f'{REOPT_FOLDER}/loadShape.csv', microgrid, mg_name, logger)
	set_allinputdata_user_parameters(REOPT_FOLDER, REOPT_INPUTS, critical_load_percent, lat, lon, api_key)
	set_allinputdata_battery_parameters(REOPT_FOLDER, existing_generation_dict['battery_kw_existing'], existing_generation_dict['battery_kwh_existing'])
	set_allinputdata_solar_parameters(REOPT_FOLDER, existing_generation_dict['solar_kw_existing'])
	set_allinputdata_wind_parameters(REOPT_FOLDER, existing_generation_dict['wind_kw_existing'])
	set_allinputdata_generator_parameters(REOPT_FOLDER, existing_generation_dict['fossil_kw_existing'])
    # - Run REopt
	omf.models.__neoMetaModel__.runForeground(REOPT_FOLDER)
    # - Write output
	microgrid_design_output(f'{REOPT_FOLDER}/allOutputData.json', f'{REOPT_FOLDER}/allInputData.json', f'{REOPT_FOLDER}/cleanMicrogridDesign.html')

def set_allinputdata_load_shape_parameters(REOPT_FOLDER, load_csv_path, microgrid, logger):
	'''
	- Write loadShape.csv. loadShape.csv is different from loads.csv because loadShape.csv is the sum of load shapes of only the loads (both critical
	  and non-critical) in the microgrid
    - Set related parameters in allInputData.json
	'''
	# Get the microgrid total loads
	load_df = pd.read_csv(load_csv_path)
	mg_load_df = pd.DataFrame()
	loads = microgrid['loads']
	mg_load_df['load'] = [0 for x in range(8760)]
	for load_name in loads:
		try:
			mg_load_df['load'] = mg_load_df['load'] + load_df[load_name]
		except:
			print('ERROR: loads in Load Data (.csv) do not match loads in circuit.')
			logger.warning('ERROR: loads in Load Data (.csv) do not match loads in circuit.')
	mg_load_df.to_csv(REOPT_FOLDER + '/loadShape.csv', header=False, index=False)
	with open(REOPT_FOLDER + '/allInputData.json') as f:
		allInputData = json.load(f)
	with open(REOPT_FOLDER + '/loadShape.csv') as f:
		allInputData['loadShape'] = f.read()
	allInputData['fileName'] = 'loadShape.csv'
	with open(REOPT_FOLDER + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)

def set_allinputdata_outage_parameters(REOPT_FOLDER, loadshape_csv_path, outage_duration):
	with open(REOPT_FOLDER + '/allInputData.json') as f:
		allInputData = json.load(f)
	# Set the REopt outage to be centered around the max load in the loadshape
	mg_load_df = pd.read_csv(loadshape_csv_path)
	max_load_index = int(mg_load_df.idxmax())
	# reset the outage timing such that the length of REOPT_INPUTS falls half before and half after the hour of max load
	outage_duration = int(outage_duration)
	if max_load_index + outage_duration/2 > 8760:
		outage_start_hour = 8760 - outage_duration
		# REopt seems not to allow an outage on the last hour of the year
	elif max_load_index - outage_duration/2 < 1:
		outage_start_hour = 2
	else:
		outage_start_hour = max_load_index - outage_duration/2
	allInputData['outage_start_hour'] = str(int(outage_start_hour))
	with open(REOPT_FOLDER + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)

def get_critical_load_percent(loadshape_csv_path, microgrid, mg_name, logger):
	''' Set the critical load percent input for REopt by finding the ratio of max critical load kws to the max kw of the loadshape of that mg'''
	mg_load_df = pd.read_csv(loadshape_csv_path)
	max_load = float(mg_load_df.max())
	# add up all max kws from critical loads to support during an outage
	max_crit_load = sum(microgrid['critical_load_kws'])
	if max_crit_load > max_load:
		warning_message = f'The critical loads specified for microgrid {mg_name} are larger than the max kw of the total loadshape.\n'
		print(warning_message)
		logger.warn(warning_message)
		with open("user_warnings.txt", "a") as myfile:
			myfile.write(warning_message)
	critical_load_percent = max_crit_load/max_load
	if critical_load_percent > 2:
		print(f'This critical load percent of {critical_load_percent} is over 2.0, the maximum allowed. Setting critical load percent to 2.0.\n')
		logger.warn(f'This critical load percent of {critical_load_percent} is over 2.0, the maximum allowed. Setting critical load percent to 2.0.\n')
		critical_load_percent = 2.0
	return critical_load_percent

def set_allinputdata_user_parameters(REOPT_FOLDER, REOPT_INPUTS, critical_load_percent, lat, lon, api_key):
	with open(REOPT_FOLDER + '/allInputData.json') as f:
		allInputData = json.load(f)
	# Pulling user defined inputs from REOPT_INPUTS.
	for key in REOPT_INPUTS:
		allInputData[key] = REOPT_INPUTS[key]
	allInputData['criticalLoadFactor'] = str(critical_load_percent)
	allInputData['latitude'] = float(lat)
	allInputData['longitude'] = float(lon)
	allInputData['api_key'] = api_key
	with open(REOPT_FOLDER + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)

def set_allinputdata_battery_parameters(REOPT_FOLDER, battery_kw_existing, battery_kwh_existing):
	with open(REOPT_FOLDER + '/allInputData.json') as f:
		allInputData = json.load(f)
	# do not analyze existing batteries if multiple existing batteries exist
	if float(battery_kwh_existing) > 1:
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
	elif float(battery_kwh_existing) > 0:
		allInputData['batteryKwExisting'] = str(battery_kw_existing)
		allInputData['batteryPowerMin'] = str(battery_kw_existing)
		allInputData['batteryKwhExisting'] = str(battery_kwh_existing)
		allInputData['batteryCapacityMin'] = str(battery_kwh_existing)
		allInputData['battery'] = 'on'
	with open(REOPT_FOLDER + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)

def set_allinputdata_solar_parameters(REOPT_FOLDER, solar_kw_existing):
	with open(REOPT_FOLDER + '/allInputData.json') as f:
		allInputData = json.load(f)
	# enable following 2 lines when using gen_existing_ref_shapes()
	# force REopt to optimize on solar even if not recommended by REopt optimization
	if allInputData['solar'] == 'on':
		allInputData['solarMin'] = '1'
	if float(solar_kw_existing) > 0:
		allInputData['solarExisting'] = str(solar_kw_existing)
		allInputData['solar'] = 'on'
	# enable following 4 lines when using gen_existing_ref_shapes()
	# if not already turned on, set solar on to 1 kw to provide loadshapes for existing gen in make_full_dss()
	if allInputData['solar'] == 'off':
		allInputData['solar'] = 'on'
		allInputData['solarMax'] = '1'
		allInputData['solarMin'] = '1'
	with open(REOPT_FOLDER + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)

def set_allinputdata_wind_parameters(REOPT_FOLDER, wind_kw_existing):
	with open(REOPT_FOLDER + '/allInputData.json') as f:
		allInputData = json.load(f)
	# enable following 2 lines when using gen_existing_ref_shapes()
	# force REopt to optimize on wind even if not recommended by REopt optimization
	if allInputData['wind'] == 'on':
		allInputData['windMin'] = '1'
	if float(wind_kw_existing) > 0:
		allInputData['windExisting'] = str(wind_kw_existing)
		allInputData['windMin'] = str(wind_kw_existing)
		allInputData['wind'] = 'on' #failsafe to include wind if found in base_dss
	# enable following 4 lines when using gen_existing_ref_shapes()
	# if not already turned on, set wind on to 1 kw to provide loadshapes for existing gen in make_full_dss()
	if allInputData['wind'] == 'off':
		allInputData['wind'] = 'on'
		allInputData['windMax'] = '1'
		allInputData['windMin'] = '1'
	with open(REOPT_FOLDER + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)

def set_allinputdata_generator_parameters(REOPT_FOLDER, fossil_kw_existing):
	with open(REOPT_FOLDER + '/allInputData.json') as f:
		allInputData = json.load(f)
	allInputData['genExisting'] = str(fossil_kw_existing)
	fossil_status = allInputData['fossil']
	if fossil_status == 'off':
		allInputData['dieselMax'] = '0'
	with open(REOPT_FOLDER + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)

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
	}
	# Sometimes missing, so only add if available.
	if 'batteryData1' in allOutData and allOutData['batteryData1'] != '[]':
		plotlyData['Storage Charge Source'] = 'batteryData1'
	if 'batteryChargeData1' in allOutData:
		plotlyData['Storage State of Charge'] = 'batteryChargeData1'
	if 'resilienceData1' in allOutData:
		plotlyData['Resilience Overview'] = 'resilienceData1'
	if 'resilienceProbData1' in allOutData:
		plotlyData['Outage Survival Probability'] = 'resilienceProbData1'
	for k,v in plotlyData.items():
		chart_data = json.loads(allOutData[v])
		fig = go.Figure(chart_data)
		fig.update_layout(
			title = k,
			legend = legend_spec,
			font = dict(
				family="sans-serif",
				color="black"
			)
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
		legend = legend_spec,
		font = dict(
			family="sans-serif",
			color="black"
		)
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
		legend = legend_spec,
		font = dict(
			family="sans-serif",
			color="black"
		)
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
	logger = microgridup.setup_logging(f'{MGU_FOLDER}/logs.txt')
	print(f'----------Testing {_dir}----------')
	for run_count in range(len(microgrids)):
		dss_filename = 'circuit.dss' if run_count == 0 else f'circuit_plusmg_{run_count-1}.dss'
		existing_generation_dict = microgridup_hosting_cap.get_microgrid_existing_generation_dict(f'{MODEL_DIR}/{dss_filename}', microgrids[f'mg{run_count}'])
		lat, lon = microgridup_hosting_cap.get_microgrid_coordinates(f'{MODEL_DIR}/{dss_filename}', microgrids[f'mg{run_count}'])
		run(MODEL_DIR, f'reopt_final_{run_count}', microgrids[f'mg{run_count}'], logger, REOPT_INPUTS, f'mg{run_count}', lat, lon, existing_generation_dict, REOPT_API_KEYS[0], False)
	os.chdir(curr_dir)
	print('Ran all tests for microgridup_design.py.')

if __name__ == '__main__':
	_tests()