import os, json, shutil, statistics, logging
from types import MappingProxyType
from pathlib import Path
import jinja2 as j2
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import microgridup
import microgridup_hosting_cap
from omf.models import microgridDesign, __neoMetaModel__
import omf.solvers.reopt_jl as reopt_jl
import concurrent.futures


def run_reopt(data, logger, invalidate_cache):
	'''
	:param data: all of the data for a model containing the following relevant keys
		MICROGRIDS: a dict of the microgrid definitions (as defined by microgrid_gen_mgs.py) for the given circuit
		REOPT_INPUTS: a dict of REopt inputs that must be set by the user. All microgrids for a given circuit share these same REopt parameters
	:type data: dict
		In multiprocessing mode, the data must be transformed back into a dict so it can be pickeled because MappingProxyType objects cannot be
		pickled
	:param logger: a logger
	:type logger: logger
	:param invalidate_cache: whether to ignore an existing directory of cached REopt results for all of the microgrids of a circuit
	:return: don't return anything. Later on, read the corresponding allInputData.json and allOutputData.json file for each microgrid to build a new
		DSS file in microgridup_hosting_cap.py
	:rtype: None
	'''
	assert isinstance(data, dict)
	assert 'MICROGRIDS' in data
	assert 'REOPT_INPUTS' in data
	assert isinstance(logger, logging.Logger)
	assert isinstance(invalidate_cache, bool)
	# - immutable_data is only used as a precaution in single-processing mode
	immutable_data = microgridup.get_immutable_dict(data)
	_create_production_factor_series_csv(immutable_data, logger, invalidate_cache)
	# - Run REopt for each microgrid
	process_argument_lists = []
	for mg_name in data['MICROGRIDS']:
		process_argument_lists.append([data, mg_name, logger, invalidate_cache])
		# - Uncomment to run in single-process mode
		#_run(immutable_data, mg_name, logger, invalidate_cache)
	# - Uncomment to run in multiprocessing mode
	with concurrent.futures.ProcessPoolExecutor() as executor:
		future_list = []
		for process_argument_list in process_argument_lists:
			future_list.append(executor.submit(_multiprocessing_run, *process_argument_list))
		for f in concurrent.futures.as_completed(future_list):
			if f.exception() is not None:
				try:
					microgrid_name = f.exception().filename.split("/")[0].split("_")[1]
				except AttributeError:
					microgrid_name = 'Unknown'
				raise Exception(f'The REopt optimization for the microgrid {microgrid_name} failed because (1) the optimizer determined there was no feasible solution for the given inputs or (2) the solver could not complete within the user-defined maximum run-time.')


def create_economic_microgrid(data, logger, invalidate_cache):
	'''
	Simulate an extra "economic" microgrid to see if there's additional peak-shaving potential

	:param data: all of the data for a model containing the following relevant keys
		MICROGRIDS: a dict of the microgrid definitions (as defined by microgrid_gen_mgs.py) for the given circuit
		REOPT_INPUTS: a dict of REopt inputs that must be set by the user. All microgrids for a given circuit share these same REopt parameters
	:type data: MappingProxyType (an immutable dict)
	:param logger: a logger
	:type logger: logger
	:param invalidate_cache: whether to ignore an existing directory of cached REopt results for all of the microgrids of a circuit
	:return: don't return anything. Later on, read the corresponding allInputData.json and allOutputData.json file for each microgrid to build a new
		DSS file in microgridup_hosting_cap.py
	:rtype: None
	'''
	assert isinstance(data, MappingProxyType)
	assert isinstance(logger, logging.Logger)
	assert isinstance(invalidate_cache, bool)
	if not Path('reopt_mgEconomic').exists() or invalidate_cache:
		economic_microgrid = {
			'loads': [],
			'gen_obs_existing': [],
		}
		for mg in data['MICROGRIDS'].values():
			economic_microgrid['loads'].extend(mg['loads'])
			economic_microgrid['switch'] = mg['switch']
			economic_microgrid['gen_bus'] = mg['gen_bus']
			economic_microgrid['gen_obs_existing'].extend(mg['gen_obs_existing'])
		microgridDesign.new('reopt_mgEconomic')
		load_df = pd.read_csv('loads.csv')
		load_df = load_df.iloc[:, load_df.apply(is_not_timeseries_column).to_list()]
		load_shape_series = load_df.apply(sum, axis=1)
		load_shape_series.to_csv('reopt_mgEconomic/loadShape.csv', header=False, index=False)
		# - Set user parameters
		lat, lon = microgridup_hosting_cap.get_microgrid_coordinates(list(data['MICROGRIDS'].values())[0])
		_set_allinputdata_user_parameters('reopt_mgEconomic', dict(data['REOPT_INPUTS']), lat, lon)
		# - Override certain user parameters
		with open('reopt_mgEconomic/allInputData.json') as f:
			allInputData = json.load(f)
		allInputData['battery'] = True
		allInputData['solar'] = True
		allInputData['wind'] = True
		allInputData['fossil'] = True
		# - The load shape and critical load shape are the same for the economic microgrid. Also, there's no outage
		allInputData['fileName'] = 'loadShape.csv'
		with open('reopt_mgEconomic/loadShape.csv') as f:
			load_shape_data = f.read()
		allInputData['loadShape'] = load_shape_data
		allInputData['criticalFileName'] = 'criticalLoadShape.csv'
		allInputData['criticalLoadShape'] = load_shape_data
		allInputData['maxRuntimeSeconds'] = data['REOPT_INPUTS']['maxRuntimeSeconds']
		# - Always set outage_start_hour to 0 because we don't want to run a REopt resilience analysis
		allInputData['outage_start_hour'] = 0
		# - We do not apply the calculated maximum technology limits to the economic microgrid. That's the point. So set the limits to be the
		#   user-inputted limits
		allInputData['batteryCapacityMax'] = data['REOPT_INPUTS']['batteryCapacityMax']
		allInputData['batteryPowerMax'] = data['REOPT_INPUTS']['batteryPowerMax']
		allInputData['solarMax'] = data['REOPT_INPUTS']['solarMax']
		allInputData['windMax'] = data['REOPT_INPUTS']['windMax']
		allInputData['dieselMax'] = data['REOPT_INPUTS']['dieselMax']
		# - The existing solar, wind, fossil, and battery amounts of the economic microgrid are calculated by including the existing generation and
		#   storage of each actual microgrid, but not new recommended generation for any of the actual microgrids
		allInputData['batteryKwhExisting'] = 0
		allInputData['batteryKwExisting'] = 0
		allInputData['solarExisting'] = 0
		allInputData['windExisting'] = 0
		allInputData['genExisting'] = 0
		for mg_name in data['MICROGRIDS'].keys():
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
		_microgrid_design_output('reopt_mgEconomic')


def is_not_timeseries_column(series):
       '''
       - Given a series, return True if the sum of the series is not the sum of numbers 1 through 8760 or 0 through 8759, else False
       '''
       # - Triangular number formula
       timeseries_signature_1 = ((8760 ** 2 ) + 8760) / 2
       timeseries_signature_2 = ((8759 ** 2 ) + 8759) / 2
       s = np.sum(series)
       return s != timeseries_signature_1 and s != timeseries_signature_2


def _multiprocessing_run(data, mg_name, logger, invalidate_cache):
	'''
	This function calls _run() with the expected argument types
	'''
	immutable_data = microgridup.get_immutable_dict(data)
	_run(immutable_data, mg_name, logger, invalidate_cache)


def _run(data, mg_name, logger, invalidate_cache):
	'''
	Generate full microgrid design for given microgrid spec dictionary and circuit file (used to gather distribution assets). Generate the microgrid
	specs for REOpt.

	:param data: the data
	:type data: MappingProxyType (an immutable dict)
	:param mg_name: the name of the microgrid
	:type mg_name: str
	:param logger: a logger
	:type logger: Logger
	:rtype: None
	'''
	assert isinstance(data, MappingProxyType)
	assert 'MICROGRIDS' in data
	assert isinstance(mg_name, str)
	assert isinstance(logger, logging.Logger)
	assert isinstance(invalidate_cache, bool)
	logger = microgridup.setup_logging('logs.log', mg_name)
	# - Our convention for reopt folder names could change, so keep this variable even though it's effectively a constant right now
	reopt_dirname = f'reopt_{mg_name}'
	if os.path.isdir(reopt_dirname) and not invalidate_cache:
		# - The cache is only for testing purposes
		print('**************************************************')
		print(f'** Using cached REopt results for {reopt_dirname} **')
		print('**************************************************')
		logger.warning('**************************************************')
		logger.warning(f'** Using cached REopt results for {reopt_dirname} **')
		logger.warning('**************************************************')
		return
	import omf.models
	shutil.rmtree(reopt_dirname, ignore_errors=True)
	omf.models.microgridDesign.new(reopt_dirname)
	_set_allinputdata_load_shape_parameters(data, mg_name, reopt_dirname, logger)
	mg_specific_reopt_inputs = _get_mg_specific_reopt_inputs(data, mg_name)
	_set_allinputdata_outage_parameters(reopt_dirname, mg_specific_reopt_inputs['outageDuration'])
	lat, lon = microgridup_hosting_cap.get_microgrid_coordinates(data['MICROGRIDS'][mg_name])
	_set_allinputdata_user_parameters(reopt_dirname, mg_specific_reopt_inputs, lat, lon)
	existing_generation_dict = microgridup_hosting_cap.get_microgrid_existing_generation_dict(data['MICROGRIDS'][mg_name])
	_set_allinputdata_battery_parameters(reopt_dirname, existing_generation_dict['battery_kw_existing'], existing_generation_dict['battery_kwh_existing'])
	_set_allinputdata_solar_parameters(reopt_dirname, existing_generation_dict['solar_kw_existing'])
	_set_allinputdata_wind_parameters(reopt_dirname, existing_generation_dict['wind_kw_existing'])
	_set_allinputdata_generator_parameters(reopt_dirname, existing_generation_dict['fossil_kw_existing'])
	# - Run REopt
	omf.models.__neoMetaModel__.runForeground(reopt_dirname)
	# - Write output
	_microgrid_design_output(reopt_dirname)


def _set_allinputdata_load_shape_parameters(data, mg_name, reopt_dirname, logger):
	'''
	- Write loadShape.csv. loadShape.csv contains a single column that is the sum of every load that is in loads.csv (i.e. it is the sum of all the
	  loads across entire installation)
		- Previously, loadShape.csv used to contain a single column that was only the sum of the loads (both critical and non-critical) in the given
		  microgrid
	- Set allInputData['loadShape'] equal to the contents of loadShape.csv
	- Set allInputData['criticalLoadShape'] equal to the sum of the columns in loads.csv that correspond to critical loads in the given microgrid
		- Previously, allInputData['criticalLoadFactor'] was used instead, but this parameter is no longer used

	:param data: the data
	:type data: MappingProxyType (an immutable dict)
	:param mg_name: the name of a microgrid
	:type mg_name: str
	:param reopt_dirname: a directory name within which to do a run of omf.models.microgridDesign
    :type reopt_dirname: str
    :param logger: a logger
	:type logger: Logger
	:rtype: None
	'''
	assert isinstance(data, MappingProxyType)
	assert isinstance(mg_name, str)
	assert isinstance(reopt_dirname, str)
	assert isinstance(logger, logging.Logger)
	load_df = pd.read_csv('loads.csv')
	# - Remove any columns that contain hourly indicies instead of kW values
	load_df = load_df.iloc[:, load_df.apply(is_not_timeseries_column).to_list()]
	# - Write loadShape.csv
	load_shape_series = load_df.apply(sum, axis=1)
	load_shape_series.to_csv(reopt_dirname + '/loadShape.csv', header=False, index=False)
	# - <reopt_dirname>/allInputData.json was already created by microgridDesign.new, so read it
	with open(reopt_dirname + '/allInputData.json') as f:
		allInputData = json.load(f)
	allInputData['fileName'] = 'loadShape.csv'
	with open(reopt_dirname + '/loadShape.csv') as f:
		allInputData['loadShape'] = f.read()
	# - Write criticalLoadshape.csv
	column_selection = []
	for load_name in data['MICROGRIDS'][mg_name]['loads']:
		if load_name in data['CRITICAL_LOADS']:
			column_selection.append(load_name)
	# - /jsonToDss writes load names as they are to the DSS file, which is fine since OpenDSS is case-insensitive. However, our microgrid generation
	#   code always outputs microgrid load names in lowercase, so I have to convert the DataFrame column names to lowercase if I want to access data
	#   in the microgrid object without crashing due to a key error
	load_df.columns = [str(x).lower() for x in load_df.columns]
	critical_load_shape_series = load_df[column_selection].apply(sum, axis=1)
	critical_load_shape_series.to_csv(reopt_dirname + '/criticalLoadShape.csv', header=False, index=False)
	with open(reopt_dirname + '/criticalLoadShape.csv') as f:
		allInputData['criticalLoadShape'] = f.read()
	allInputData['criticalFileName'] = 'criticalLoadShape.csv'
	with open(reopt_dirname + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)


def _set_allinputdata_outage_parameters(reopt_dirname, outage_duration):
	'''
	Set allInputData['outage_start_hour'] which is relevant for microgridDesign.py

	:param reopt_dirname: the REopt folder
    :type reopt_dirname: str
    :param outage_duration: the length of the outage
	:type outage_duration: int
    :rtype: None
	'''
	assert isinstance(reopt_dirname, str)
	assert isinstance(outage_duration, int)
	with open(reopt_dirname + '/allInputData.json') as f:
		allInputData = json.load(f)
	# - Set the REopt outage to be centered around the max load in the loadshape
	mg_load_series = pd.read_csv(f'{reopt_dirname}/criticalLoadShape.csv', header=None)[0]
	max_load_index = int(mg_load_series.idxmax())
	# - Set the outage timing such that half of the outage occurs before the hour of the max load and half of the outage occurs after the hour of the
	#   max load
	if max_load_index + outage_duration/2 > 8760:
		# - REopt seems not to allow an outage DURING the last hour of the year
		#   - E.g. 8760 - 48 = 8712. ["outage_start_time_step"] = 8712 and ["outage_end_time_step"] = 8760, so the outage will start at the beginning
		#     of hour 8712 and finish at the beginning of hour 8760
		outage_start_hour = 8760 - outage_duration
	elif max_load_index - outage_duration/2 < 1:
		# - Idk why this is 2 and not 1 but it probably doesn't make a huge difference
		outage_start_hour = 2
	else:
		outage_start_hour = max_load_index - outage_duration/2
	allInputData['outage_start_hour'] = outage_start_hour
	with open(reopt_dirname + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)


def _set_allinputdata_user_parameters(reopt_dirname, mg_specific_reopt_inputs, lat, lon):
	'''
	- We used to use ["electric_load"]["critical_load_fraction"] to set ["electric_load"]["critical_loads_kw"], but we no longer do. Instead, we set
	  ["electric_load"]["critical_loads_kw"] directly
	- ["electric_load"]["critical_load_fraction"] is still set in microgridDesign.py, but the REopt output shows it isn't used when
	  ["electric_load"]["critical_loads_kw"] is set directly, so it's fine

	:param reopt_dirname: the REopt folder
	:type reopt_dirname: str
	:param mg_specific_reopt_inputs: the mg-specific REopt inputs specified by the user that are relevant for microgridDesign.py
	:type mg_specific_reopt_inputs: str
	:param lat: latitude
	:type lat: float
	:param lon: longitude
	:type lon: float
	:rtype: None
	'''
	assert isinstance(reopt_dirname, str)
	assert isinstance(mg_specific_reopt_inputs, dict)
	assert isinstance(lat, float)
	assert isinstance(lon, float)
	with open(reopt_dirname + '/allInputData.json') as f:
		allInputData = json.load(f)
	for k, v in mg_specific_reopt_inputs.items():
		allInputData[k] = v
	allInputData['latitude'] = lat
	allInputData['longitude'] = lon
	with open(reopt_dirname + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)


def _set_allinputdata_battery_parameters(reopt_dirname, battery_kw_existing, battery_kwh_existing):
	'''
	- If new batteries are enabled, set ['ElectricStorage']['max_kwh'] equal to the lesser of (1) the total kWh consumed during the outage window or
	  (2) the user-defined maximum kWh
	- If new batteries are not enabled, and there are existing batteries, set ['ElectricStorage']['max_kwh'] equal to the amount of existing battery
	  capacity and set ['ElectricStorage']['max_kw'] equal to the amount of existing battery power. If there are not existing batteries, set
	  ['ElectricStorage']['max_kwh'] equal to 0 and ['ElectricStorage']['max_kw'] equal to 0

	:param reopt_dirname; the REopt folder
	:type reopt_dirname: str
	:param battery_kw_existing: the amount of battery kW before REopt
	:type battery_kw_existing: float
	:param battery_kwh_existing: the amount of battery kWh before REopt
	:type battery_kwh_existing: float
	:rtype: None
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
	assert isinstance(reopt_dirname, str)
	assert isinstance(battery_kw_existing, float)
	assert isinstance(battery_kwh_existing, float)
	with open(reopt_dirname + '/allInputData.json') as f:
		allInputData = json.load(f)
	allInputData['batteryKwhExisting'] = battery_kwh_existing
	allInputData['batteryKwExisting'] = battery_kw_existing
	if allInputData['battery']:
		critical_load_series = pd.read_csv(reopt_dirname + '/criticalLoadShape.csv', header=None)[0]
		outage_start_hour = int(allInputData['outage_start_hour'])
		outage_duration = int(allInputData['outageDuration'])
		calculated_max_kwh = float(critical_load_series[outage_start_hour:outage_start_hour + outage_duration].sum())
		if calculated_max_kwh < float(allInputData['batteryCapacityMax']):
			allInputData['batteryCapacityMax'] = calculated_max_kwh
		# - allInputData['batteryPowerMax'] is set in set_allinputdata_user_parameters()
	else:
		allInputData['batteryCapacityMax'] = battery_kwh_existing
		allInputData['batteryPowerMax'] = battery_kw_existing
	# - allInputData['batteryCapacityMin'] is set in set_allinputdata_user_parameters()
	# - allInputData['batteryPowerMin'] is set in set_allinputdata_user_parameters()
	with open(reopt_dirname + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)


def _set_allinputdata_solar_parameters(reopt_dirname, solar_kw_existing):
	'''
	- If new solar is enabled, set ['PV']['max_kw'] equal to the lesser of (1) the maximum value in the critical load shape series multiplied by 4 or
	  (2) the user-defined maximum value
	- If new solar is not enabled, set ['PV']['max_kw'] equal to 0
	- Always set ['PV']['existing_kw'] equal to the amount of existing solar that exists in the circuit. REopt will include existing solar generation
	  in its calculation regardless of whether new solar generation is enabled
	- ['PV']['min_kw'] is set by the user (defaults to 0)

	:param reopt_dirname: the REopt folder
	:type reopt_dirname: str
	:param solar_kw_existing: the amount of solar generation that already exists before REopt
	:type solar_kw_existing: float
	:rtype: None
	'''
	assert isinstance(reopt_dirname, str)
	assert isinstance(solar_kw_existing, float)
	with open(reopt_dirname + '/allInputData.json') as f:
		allInputData = json.load(f)
	allInputData['solarExisting'] = solar_kw_existing
	if allInputData['solar']:
		critical_load_series = pd.read_csv(reopt_dirname + '/criticalLoadShape.csv', header=None)[0]
		calculated_max_kw = float(critical_load_series.max() * 4)
		if calculated_max_kw < float(allInputData['solarMax']):
			allInputData['solarMax'] = calculated_max_kw
	else:
		allInputData['solarMax'] = 0
	with open(reopt_dirname + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)


def _set_allinputdata_wind_parameters(reopt_dirname, wind_kw_existing):
	'''
	- If new wind is enabled, set ['Wind']['max_kw'] equal to the lesser of (1) the maximum value in the critical load shape series multiplied by 2 or
	  (2) the user-defined maximum value
	- If new wind is not enabled, and there is existing wind, set ['Wind']['max_kw'] equal to the amount of existing wind
	- ['Wind']['min_kw'] is set by the user (defaults to 0)

	:param reopt_dirname: the REopt folder
	:type reopt_dirname: str
    :param wind_kw_existing: the amount of wind kW before REopt
    :type wind_kw_existing: float
	:rtype: None
	'''
	assert isinstance(reopt_dirname, str)
	assert isinstance(wind_kw_existing, float)
	with open(reopt_dirname + '/allInputData.json') as f:
		allInputData = json.load(f)
	# - allInputData['windExisting'] is only used by microgridUP, not REopt
	allInputData['windExisting'] = wind_kw_existing
	critical_load_series = pd.read_csv(reopt_dirname + '/criticalLoadShape.csv', header=None)[0]
	calculated_max_kw = float(critical_load_series.max() * 2)
	if allInputData['wind']:
		if calculated_max_kw < float(allInputData['windMax']):
			allInputData['windMax'] = calculated_max_kw
	else:
		allInputData['windMax'] = wind_kw_existing
	with open(reopt_dirname + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)


def _set_allinputdata_generator_parameters(reopt_dirname, fossil_kw_existing):
	'''
	- If new fossil generators are enabled, set ['Generator']['max_kw'] equal to the lesser of (1) the maximum value in the critical load shape series
	  or (2) the user-defined maximum value
    - If new fossil generators are not enabled, set ['Generator']['max_kw'] to 0
    - Always set ['Generator']['existing_kw'] equal to the amount of existing fossil generation that exists in the circuit. REopt will include
      existing fossil generation in its calculation regardless of whether new fossil generation is enabled
    - ['Generator']['min_kw'] is set by the user (defaults to 0)

	:param reopt_dirname: the REopt folder
	:type reopt_dirname: str
	:param fossil_kw_existing: the amount of fossil kW before REopt
	:type fossil_kw_existing: float
	:rtype: None
	'''
	assert isinstance(reopt_dirname, str)
	assert isinstance(fossil_kw_existing, float)
	with open(reopt_dirname + '/allInputData.json') as f:
		allInputData = json.load(f)
	allInputData['genExisting'] = fossil_kw_existing
	if allInputData['fossil']:
		critical_load_series = pd.read_csv(reopt_dirname + '/criticalLoadShape.csv', header=None)[0]
		calculated_max_kw = float(critical_load_series.max())
		if calculated_max_kw < float(allInputData['dieselMax']):
			allInputData['dieselMax'] = calculated_max_kw
	else:
		allInputData['dieselMax'] = 0
	with open(reopt_dirname + '/allInputData.json', 'w') as f:
		json.dump(allInputData, f, indent=4)


def _microgrid_design_output(reopt_dirname):
	''' Generate a clean microgridDesign output with edge-to-edge design. '''
	assert isinstance(reopt_dirname, str)
	all_html = ''
	legend_spec = {'orientation':'h', 'xanchor':'left'}#, 'x':0, 'y':-0.2}
	with open(f'{reopt_dirname}/allOutputData.json') as file:
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
	with open(f'{reopt_dirname}/allInputData.json') as f:
		all_input_data = json.load(f)
	with open(f'{reopt_dirname}/results.json') as f:
		results = json.load(f)
	df = pd.DataFrame({
		'Solar kW': [all_input_data['solarExisting'], 0, all_input_data['solarExisting'], 0, 0],
		'Wind kW': [all_input_data['windExisting'], 0, all_input_data['windExisting'], 0, 0],
		'Storage kW': [all_input_data['batteryKwExisting'], 0, all_input_data['batteryKwExisting'], 0, 0],
		'Storage kWh': [all_input_data['batteryKwhExisting'], 0, all_input_data['batteryKwhExisting'], 0, 0],
		'Fossil kW': [all_input_data['genExisting'], 0, all_input_data['genExisting'], 0, 0],
		'Load kW': [0, 0, 0, round(statistics.mean(results['ElectricLoad']['load_series_kw'])), round(max(results['ElectricLoad']['load_series_kw']))],
		'Critical Load kW': [0, 0, 0, round(statistics.mean(results['ElectricLoad']['critical_load_series_kw'])), round(max(results['ElectricLoad']['critical_load_series_kw']))]
	}, index=['Existing', 'New', 'Total', 'Average', 'Peak'], dtype=np.float64)
	if 'sizePV1' in allOutData:
		df.loc['Total', 'Solar kW'] = round(allOutData['sizePV1'])
		df.loc['New', 'Solar kW'] = round(allOutData['sizePV1'] - float(all_input_data['solarExisting']))
	if 'sizeWind1' in allOutData:
		df.loc['Total', 'Wind kW'] = round(allOutData['sizeWind1'])
		df.loc['New', 'Wind kW'] = round(allOutData['sizeWind1'] - float(all_input_data['windExisting']))
	if 'powerBattery1' in allOutData:
		df.loc['Total', 'Storage kW'] = round(allOutData['powerBattery1'])
		df.loc['New', 'Storage kW'] = round(allOutData['powerBattery1'] - float(all_input_data['batteryKwExisting']))
	if 'capacityBattery1' in allOutData:
		df.loc['Total', 'Storage kWh'] = round(allOutData['capacityBattery1'])
		df.loc['New', 'Storage kWh'] = round(allOutData['capacityBattery1'] - float(all_input_data['batteryKwhExisting']))
	if 'sizeDiesel1' in allOutData:
		df.loc['Total', 'Fossil kW'] = round(allOutData['sizeDiesel1'])
		df.loc['New', 'Fossil kW'] = round(allOutData['sizeDiesel1'] - float(all_input_data['genExisting']))
	generation_fig = go.Figure(data=[
		go.Bar(name='Existing Generation (kW)', x=df.columns.to_series(), y=df.loc['Existing']),
		go.Bar(name='New Generation (kW)', x=df.columns.to_series(), y=df.loc['New']),
		go.Bar(name='Total Generation (kW)', x=df.columns.to_series(), y=df.loc['Total']),
		go.Bar(name='Average Load (kW)', x=df.columns.to_series(), y=df.loc['Average']),
		go.Bar(name='Peak Load (kW)', x=df.columns.to_series(), y=df.loc['Peak']),
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
	with open(f'{reopt_dirname}/allInputData.json') as inFile:
		allInputData = json.load(inFile)
	allInputData['loadShape'] = 'From File'
	allInputData['criticalLoadShape'] = 'From File'
	# Templating.
	with open(f'{microgridup.MGU_DIR}/templates/template_microgridDesign.html') as inFile:
		mgd_template = j2.Template(inFile.read())
	mgd = mgd_template.render(
		chart_html=all_html,
		allInputData=allInputData
	)
	with open(f'{reopt_dirname}/cleanMicrogridDesign.html', 'w') as outFile:
		outFile.write(mgd)


def _get_mg_specific_reopt_inputs(data, mg_name):
	'''
	:param data: the data
	:type data: MappingProxyType (an immutable dict)
	:param mg_name: the name of the microgrid
	:type mg_name: str
	:return: inputs to Julia REopt with microgrid-specific REopt parameter overrides applied
	:rtype: dict
	'''
	assert isinstance(data, MappingProxyType)
	assert isinstance(mg_name, str)
	mg_specific_parameters = dict(data['REOPT_INPUTS'])
	mg = data['MICROGRIDS'][mg_name]
	for k, v in mg['parameter_overrides']['reopt_inputs'].items():
		if k not in mg_specific_parameters:
			raise KeyError(f'The parameter "{k}" could not be overriden on a per-microgrid basis because it does not exist as a default parameter.')
		mg_specific_parameters[k] = v
	return mg_specific_parameters


def _create_production_factor_series_csv(data, logger, invalidate_cache):
	'''
	Do an initial REopt run to get "production_factor_series" vectors for solar and wind generators. Basically, situtations can occur where solar or
	wind generators are in a circuit, but are not included in a microgrid (or the microgrid that they are included in has no critical loads).  If
	either of these situations occur, our inputs to REopt are configured such that no "PV" or "Wind" data will be present in the REopt output and as a
	result we won't be able to generate load shapes for those generators. To get around this issue, we just do an extra REopt run with solar and wind
	enabled and then actual microgrids can read the "production_factor_series" data as needed

	:param data: the data
	:type data: MappingProxyType (an immutable dict)
	:param logger: a logger
	:type logger: Logger
	:rtype: None
	'''
	assert isinstance(data, MappingProxyType)
	assert isinstance(logger, logging.Logger)
	assert isinstance(invalidate_cache, bool)
	if not Path('production_factor_series.csv').exists() or invalidate_cache:
		microgridDesign.new('reopt_loadshapes')
		# - The load shape for production_factor_series.csv needs to be the same as for the microgrid(s) in order to use the same wind turbine size
		#   class. This is tricky because technically different microgrids could have sufficiently different load shapes such that one microgrid could
		#   use a smaller size class and another microgrid would use a larger size class, so which size class should production_factor_series.csv use?
		#   For now, we just use whatever size class mg0 uses and assume all microgrids have similar load profiles (and thus, similar size classes)
		#   - We could make use of multiprocessing if we had to for 4 simultaneous REopt runs
		first_mg_name = list(data['MICROGRIDS'].keys())[0]
		_set_allinputdata_load_shape_parameters(data, first_mg_name, 'reopt_loadshapes', logger)
		with open('reopt_loadshapes/allInputData.json') as f:
			allInputData = json.load(f)
		allInputData['maxRuntimeSeconds'] = data['REOPT_INPUTS']['maxRuntimeSeconds']
		lat, lon = microgridup_hosting_cap.get_microgrid_coordinates(data['MICROGRIDS'][first_mg_name])
		# - The coordinates for production_factor_series.csv need to be the same as for the microgrid(s) in order to use the same historical REopt
		#   wind data
		allInputData['latitude'] = lat
		allInputData['longitude'] = lon
		# - We only care about the inputs to the model insofar as they (1) include solar and wind output and (2) the model completes as quickly as
		#   possible
		allInputData['solar'] = True
		allInputData['wind'] = True
		allInputData['battery'] = False
		allInputData['fossil'] = False
		with open('reopt_loadshapes/allInputData.json', 'w') as f:
			json.dump(allInputData, f, indent=4)
		__neoMetaModel__.runForeground('reopt_loadshapes')
		try:
			with open('reopt_loadshapes/results.json') as f:
				results = json.load(f)
		except FileNotFoundError as e:
			with open('reopt_loadshapes/stderr.txt') as f:
				err_msg = f.read()
			logger.warning(err_msg)
			raise e
		shutil.rmtree('reopt_loadshapes')
		production_factor_series_df = pd.DataFrame()
		production_factor_series_df['pv_production_factor_series'] = pd.Series(results['PV']['production_factor_series'])
		try:
			production_factor_series_df['wind_production_factor_series'] = pd.Series(results['Wind']['production_factor_series'])
		except:
			# - On some platforms reopt_jl can't handle wind, and it's safe to skip this output.
			error_msg = 'results.json did not contain valid data for ["Wind"]["production_factor_series"]'
			print(error_msg)
			logger.warning(error_msg)
		production_factor_series_df.to_csv('production_factor_series.csv', index=False)


def _tests():
	# - Asssert that REopt's own tests pass
	reopt_jl._test()
	# - Load lehigh1mg to use as test input
	test_model = 'lehigh1mg'
	absolute_model_directory = f'{microgridup.PROJ_DIR}/{test_model}'
	# HACK: work in directory because we're very picky about the current dir.
	curr_dir = os.getcwd()
	if curr_dir != absolute_model_directory:
		os.chdir(absolute_model_directory)
	with open('allInputData.json') as file:
		data = microgridup.get_immutable_dict(json.load(file))
	mg_name = 'mg0'
	print(f'----------microgrid_design.py testing {test_model}----------')
	logger = microgridup.setup_logging('logs.log', mg_name)
	_run(data, mg_name, logger, False)
	# - Assert that we got valid output from REopt
	with open(f'reopt_{mg_name}/REoptInputs.json') as f:
		inputs = json.load(f)
	with open(f'reopt_{mg_name}/results.json') as f:
		results = json.load(f)
	# - Assert that the input load shape matches the output load shape
	assert inputs['s']['electric_load']['loads_kw'] == results['ElectricLoad']['load_series_kw']
	# - Assert that the optimal solar size is within 5% of an expected value
	assert abs(1 - results['PV']['size_kw']/3325) < 0.05
	# - Assert that the optimal generator size is within 5% of an expected value
	assert abs(1 - results['Generator']['size_kw']/1586) < 0.05
	# - Assert that the optimal storage size is within 5% of an expected value
	assert abs(1 - results['ElectricStorage']['size_kw']/413) < 0.05
	assert abs(1 - results['ElectricStorage']['size_kwh']/545) < 0.05
	# - Assert that the optimal lifecycle cost is within 5% of an expected value
	assert abs(1 - results['Financial']['lcc']/1.7430358e7) < 0.05
	os.chdir(curr_dir)
	print('Ran all tests for microgridup_design.py.')


if __name__ == '__main__':
	_tests()