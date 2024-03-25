import os, json, shutil, statistics, logging
from pathlib import Path
from copy import deepcopy
import jinja2 as j2
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import microgridup
import microgridup_hosting_cap
from omf.models import microgridDesign, __neoMetaModel__
import omf.solvers.reopt_jl as reopt_jl
import concurrent.futures


MGU_FOLDER = os.path.abspath(os.path.dirname(__file__))
if MGU_FOLDER == '/':
	MGU_FOLDER = '' #workaround for docker root installs
PROJ_FOLDER = f'{MGU_FOLDER}/data/projects'


def run_reopt(microgrids, logger, reopt_inputs, invalidate_cache):
	'''
	:param microgrids: all of the microgrid definitions (as defined by microgrid_gen_mgs.py) for the given circuit
	:type microgrids: dict
	:param logger: a logger
	:type logger: logger
	:param reopt_inputs: REopt inputs that must be set by the user. All microgrids for a given circuit share these same REopt parameters.
	:type reopt_inputs: dict
	:param invalidate_cache: whether to ignore an existing directory of cached REopt results for all of the microgrids of a circuit
	:return: don't return anything. Instead, just read the corresponding allInputData.json and allOutputData.json file for each microgrid to build a
	    new DSS file in microgridup_hosting_cap.py
	:rtype: None
	'''
	assert isinstance(microgrids, dict)
	assert isinstance(logger, logging.Logger)
	assert isinstance(reopt_inputs, dict)
	assert isinstance(invalidate_cache, bool)
	create_production_factor_series_csv(microgrids, logger, reopt_inputs, invalidate_cache)
	# - Run REopt for each microgrid
	process_argument_lists = []
	for mg_name in microgrids.keys():
		microgrid = microgrids[mg_name]
		# - Apply microgrid parameter overrides
		mg_specific_reopt_inputs = deepcopy(reopt_inputs)
		for param, val in mg_specific_reopt_inputs['mgParameterOverrides'][mg_name].items():
			mg_specific_reopt_inputs[param] = str(val)
		del mg_specific_reopt_inputs['mgParameterOverrides']
		# - Generate a set of arguments for a single process
		existing_generation_dict = microgridup_hosting_cap.get_microgrid_existing_generation_dict('circuit.dss', microgrid)
		lat, lon = microgridup_hosting_cap.get_microgrid_coordinates('circuit.dss', microgrid)
		process_argument_lists.append([f'reopt_{mg_name}', microgrid, logger, mg_specific_reopt_inputs, mg_name, lat, lon, existing_generation_dict, invalidate_cache])
		# - Uncomment to run in single-process mode
		#run(f'reopt_{mg_name}', microgrid, logger, mg_specific_reopt_inputs, mg_name, lat, lon, existing_generation_dict, invalidate_cache)
	# - Uncomment to run in multiprocessing mode
	with concurrent.futures.ProcessPoolExecutor() as executor:
		future_list = []
		for process_argument_list in process_argument_lists:
			future_list.append(executor.submit(run, *process_argument_list))
		for f in concurrent.futures.as_completed(future_list):
			if f.exception() is not None:
				raise Exception(f'The REopt optimization for the microgrid {f.exception().filename.split("/")[0].split("_")[1]} failed because (1) the optimizer determined there was no feasible solution for the given inputs or (2) the solver could not complete within the user-defined maximum rum-time.')


def create_production_factor_series_csv(microgrids, logger, reopt_inputs, invalidate_cache):
	# - Do an initial REopt run to get "production_factor_series" vectors for solar and wind generators. Basically, situtations can occur where solar
	#   or wind generators are in a circuit, but are not included in a microgrid (or the microgrid that they are included in has no critical loads).
	#   If either of these situations occur, our inputs to REopt are configured such that no "PV" or "Wind" data will be present in the REopt output
	#   and as a result we won't be able to generate load shapes for those generators. To get around this issue, we just do an extra REopt run with
	#   solar and wind enabled and then actual microgrids can read the "production_factor_series" data as needed
	if not Path('production_factor_series.csv').exists() or invalidate_cache is True:
		microgridDesign.new('reopt_loadshapes')
		# - The load shape for production_factor_series.csv needs to be the same as for the microgrid(s) in order to use the same wind turbine size
		#   class. This is tricky because technically different microgrids could have sufficiently different load shapes such that one microgrid could
		#   use a smaller size class and another microgrid would use a larger size class, so which size class should production_factor_series.csv use?
		#   For now, we just use whatever size class mg0 uses and assume all microgrids have similar load profiles (and thus, similar size classes)
		#   - We could make use of multiprocessing if we had to for 4 simultaneous REopt runs
		set_allinputdata_load_shape_parameters('reopt_loadshapes', f'loads.csv', list(microgrids.values())[0], logger)
		with open('reopt_loadshapes/allInputData.json') as f:
			allInputData = json.load(f)
		allInputData['maxRuntimeSeconds'] = reopt_inputs['maxRuntimeSeconds']
		lat, lon = microgridup_hosting_cap.get_microgrid_coordinates('circuit.dss', list(microgrids.values())[0])
		# - The coordinates for production_factor_series.csv need to be the same as for the microgrid(s) in order to use the same historical REopt
		#   wind data
		allInputData['latitude'] = lat
		allInputData['longitude'] = lon
		# - We only care about the inputs to the model insofar as they (1) include solar and wind output and (2) the model completes as quickly as
		#   possible
		allInputData['solar'] = 'on'
		allInputData['wind'] = 'on'
		allInputData['battery'] = 'off'
		allInputData['fossil'] = 'off'
		with open('reopt_loadshapes/allInputData.json', 'w') as f:
			json.dump(allInputData, f, indent=4)
		__neoMetaModel__.runForeground('reopt_loadshapes')
		with open('reopt_loadshapes/results.json') as f:
			results = json.load(f)
		shutil.rmtree('reopt_loadshapes')
		production_factor_series_df = pd.DataFrame()
		production_factor_series_df['pv_production_factor_series'] = pd.Series(results['PV']['production_factor_series'])
		try:
			production_factor_series_df['wind_production_factor_series'] = pd.Series(results['Wind']['production_factor_series'])
		except:
			pass #on some platforms reopt_jl can't handle wind, and it's safe to skip this output.
		production_factor_series_df.to_csv('production_factor_series.csv', index=False)


def create_economic_microgrid(microgrids, logger, reopt_inputs, invalidate_cache):
	'''
	- Same parameters as run_reopt
	- Currently, we do NOT mutate the microgrids dict that contains the other real microgrids because we don't need to
	'''
	assert isinstance(microgrids, dict)
	assert isinstance(logger, logging.Logger)
	assert isinstance(reopt_inputs, dict)
	assert isinstance(invalidate_cache, bool)
	# - Add an extra "economic" microgrid to see if there's additional peak-shaving potential
	if not Path('reopt_mgEconomic').exists() or invalidate_cache is True:
		economic_microgrid = {
			'loads': [],
			'gen_obs_existing': [],
			'critical_load_kws': []
		}
		for mg in microgrids.values():
			economic_microgrid['loads'].extend(mg['loads'])
			economic_microgrid['switch'] = mg['switch']
			economic_microgrid['gen_bus'] = mg['gen_bus']
			economic_microgrid['gen_obs_existing'].extend(mg['gen_obs_existing'])
			economic_microgrid['critical_load_kws'].extend(mg['critical_load_kws'])
		microgridDesign.new('reopt_mgEconomic')
		load_df = pd.read_csv('loads.csv')
		load_df = load_df.iloc[:, load_df.apply(is_not_timeseries_column).to_list()]
		load_shape_series = load_df.apply(sum, axis=1)
		load_shape_series.to_csv('reopt_mgEconomic/loadShape.csv', header=False, index=False)
		# - Set user parameters
		lat, lon = microgridup_hosting_cap.get_microgrid_coordinates('circuit.dss', list(microgrids.values())[0])
		set_allinputdata_user_parameters('reopt_mgEconomic', reopt_inputs, lat, lon)
		# - Override certain user parameters
		with open('reopt_mgEconomic/allInputData.json') as f:
			allInputData = json.load(f)
		allInputData['battery'] = 'on'
		allInputData['solar'] = 'on'
		allInputData['wind'] = 'on'
		allInputData['fossil'] = 'on'
		# - The load shape and critical load shape are the same for the economic microgrid. Also, there's no outage
		allInputData['fileName'] = 'loadShape.csv'
		with open('reopt_mgEconomic/loadShape.csv') as f:
			load_shape_data = f.read()
		allInputData['loadShape'] = load_shape_data
		allInputData['criticalFileName'] = 'criticalLoadShape.csv'
		allInputData['criticalLoadShape'] = load_shape_data
		allInputData['maxRuntimeSeconds'] = reopt_inputs['maxRuntimeSeconds']
		# - Always set outage_start_hour to 0 because we don't want to run a REopt resilience analysis
		allInputData['outage_start_hour'] = '0'
		# - We do not apply the calculated maximum technology limits to the economic microgrid. That's the point. So set the limits to be the
		#   user-inputted limits
		allInputData['batteryCapacityMax'] = reopt_inputs['batteryCapacityMax']
		allInputData['batteryPowerMax'] = reopt_inputs['batteryPowerMax']
		allInputData['solarMax'] = reopt_inputs['solarMax']
		allInputData['windMax'] = reopt_inputs['windMax']
		allInputData['dieselMax'] = reopt_inputs['dieselMax']
		# - The existing solar, wind, fossil, and battery amounts of the economic microgrid are calculated by including the existing generation and
		#   storage of each actual microgrid, but not new recommended generation for any of the actual microgrids
		allInputData['batteryKwhExisting'] = 0
		allInputData['batteryKwExisting'] = 0
		allInputData['solarExisting'] = 0
		allInputData['windExisting'] = 0
		allInputData['genExisting'] = 0
		for mg_name in microgrids.keys():
			with open(f'reopt_{mg_name}/allInputData.json') as f:
				in_data = json.load(f)
			allInputData['batteryKwhExisting'] += float(in_data['batteryKwhExisting'])
			allInputData['batteryKwExisting'] += float(in_data['batteryKwExisting'])
			allInputData['solarExisting'] += float(in_data['solarExisting'])
			allInputData['windExisting'] += float(in_data['windExisting'])
			allInputData['genExisting'] += float(in_data['genExisting'])
		with open('reopt_mgEconomic/allInputData.json', 'w') as f:
			json.dump(allInputData, f, indent=4)
		__neoMetaModel__.runForeground('reopt_mgEconomic')
		microgrid_design_output('reopt_mgEconomic')


def run(REOPT_FOLDER, microgrid, logger, REOPT_INPUTS, mg_name, lat, lon, existing_generation_dict, INVALIDATE_CACHE):
	'''
	Generate full microgrid design for given microgrid spec dictionary and circuit file (used to gather distribution assets). Generate the microgrid
	specs for REOpt.

	:param REOPT_FOLDER: a directory within the outermost model directory for running REopt on a particular microgrid
	:type REOPT_FOLDER: str
	:param microgrid: a microgrid definition
	:type microgrid: dict
	:param logger: a logger instance
	:type logger: Logger
	:param REOPT_INPUTS: user-defined input parameters for REOPT
	:type REOPT_INPUTS: dict
	:param mg_name: the name of the microgrid
	:type mg_name: str
	:param lat: latitude
	:type lat: float
	:param lon: longitude
	:type lon: float
	:param existing_generation_dict: the existing generation in microgrid
	:type existing_generation_dict: dict
	:param INVALIDATE_CACHE: whether to reuse the existing REOPT results
	:type INVALIDATE_CACHCE: float
	:rtype: None
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
	set_allinputdata_outage_parameters(REOPT_FOLDER, f'{REOPT_FOLDER}/criticalLoadShape.csv', REOPT_INPUTS['outageDuration'])
	set_allinputdata_user_parameters(REOPT_FOLDER, REOPT_INPUTS, lat, lon)
	set_allinputdata_battery_parameters(REOPT_FOLDER, existing_generation_dict['battery_kw_existing'], existing_generation_dict['battery_kwh_existing'])
	set_allinputdata_solar_parameters(REOPT_FOLDER, existing_generation_dict['solar_kw_existing'])
	set_allinputdata_wind_parameters(REOPT_FOLDER, existing_generation_dict['wind_kw_existing'])
	set_allinputdata_generator_parameters(REOPT_FOLDER, existing_generation_dict['fossil_kw_existing'])
	# - Run REopt
	omf.models.__neoMetaModel__.runForeground(REOPT_FOLDER)
	# - Write output
	microgrid_design_output(REOPT_FOLDER)


def set_allinputdata_load_shape_parameters(REOPT_FOLDER, load_csv_path, microgrid, logger):
	'''
	- Write loadShape.csv. loadShape.csv contains a single column that is the sum of every load that is in loads.csv (i.e. it is the sum of all the
	  loads across entire installation)
		- Previously, loadShape.csv used to contain a single column that was only the sum of the loads (both critical and non-critical) in the given
		  microgrid
	- Set allInputData['loadShape'] equal to the contents of loadShape.csv
	- Set allInputData['criticalLoadShape'] equal to the sum of the columns in loads.csv that correspond to critical loads in the given microgrid
		- Previously, allInputData['criticalLoadFactor'] was used instead, but this parameter is no longer used
	'''
	load_df = pd.read_csv(load_csv_path)
	# - Remove any columns that contain hourly indicies instead of kW values
	load_df = load_df.iloc[:, load_df.apply(is_not_timeseries_column).to_list()]
	# - Write loadShape.csv
	load_shape_series = load_df.apply(sum, axis=1)
	load_shape_series.to_csv(REOPT_FOLDER + '/loadShape.csv', header=False, index=False)
	with open(REOPT_FOLDER + '/allInputData.json') as f:
		allInputData = json.load(f)
	allInputData['fileName'] = 'loadShape.csv'
	with open(REOPT_FOLDER + '/loadShape.csv') as f:
		allInputData['loadShape'] = f.read()
    # - Write criticalLoadshape.csv
	if len(microgrid['loads']) != len(microgrid['critical_load_kws']):
		raise Exception('The number of entries in microgrid["loads"] does not match the number of entries in microgrid["critical_load_kws"].')
	column_selection = []
	for tup in zip(microgrid['loads'], microgrid['critical_load_kws']):
		if float(tup[1]) > 0:
			column_selection.append(tup[0])
	# - /jsonToDss writes load names as they are to the DSS file, which is fine since OpenDSS is case-insensitive. However, our microgrid generation
	#   code always outputs microgrid load names in lowercase, so I have to convert the DataFrame column names to lowercase if I want to access data
	#   in the microgrid object without crashing due to a key error
	load_df.columns = [str(x).lower() for x in load_df.columns]
	critical_load_shape_series = load_df[column_selection].apply(sum, axis=1)
	critical_load_shape_series.to_csv(REOPT_FOLDER + '/criticalLoadShape.csv', header=False, index=False)
	with open(REOPT_FOLDER + '/criticalLoadShape.csv') as f:
		allInputData['criticalLoadShape'] = f.read()
	allInputData['criticalFileName'] = 'criticalLoadShape.csv'
	with open(REOPT_FOLDER + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)


def is_not_timeseries_column(series):
       '''
       - Given a series, return True if the sum of the series is not the sum of numbers 1 through 8760 or 0 through 8759, else False
       '''
       # - Triangular number formula
       timeseries_signature_1 = ((8760 ** 2 ) + 8760) / 2
       timeseries_signature_2 = ((8759 ** 2 ) + 8759) / 2
       s = np.sum(series)
       return s != timeseries_signature_1 and s != timeseries_signature_2


def set_allinputdata_outage_parameters(REOPT_FOLDER, critical_loadshape_csv_path, outage_duration):
	with open(REOPT_FOLDER + '/allInputData.json') as f:
		allInputData = json.load(f)
	# Set the REopt outage to be centered around the max load in the loadshape
	mg_load_series = pd.read_csv(critical_loadshape_csv_path, header=None)[0]
	max_load_index = int(mg_load_series.idxmax())
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


def set_allinputdata_user_parameters(REOPT_FOLDER, REOPT_INPUTS, lat, lon):
	'''
	- Set all of the REopt input parameters specified by the user
	- We used to use ["electric_load"]["critical_load_fraction"] to set ["electric_load"]["critical_loads_kw"], but we no longer do. Instead, we set
	  ["electric_load"]["critical_loads_kw"] directly
	- ["electric_load"]["critical_load_fraction"] is still set in microgridDesign.py, but the REopt output shows it isn't used when
	  ["electric_load"["critical_loads_kw"] is set directly, so it's fine
	'''
	with open(REOPT_FOLDER + '/allInputData.json') as f:
		allInputData = json.load(f)
	# Pulling user defined inputs from REOPT_INPUTS.
	for key in REOPT_INPUTS:
		allInputData[key] = REOPT_INPUTS[key]
	allInputData['latitude'] = float(lat)
	allInputData['longitude'] = float(lon)
	with open(REOPT_FOLDER + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)


def set_allinputdata_battery_parameters(REOPT_FOLDER, battery_kw_existing, battery_kwh_existing):
	'''
	- If new batteries are enabled, set ['ElectricStorage']['max_kwh'] equal to the lesser of (1) the total kWh consumed during the outage window or
	  (2) the user-defined maximum kWh
    - If new batteries are not enabled, and there are existing batteries, set ['ElectricStorage']['max_kwh'] equal to the amount of existing battery
      capacity and set ['ElectricStorage']['max_kw'] equal to the amount of existing battery power. If there are not existing batteries, set
      ['ElectricStorage']['max_kwh'] equal to 0 and ['ElectricStorage']['max_kw'] equal to 0

	'''
    # - How do we want to handle existing vs new batteries?
    #   - There are existing batteries and new batteries are enabled
	#       - Old approach: Pretend the existing batteries don't exist by setting existing kWh and kW to 0
    #       - New approach: ???
    #   - There are no existing batteries and new batteries are enabled
    #       - No problem
    #   - There are existing batteries are new batteries are not enabled
	#       - Set the max kWh and kW REopt parameters to the existing kWh and kW values in the circuit
    #   - There are no existing batteries and new batteries are not enabled
    #       - No problem
	with open(REOPT_FOLDER + '/allInputData.json') as f:
		allInputData = json.load(f)
	allInputData['batteryKwhExisting'] = str(battery_kwh_existing)
	allInputData['batteryKwExisting'] = str(battery_kw_existing)
	if allInputData['battery'] == 'on':
		critical_load_series = pd.read_csv(REOPT_FOLDER + '/criticalLoadShape.csv', header=None)[0]
		outage_start_hour = int(allInputData['outage_start_hour'])
		outage_duration = int(allInputData['outageDuration'])
		calculated_max_kwh = critical_load_series[outage_start_hour:outage_start_hour + outage_duration].sum()
		if calculated_max_kwh < float(allInputData['batteryCapacityMax']):
			allInputData['batteryCapacityMax'] = str(calculated_max_kwh)
		# - allInputData['batteryPowerMax'] is set in set_allinputdata_user_parameters()
	else:
		allInputData['batteryCapacityMax'] = str(battery_kwh_existing)
		allInputData['batteryPowerMax'] = str(battery_kw_existing)
	# - allInputData['batteryCapacityMin'] is set in set_allinputdata_user_parameters()
	# - allInputData['batteryPowerMin'] is set in set_allinputdata_user_parameters()
	with open(REOPT_FOLDER + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)


def set_allinputdata_solar_parameters(REOPT_FOLDER, solar_kw_existing):
	'''
	- If new solar is enabled, set ['PV']['max_kw'] equal to the lesser of (1) the maximum value in the critical load shape series multiplied by 4 or
	  (2) the user-defined maximum value
	- If new solar is not enabled, set ['PV']['max_kw'] equal to 0
	- Always set ['PV']['existing_kw'] equal to the amount of existing solar that exists in the circuit. REopt will include existing solar generation
	  in its calculation regardless of whether new solar generation is enabled
	- ['PV']['min_kw'] is set by the user (defaults to 0)
	'''
	with open(REOPT_FOLDER + '/allInputData.json') as f:
		allInputData = json.load(f)
	allInputData['solarExisting'] = str(solar_kw_existing)
	if allInputData['solar'] == 'on':
		critical_load_series = pd.read_csv(REOPT_FOLDER + '/criticalLoadShape.csv', header=None)[0]
		calculated_max_kw = critical_load_series.max() * 4
		if calculated_max_kw < float(allInputData['solarMax']):
			allInputData['solarMax'] = str(calculated_max_kw)
	else:
		allInputData['solarMax'] = '0'
	with open(REOPT_FOLDER + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)


def set_allinputdata_wind_parameters(REOPT_FOLDER, wind_kw_existing):
	'''
	- If new wind is enabled, set ['Wind']['max_kw'] equal to the lesser of (1) the maximum value in the critical load shape series multiplied by 2 or
	  (2) the user-defined maximum value
	- If new wind is not enabled, and there is existing wind, set ['Wind']['max_kw'] equal to the amount of existing wind
	- ['Wind']['min_kw'] is set by the user (defaults to 0)
	'''
	with open(REOPT_FOLDER + '/allInputData.json') as f:
		allInputData = json.load(f)
	# - allInputData['windExisting'] is only used by microgridUP, not REopt
	allInputData['windExisting'] = str(wind_kw_existing)
	critical_load_series = pd.read_csv(REOPT_FOLDER + '/criticalLoadShape.csv', header=None)[0]
	calculated_max_kw = critical_load_series.max() * 2
	if allInputData['wind'] == 'on':
		if calculated_max_kw < float(allInputData['windMax']):
			allInputData['windMax'] = str(calculated_max_kw)
	else:
		allInputData['windMax'] = str(wind_kw_existing)
	with open(REOPT_FOLDER + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)


def set_allinputdata_generator_parameters(REOPT_FOLDER, fossil_kw_existing):
	'''
	- If new fossil generators are enabled, set ['Generator']['max_kw'] equal to the lesser of (1) the maximum value in the critical load shape series
	  or (2) the user-defined maximum value
    - If new fossil generators are not enabled, set ['Generator']['max_kw'] to 0
    - Always set ['Generator']['existing_kw'] equal to the amount of existing fossil generation that exists in the circuit. REopt will include
      existing fossil generation in its calculation regardless of whether new fossil generation is enabled
    - ['Generator']['min_kw'] is set by the user (defaults to 0)
	'''
	with open(REOPT_FOLDER + '/allInputData.json') as f:
		allInputData = json.load(f)
	allInputData['genExisting'] = str(fossil_kw_existing)
	if allInputData['fossil'] == 'on':
		critical_load_series = pd.read_csv(REOPT_FOLDER + '/criticalLoadShape.csv', header=None)[0]
		calculated_max_kw = critical_load_series.max()
		if calculated_max_kw < float(allInputData['dieselMax']):
			allInputData['dieselMax'] = str(calculated_max_kw)
	else:
		allInputData['dieselMax'] = '0'
	with open(REOPT_FOLDER + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)


def microgrid_design_output(reopt_folder):
	''' Generate a clean microgridDesign output with edge-to-edge design. '''
	all_html = ''
	legend_spec = {'orientation':'h', 'xanchor':'left'}#, 'x':0, 'y':-0.2}
	with open(f'{reopt_folder}/allOutputData.json') as file:
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
		plotlyData['Resilience Overview - Longest Outage Survived'] = 'resilienceData1'
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
				color="black"))
		if k == 'Resilience Overview - Longest Outage Survived':
			min_ = min(chart_data[0]['y'])
			max_ = max(chart_data[0]['y'])
			mean = statistics.mean(chart_data[0]['y'])
			stdev = statistics.stdev(chart_data[0]['y'])
			stat_y_spacing = [(max_ * 1.25) - (i * (((max_ * 1.25) - max_) / 6)) for i in range(1, 6)]
			fig.add_annotation(x=8500, y=(max_ * 1.25), text=f'Min hours: {format(min_, ".3f")}', showarrow=False, xanchor="right")
			fig.add_annotation(x=8500, y=stat_y_spacing[0], text=f'Max hours: {format(max_, ".3f")}', showarrow=False, xanchor="right")
			fig.add_annotation(x=8500, y=stat_y_spacing[1], text=f'Mean hours: {format(mean, ".3f")}', showarrow=False, xanchor="right")
			fig.add_annotation(x=8500, y=stat_y_spacing[2], text=f'Mean + 1σ hours: {format(mean + stdev, ".3f")}', showarrow=False, xanchor="right")
			fig.add_annotation(x=8500, y=stat_y_spacing[3], text=f'Mean + 2σ hours: {format(mean + (2 * stdev), ".3f")}', showarrow=False, xanchor="right")
			fig.add_annotation(x=8500, y=stat_y_spacing[4], text=f'Mean + 3σ hours: {format(mean + (3 * stdev), ".3f")}', showarrow=False, xanchor="right")
			fig.update_xaxes(title_text='Hour of year when outage starts')
			fig.update_yaxes(title_text='Hours')
		if k == 'Outage Survival Probability':
			fig.update_xaxes(title_text='Length of outage (hours)')
			fig.update_yaxes(title_text='Probability')
		if k == 'Generation Serving Load':
			fig.update_yaxes(title_text='kW')
		if k == 'Solar Generation Detail':
			fig.update_yaxes(title_text='kW')
		if k == 'Wind Generation Detail':
			fig.update_yaxes(title_text='kW')
		if k == 'Fossil Generation Detail':
			fig.update_yaxes(title_text='kW')
		if k == 'Storage Charge Source':
			fig.update_yaxes(title_text='kW')
		fig.update_yaxes(rangemode="tozero")
		fig_html = fig.to_html(default_height='600px')
		all_html = all_html + fig_html
	# Make generation overview chart
	with open(f'{reopt_folder}/allInputData.json') as f:
		all_input_data = json.load(f)
	with open(f'{reopt_folder}/results.json') as f:
		results = json.load(f)
	df = pd.DataFrame({
		'Solar kW': [all_input_data['solarExisting'], 0, all_input_data['solarExisting'], 0, 0],
		'Wind kW': [all_input_data['windExisting'], 0, all_input_data['windExisting'], 0, 0],
		'Storage kW': [all_input_data['batteryKwExisting'], 0, all_input_data['batteryKwExisting'], 0, 0],
		'Storage kWh': [all_input_data['batteryKwhExisting'], 0, all_input_data['batteryKwhExisting'], 0, 0],
		'Fossil kW': [all_input_data['genExisting'], 0, all_input_data['genExisting'], 0, 0],
		'Critical Load kW': [0, 0, 0, int(statistics.mean(results['ElectricLoad']['critical_load_series_kw'])), int(max(results['ElectricLoad']['critical_load_series_kw']))]
	}, index=['Existing', 'New', 'Total', 'Average', 'Peak'], dtype=np.float64)
	if 'sizePV1' in allOutData:
		df.loc['Total', 'Solar kW'] = int(allOutData['sizePV1'])
		df.loc['New', 'Solar kW'] = int(allOutData['sizePV1'] - float(all_input_data['solarExisting']))
	if 'sizeWind1' in allOutData:
		df.loc['Total', 'Wind kW'] = int(allOutData['sizeWind1'])
		df.loc['New', 'Wind kW'] = int(allOutData['sizeWind1'] - float(all_input_data['windExisting']))
	if 'powerBattery1' in allOutData:
		df.loc['Total', 'Storage kW'] = int(allOutData['powerBattery1'])
		df.loc['New', 'Storage kW'] = int(allOutData['powerBattery1'] - float(all_input_data['batteryKwExisting']))
	if 'capacityBattery1' in allOutData:
		df.loc['Total', 'Storage kWh'] = int(allOutData['capacityBattery1'])
		df.loc['New', 'Storage kWh'] = int(allOutData['capacityBattery1'] - float(all_input_data['batteryKwhExisting']))
	if 'sizeDiesel1' in allOutData:
		df.loc['Total', 'Fossil kW'] = int(allOutData['sizeDiesel1'])
		df.loc['New', 'Fossil kW'] = int(allOutData['sizeDiesel1'] - float(all_input_data['genExisting']))
	generation_fig = go.Figure(data=[
		go.Bar(name='Existing Generation (kW)', x=df.columns.to_series(), y=df.loc['Existing']),
		go.Bar(name='New Generation (kW)', x=df.columns.to_series(), y=df.loc['New']),
		go.Bar(name='Total Generation (kW)', x=df.columns.to_series(), y=df.loc['Total']),
		go.Bar(name='Average Critical Load (kW)', x=df.columns.to_series(), y=df.loc['Average']),
		go.Bar(name='Peak Critical Load (kW)', x=df.columns.to_series(), y=df.loc['Peak']),
	])
	generation_fig.update_layout(
		title='Generation Overview',
		font=dict(family="sans-serif",
		color="black"),
		xaxis_title='Generation Type',
		yaxis_title='kW',
		legend=dict(orientation='h'))
	max_ = df.max().max()
	if 'fuelUsedDieselRounded1' in allOutData:
		generation_fig.add_annotation(x=4, y=(max_ * 1.2), text=f'Fossil Fuel Used in Outage (kGal Diesel Equiv.): {allOutData["fuelUsedDieselRounded1"] / 1000.0}', showarrow=False, xanchor="left")
	generation_fig_html = generation_fig.to_html(default_height='600px')
	all_html = generation_fig_html + all_html
	# Make financial overview chart
	fin_data_bau = {
		'Demand Cost ($)':allOutData["demandCostBAU1"],
		'Energy Cost ($)':allOutData["energyCostBAU1"],
		'Total Cost ($)':allOutData["totalCostBAU1"]}
	fin_data_microgrid = {
		'Demand Cost ($)':allOutData["demandCost1"],
		'Energy Cost ($)':allOutData["energyCost1"],
		'Total Cost ($)':allOutData["totalCost1"]}
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
	with open(f'{reopt_folder}/allInputData.json') as inFile:
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
	with open(f'{reopt_folder}/cleanMicrogridDesign.html', 'w') as outFile:
		outFile.write(mgd)


def _tests():
	# - Asssert that REopt's own tests pass
	reopt_jl._test()
	# - Load lehigh1mg to use as test input
	with open('testfiles/test_params.json') as file:
		test_params = json.load(file)
	REOPT_INPUTS = test_params['REOPT_INPUTS']
	control_test_args = test_params['control_test_args']
	_dir = 'lehigh1mg'
	microgrids = control_test_args[_dir]
	MODEL_DIR = f'{PROJ_FOLDER}/{_dir}'
	# HACK: work in directory because we're very picky about the current dir.
	curr_dir = os.getcwd()
	workDir = os.path.abspath(MODEL_DIR)
	if curr_dir != workDir:
		os.chdir(workDir)
	logger = microgridup.setup_logging(f'{MGU_FOLDER}/logs.txt')
	print(f'----------Testing {_dir}----------')
	for run_count in range(len(microgrids)):
		microgrid = microgrids[f'mg{run_count}']
		existing_generation_dict = microgridup_hosting_cap.get_microgrid_existing_generation_dict(f'{MODEL_DIR}/circuit.dss', microgrid)
		lat, lon = microgridup_hosting_cap.get_microgrid_coordinates(f'{MODEL_DIR}/circuit.dss', microgrid)
		run(f'reopt_mg{run_count}', microgrid, logger, REOPT_INPUTS, f'mg{run_count}', lat, lon, existing_generation_dict, True)
		# - Assert that we got valid output from REopt
		with open(f'reopt_mg{run_count}/REoptInputs.json') as f:
			inputs = json.load(f)
		with open(f'reopt_mg{run_count}/results.json') as f:
			results = json.load(f)
		# - Assert that the input load shape matches the output load shape
		assert inputs['s']['electric_load']['loads_kw'] == results['ElectricLoad']['load_series_kw']
		# - Assert that the optimal solar size is within 5% of an expected value
		assert abs(1 - results['PV']['size_kw']/4534.8271) < 0.05
		# - Assert that the optimal generator size is within 5% of an expected value
		assert abs(1 - results['Generator']['size_kw']/1391.77) < 0.05
		# - Assert that the optimal storage size is within 5% of an expected value
		assert abs(1 - results['ElectricStorage']['size_kw']/564.55) < 0.05
		assert abs(1 - results['ElectricStorage']['size_kwh']/1397.13) < 0.05
		# - Assert that the optimal lifecycle cost is within 5% of an expected value
		assert abs(1 - results['Financial']['lcc']/1.73823260427e7) < 0.05
	os.chdir(curr_dir)
	print('Ran all tests for microgridup_design.py.')

if __name__ == '__main__':
	_tests()