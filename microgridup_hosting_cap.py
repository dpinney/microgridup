import csv, json, os
import pandas as pd
import numpy as np
from os import path
from pathlib import Path
from omf.solvers import opendss
from omf.solvers.opendss import dssConvert
from omf.solvers import opendss
import plotly
import plotly.graph_objects as go
import datetime
import microgridup
import omf.models

def _getByName(tree, name):
	''' Return first object with name in tree as an OrderedDict. '''
	matches =[]
	for x in tree:
		if x.get('object',''):
			if x.get('object','').split('.')[1] == name:
				matches.append(x)
	return matches[0]

def get_gen_ob_from_reopt(REOPT_FOLDER):
	''' Get generator objects from REopt. Calculate new gen sizes. Returns all gens in a dictionary.
	TODO: To implement multiple same-type existing generators within a single microgrid, 
	will need to implement searching the tree of FULL_NAME to find kw ratings of existing gens'''
	with open(REOPT_FOLDER + '/allOutputData.json') as file: 
		reopt_out = json.load(file)
	mg_num = 1
	gen_sizes = {}
	'''	Notes: Existing solar and diesel are supported natively in REopt.
		Existing wind and batteries require setting the minimimum generation threshold (windMin, batteryPowerMin, batteryCapacityMin) 
		explicitly to the existing generator sizes in REopt
		SIDE EFFECTS: If additional kwh but not additional kw above existing battery kw is recommended by REopt,
		 gen_sizes will show new batteries with kwh>0 but kw = 0.  This side effect is handled explicitly in '''
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
	# battery power refers to the power rating of the battery's inverter  (kw)
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
	# print("gen_sizes:",gen_sizes)
	return gen_sizes #dictionary of all gen sizes

def mg_phase_and_kv(dss_filename, microgrid, mg_name, logger):
	'''Returns a dict with the phases at the gen_bus and kv 
	of the loads for a given microgrid.
	TODO: If needing to set connection type explicitly, could use this function to check that all "conn=" are the same (wye or empty for default, or delta)'''
	tree = dssConvert.dssToTree(dss_filename)
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
		print("load_phase_list after removal of ground phase:", load_phase_list)
		logger.warning("load_phase_list after removal of ground phase:", load_phase_list)
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
	logger.warning('mg_phase_and_kv out_dict:', out_dict)
	return out_dict
	
def build_new_gen_ob_and_shape(REOPT_FOLDER, GEN_NAME, microgrid, dss_filename, mg_name, logger):
	'''Create new generator objects and shapes. 
	Returns a list of generator objects formatted for reading into openDSS tree.
	SIDE EFFECTS: creates GEN_NAME generator shape
	TODO: To implement multiple same-type existing generators within a single microgrid, 
	will need to implement searching the tree of FULL_NAME to find kw ratings of existing gens'''
	gen_sizes = get_gen_ob_from_reopt(REOPT_FOLDER)
	# print("build_new_gen_ob_and_shape() gen_sizes into OpenDSS:", gen_sizes)
	with open(REOPT_FOLDER + '/allOutputData.json') as file:
		reopt_out = json.load(file)
	gen_df_builder = pd.DataFrame()
	gen_obs = []
	mg_num = 1
	#print("microgrid:", microgrid)
	phase_and_kv = mg_phase_and_kv(dss_filename, microgrid, mg_name, logger)
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

    # - TODO: can I remove this?
	# remove 1 kw new fossil if built as an artifact of feedback_reopt_gen_values()
	if fossil_size_new < 1.01 and fossil_size_new > 0.99:
		fossil_size_new = 0
		fossil_size_total -= fossil_size_new
    # - TODO: can I remove this?

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
	gen_df_builder.to_csv(GEN_NAME, index=False)
	return gen_obs


def mg_add_cost(outputCsvName, microgrid, mg_name, dss_filename, logger, SINGLE_PHASE_RELAY_COST, THREE_PHASE_RELAY_COST):
	'''Returns a costed csv of all switches and other upgrades needed to allow the microgrid 
	to operate in islanded mode to support critical loads
	TO DO: When critical load list references actual load buses instead of kw ratings,
	use the DSS tree structure to find the location of the load buses and the SCADA disconnect switches'''
	SCADA_COST = 50000
	MG_CONTROL_COST = 100000
	MG_DESIGN_COST = 100000
	mg_loads = microgrid['loads']
	switch_name = microgrid['switch']
	tree = dssConvert.dssToTree(dss_filename)
	load_map = {x.get('object',''):i for i, x in enumerate(tree)}
	# print out a csv of the 
	with open(outputCsvName, 'w', newline='') as outcsv:
		writer = csv.writer(outcsv)
		writer.writerow(["Microgrid","Location", "Recommended Upgrade", "Cost Estimate ($)"])
		writer.writerow([mg_name, mg_name, "Microgrid Design", MG_DESIGN_COST])
		writer.writerow([mg_name, mg_name, "Microgrid Controls", MG_CONTROL_COST])
		# for switch in switch_name: # TO DO: iterate through all disconnect points for the mg by going through the DSS file
		writer.writerow([mg_name, switch_name, "SCADA disconnect switch", SCADA_COST])
		if len(mg_loads) > 1: # if the entire microgrid is a single load (100% critical load), there is no need for metering past SCADA
			for load in mg_loads:
				ob = tree[load_map[f'load.{load}']]
				# print("mg_add_cost() ob:", ob)
				bus_name = ob.get('bus1','')
				bus_name_list = bus_name.split('.')
				load_phases = []
				load_phases = bus_name_list[-(len(bus_name_list)-1):]
				# print("mg_add_cost() load_phases on bus_name: phases", load_phases, "on bus", bus_name)
				if len(load_phases) > 1:
					writer.writerow([mg_name, load, "3-phase relay", THREE_PHASE_RELAY_COST])
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
					writer.writerow([mg_name, load, "AMI disconnect meter", SINGLE_PHASE_RELAY_COST])
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

def make_full_dss(input_dss_filename, GEN_NAME, LOAD_NAME, output_dss_filename, gen_obs, microgrid):
	''' insert generation objects into dss.
	ASSUMPTIONS: 
	SIDE EFFECTS: writes FULL_NAME dss'''
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
		gen_df = pd.read_csv(GEN_NAME)
	except Exception:
		# - This microgrid has no new or existing generation objects (probably because there were no critical loads in the microgrid), so
		#   "generation.csv" is empty
		gen_df = pd.DataFrame()
	load_df = pd.read_csv(LOAD_NAME)
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
			# insert loadshape for new generators with shape_data in GEN_NAME
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
			# insert loadshapes for new storage objects with shape_data in GEN_NAME
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

def microgrid_report_csv(inputName, outputCsvName, REOPT_FOLDER, microgrid, mg_name, ADD_COST_NAME, logger):
	''' Generate a report on each microgrid '''
	with open(REOPT_FOLDER + inputName) as file:
		reopt_out = json.load(file)
	gen_sizes = get_gen_ob_from_reopt(REOPT_FOLDER)
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
	# load = pd.read_csv(REOPT_FOLDER + '/loadShape.csv',header = None)
	load = []
	with open(REOPT_FOLDER + '/loadShape.csv', newline = '') as csvfile:
		load_reader = csv.reader(csvfile, delimiter = ' ')
		for row in load_reader:
			load.append(float(row[0]))

	with open(outputCsvName, 'w', newline='') as outcsv:
		writer = csv.writer(outcsv)
		writer.writerow(["Microgrid Name", "Generation Bus", "Minimum 1 hr Load (kW)", "Average 1 hr Load (kW)",
			"Average Daytime 1 hr Load (kW)", 
			"Maximum 1 hr Load (kW)", "Maximum 1 hr Critical Load (kW)", 
			"Existing Fossil Generation (kW)", "New Fossil Generation (kW)",
			# "Diesel Fuel Used During Outage (gal)", 
			"Existing Solar (kW)", "New Solar (kW)", 
			"Existing Battery Power (kW)", "Existing Battery Energy Storage (kWh)", "New Battery Power (kW)",
			"New Battery Energy Storage (kWh)", "Existing Wind (kW)", "New Wind (kW)", 
			"Total Generation on Microgrid (kW)", "Renewable Generation (% of Annual kWh)", "Emissions (Yr 1 Tons CO2)", 
			"Emissions Reduction (Yr 1 % CO2)", "Average Outage Survived (h)",
			"O+M Costs (Yr 1 $ before tax)",
			"CapEx ($)", "CapEx after Tax Incentives ($)", "Net Present Value ($)"])
		mg_num = 1 # mg_num refers to the dict key suffix in allOutputData.json from reopt folder
		gen_bus_name = microgrid['gen_bus']
		#load = reopt_out.get(f'load{mg_num}', 0.0)
		min_load = round(min(load))
		ave_load = round(sum(load)/len(load))
		np_load = np.array_split(load, 365)
		np_load = np.array(np_load) #a flattened array of 365 arrays of 24 hours each
		daytime_kwh = np_load[:,9:17] #365 8-hour daytime arrays
		avg_daytime_load = int(np.average(np.average(daytime_kwh, axis=1)))
		max_load = round(max(load))
		# do not show the 1kw fossil that is a necessary artifact of final run of REopt
		#diesel_used_gal =reopt_out.get(f'fuelUsedDiesel{mg_num}', 0.0)
		fossil_output_one_kw = False
		if fossil_size_new < 1.01 and fossil_size_new > 0.99:
			fossil_output_one_kw = True
			fossil_size_total = fossil_size_total - fossil_size_new
			fossil_size_new = 0
		total_gen = fossil_size_total + solar_size_total + battery_pow_total + wind_size_total
		renewable_gen = reopt_out.get(f'yearOnePercentRenewable{mg_num}', 0.0)
		year_one_emissions = reopt_out.get(f'yearOneEmissionsTons{mg_num}', 0.0)
		year_one_emissions_reduced = reopt_out.get(f'yearOneEmissionsReducedPercent{mg_num}', 0.0)
		# print("year_one_emissions_reduced:", year_one_emissions_reduced)
		if year_one_emissions_reduced < 0:
			year_one_emissions_reduced = 0
		# print("year_one_emissions_reduced after 0 condition:", year_one_emissions_reduced)
		# calculate added year 0 costs from mg_add_cost()
		mg_add_cost_df = pd.read_csv(ADD_COST_NAME)
		mg_add_cost = mg_add_cost_df['Cost Estimate ($)'].sum()
		# print('mg_add_cost:',mg_add_cost)
		#TODO: Redo post-REopt economic calculations to match updated discounts, taxations, etc
		npv = reopt_out.get(f'savings{mg_num}', 0.0) - mg_add_cost # overall npv against the business as usual case from REopt
		cap_ex = reopt_out.get(f'initial_capital_costs{mg_num}', 0.0) + mg_add_cost# description from REopt: Up-front capital costs for all technologies, in present value, excluding replacement costs and incentives
		cap_ex_after_incentives = reopt_out.get(f'initial_capital_costs_after_incentives{mg_num}', 0.0) + mg_add_cost # description from REopt: Up-front capital costs for all technologies, in present value, excluding replacement costs, including incentives
		#years_of_analysis = reopt_out.get(f'analysisYears{mg_num}', 0.0)
		battery_replacement_year = reopt_out.get(f'batteryCapacityReplaceYear{mg_num}', 0.0)
		inverter_replacement_year = reopt_out.get(f'batteryPowerReplaceYear{mg_num}', 0.0)
		discount_rate = reopt_out.get(f'discountRate{mg_num}', 0.0)
		# TODO: Once incentive structure is finalized, update NPV and cap_ex_after_incentives calculation to include depreciation over time if appropriate
		# economic outcomes with the capital costs of existing wind and batteries deducted:
		npv_existing_gen_adj = npv \
			+ wind_size_existing * reopt_out.get(f'windCost{mg_num}', 0.0) * .82 \
			+ battery_cap_existing * reopt_out.get(f'batteryCapacityCost{mg_num}', 0.0) \
			+ battery_cap_existing * reopt_out.get(f'batteryCapacityCostReplace{mg_num}', 0.0) * ((1+discount_rate)**-battery_replacement_year) \
			+ battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0) \
			+ battery_pow_existing * reopt_out.get(f'batteryPowerCostReplace{mg_num}', 0.0) * ((1+discount_rate)**-inverter_replacement_year)
		cap_ex_existing_gen_adj = cap_ex \
			- wind_size_existing * reopt_out.get(f'windCost{mg_num}', 0.0) \
			- battery_cap_existing * reopt_out.get(f'batteryCapacityCost{mg_num}', 0.0) \
			- battery_cap_existing * reopt_out.get(f'batteryCapacityCostReplace{mg_num}', 0.0) * ((1+discount_rate)**-battery_replacement_year) \
			- battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0) \
			- battery_pow_existing * reopt_out.get(f'batteryPowerCostReplace{mg_num}', 0.0) * ((1+discount_rate)**-inverter_replacement_year)
		#TODO: UPDATE cap_ex_after_incentives_existing_gen_adj in 2022 to erase the 18% cost reduction for wind above 100kW as it will have ended
		# TODO: Update the cap_ex_after_incentives_existing_gen_adj with ITC if it becomes available for batteries
		cap_ex_after_incentives_existing_gen_adj = cap_ex_after_incentives \
			- wind_size_existing * reopt_out.get(f'windCost{mg_num}', 0.0)*.82 \
			- battery_cap_existing * reopt_out.get(f'batteryCapacityCost{mg_num}', 0.0) \
			- battery_cap_existing * reopt_out.get(f'batteryCapacityCostReplace{mg_num}', 0.0) * ((1+discount_rate)**-battery_replacement_year) \
			- battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0) \
			- battery_pow_existing * reopt_out.get(f'batteryPowerCostReplace{mg_num}', 0.0) * ((1+discount_rate)**-inverter_replacement_year)
		year_one_OM = reopt_out.get(f'yearOneOMCostsBeforeTax{mg_num}', 0.0)
		# When an existing battery and new battery are suggested by the model, need to add back in the existing inverter cost:
		if battery_pow_new == battery_pow_existing and battery_pow_existing != 0: 
			npv_existing_gen_adj = npv_existing_gen_adj \
				- battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0) \
				- battery_pow_existing * reopt_out.get(f'batteryPowerCostReplace{mg_num}', 0.0) * ((1+discount_rate)**-inverter_replacement_year)
			cap_ex_existing_gen_adj = cap_ex_existing_gen_adj \
				+ battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0) \
				+ battery_pow_existing * reopt_out.get(f'batteryPowerCostReplace{mg_num}', 0.0) * ((1+discount_rate)**-inverter_replacement_year)
			cap_ex_after_incentives_existing_gen_adj = cap_ex_after_incentives_existing_gen_adj \
				+ battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0) \
				+ battery_pow_existing * reopt_out.get(f'batteryPowerCostReplace{mg_num}', 0.0) * ((1+discount_rate)**-inverter_replacement_year)
		# take away the 1kw fossil gen cost if necessary
		if fossil_output_one_kw == True:
			cap_ex_existing_gen_adj = cap_ex_existing_gen_adj - 1*reopt_out.get(f'dieselGenCost{mg_num}', 0.0)
			cap_ex_after_incentives_existing_gen_adj = cap_ex_after_incentives_existing_gen_adj - 1*reopt_out.get(f'dieselGenCost{mg_num}', 0.0)
			#TODO: Calculate NPV with O+M costs properly depreciated over time if needed; Need to pull in the discount rate;
			npv_existing_gen_adj = npv_existing_gen_adj + 1*reopt_out.get(f'dieselGenCost{mg_num}', 0.0) # - years_of_analysis*reopt_out.get(f'dieselOMCostKw{mg_num}', 0.0)- years_of_analysis*1/fossil_size_total*sum(reopt_out.get(f'powerDiesel{mg_num}', 0.0))*reopt_out.get(f'dieselOMCostKwh{mg_num}', 0.0)
			# subtract the added O+M cost of the 1 kw fossil; fossil_size_total already has the 1kw subtracted in this function
			if fossil_size_total == 0:
				year_one_OM = year_one_OM - 1*reopt_out.get(f'dieselOMCostKw{mg_num}', 0.0)-sum(reopt_out.get(f'powerDiesel{mg_num}', 0.0))*reopt_out.get(f'dieselOMCostKwh{mg_num}', 0.0)			
			elif fossil_size_total != 0:
				year_one_OM = year_one_OM - 1*reopt_out.get(f'dieselOMCostKw{mg_num}', 0.0)-1/fossil_size_total*sum(reopt_out.get(f'powerDiesel{mg_num}', 0.0))*reopt_out.get(f'dieselOMCostKwh{mg_num}', 0.0)		
		# min_outage = reopt_out.get(f'minOutage{mg_num}')
		# if min_outage is not None:
		# 	min_outage = int(round(min_outage))
		# print(f'Minimum Outage Survived (h) for {mg_name}:', min_outage)
		avg_outage = reopt_out.get(f'avgOutage{mg_num}')
		if avg_outage is not None:
			avg_outage = int(round(avg_outage))
		critical_load_series = pd.read_csv(REOPT_FOLDER + '/criticalLoadShape.csv', header=None)[0]
		row = [str(mg_name), microgrid["gen_bus"], min_load, ave_load, round(avg_daytime_load),
			max_load, round(critical_load_series.max()),
			round(fossil_size_existing), round(fossil_size_new), # round(diesel_used_gal),
			round(solar_size_existing),
			round(solar_size_new), round(battery_pow_existing), round(battery_cap_existing), round(battery_pow_new),
			round(battery_cap_new), round(wind_size_existing), round(wind_size_new), round(total_gen), round(renewable_gen),
			round(year_one_emissions), round(year_one_emissions_reduced), avg_outage,
			int(round(year_one_OM)), int(round(cap_ex_existing_gen_adj)), int(round(cap_ex_after_incentives_existing_gen_adj)), int(round(npv_existing_gen_adj))]
		writer.writerow(row)
		# print("row:", row)
	

def make_chart(csvName, circuitFilePath, category_name, x, y_list, year, qsts_steps, chart_name, y_axis_name, ansi_bands=False):
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

def gen_powerflow_results(CIRCUIT_FILE, YEAR, QSTS_STEPS, logger):
	''' Generate full powerflow results on a given circuit. '''
	print('QSTS with ', CIRCUIT_FILE, 'AND CWD IS ', os.getcwd())
	logger.warning(f'QSTS with {CIRCUIT_FILE} AND CWD IS {os.getcwd()}')
	opendss.newQstsPlot(CIRCUIT_FILE,
		stepSizeInMinutes=60, 
		numberOfSteps=QSTS_STEPS,
		keepAllFiles=False,
		actions={},
		filePrefix='timeseries')
	make_chart('timeseries_gen.csv', CIRCUIT_FILE, 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], YEAR, QSTS_STEPS, "Generator Output", "Average hourly kW")
	make_chart('timeseries_load.csv', CIRCUIT_FILE, 'Name', 'hour', ['V1(PU)','V2(PU)','V3(PU)'], YEAR, QSTS_STEPS, "Load Voltage", "PU", ansi_bands = True)
	make_chart('timeseries_source.csv', CIRCUIT_FILE, 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], YEAR, QSTS_STEPS, "Voltage Source Output", "Average hourly kW")
	try:
		make_chart('timeseries_control.csv', CIRCUIT_FILE, 'Name', 'hour', ['Tap(pu)'], YEAR, QSTS_STEPS, "Tap Position", "PU")
	except:
		pass #TODO: better detection of missing control data.

def run(REOPT_FOLDER_FINAL, GEN_NAME, microgrid, input_dss_filename, mg_name, LOAD_NAME, output_dss_filename, ADD_COST_NAME, logger, REOPT_INPUTS):
	gen_obs = build_new_gen_ob_and_shape(REOPT_FOLDER_FINAL, GEN_NAME, microgrid, input_dss_filename, mg_name, logger)
	make_full_dss(input_dss_filename, GEN_NAME, LOAD_NAME, output_dss_filename, gen_obs, microgrid)
	# Generate microgrid control hardware costs.
	mg_add_cost(ADD_COST_NAME, microgrid, mg_name, input_dss_filename, logger, int(REOPT_INPUTS['single_phase_relay_cost']), int(REOPT_INPUTS['three_phase_relay_cost']))
	microgrid_report_csv('/allOutputData.json', f'ultimate_rep_{output_dss_filename}.csv', REOPT_FOLDER_FINAL, microgrid, mg_name, ADD_COST_NAME, logger)

def get_microgrid_coordinates(dss_path, microgrid):
	tree = dssConvert.dssToTree(dss_path)
	evil_glm = dssConvert.evilDssTreeToGldTree(tree)
	# using evil_glm to get around the fact that buses in openDSS are created in memory and do not exist in the BASE_NAME dss file
	for ob in evil_glm.values():
		ob_name = ob.get('name','')
		ob_type = ob.get('object','')
		# pull out long and lat of the gen_bus
		if ob_type == "bus" and ob_name == microgrid['gen_bus']:
			ob_lat = ob.get('latitude','')
			ob_long = ob.get('longitude','')
			return (ob_lat, ob_long)
	raise Exception("Couldn't determine microgrid latitude and longitude")

def get_microgrid_existing_generation_dict(dss_path, microgrid):
	tree = dssConvert.dssToTree(dss_path)
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
		'battery_kw_existing': sum(battery_kw_existing),
		'battery_kwh_existing': sum(battery_kwh_existing),
		'solar_kw_existing': sum(solar_kw_existing),
		'wind_kw_existing': sum(wind_kw_existing),
		'fossil_kw_existing': sum(fossil_kw_existing)
	}

def run_hosting_capacity(dss_filename):
	'''
	Run the traditional algorithm in omf.models.hostingCapacity() on the initial dss file

	:type dss_filename: str
	:param dss_filename: the filename of the dss file (e.g. circuit_plusmg_{i}.dss)
	:rtype: None
	'''
	assert type(dss_filename) == str
	omf.models.hostingCapacity.new('hosting_capacity')
	with open('hosting_capacity/allInputData.json') as f:
		all_input_data = json.load(f)
	# - Disable AMI algorithm
	all_input_data['runAmiAlgorithm'] = 'off'
	# - Remove omd file that was copied by default into the hosting_capacity/ directory because we replace it with a different omd
	os.remove(f"hosting_capacity/{all_input_data['feederName1']}.omd")
	# - Create and set the new omd file
	dssConvert.dssToOmd(dss_filename, f'hosting_capacity/{dss_filename}.omd')
	all_input_data['feederName1'] = dss_filename
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
	omf.models.__neoMetaModel__.runForeground('hosting_capacity')
	with open('hosting_capacity/allOutputData.json') as f:
		data = json.load(f)
	# - Organize graph data
	kw_capacity_per_bus = data['traditionalHCResults']
	tree = dssConvert.dssToTree(dss_filename)
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
	non_violation_rows = df[(df['thermal_violation'] == False) & (df['voltage_violation'] == False)]
	voltage_violation_rows = df[(df['thermal_violation'] == False) & (df['voltage_violation'] == True)]
	thermal_violation_rows = df[(df['thermal_violation'] == True) & (df['voltage_violation'] == False)]
	duel_violation_rows = df[(df['thermal_violation'] == True) & (df['voltage_violation'] == True)]
	fig = go.Figure(data=[
		go.Bar(name='Bus Existing kW Load', x=df['bus'], y=df['load_kw'], marker_color='purple', hovertemplate='<br>'.join(['bus: %{x}', 'Bus Existing kW Load: %{y}'])),
		go.Bar(name='Bus Existing kW Generation', x=df['bus'], y=df['generation_kw'], marker_color='blue', hovertemplate='<br>'.join(['bus: %{x}', 'Bus Existing kW Generation: %{y}'])),
		go.Bar(name='Bus Max kW Capacity', x=non_violation_rows['bus'], y=non_violation_rows['max_kw'], marker_color='green', hovertemplate='<br>'.join(['bus: %{x}', 'Bus Max kW Capacity: %{y}'])),
		go.Bar(name='Bus Voltage Violation kW', x=voltage_violation_rows['bus'], y=voltage_violation_rows['max_kw'], marker_color='yellow', hovertemplate='<br>'.join(['bus: %{x}', 'Bus Voltage Violation kW: %{y}'])),
		go.Bar(name='Bus Thermal Violation kW', x=thermal_violation_rows['bus'], y=thermal_violation_rows['max_kw'], marker_color='orange', hovertemplate='<br>'.join(['bus: %{x}', 'Bus Thermal Violation kW: %{y}'])),
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

def _tests():
	# Load arguments from JSON.
	with open('testfiles/test_params.json') as file:
		test_params = json.load(file)
	control_test_args = test_params['control_test_args']
	# Setup paths.
	MGU_FOLDER = os.path.abspath(os.path.dirname(__file__))
	if MGU_FOLDER == '/':
		MGU_FOLDER = '' #workaround for docker root installs
	PROJ_FOLDER = f'{MGU_FOLDER}/data/projects'
	# TESTING DIRECTORY.
	_dir = 'lehigh4mgs' # Change to test on different directory.
	MODEL_DIR = f'{PROJ_FOLDER}/{_dir}'
	# HACK: work in directory because we're very picky about the current dir.
	curr_dir = os.getcwd()
	workDir = os.path.abspath(MODEL_DIR)
	if curr_dir != workDir:
		os.chdir(workDir)
	microgrids = control_test_args[_dir]
	logger = microgridup.setup_logging(f'{MGU_FOLDER}/logs.txt')
	# As many tests per directory as there are microgrids/REopt API calls per directory.
	mg_names_sorted = sorted(microgrids.keys())
	REOPT_INPUTS = {
		'single_phase_relay_cost': 300,
		'three_phase_relay_cost': 20000
	}
	for i in range(0, len(mg_names_sorted)):
		mg_name = mg_names_sorted[i]
		if i == 0:
			BASE_DSS = 'circuit.dss'
		else:
			BASE_DSS = f'circuit_plus_{mg_names_sorted[i-1]}.dss'
		if i == len(mg_names_sorted) - 1:
			output_dss_filename = 'circuit_plus_mgAll.dss'
		else:
			output_dss_filename = f'circuit_plus_{mg_name}.dss'
		run(f'reopt_{mg_name}', 'generation.csv', microgrids[mg_name], BASE_DSS, mg_name, 'loads.csv', output_dss_filename, f'mg_add_cost_{mg_name}.csv', logger, REOPT_INPUTS)
	os.chdir(curr_dir)

if __name__ == '__main__':
	_tests()