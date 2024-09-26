import csv, json, os, datetime, logging
from types import MappingProxyType
from os import path
import pandas as pd
import numpy as np
import plotly
import plotly.graph_objects as go
from omf.solvers import opendss
from omf.solvers.opendss import dssConvert
from omf.solvers import opendss
import omf.models
import microgridup


def run(data, mg_name, input_dss_filename, output_dss_filename, logger):
	'''
	Use the REopt results and the input DSS file to create new generation objects that follow the REopt recommendations. Combine the input DSS file
	and new generation objects in the output DSS file. Along the way, write a CSV that describes various costs of building the new circuit and ...

	:param data: the data
	:type data: MappingProxyType (an immutable dict)
	:param mg_name: a microgrid name
	:type mg_name: str
	:param input_dss_filename: the name of the DSS file that contains the state of the circuit before new REopt-recommened DSS generation objects have
		been added
	:type input_dss_filename: str
	:param output_dss_filename: the name of the DSS file that contains the state of the circuit after the new REopt-recommended DSS generation objects
	    have been added
	:type output_dss_filename: str
	:param logger: a logger
	:type logger: Logger
	:rtype: None
	'''
	assert isinstance(data, MappingProxyType)
	assert isinstance(mg_name, str)
	assert isinstance(input_dss_filename, str)
	assert isinstance(output_dss_filename, str)
	assert isinstance(logger, logging.Logger)
	microgrid = data['MICROGRIDS'][mg_name]
	gen_obs = _build_new_gen_ob_and_shape(data, mg_name, input_dss_filename, logger)
	_make_full_dss(microgrid, gen_obs, input_dss_filename, output_dss_filename)
	# Generate microgrid control hardware costs.
	_mg_add_cost(data, mg_name, input_dss_filename, logger)
	_microgrid_report_csv(data, mg_name, f'ultimate_rep_{output_dss_filename}.csv', logger)


def gen_powerflow_results(YEAR, QSTS_STEPS, logger):
	''' Generate full powerflow results on a given circuit. '''
	CIRCUIT_FILE = 'circuit_plus_mgAll.dss'
	print('QSTS with ', CIRCUIT_FILE, 'AND CWD IS ', os.getcwd())
	logger.warning(f'QSTS with {CIRCUIT_FILE} AND CWD IS {os.getcwd()}')
	opendss.newQstsPlot(CIRCUIT_FILE,
		stepSizeInMinutes=60,
		numberOfSteps=QSTS_STEPS,
		keepAllFiles=False,
		actions={},
		filePrefix='timeseries')
	if os.path.exists(f'timeseries_gen.csv'):
		_make_chart('timeseries_gen.csv', CIRCUIT_FILE, 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], YEAR, QSTS_STEPS, "Generator Output", "Average hourly kW")
	_make_chart('timeseries_load.csv', CIRCUIT_FILE, 'Name', 'hour', ['V1(PU)','V2(PU)','V3(PU)'], YEAR, QSTS_STEPS, "Load Voltage", "PU", ansi_bands = True)
	_make_chart('timeseries_source.csv', CIRCUIT_FILE, 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], YEAR, QSTS_STEPS, "Voltage Source Output", "Average hourly kW")
	if os.path.exists(f'timeseries_control'):
		_make_chart('timeseries_control.csv', CIRCUIT_FILE, 'Name', 'hour', ['Tap(pu)'], YEAR, QSTS_STEPS, "Tap Position", "PU")


def get_microgrid_existing_generation_dict(microgrid):
	'''
	:param microgrid: a micrgorid
	:type microgrid: MappingProxyType (an immutable dict)
	:return: a dict of floats which describe amounts of existing generation by category
	:rtype: dict
	'''
	assert isinstance(microgrid, MappingProxyType)
	tree = dssConvert.dssToTree('circuit.dss')
	load_map = {x.get('object',''):i for i, x in enumerate(tree)}
	solar_kw_existing = []
	fossil_kw_existing = []
	battery_kw_existing = []
	battery_kwh_existing = []
	wind_kw_existing = []
	for gen_ob in microgrid['gen_obs_existing']:
		if gen_ob.startswith('solar_'):
			solar_kw_existing.append(float(tree[load_map[f'generator.{gen_ob}']].get('kw')))
		elif gen_ob.startswith('fossil_'):
			fossil_kw_existing.append(float(tree[load_map[f'generator.{gen_ob}']].get('kw')))
		elif gen_ob.startswith('wind_'):
			wind_kw_existing.append(float(tree[load_map[f'generator.{gen_ob}']].get('kw')))
		elif gen_ob.startswith('battery_'):
			battery_kw_existing.append(float(tree[load_map[f'storage.{gen_ob}']].get('kwrated')))
			battery_kwh_existing.append(float(tree[load_map[f'storage.{gen_ob}']].get('kwhrated')))
	return {
		'battery_kw_existing': 0.0 if len(battery_kw_existing) == 0 else sum(battery_kw_existing),
		'battery_kwh_existing': 0.0 if len(battery_kwh_existing) == 0 else sum(battery_kwh_existing),
		'solar_kw_existing': 0.0 if len(solar_kw_existing) == 0 else sum(solar_kw_existing),
		'wind_kw_existing': 0.0 if len(wind_kw_existing) == 0 else sum(wind_kw_existing),
		'fossil_kw_existing': 0.0 if len(fossil_kw_existing) == 0 else sum(fossil_kw_existing)}


def get_microgrid_coordinates(microgrid):
	'''
	:param microgrid: a microgrid to get coordinates for
	:type microgrid: MappingProxyType (an immutable dict)
	:return: (lat, lon) floating-point coordinates
	:rtype: tuple
	'''
	assert isinstance(microgrid, MappingProxyType)
	tree = dssConvert.dssToTree('circuit.dss')
	evil_glm = dssConvert.evilDssTreeToGldTree(tree)
	# using evil_glm to get around the fact that buses in openDSS are created in memory and do not exist in the BASE_NAME dss file
	for ob in evil_glm.values():
		ob_name = ob.get('name','')
		ob_type = ob.get('object','')
		# pull out long and lat of the gen_bus
		if ob_type == "bus" and ob_name == microgrid['gen_bus']:
			try:
				ob_lat = float(ob['latitude'])
				ob_long = float(ob['longitude'])
				return (ob_lat, ob_long)
			except:
				raise Exception("Couldn't determine microgrid latitude and longitude.")
	raise Exception("Couldn't determine microgrid latitude and longitude.")


def run_hosting_capacity():
	'''
	Run the traditional algorithm in omf.models.hostingCapacity() on the initial dss file

	:rtype: None
	'''
	omf.models.hostingCapacity.new('hosting_capacity')
	with open('hosting_capacity/allInputData.json') as f:
		all_input_data = json.load(f)
	# - Disable AMI algorithm and downline algorithm
	all_input_data['runAmiAlgorithm'] = 'off'
	all_input_data['runDownlineAlgorithm'] = 'off'
	# - Remove omd file that was copied by default into the hosting_capacity/ directory because we replace it with a different omd
	os.remove(f"hosting_capacity/{all_input_data['feederName1']}.omd")
	# - Create and set the new omd file
	dssConvert.dssToOmd('circuit.dss', f'hosting_capacity/circuit.dss.omd')
	all_input_data['feederName1'] = 'circuit.dss'
	# - Ignore the timeseries column if it exists in loads.csv
	timeseries_signature1 = ((8760 ** 2 ) + 8760) / 2
	timeseries_signature2 = ((8759 ** 2 ) + 8759) / 2
	load_df = pd.read_csv('loads.csv')
	if [timeseries_signature1, timeseries_signature2].count(load_df.iloc[:8760, 0].sum()) > 0:
		load_df = load_df.iloc[:, 1:]
	# - Instead of testing each bus up to 50000 kW, just test up to 4x the peak load across all meters to speed up the calculation
	all_input_data['traditionalHCMaxTestkw'] = load_df.apply(np.max).sum() * 4
	with open('hosting_capacity/allInputData.json', 'w') as f:
		json.dump(all_input_data, f, indent=4)
	cwd = os.getcwd()
	omf.models.__neoMetaModel__.runForeground(f'{os.getcwd()}/hosting_capacity')
	# - IDK why running hostingCapacity.py changes working directories, but change it back
	os.chdir(cwd)
	with open('hosting_capacity/allOutputData.json') as f:
		data = json.load(f)
	# - Organize graph data
	kw_capacity_per_bus = data['traditionalHCResults']
	tree = dssConvert.dssToTree('circuit.dss')
	kw_load_and_gen_per_bus = {}
	for d in tree:
		if d.get('object', '').startswith('load.'):
			bus_name = d['bus1'].split('.')[0]
			if kw_load_and_gen_per_bus.get(bus_name) is None:
				kw_load_and_gen_per_bus[bus_name] = {'load': float(d['kw']), 'generation': 0}
			else:
				kw_load_and_gen_per_bus[bus_name]['load'] += float(d['kw'])
		if d.get('object', '').startswith('generator'):
			bus_name = d['bus1'].split('.')[0]
			if kw_load_and_gen_per_bus.get(bus_name) is None:
				kw_load_and_gen_per_bus[bus_name] = {'generation': float(d['kw']), 'load': 0}
			else:
				kw_load_and_gen_per_bus[bus_name]['generation'] += float(d['kw'])
	# - Create graph
	df = pd.DataFrame(kw_capacity_per_bus)
	df['load_kw'] = df.apply(lambda row: kw_load_and_gen_per_bus[row['bus']].get('load', 0), axis=1)
	df['generation_kw'] = df.apply(lambda row: kw_load_and_gen_per_bus[row['bus']].get('generation', 0), axis=1)
	non_violation_rows = df[(df['thermally_limited'] == False) & (df['voltage_limited'] == False)]
	voltage_limited_rows = df[(df['thermally_limited'] == False) & (df['voltage_limited'] == True)]
	thermally_limited_rows = df[(df['thermally_limited'] == True) & (df['voltage_limited'] == False)]
	duel_violation_rows = df[(df['thermally_limited'] == True) & (df['voltage_limited'] == True)]
	fig = go.Figure(data=[
		go.Bar(name='Bus Existing kW Load', x=df['bus'], y=df['load_kw'], marker_color='purple', hovertemplate='<br>'.join(['bus: %{x}', 'Bus Existing kW Load: %{y}'])),
		go.Bar(name='Bus Existing kW Generation', x=df['bus'], y=df['generation_kw'], marker_color='blue', hovertemplate='<br>'.join(['bus: %{x}', 'Bus Existing kW Generation: %{y}'])),
		go.Bar(name='Bus Max kW Capacity', x=non_violation_rows['bus'], y=non_violation_rows['max_kw'], marker_color='green', hovertemplate='<br>'.join(['bus: %{x}', 'Bus Max kW Capacity: %{y}'])),
		go.Bar(name='Bus Voltage Violation kW', x=voltage_limited_rows['bus'], y=voltage_limited_rows['max_kw'], marker_color='yellow', hovertemplate='<br>'.join(['bus: %{x}', 'Bus Voltage Violation kW: %{y}'])),
		go.Bar(name='Bus Thermal Violation kW', x=thermally_limited_rows['bus'], y=thermally_limited_rows['max_kw'], marker_color='orange', hovertemplate='<br>'.join(['bus: %{x}', 'Bus Thermal Violation kW: %{y}'])),
		go.Bar(name='Bus Voltage and Thermal Violation kW', x=duel_violation_rows['bus'], y=duel_violation_rows['max_kw'], marker_color='red', hovertemplate='<br>'.join(['bus: %{x}', 'Bus Voltage and Thermal Violation kW: %{y}']))])
	fig.update_layout(
		title='Traditional Hosting Capacity By Bus',
		font=dict(family="sans-serif",
		color="black"),
		xaxis_title='Bus Name',
		yaxis_title='kW',
		legend=dict(orientation='h'))
	fig.write_html('hosting_capacity/traditionalGraphData.html')
	# - Create table
	html = (
        '<html>'
            '<head>'
                '<link rel="stylesheet" href="/static/microgridup.css">'
            '</head>'
            '<body>'
                '<div class="tableDiv">'
                f'{df.to_html(index=False, border=0)}'
                '</div>'
    )
	with open('hosting_capacity/traditionalGraphTable.html', 'w') as f:
		f.write(html)


def _build_new_gen_ob_and_shape(data, mg_name, dss_filename, logger):
	'''
	Create new generator objects and shapes.
	SIDE EFFECTS: creates generation.csv generator shape
	TODO: To implement multiple same-type existing generators within a single microgrid, will need to implement searching the tree of FULL_NAME to
	find kw ratings of existing gens

	:param data: the data
	:type data: MappingProxyType (an immutable dict)
	:param mg_name: the name of a microgrid
	:type mg_name: str
	:param dss_filename: the name of the DSS file that contains the state of the circuit before new REopt-recommened DSS generation objects have been
		added
	:type dss_filename: str
	:param logger: a logger
	:type logger: Logger
	:return: a list of generator objects formatted for reading into openDSS tree
	:rtype: list
	'''
	assert isinstance(data, MappingProxyType)
	assert isinstance(mg_name, str)
	assert isinstance(dss_filename, str)
	assert isinstance(logger, logging.Logger)
	reopt_dirname = f'reopt_{mg_name}'
	gen_sizes = _get_gen_ob_from_reopt(reopt_dirname)
	# print("build_new_gen_ob_and_shape() gen_sizes into OpenDSS:", gen_sizes)
	with open(reopt_dirname + '/allOutputData.json') as file:
		reopt_out = json.load(file)
	gen_df_builder = pd.DataFrame()
	gen_obs = []
	mg_num = 1
	microgrid = data['MICROGRIDS'][mg_name]
	#print("microgrid:", microgrid)
	phase_and_kv = _mg_phase_and_kv(data, mg_name, dss_filename, logger)
	tree = dssConvert.dssToTree(dss_filename)
	gen_map = {x.get('object',''):i for i, x in enumerate(tree)}\
	# Build new solar gen objects and loadshapes
	solar_size_total = gen_sizes.get('solar_size_total')
	solar_size_new = gen_sizes.get('solar_size_new')
	if solar_size_new > 0:
		gen_obs.append({
			'!CMD': 'new',
			'object':f'generator.solar_{microgrid["gen_bus"]}',
			'bus1':f'{microgrid["gen_bus"]}.{".".join(phase_and_kv["phases"])}',
			'phases':len(phase_and_kv['phases']),
			'kv':phase_and_kv['kv'],
			'kw':f'{solar_size_new}',
			'pf':'1'
		})
		# 0-1 scale the power output loadshape to the total generation kw of that type of generator using pandas
		gen_df_builder[f'solar_{microgrid["gen_bus"]}'] = pd.Series([0] * 8760)
		if solar_size_total > 0:
			gen_df_builder[f'solar_{microgrid["gen_bus"]}'] = pd.Series(reopt_out.get(f'powerPV{mg_num}')) / solar_size_total * solar_size_new
	# build loadshapes for existing generation from BASE_NAME, inputting the 0-1 solar generation loadshape and scaling by their rated kw
	solar_size_existing = gen_sizes.get('solar_size_existing')
	if solar_size_existing > 0:
		for gen_ob_existing in microgrid['gen_obs_existing']:
			if gen_ob_existing.startswith('solar_'):
				# get kw rating for this generator from the DSS tree
				gen_kw = float(tree[gen_map[f'generator.{gen_ob_existing}']].get('kw',''))
				gen_df_builder[f'{gen_ob_existing}'] = pd.Series([0] * 8760)
				if solar_size_total > 0:
					gen_df_builder[f'{gen_ob_existing}'] = pd.Series(reopt_out.get(f'powerPV{mg_num}')) / solar_size_total * gen_kw
	# Build new fossil gen objects and loadshapes
	fossil_size_total = gen_sizes.get('fossil_size_total')
	fossil_size_new = gen_sizes.get('fossil_size_new')
	if fossil_size_new > 0:
		gen_obs.append({
			'!CMD': 'new',
			'object':f'generator.fossil_{microgrid["gen_bus"]}',
			'bus1':f'{microgrid["gen_bus"]}.{".".join(phase_and_kv["phases"])}',
			'phases':len(phase_and_kv['phases']),
			'kv':phase_and_kv['kv'],
			'kw':f'{fossil_size_new}',
			'xdp':'0.27',
			'xdpp':'0.2',
			'h':'2'
		})
		# 0-1 scale the power output loadshape to the total generation kw of that type of generator
		gen_df_builder[f'fossil_{microgrid["gen_bus"]}'] = pd.Series([0] * 8760)
		if fossil_size_total > 0:
			gen_df_builder[f'fossil_{microgrid["gen_bus"]}'] = pd.Series(reopt_out.get(f'powerDiesel{mg_num}')) / fossil_size_total * fossil_size_new
		# TODO: if using real loadshapes for fossil, need to scale them based on rated kw of the new fossil
		# gen_df_builder[f'fossil_{microgrid["gen_bus"]}'] = pd.Series(np.zeros(8760)) # insert an array of zeros for the fossil generation shape to simulate no outage
	# build loadshapes for multiple existing fossil generators from BASE_NAME, inputting the 0-1 fossil generation loadshape and multiplying by the kw of the existing gen
	fossil_size_existing = gen_sizes.get('fossil_size_existing')
	if fossil_size_existing > 0:	
		for gen_ob_existing in microgrid['gen_obs_existing']:
			if gen_ob_existing.startswith('fossil_'):
				gen_kw = float(tree[gen_map[f'generator.{gen_ob_existing}']].get('kw',''))
				gen_df_builder[f'{gen_ob_existing}'] = pd.Series([0] * 8760)
				if fossil_size_total > 0:
					gen_df_builder[f'{gen_ob_existing}'] = pd.Series(reopt_out.get(f'powerDiesel{mg_num}')) / fossil_size_total * gen_kw
				# gen_df_builder[f'{gen_ob_existing}'] = pd.Series(np.zeros(8760)) # insert an array of zeros for the fossil generation shape to simulate no outage
	# Build new wind gen objects and loadshapes
	wind_size_total = gen_sizes.get('wind_size_total')
	wind_size_new = gen_sizes.get('wind_size_new')
	if wind_size_new > 0:
		gen_obs.append({
			'!CMD': 'new',
			'object':f'generator.wind_{microgrid["gen_bus"]}',
			'bus1':f'{microgrid["gen_bus"]}.{".".join(phase_and_kv["phases"])}',
			'phases':len(phase_and_kv['phases']),
			'kv':phase_and_kv['kv'],
			'kw':f'{wind_size_new}',
			'pf':'1'
		})
		# 0-1 scale the power output loadshape to the total generation and multiply by the new kw of that type of generator
		gen_df_builder[f'wind_{microgrid["gen_bus"]}'] = pd.Series([0] * 8760)
		if wind_size_total > 0:
			gen_df_builder[f'wind_{microgrid["gen_bus"]}'] = pd.Series(reopt_out.get(f'powerWind{mg_num}')) / wind_size_total * wind_size_new
	# build loadshapes for existing Wind generation from BASE_NAME
	wind_size_existing = gen_sizes.get('wind_size_existing')
	if wind_size_existing > 0:	
		for gen_ob_existing in microgrid['gen_obs_existing']:
			if gen_ob_existing.startswith('wind_'):
				gen_kw = float(tree[gen_map[f'generator.{gen_ob_existing}']].get('kw',''))
				gen_df_builder[f'{gen_ob_existing}'] = pd.Series([0] * 8760)
				if wind_size_total > 0:
					gen_df_builder[f'{gen_ob_existing}'] = pd.Series(reopt_out.get(f'powerWind{mg_num}')) / wind_size_total * gen_kw
	# calculate battery loadshape (serving load - charging load)
	battery_pow_total = gen_sizes.get('battery_pow_total')
	# calculate battery load
	if battery_pow_total > 0:	
		batToLoad = pd.Series(reopt_out.get(f'powerBatteryToLoad{mg_num}'))
		gridToBat = np.zeros(8760)
		# TO DO: add logic to update insertion of grid charging if microgird_control.py supports it 	
		gridToBat = pd.Series(reopt_out.get(f'powerGridToBattery{mg_num}'))
		pVToBat = np.zeros(8760)
		if solar_size_total > 0:
			pVToBat = pd.Series(reopt_out.get(f'powerPVToBattery{mg_num}'))
		fossilToBat = np.zeros(8760)
		if fossil_size_total > 0:
			fossilToBat = pd.Series(reopt_out.get(f'powerDieselToBattery{mg_num}'))
		windToBat = np.zeros(8760)
		if wind_size_total > 0:
			windToBat = pd.Series(reopt_out.get(f'powerWindToBattery{mg_num}'))
		battery_load = batToLoad - gridToBat - pVToBat - fossilToBat - windToBat
	else:
		battery_load = 0
	# get DSS objects and loadshapes for new battery
	# if additional battery power is recommended by REopt, add in full sized new battery
	battery_cap_total = gen_sizes.get('battery_cap_total')
	battery_cap_new = gen_sizes.get('battery_cap_new')
	battery_pow_new = gen_sizes.get('battery_pow_new')
	battery_pow_existing = gen_sizes.get('battery_pow_existing')
	if battery_pow_new > 0:
		# print("build_new_gen() 1a")
		gen_obs.append({
			'!CMD': 'new',
			'object':f'storage.battery_{microgrid["gen_bus"]}',
			'bus1':f'{microgrid["gen_bus"]}.{".".join(phase_and_kv["phases"])}',
			'phases':len(phase_and_kv['phases']),
			'kv':phase_and_kv['kv'],
			'kwrated':f'{battery_pow_total}',
			'dispmode':'follow',
			'kwhstored':f'{battery_cap_total}',
			'kwhrated':f'{battery_cap_total}',
			'%charge':'100',
			'%discharge':'100',
			'%effcharge':'96',
			'%effdischarge':'96',
			'%idlingkw':'0'
		})
		# in this case the new battery takes the full battery load, as existing battery is removed from service
		# in dispmode=follow, OpenDSS takes in a 0-1 loadshape and scales it by the kwrated
		gen_df_builder[f'battery_{microgrid["gen_bus"]}'] = pd.Series([0] * 8760)
		if battery_pow_total > 0:
			gen_df_builder[f'battery_{microgrid["gen_bus"]}'] = battery_load / battery_pow_total
	# if only additional energy storage (kWh) is recommended, add a battery of same power as existing battery with the recommended additional kWh
	elif battery_cap_new > 0:
		# print("build_new_gen() 1b")
		# print("Check that battery_pow_existing (",battery_pow_existing, ") and battery_pow_total (", battery_pow_total, ") are the same")
		gen_obs.append({
			'!CMD': 'new',
			'object':f'storage.battery_{microgrid["gen_bus"]}',
			'bus1':f'{microgrid["gen_bus"]}.{".".join(phase_and_kv["phases"])}',
			'phases':len(phase_and_kv['phases']),
			'kv':phase_and_kv['kv'],
			'kwrated':f'{battery_pow_existing}', # in this case, battery_pow_existing = battery_pow_total
			'dispmode':'follow',
			'kwhstored':f'{battery_cap_new}',
			'kwhrated':f'{battery_cap_new}',
			'%charge':'100',
			'%discharge':'100',
			'%effcharge':'96',
			'%effdischarge':'96',
			'%idlingkw':'0'
		})
		# 0-1 scale the power output loadshape to the total power, and multiply by the ratio of new energy storage kwh over the total storage kwh
		# in dispmode=follow, OpenDSS takes in a 0-1 loadshape and auto scales it by the kwrated
		gen_df_builder[f'battery_{microgrid["gen_bus"]}'] = pd.Series([0] * 8760)
		if battery_pow_total > 0 and battery_cap_total > 0:
			gen_df_builder[f'battery_{microgrid["gen_bus"]}'] = battery_load / battery_pow_total * battery_cap_new / battery_cap_total
	# build loadshapes for existing battery generation from BASE_NAME
	battery_cap_existing = gen_sizes.get('battery_cap_existing')
	for gen_ob_existing in microgrid['gen_obs_existing']:
		# print("build_new_gen() storage 2", gen_ob_existing)
		if gen_ob_existing.startswith('battery_'):
			# print("build_new_gen() storage 3", gen_ob_existing)
			#TODO: IF multiple existing battery generator objects are in gen_obs, we need to scale the output loadshapes by their rated kW
			# if additional battery power is recommended by REopt, give existing batteries loadshape of zeros as they are deprecated
			if battery_pow_new > 0:
				# print("build_new_gen() storage 4", gen_ob_existing)
				gen_df_builder[f'{gen_ob_existing}'] = pd.Series(np.zeros(8760))
				warning_message = f'Pre-existing battery {gen_ob_existing} will not be utilized to support loads in microgrid {mg_name}.\n'
				print(warning_message)
				logger.warning(warning_message)
				with open("user_warnings.txt", "a") as myfile:
					myfile.write(warning_message)
			# if only additional energy storage (kWh) is recommended, scale the existing battery shape to the % of kwh storage capacity of the existing battery
			elif battery_cap_new > 0 and battery_pow_total > 0 and battery_cap_total > 0:
				# print("build_new_gen() storage 5", gen_ob_existing)
				# batt_kwh = float(tree[gen_map[f'storage.{gen_ob_existing}']].get('kwhrated',''))
				gen_df_builder[f'{gen_ob_existing}'] = battery_load / battery_pow_total * battery_cap_existing / battery_cap_total #batt_kwh
			# if no new battery has been built, existing battery takes the full battery load, using 0-1 scale
			else:
				# print("build_new_gen() storage 6", gen_ob_existing)
				# - TODO: why is this less than and equals???
				if battery_pow_total <= 0:
					gen_df_builder[f'{gen_ob_existing}'] = pd.Series([0] * 8760)
				else:
					gen_df_builder[f'{gen_ob_existing}'] = battery_load / battery_pow_total
	gen_df_builder.to_csv('generation.csv', index=False)
	return gen_obs


def _mg_phase_and_kv(data, mg_name, dss_filename, logger):
	'''
	TODO: If needing to set connection type explicitly, could use this function to check that all "conn=" are the same (wye or empty for default, or
	delta)

	:param data: the data
	:type data: MappingProxyType (an immutable dict)
	:param mg_name: the name of a microgrid
	:type mg_name: str
	:param dss_filename: the name of the DSS file that contains the state of the circuit before new REopt-recommened DSS generation objects have been
		added
	:type dss_filename: str
	:param logger: a logger
	:type logger: Logger
	:return: dict with the phases at the gen_bus and kv of the loads for a given microgrid.
	:rtype: dict
	'''
	assert isinstance(data, MappingProxyType)
	assert isinstance(mg_name, str)
	assert isinstance(dss_filename, str)
	assert isinstance(logger, logging.Logger)
	tree = dssConvert.dssToTree(dss_filename)
	microgrid = data['MICROGRIDS'][mg_name]
	mg_loads = microgrid['loads']
	load_phase_list = []
	gen_bus_kv_list = []
	load_map = {x.get('object',''):i for i, x in enumerate(tree)}
	for load_name in mg_loads:
		ob = tree[load_map[f'load.{load_name}']]
		# print("mg_phase_and_kv ob:", ob)
		bus_name = ob.get('bus1','')
		bus_name_list = bus_name.split('.')
		load_phases = []
		load_phases = bus_name_list[-(len(bus_name_list)-1):]
		print("load_phases on bus_name: phases", load_phases, "on bus", bus_name)
		logger.warning(f"load_phases on bus_name: phases {load_phases} on bus {bus_name}")
		for phase in load_phases:
			if phase not in load_phase_list:
				load_phase_list.append(phase)
		# set the voltage for the gen_bus and check that all loads match in voltage
		load_kv = ob.get('kv','')
		# append all new load_kv's to the list
		if load_kv not in gen_bus_kv_list:
			gen_bus_kv_list.append(load_kv)
	if len(gen_bus_kv_list) > 1:
		gen_bus_kv_message = f'More than one load voltage is specified on microgrid {mg_name}. Check Oneline diagram to verify that phases and voltages of {mg_loads} are correctly supported by gen_bus {microgrid["gen_bus"]}.\n'
		print(gen_bus_kv_message)
		logger.warning(gen_bus_kv_message)
		if path.exists("user_warnings.txt"):
			with open("user_warnings.txt", "r+") as myfile:
				if gen_bus_kv_message not in myfile.read():
					myfile.write(gen_bus_kv_message)
		else:
			with open("user_warnings.txt", "a") as myfile:
				myfile.write(gen_bus_kv_message)
	# print("gen_bus_kv_list:",gen_bus_kv_list)
	out_dict = {}
	out_dict['gen_bus'] = microgrid["gen_bus"]
	load_phase_list.sort()
	# neutral phase is assumed, and should not be explicit in load_phase_list
	if load_phase_list[0] == '0':
		load_phase_list = load_phase_list[1:]
		print(f"load_phase_list after removal of ground phase: {load_phase_list}")
		logger.warning(f"load_phase_list after removal of ground phase: {load_phase_list}")
	out_dict['phases'] = load_phase_list
	# Kv selection method prior to January 2022:
	# Choose the maximum voltage based upon the phases that are supported, assuming all phases in mg can be supported from gen_bus and that existing tranformers will handle any kv change
	# out_dict['kv'] = max(gen_bus_kv_list)
	# Retrieve the calculated line to neutral kv from the gen_bus itself (January 2022):
	kv_mappings = opendss.get_bus_kv_mappings(dss_filename)
	# print('kv_mappings:',kv_mappings)
	gen_bus_kv = kv_mappings.get(microgrid["gen_bus"])
	# if 3 phases are supported at the gen_bus, convert the kv rating to line to line voltage
	# if len(load_phase_list) == 3:
	# 	gen_bus_kv = gen_bus_kv * math.sqrt(3)
	# TODO: match up the calculated kv at the gen_bus with the appropriate line to neutral or line to line kv from voltagebases from the BASE_NAME dss file so that PU voltages compute accurately
	out_dict['kv'] = gen_bus_kv
	print('mg_phase_and_kv out_dict:', out_dict)
	logger.warning(f'mg_phase_and_kv out_dict: {out_dict}')
	return out_dict


def _make_full_dss(microgrid, gen_obs, input_dss_filename, output_dss_filename):
	'''
	insert generation objects into dss.
	ASSUMPTIONS: 
	SIDE EFFECTS: writes FULL_NAME dss

	:param microgrid: a microgrid
	:type microgrid: MappingProxyType (an immutable dict)
	:param gen_obs: the REopt-recommended generation objects that we created in DSS format
	:type gen_obs: list
	:param input_dss_filename: the name of the DSS file that contains the state of the circuit before new REopt-recommened DSS generation objects have
		been added
	:type input_dss_filename: str
	:param output_dss_filename: the name of the DSS file that contains the state of the circuit after the new REopt-recommended DSS generation objects
		have been added
	:rtype: None
	'''
	assert isinstance(microgrid, MappingProxyType)
	assert isinstance(gen_obs, list)
	assert isinstance(input_dss_filename, str)
	assert isinstance(output_dss_filename, str)
	tree = dssConvert.dssToTree(input_dss_filename)
	# make a list of names all existing loadshape objects
	load_map = {x.get('object',''):i for i, x in enumerate(tree)}
	bus_list_pos = -1
	for i, ob in enumerate(tree):
		if ob.get('!CMD','') == 'makebuslist':
			bus_list_pos = i
	for ob in gen_obs:
		tree.insert(bus_list_pos, ob)
	# Gather loadshapes and generator duties.
	try:
		gen_df = pd.read_csv('generation.csv')
	except Exception:
		# - This microgrid has no new or existing generation objects (probably because there were no critical loads in the microgrid), so
		#   "generation.csv" is empty
		gen_df = pd.DataFrame()
	load_df = pd.read_csv('loads.csv')
	load_df.columns = [str(x).lower() for x in load_df.columns]
	# get 1kw reference loadshapes for solar and wind existing gens that are outside of 'microgrid'
	ref_df = pd.read_csv('production_factor_series.csv')
	shape_insert_list = {}
	ob_deletion_list = []
	for i, ob in enumerate(tree):
		ob_string = ob.get('object','')
		# reset shape_data to be blank before every run of the loop
		shape_data = None
		# insert loadshapes for load objects
		if ob_string.startswith('load.'):
			ob_name = ob_string[5:]
			shape_data = load_df[ob_name]
			shape_name = ob_name + '_shape'
			ob['yearly'] = shape_name
			# check to make sure no duplication of loadshapes in DSS file
			if f'loadshape.{shape_name}' not in load_map:
				shape_insert_list[i] = {
					'!CMD': 'new',
					'object': f'loadshape.{shape_name}',
					'npts': f'{len(shape_data)}',
					'interval': '1',
					'useactual': 'yes',
					'mult': f'{list(shape_data)}'.replace(' ','')
				}
		# insert loadshapes for generator objects
		elif ob_string.startswith('generator.'):
			# print("1_gen:", ob)
			ob_name = ob_string[10:]
			# print('ob_name:', ob_name)
			shape_name = ob_name + '_shape'
			# insert loadshape for existing generators
			if ob_name.endswith('_existing'):
				# TODO: if actual production loadshape is available for a given object, insert it, else use synthetic loadshapes as defined here
				# if object is outside of microgrid and without a loadshape, give it a valid production loadshape for solar and wind or a loadshape of zeros for fossil
				if ob_name not in microgrid['gen_obs_existing'] and f'loadshape.{shape_name}' not in load_map:
					if ob_name.startswith('fossil_'):
						ob['yearly'] = shape_name
						shape_insert_list[i] = {
							'!CMD': 'new',
							'object': f'loadshape.{shape_name}',
							'npts': '8760',
							'interval': '1',
							'useactual': 'yes',
							'mult': f'{[0.0] * 8760}'.replace(' ','')
						}
					elif ob_name.startswith('solar_'):
						ob['yearly'] = shape_name
						shape_data = ref_df['pv_production_factor_series'] * float(ob['kw'])  # enable when using gen_existing_ref_shapes()
						shape_insert_list[i] = {
							'!CMD': 'new',
							'object': f'loadshape.{shape_name}',
							'npts': '8760',
							'interval': '1',
							'useactual': 'yes',
							'mult': f'{list(shape_data)}'.replace(' ','')
						}
					elif ob_name.startswith('wind_'):
						ob['yearly'] = shape_name
						shape_data = ref_df['wind_production_factor_series'] * float(ob['kw']) # enable when using gen_existing_ref_shapes()
						shape_insert_list[i] = {
							'!CMD': 'new',
							'object': f'loadshape.{shape_name}',
							'npts': '8760',
							'interval': '1',
							'useactual': 'yes',
							'mult': f'{list(shape_data)}'.replace(' ','')
						}
					#TODO: build in support for all other generator types (CHP)
				# if generator object is located in the microgrid, insert new loadshape object
				elif ob_name in microgrid['gen_obs_existing']:
					# print("4_gen:", ob)
					# if loadshape object already exists, overwrite the 8760 hour data in ['mult']
					# ASSUMPTION: Existing generators will be reconfigured to be controlled by new microgrid
					if f'loadshape.{shape_name}' in load_map:
						j = load_map.get(f'loadshape.{shape_name}') # indexes of load_map and tree match
						shape_data = gen_df[ob_name]
						tree[j]['mult'] = f'{list(shape_data)}'.replace(' ','')
					else:
						ob['yearly'] = shape_name
						shape_data = gen_df[ob_name]
						shape_insert_list[i] = {
							'!CMD': 'new',
							'object': f'loadshape.{shape_name}',
							'npts': f'{len(shape_data)}',
							'interval': '1',
							'useactual': 'yes',
							'mult': f'{list(shape_data)}'.replace(' ','')
						}
			# insert loadshape for new generators with shape_data in generation.csv
			elif f'loadshape.{shape_name}' not in load_map:
				ob['yearly'] = shape_name
				shape_data = gen_df[ob_name]
				shape_insert_list[i] = {
					'!CMD': 'new',
					'object': f'loadshape.{shape_name}',
					'npts': f'{len(shape_data)}',
					'interval': '1',
					'useactual': 'yes',
					'mult': f'{list(shape_data)}'.replace(' ','')
				}
		# insert loadshapes for storage objects
		elif ob_string.startswith('storage.'):
			ob_name = ob_string[8:]
			shape_name = ob_name + '_shape'
			# TODO: if actual power production loadshape is available for a given storage object, insert it, else use synthetic loadshapes as defined here
			if ob_name.endswith('_existing'):
				# if object is outside of microgrid and without a loadshape, give it a loadshape of zeros
				if ob_name not in microgrid['gen_obs_existing'] and f'loadshape.{shape_name}' not in load_map:
					ob['yearly'] = shape_name
					shape_insert_list[i] = {
						'!CMD': 'new',
						'object': f'loadshape.{shape_name}',
						'npts': '8760',
						'interval': '1',
						'useactual': 'yes',
						'mult': f'{list([0.0] * 8760)}'.replace(' ','')
					}
				elif ob_name in microgrid['gen_obs_existing']:
					# HACK implemented here to erase unused existing batteries from the dss file
					# if the loadshape of an existing battery is populated as zeros in build_new_gen_ob_and_shape(), this object is not in use and should be erased along with its loadshape
					if sum(gen_df[ob_name]) == 0:
						ob_deletion_list.append(ob_string)
					# if loadshape object already exists and is not zeros, overwrite the 8760 hour data in ['mult']
					# ASSUMPTION: Existing generators in gen_obs_existing will be reconfigured to be controlled by new microgrid
					elif f'loadshape.{shape_name}' in load_map:
						# print("4b_storage:", ob_name)
						j = load_map.get(f'loadshape.{shape_name}') # indexes of load_map and tree match
						shape_data = gen_df[ob_name]
						# print(shape_name, 'shape_data:', shape_data.head(20))
						tree[j]['mult'] = f'{list(shape_data)}'.replace(' ','')
						# print(shape_name, "tree[j]['mult']:", tree[j]['mult'][:20])
						# print("4a_storage achieved insert")
					else:
						# print("4c_storage:", ob_name)
						ob['yearly'] = shape_name
						shape_data = gen_df[ob_name]
						shape_insert_list[i] = {
							'!CMD': 'new',
							'object': f'loadshape.{shape_name}',
							'npts': f'{len(shape_data)}',
							'interval': '1',
							'useactual': 'yes',
							'mult': f'{list(shape_data)}'.replace(' ','')
						}
			# insert loadshapes for new storage objects with shape_data in generation.csv
			elif f'loadshape.{shape_name}' not in load_map:
				# print("5_storage", ob_name)
				shape_data = gen_df[ob_name]
				ob['yearly'] = shape_name
				shape_insert_list[i] = {
					'!CMD': 'new',
					'object': f'loadshape.{shape_name}',
					'npts': f'{len(shape_data)}',
					'interval': '1',
					'useactual': 'yes',
					'mult': f'{list(shape_data)}'.replace(' ','')
				}
	# Do shape insertions at proper places
	for key in shape_insert_list:
		min_pos = min(shape_insert_list.keys())
		tree.insert(min_pos, shape_insert_list[key])
	# Delete unused existing battery objects and their loadshapes from the tree
	load_map = {x.get('object',''):i for i, x in enumerate(tree)}
	for ob_string in ob_deletion_list:
		i = load_map.get(ob_string)
		del tree[i]
		load_map = {x.get('object',''):i for i, x in enumerate(tree)}
		ob_name = ob_string[8:]
		shape_name = ob_name + '_shape'
		if f'loadshape.{shape_name}' in load_map:
			j = load_map.get(f'loadshape.{shape_name}')
			del tree[j]
			load_map = {x.get('object',''):i for i, x in enumerate(tree)}	
	# Write new DSS file.
	dssConvert.treeToDss(tree, output_dss_filename)


def _mg_add_cost(data, mg_name, dss_filename, logger):
	'''
	Write a costed csv of all switches and other upgrades needed to allow the microgrid to operate in islanded mode to support critical loads
	TO DO: When critical load list references actual load buses instead of kw ratings, use the DSS tree structure to find the location of the load
	buses and the SCADA disconnect switches

	:param data: the data
	:type data: MappingProxyType (an immutable dict)
	:param mg_name: the name of a microgrid
	:type mg_name: str
	:param outputCsvName: the name of the output CSV that will contain costs for adding microgrid controls
	:type outputCsvName: str
	:param dss_filename: the name of the DSS file that contains the state of the circuit before new REopt-recommened DSS generation objects have been
		added
	:type dss_filename: str
	:param logger: a logger
	:type logger: Logger
	:rtype: None
	'''
	assert isinstance(data, MappingProxyType)
	assert isinstance(mg_name, str)
	assert isinstance(dss_filename, str)
	assert isinstance(logger, logging.Logger)
	SCADA_COST = 50000
	MG_CONTROL_COST = 100000
	MG_DESIGN_COST = 100000
	mg_loads = data['MICROGRIDS'][mg_name]['loads']
	switch_name = data['MICROGRIDS'][mg_name]['switch']
	# - Apply per-microgrid parameter overrides
	single_phase_relay_cost = data['singlePhaseRelayCost'] if 'singlePhaseRelayCost' not in data['MICROGRIDS'][mg_name]['parameter_overrides'] else data['MICROGRIDS'][mg_name]['parameter_overrides']['singlePhaseRelayCost']
	three_phase_relay_cost = data['threePhaseRelayCost'] if 'threePhaseRelayCost' not in data['MICROGRIDS'][mg_name]['parameter_overrides'] else data['MICROGRIDS'][mg_name]['parameter_overrides']['threePhaseRelayCost']
	tree = dssConvert.dssToTree(dss_filename)
	load_map = {x.get('object',''):i for i, x in enumerate(tree)}
	# - The jsCircuitModel is always optional, but should exist for circuits that were built with the manual circuit editor
	if 'jsCircuitModel' in data:
		jsCircuitModel = {json.loads(s)['name'].lower(): json.loads(s) for s in json.loads(data['jsCircuitModel'])}
	else:
		jsCircuitModel = None
	mg_cost_csv_filename = f'mg_add_cost_{mg_name}.csv'
	with open(mg_cost_csv_filename, 'w', newline='') as outcsv:
		writer = csv.writer(outcsv)
		writer.writerow(['Microgrid','Location', 'Recommended Upgrade', 'Component Count', 'Cost Estimate ($)'])
		writer.writerow([mg_name, mg_name, 'Microgrid Design', '1', MG_DESIGN_COST])
		writer.writerow([mg_name, mg_name, 'Microgrid Controls', '1', MG_CONTROL_COST])
		# for switch in switch_name: # TO DO: iterate through all disconnect points for the mg by going through the DSS file
		writer.writerow([mg_name, switch_name, 'SCADA disconnect switch', '1', SCADA_COST])
		# - If the entire microgrid is a single load (100% critical load), there is no need for metering past SCADA
		#   - 05/06/2024: one load can be a composite of multiple loads, so we don't assume the above statement anymore. Disabled the if-statement
		#if len(mg_loads) > 1:
		for load in mg_loads:
			ob = tree[load_map[f'load.{load}']]
			# print("mg_add_cost() ob:", ob)
			bus_name = ob.get('bus1','')
			bus_name_list = bus_name.split('.')
			load_phases = []
			load_phases = bus_name_list[-(len(bus_name_list)-1):]
			# print("mg_add_cost() load_phases on bus_name: phases", load_phases, "on bus", bus_name)
			if len(load_phases) > 1:
				if jsCircuitModel is None:
					writer.writerow([mg_name, load, "3-phase relay(s)", '1', three_phase_relay_cost])
				else:
					writer.writerow([mg_name, load, "3-phase relay(s)", jsCircuitModel[load]['threePhaseLoadCount'], int(three_phase_relay_cost) * int(jsCircuitModel[load]['threePhaseLoadCount'])])
				three_phase_message = 'Supporting critical loads across microgrids assumes the ability to remotely disconnect 3-phase loads.\n'
				print(three_phase_message)
				logger.warning(three_phase_message)
				if path.exists("user_warnings.txt"):
					with open("user_warnings.txt", "r+") as myfile:
						if three_phase_message not in myfile.read():
							myfile.write(three_phase_message)
				else:
					with open("user_warnings.txt", "a") as myfile:
						myfile.write(three_phase_message)
			else:
				if jsCircuitModel is None:
					writer.writerow([mg_name, load, "AMI disconnect meter(s)", 1, single_phase_relay_cost])
				else:
					writer.writerow([mg_name, load, "AMI disconnect meter(s)", jsCircuitModel[load]['singlePhaseLoadCount'], int(single_phase_relay_cost) * int(jsCircuitModel[load]['singlePhaseLoadCount'])])
				ami_message = 'Supporting critical loads across microgrids assumes an AMI metering system. If not currently installed, add budget for the creation of an AMI system.\n'
				print(ami_message)
				logger.warning(ami_message)
				if path.exists("user_warnings.txt"):
					with open("user_warnings.txt", "r+") as myfile:
						if ami_message not in myfile.read():
							myfile.write(ami_message)
				else:
					with open("user_warnings.txt", "a") as myfile:
						myfile.write(ami_message)


def _microgrid_report_csv(data, mg_name, outputCsvName, logger):
	'''
	Generate a report on each microgrid

	:param data: the data
	:type data: MappingProxyType (an immutable dict)
	:param mg_name: the name of a microgrid
	:type mg_name: str
	:param outputCsvName: the name of the CSV that will contain all of the financial and energy data on a microgrid
	:type outputCsvName: str
	:param logger: a logger
	:type logger: Logger
	:rtype: None
	'''
	assert isinstance(data, MappingProxyType)
	assert isinstance(mg_name, str)
	assert isinstance(outputCsvName, str)
	assert isinstance(logger, logging.Logger)
	microgrid = data['MICROGRIDS'][mg_name]
	reopt_dirname = f'reopt_{mg_name}'
	gen_sizes = _get_gen_ob_from_reopt(reopt_dirname)
	print("microgrid_report_csv() gen_sizes into CSV report:", gen_sizes)
	logger.warning(f"microgrid_report_csv() gen_sizes into CSV report: {gen_sizes}")
	solar_size_total = gen_sizes.get('solar_size_total')
	solar_size_new = gen_sizes.get('solar_size_new')
	solar_size_existing = gen_sizes.get('solar_size_existing')
	fossil_size_total = gen_sizes.get('fossil_size_total')
	fossil_size_new = gen_sizes.get('fossil_size_new')
	fossil_size_existing = gen_sizes.get('fossil_size_existing')
	wind_size_total = gen_sizes.get('wind_size_total')
	wind_size_new = gen_sizes.get('wind_size_new')
	wind_size_existing = gen_sizes.get('wind_size_existing')
	battery_cap_total = gen_sizes.get('battery_cap_total')
	battery_cap_new = gen_sizes.get('battery_cap_new')
	battery_cap_existing = gen_sizes.get('battery_cap_existing')
	battery_pow_total = gen_sizes.get('battery_pow_total')
	battery_pow_new = gen_sizes.get('battery_pow_new')
	battery_pow_existing = gen_sizes.get('battery_pow_existing')
	# if additional battery capacity is being recomended, update kw of new battery to that of existing battery
	if battery_cap_new > 0 and battery_pow_new == 0:
		battery_pow_new = battery_pow_existing
	total_gen = fossil_size_total + solar_size_total + battery_pow_total + wind_size_total
	with open(f'{reopt_dirname}/allOutputData.json') as file:
		output_data = json.load(file)
	# calculate added year 0 costs from mg_add_cost()
	mg_add_cost_df = pd.read_csv(f'mg_add_cost_{mg_name}.csv')
	mg_add_cost = mg_add_cost_df['Cost Estimate ($)'].sum()
	#TODO: Redo post-REopt economic calculations to match updated discounts, taxations, etc
	npv = output_data.get(f'savings1', 0.0) - mg_add_cost # overall npv against the business as usual case from REopt
	cap_ex = output_data.get(f'initial_capital_costs1', 0.0) + mg_add_cost# description from REopt: Up-front capital costs for all technologies, in present value, excluding replacement costs and incentives
	cap_ex_after_incentives = output_data.get(f'initial_capital_costs_after_incentives1', 0.0) + mg_add_cost # description from REopt: Up-front capital costs for all technologies, in present value, excluding replacement costs, including incentives
	#years_of_analysis = output_data.get(f'analysisYears1', 0.0)
	battery_replacement_year = output_data.get(f'batteryCapacityReplaceYear1', 0.0)
	inverter_replacement_year = output_data.get(f'batteryPowerReplaceYear1', 0.0)
	discount_rate = output_data.get(f'discountRate1', 0.0)
	# TODO: Once incentive structure is finalized, update NPV and cap_ex_after_incentives calculation to include depreciation over time if appropriate
	# economic outcomes with the capital costs of existing wind and batteries deducted:
	npv_existing_gen_adj = npv \
		+ wind_size_existing * output_data.get(f'windCost1', 0.0) * .82 \
		+ battery_cap_existing * output_data.get(f'batteryCapacityCost1', 0.0) \
		+ battery_cap_existing * output_data.get(f'batteryCapacityCostReplace1', 0.0) * ((1+discount_rate)**-battery_replacement_year) \
		+ battery_pow_existing * output_data.get(f'batteryPowerCost1', 0.0) \
		+ battery_pow_existing * output_data.get(f'batteryPowerCostReplace1', 0.0) * ((1+discount_rate)**-inverter_replacement_year)
	cap_ex_existing_gen_adj = cap_ex \
		- wind_size_existing * output_data.get(f'windCost1', 0.0) \
		- battery_cap_existing * output_data.get(f'batteryCapacityCost1', 0.0) \
		- battery_cap_existing * output_data.get(f'batteryCapacityCostReplace1', 0.0) * ((1+discount_rate)**-battery_replacement_year) \
		- battery_pow_existing * output_data.get(f'batteryPowerCost1', 0.0) \
		- battery_pow_existing * output_data.get(f'batteryPowerCostReplace1', 0.0) * ((1+discount_rate)**-inverter_replacement_year)
	#TODO: UPDATE cap_ex_after_incentives_existing_gen_adj in 2022 to erase the 18% cost reduction for wind above 100kW as it will have ended
	# TODO: Update the cap_ex_after_incentives_existing_gen_adj with ITC if it becomes available for batteries
	cap_ex_after_incentives_existing_gen_adj = cap_ex_after_incentives \
		- wind_size_existing * output_data.get(f'windCost1', 0.0)*.82 \
		- battery_cap_existing * output_data.get(f'batteryCapacityCost1', 0.0) \
		- battery_cap_existing * output_data.get(f'batteryCapacityCostReplace1', 0.0) * ((1+discount_rate)**-battery_replacement_year) \
		- battery_pow_existing * output_data.get(f'batteryPowerCost1', 0.0) \
		- battery_pow_existing * output_data.get(f'batteryPowerCostReplace1', 0.0) * ((1+discount_rate)**-inverter_replacement_year)
	year_one_OM = output_data.get(f'yearOneOMCostsBeforeTax1', 0.0)
	# When an existing battery and new battery are suggested by the model, need to add back in the existing inverter cost:
	if battery_pow_new == battery_pow_existing and battery_pow_existing != 0:
		npv_existing_gen_adj = npv_existing_gen_adj \
			- battery_pow_existing * output_data.get(f'batteryPowerCost1', 0.0) \
			- battery_pow_existing * output_data.get(f'batteryPowerCostReplace1', 0.0) * ((1+discount_rate)**-inverter_replacement_year)
		cap_ex_existing_gen_adj = cap_ex_existing_gen_adj \
			+ battery_pow_existing * output_data.get(f'batteryPowerCost1', 0.0) \
			+ battery_pow_existing * output_data.get(f'batteryPowerCostReplace1', 0.0) * ((1+discount_rate)**-inverter_replacement_year)
		cap_ex_after_incentives_existing_gen_adj = cap_ex_after_incentives_existing_gen_adj \
			+ battery_pow_existing * output_data.get(f'batteryPowerCost1', 0.0) \
			+ battery_pow_existing * output_data.get(f'batteryPowerCostReplace1', 0.0) * ((1+discount_rate)**-inverter_replacement_year)
	# min_outage = output_data.get(f'minOutage1')
	# if min_outage is not None:
	# 	min_outage = int(round(min_outage))
	# print(f'Minimum Outage Survived (h) for {mg_name}:', min_outage)
	year_one_emissions_reduced = output_data.get(f'yearOneEmissionsReducedPercent1', 0)
	load_series = pd.read_csv(reopt_dirname + '/loadShape.csv', header=None, dtype=np.float64)[0]
	critical_load_series = pd.read_csv(reopt_dirname + '/criticalLoadShape.csv', header=None, dtype=np.float64)[0]
	csv_data = (
		('Microgrid Name', mg_name),
		('Generation Bus', microgrid["gen_bus"]),
		('Minimum 1 hr Load (kW)', round(load_series.min())),
		('Average 1 hr Load (kW)', round(load_series.mean())),
		('Average Daytime 1 hr Load (kW)', round(np.average(np.average(np.array(np.split(load_series.to_numpy(), 365))[:, 9:17], axis=1)))),
		('Maximum 1 hr Load (kW)', round(load_series.max())),
		('Minimum 1 hr Critical Load (kW)', round(critical_load_series.min())),
		('Average 1 hr Critical Load (kW)', round(critical_load_series.mean())),
		('Average Daytime 1 hr Critical Load (kW)', round(np.average(np.average(np.array(np.split(critical_load_series.to_numpy(), 365))[:, 9:17], axis=1)))),
		('Maximum 1 hr Critical Load (kW)', round(critical_load_series.max())),
		('Existing Fossil Generation (kW)', round(fossil_size_existing)),
		('New Fossil Generation (kW)', round(fossil_size_new)),
		# "Diesel Fuel Used During Outage (gal)",
		('Existing Solar (kW)', round(solar_size_existing)),
		('New Solar (kW)', round(solar_size_new)),
		('Existing Battery Power (kW)', round(battery_pow_existing)),
		('Existing Battery Energy Storage (kWh)', round(battery_cap_existing)),
		('New Battery Power (kW)', round(battery_pow_new)),
		('New Battery Energy Storage (kWh)', round(battery_cap_new)),
		('Existing Wind (kW)', round(wind_size_existing)),
		('New Wind (kW)', round(wind_size_new)),
		('Total Generation on Microgrid (kW)', round(total_gen)),
		('Renewable Generation (% of Annual kWh)', round(output_data.get(f'yearOnePercentRenewable1', 0))),
		('Emissions (Yr 1 Tons CO2)', round(output_data.get(f'yearOneEmissionsTons1', 0))),
		('Emissions Reduction (Yr 1 % CO2)', round(year_one_emissions_reduced)),
		('Average Outage Survived (h)', round(output_data.get(f'avgOutage1')) if output_data.get(f'avgOutage1') is not None else None),
		('O+M Costs (Yr 1 $ before tax)', round(year_one_OM)),
		('CapEx ($)', round(cap_ex_existing_gen_adj)),
		('CapEx after Tax Incentives ($)', round(cap_ex_after_incentives_existing_gen_adj)),
		('Net Present Value ($)', round(npv_existing_gen_adj)))
	with open(outputCsvName, 'w', newline='') as outcsv:
		writer = csv.writer(outcsv)
		writer.writerows(zip(*csv_data))


def _get_gen_ob_from_reopt(reopt_dirname):
	'''
	Get generator objects from REopt. Calculate new gen sizes. Returns all gens in a dictionary.
	TODO: To implement multiple same-type existing generators within a single microgrid, will need to implement searching the tree of FULL_NAME to
	find kw ratings of existing gens

	:param reopt_dirname: the name of the REopt directory
	:type reopt_dirname: str
	:return: a dict of the amounts of all new and existing generation types
	:rtype: dict
	'''
	assert isinstance(reopt_dirname, str)
	with open(reopt_dirname + '/allOutputData.json') as file:
		reopt_out = json.load(file)
	mg_num = 1
	gen_sizes = {}
	'''	Notes: Existing solar and diesel are supported natively in REopt.
		SIDE EFFECTS: If additional kwh but not additional kw above existing battery kw is recommended by REopt,
		 gen_sizes will show new batteries with kwh>0 but kw = 0. Is this side effect handled?'''
	solar_size_total = reopt_out.get(f'sizePV{mg_num}', 0.0)
	solar_size_existing = reopt_out.get(f'sizePVExisting{mg_num}', 0.0)
	solar_size_new = solar_size_total - solar_size_existing
	wind_size_total = reopt_out.get(f'sizeWind{mg_num}', 0.0)
	wind_size_existing = reopt_out.get(f'windExisting{mg_num}', 0.0)
	if wind_size_total - wind_size_existing > 0:
		wind_size_new = wind_size_total - wind_size_existing
	else:
		wind_size_new = 0.0
	# calculate additional diesel to be added to existing diesel gen (if any) to adjust kW based on diesel_sizing()
	fossil_size_total = reopt_out.get(f'sizeDiesel{mg_num}', 0.0)
	fossil_size_existing = reopt_out.get(f'sizeDieselExisting{mg_num}', 0.0)
	if fossil_size_total - fossil_size_existing > 0:
		fossil_size_new = fossil_size_total - fossil_size_existing
	else:
		fossil_size_new = 0.0
	# print('get_gen_ob_from_reopt() fossil_size_new:', fossil_size_new)
	# battery capacity refers to the amount of energy that can be stored (kwh)
	battery_cap_total = reopt_out.get(f'capacityBattery{mg_num}', 0.0)
	battery_cap_existing = reopt_out.get(f'batteryKwhExisting{mg_num}', 0.0)
	if battery_cap_total - battery_cap_existing > 0:
		battery_cap_new = battery_cap_total - battery_cap_existing
	else:
		battery_cap_new = 0.0 #TO DO: update logic here to make run more robust to oversized existing battery generation
	# battery power refers to the power rating of the battery's inverter (kw)
	battery_pow_total = reopt_out.get(f'powerBattery{mg_num}', 0.0)
	battery_pow_existing = reopt_out.get(f'batteryKwExisting{mg_num}', 0.0)
	if battery_pow_total - battery_pow_existing > 0:
		battery_pow_new = battery_pow_total - battery_pow_existing
	else:
		battery_pow_new = 0.0 #TO DO: Fix logic so that new batteries cannot add kwh without adding kw
	gen_sizes.update({'solar_size_total':solar_size_total,'solar_size_existing':solar_size_existing, 'solar_size_new':solar_size_new, \
		'wind_size_total':wind_size_total, 'wind_size_existing':wind_size_existing, 'wind_size_new':wind_size_new, \
		'fossil_size_total':fossil_size_total, 'fossil_size_existing':fossil_size_existing, 'fossil_size_new':fossil_size_new, \
		'battery_cap_total':battery_cap_total, 'battery_cap_existing':battery_cap_existing, 'battery_cap_new':battery_cap_new, \
		'battery_pow_total':battery_pow_total, 'battery_pow_existing':battery_pow_existing, 'battery_pow_new':battery_pow_new})
	return gen_sizes


def _make_chart(csvName, circuitFilePath, category_name, x, y_list, year, qsts_steps, chart_name, y_axis_name, ansi_bands=False):
	''' Charting outputs.
	y_list is a list of column headers from csvName including all possible phases
	category_name is the column header for the names of the monitoring object in csvName
	x is the column header of the timestep in csvName
	chart_name is the name of the chart to be displayed'''
	gen_data = pd.read_csv(csvName)
	tree = dssConvert.dssToTree(circuitFilePath)
	data = []
	for ob_name in set(gen_data[category_name]):
		# csv_column_headers = y_list
		# search the tree of the updated circuit to find the phases associate with ob_name
		dss_ob_name = ob_name.split('-')[1]
		the_object = _getByName(tree, dss_ob_name)
		# create phase list, removing neutral phases
		phase_ids = the_object.get('bus1','').replace('.0','').split('.')[1:]
		# when charting objects with the potential for multiple phases, if object is single phase, index out the correct column heading to match the phase
		if len(y_list) == 3 and len(phase_ids) == 1:
			csv_column_headers = []
			csv_column_headers.append(y_list[int(phase_ids[0])-1])
		else:
			csv_column_headers = y_list

		for y_name in csv_column_headers:
			this_series = gen_data[gen_data[category_name] == ob_name]
			trace = go.Scatter(
				x = pd.to_datetime(this_series[x], unit = 'h', origin = pd.Timestamp(f'{year}-01-01')), #TODO: make this datetime convert arrays other than hourly or with a different startdate than Jan 1 if needed
				y = this_series[y_name], # ToDo: rounding to 3 decimals here would be ideal, but doing so does not accept Inf values 
				name = ob_name + '_' + y_name,
				hoverlabel = dict(namelength = -1)
			)
			data.append(trace)
	layout = go.Layout(
		#title = f'{csvName} Output',
		title = chart_name,
		xaxis = dict(title="Date"),
		yaxis = dict(title=y_axis_name),
		#yaxis = dict(title = str(y_list))
		font = dict(family="sans-serif", color="black"),
		legend = dict(orientation='h'))
	fig = go.Figure(data, layout)

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


def _getByName(tree, name):
	''' Return first object with name in tree as an OrderedDict. '''
	matches =[]
	for x in tree:
		if x.get('object',''):
			if x.get('object','').split('.')[1] == name:
				matches.append(x)
	return matches[0]


def _tests():
	# Load lehigh4mg to use as test input
	test_model = 'lehigh4mgs'
	absolute_model_directory = f'{microgridup.PROJ_DIR}/{test_model}'
	# HACK: work in directory because we're very picky about the current dir.
	curr_dir = os.getcwd()
	if curr_dir != absolute_model_directory:
		os.chdir(absolute_model_directory)
	with open('allInputData.json') as file:
		immutable_data = microgridup.get_immutable_dict(json.load(file))
	print(f'----------microgridup_hosting_cap.py testing {test_model}----------')
	mg_names_sorted = sorted(immutable_data['MICROGRIDS'].keys())
	for i in range(0, len(mg_names_sorted)):
		mg_name = mg_names_sorted[i]
		logger = microgridup.setup_logging('logs.log', mg_name)
		if i == 0:
			input_dss_filename = 'circuit.dss'
		else:
			input_dss_filename = f'circuit_plus_{mg_names_sorted[i-1]}.dss'
		if i == len(mg_names_sorted) - 1:
			output_dss_filename = 'circuit_plus_mgAll.dss'
		else:
			output_dss_filename = f'circuit_plus_{mg_name}.dss'
		run(immutable_data, mg_name, input_dss_filename, output_dss_filename, logger)
	run_hosting_capacity()
	os.chdir(curr_dir)
	print('Ran all tests for microgridup_hosting_cap.py.')


if __name__ == '__main__':
	_tests()