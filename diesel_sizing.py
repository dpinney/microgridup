import json
import pandas as pd
import numpy as np
import csv
from os.path import join as pJoin
from omf.solvers import opendss
from omf.solvers.opendss import dssConvert

# pulling from results.json
# def diesel_min_size(REOPT_FOLDER):
# 	''' A quick way to calculate max load needing to be covered by diesel in an outage.
# 	This method assumes only solar generation and no support from battery
# 	to model the worst case long term outage.'''
# 	with open(pJoin(REOPT_FOLDER, 'results.json')) as jsonFile:
# 		results = json.load(jsonFile)
# 	resultsSubset = results['outputs']['Scenario']['Site']
# 	load_df = pd.DataFrame()
# 	load_df['total_load'] = pd.Series(resultsSubset['LoadProfile']['year_one_electric_load_series_kw'])
# 	load_df['solar_gen'] = pd.Series(resultsSubset['PV']['year_one_power_production_series_kw'])
# 	load_df['remaining_load'] = load_df['total_load']-load_df['solar_gen']
# 	# max load in loadshape
# 	max_load = max(load_df['total_load'])
# 	# diesel size recommended by REopt
# 	diesel_REopt = resultsSubset['Generator']['size_kw']
# 	# diesel size needed for uninterupted power throughout the year
# 	diesel_uninterrupted = max(load_df['remaining_load'])
# 	#print(load_df)
# 	print("Max total load for", REOPT_FOLDER, ":", max_load)
# 	print("Max load needed to be supported by diesel for", REOPT_FOLDER, ":", diesel_uninterrupted)
# 	print("% more kW diesel needed than recommended by REopt for", REOPT_FOLDER, ":", (diesel_uninterrupted - diesel_REopt)/diesel_REopt)
# 	return diesel_uninterrupted

# if __name__ == '__main__':
# 	diesel_min_size('lehigh_reopt_1')
# 	diesel_min_size('lehigh_reopt_2')
# 	diesel_min_size('lehigh_reopt_3')
# 	diesel_min_size('lehigh_reopt_4')

# pulling from allOutputData.json
def max_net_load(inputName, REOPT_FOLDER):
	''' A quick way to calculate max net load needing to be covered by diesel 
	generation in an outage. This method assumes only solar, wind and diesel generation 
	when islanded from main grid, with no support from battery to model 
	the worst case long term outage. '''
	reopt_out = json.load(open(REOPT_FOLDER + inputName))
	mg_num = 1
	load_df = pd.DataFrame()
	load_df['total_load'] = pd.Series(reopt_out.get(f'load{mg_num}', np.zeros(8760)))
	load_df['solar_shape'] = pd.Series(reopt_out.get(f'powerPV{mg_num}', np.zeros(8760)))
	load_df['wind_shape'] = pd.Series(reopt_out.get(f'powerWind{mg_num}', np.zeros(8760)))
	load_df['net_load'] = load_df['total_load']-load_df['solar_shape']-load_df['wind_shape']
	# max load in loadshape
	max_total_load = max(load_df['total_load'])
	# max net load not covered by solar or wind
	# Equivalent to diesel size needed for uninterupted power throughout the year
	max_net_load = max(load_df['net_load'])
	# diesel size recommended by REopt
	diesel_REopt = reopt_out.get(f'sizeDiesel{mg_num}', 0.0)
	# print(load_df)
	print("Max total load for", REOPT_FOLDER, ":", max_total_load)
	print("Max load needed to be supported by diesel for", REOPT_FOLDER, ":", max_net_load)
	print("% more kW diesel needed than recommended by REopt for", REOPT_FOLDER, ":", round(100*(max_net_load - diesel_REopt)/diesel_REopt))
	return max_net_load


def diesel_sizing(inputName, REOPT_FOLDER, DIESEL_SAFETY_FACTOR, max_net_load):
	''' Calculate total diesel kW needed to meet max net load at all hours of the year
	plus a user-inputted design safety factor'''
	reopt_out = json.load(open(REOPT_FOLDER + inputName))
	mg_num = 1
	diesel_total_REopt = reopt_out.get(f'sizeDiesel{mg_num}', 0.0)
	if max_net_load >= diesel_total_REopt:
		diesel_total_calc = max_net_load*(1+DIESEL_SAFETY_FACTOR)
	elif max_net_load < diesel_total_REopt:
		diesel_total_calc = diesel_total_REopt*(1+DIESEL_SAFETY_FACTOR)
	print(diesel_total_calc,"kW diesel_total_calc is", round(100*(diesel_total_calc-diesel_total_REopt)/diesel_total_REopt), "% more kW diesel than recommended by REopt for", REOPT_FOLDER)
	return diesel_total_calc

def mg_phase_and_kv(BASE_NAME, microgrid):
	'''Checks to make sure gen_obs_existing and loads have the 
	same kv and phases supported on the gen_bus of a given microgrid.
	Returns a dict with the phases and kv of a given microgrid'''
	tree = dssConvert.dssToTree(BASE_NAME)
	mg_ob = microgrid
	gen_bus_name = mg_ob['gen_bus']
	mg_loads = mg_ob['loads']
	# define the voltage on the gen_bus to match all loads on the gen_bus; Throw an error if they do not match
	load_phase_list = []
	gen_bus_kv = []
	#TODO: for efficiency, can I build a mapping of the object names from the tree, and then get that item from the map/dict?

	for load_name in mg_loads:
		for i, ob in enumerate(tree):
			ob_string = ob.get('object','')
			if ob_string.startswith('load.'):
				ob_name = ob_string[5:]
				if ob_name == load_name:
					# find the phase of the load
					bus_name = ob.get('bus1','')
					bus_name_list = bus_name.split('.')
					load_phases = []
					load_phases = bus_name_list[-(len(bus_name_list)-1):]
					for phase in load_phases:
						if phase not in load_phase_list:
							load_phase_list.append(phase)
					# set the voltage for the gen_bus and check that all loads match in voltage
					load_kv = ob.get('kv','')
					if load_kv not in gen_bus_kv and len(gen_bus_kv) > 0:
						raise Exception(f'More than one load voltage is specified on gen_bus {gen_bus_name}. Check voltage of {load_name}.')
					elif load_kv not in gen_bus_kv and len(gen_bus_kv) == 0:
						gen_bus_kv = load_kv
	load_phase_list.sort()
	out_dict = {}
	out_dict['gen_bus'] = gen_bus_name
	out_dict['phases'] = load_phase_list
	out_dict['kv'] = gen_bus_kv
	#print('out_dict', out_dict)
	return out_dict

def get_gen_ob_from_reopt(REOPT_FOLDER, diesel_total_calc=False):
	''' Get generator objects from REopt. Calculate new gen sizes, using updated diesel size 
	from diesel_total_calc if True. Returns all gens in a dictionary.
	TODO: To implement multiple same-type existing generators within a single microgrid, 
	will need to implement searching the tree of FULL_NAME to find kw ratings of existing gens'''
	reopt_out = json.load(open(REOPT_FOLDER + '/allOutputData.json'))
	mg_num = 1
	gen_sizes = {}
	'''	Notes: Existing solar and diesel are supported natively in REopt.
		diesel_total_calc is used to set the total amount of diesel generation.
		Existing wind and batteries require setting the minimimum generation threshold (windMin, batteryPowerMin, batteryCapacityMin) in REopt'''
	solar_size_total = reopt_out.get(f'sizePV{mg_num}', 0.0)
	solar_size_existing = reopt_out.get(f'sizePVExisting{mg_num}', 0.0)
	solar_size_new = solar_size_total - solar_size_existing
	wind_size_total = reopt_out.get(f'sizeWind{mg_num}', 0.0) # TO DO: Update size of wind based on existing generation once we find a way to get a loadshape for that wind if REopt recommends no wind
	wind_size_existing = reopt_out.get(f'windExisting{mg_num}', 0.0)
	if wind_size_total - wind_size_existing > 0:
		wind_size_new = wind_size_total - wind_size_existing 
	else:
		wind_size_new = 0 #TO DO: update logic here to make run more robust to oversized existing wind gen	
	# calculate additional diesel to be added to existing diesel gen (if any) to adjust kW based on diesel_sizing()
	if diesel_total_calc == False:
		diesel_size_total = reopt_out.get(f'sizeDiesel{mg_num}', 0.0)
	else:
		diesel_size_total = diesel_total_calc
	diesel_size_existing = reopt_out.get(f'sizeDieselExisting{mg_num}', 0.0)
	if diesel_size_total - diesel_size_existing > 0:
		diesel_size_new = diesel_size_total - diesel_size_existing
	else:
		diesel_size_new = 0	
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

	gen_sizes.update({'solar_size_total':solar_size_total,'solar_size_existing':solar_size_existing, 'solar_size_new':solar_size_new, \
		'wind_size_total':wind_size_total, 'wind_size_existing':wind_size_existing, 'wind_size_new':wind_size_new, \
		'diesel_size_total':diesel_size_total, 'diesel_size_existing':diesel_size_existing, 'diesel_size_new':diesel_size_new, \
		'battery_cap_total':battery_cap_total, 'battery_cap_existing':battery_cap_existing, 'battery_cap_new':battery_cap_new, \
		'battery_pow_total':battery_pow_total, 'battery_pow_existing':battery_pow_existing, 'battery_pow_new':battery_pow_new})

	return gen_sizes #dictionary of all gen sizes

def set_reopt_gen_values():
	pass

def build_new_gen_ob_and_shape(REOPT_FOLDER, GEN_NAME, microgrid, gen_sizes, BASE_NAME):
	'''Create new generator objects and shapes. 
	Returns a list of generator objects formatted for reading into openDSS tree.
	SIDE EFFECTS: creates GEN_NAME generator shape
	TODO: To implement multiple same-type existing generators within a single microgrid, 
	will need to implement searching the tree of FULL_NAME to find kw ratings of existing gens'''

	reopt_out = json.load(open(REOPT_FOLDER + '/allOutputData.json'))
	gen_obs = []
	mg_num = 1
	mg_ob = microgrid
	gen_bus_name = mg_ob['gen_bus']
	gen_obs_existing = mg_ob['gen_obs_existing']
	phase_and_kv = mg_phase_and_kv(BASE_NAME, microgrid)
	
	# Build new solar gen objects and loadshapes
	solar_size_total = gen_sizes.get(solar_size_total)
	solar_size_new = gen_sizes.get(solar_size_new)
	solar_size_existing = gen_sizes.get(solar_size_existing)
	if solar_size_new > 0:
		gen_obs.append({
			'!CMD': 'new',
			'object':f'generator.solar_{gen_bus_name}',
			'bus1':f"{gen_bus_name}.{'.'.join(phase_and_kv['phases'])}",
			'phases':len(phase_and_kv['phases']),
			'kv':phase_and_kv['kv'],
			'kw':f'{solar_size_new}',
			'pf':'1'
		})
		# 0-1 scale the power output loadshape to the total generation kw of that type of generator using pandas
		gen_df_builder[f'solar_{gen_bus_name}'] = pd.Series(reopt_out.get(f'powerPV{mg_num}'))/solar_size_total*solar_size_new
	# build loadshapes for existing generation from BASE_NAME, inputting the 0-1 solar generation loadshape and scaling by their rated kw
	if solar_size_existing > 0:
		for gen_ob_existing in gen_obs_existing:
			if gen_ob_existing.startswith('solar_'):
				gen_df_builder[f'{gen_ob_existing}'] = pd.Series(reopt_out.get(f'powerPV{mg_num}'))/solar_size_total*solar_size_existing 
				#HACK Implemented: TODO: IF multiple existing solar generator objects are in gen_obs, we need to scale the output loadshapes by their rated kW 
	
	# Build new diesel gen objects and loadshapes
	diesel_size_total = gen_sizes.get(diesel_size_total)
	diesel_size_new = gen_sizes.get(diesel_size_new)
	diesel_size_existing = gen_sizes.get(diesel_size_existing)
	if diesel_size_new > 0:
		gen_obs.append({
			'!CMD': 'new',
			'object':f'generator.diesel_{gen_bus_name}',
			'bus1':f"{gen_bus_name}.{'.'.join(phase_and_kv['phases'])}",
			'kv':phase_and_kv['kv'],
			'kw':f'{diesel_size_new}',
			'phases':len(phase_and_kv['phases']),
			'xdp':'0.27',
			'xdpp':'0.2',
			'h':'2',
			'conn':'delta'
		})
		# 0-1 scale the power output loadshape to the total generation kw of that type of generator
		# gen_df_builder[f'diesel_{gen_bus_name}'] = pd.Series(reopt_out.get(f'powerDiesel{mg_num}'))/diesel_size_total # insert the 0-1 diesel generation shape provided by REopt to simulate the outage specified in REopt
		# TODO: if using real loadshapes for diesel, need to scale them based on rated kw of the new diesel
		gen_df_builder[f'diesel_{gen_bus_name}'] = pd.DataFrame(np.zeros(8760)) # insert an array of zeros for the diesel generation shape to simulate no outage
	# build loadshapes for existing generation from BASE_NAME, inputting the 0-1 diesel generation loadshape 
	if diesel_size_existing > 0:	
		for gen_ob_existing in gen_obs_existing:
			if gen_ob_existing.startswith('diesel_'):
				# gen_df_builder[f'{gen_ob_existing}'] = pd.Series(reopt_out.get(f'powerDiesel{mg_num}'))/diesel_size_total # insert the 0-1 diesel generation shape provided by REopt to simulate the outage specified in REopt
				# TODO: if using real loadshapes for diesel, need to scale them based on rated kw of that individual generator object
				gen_df_builder[f'{gen_ob_existing}'] = pd.DataFrame(np.zeros(8760)) # insert an array of zeros for the diesel generation shape to simulate no outage
	
	# Build new wind gen objects and loadshapes
	wind_size_total = gen_sizes.get(wind_size_total)
	wind_size_new = gen_sizes.get(wind_size_new)
	wind_size_existing = gen_sizes.get(wind_size_existing)
	if wind_size_new > 0:
		gen_obs.append({
			'!CMD': 'new',
			'object':f'generator.wind_{gen_bus_name}',
			'bus1':f"{gen_bus_name}.{'.'.join(phase_and_kv['phases'])}",
			'phases':len(phase_and_kv['phases']),
			'kv':phase_and_kv['kv'],
			'kw':f'{wind_size_new}',
			'pf':'1'
		})
		# 0-1 scale the power output loadshape to the total generation and multiply by the new kw of that type of generator
		gen_df_builder[f'wind_{gen_bus_name}'] = pd.Series(reopt_out.get(f'powerWind{mg_num}'))/wind_size_total*wind_size_new
	# build loadshapes for existing Wind generation from BASE_NAME
	if wind_size_existing > 0:	
		for gen_ob_existing in gen_obs_existing:
			if gen_ob_existing.startswith('wind_'):
				#HACK Implemented: TODO: IF multiple existing wind generator objects are in gen_obs, we need to scale the output loadshapes by their rated kW
				gen_df_builder[f'{gen_ob_existing}'] = pd.Series(reopt_out.get(f'powerWind{mg_num}'))/wind_size_total*wind_size_existing

	# calculate battery loadshape (serving load - charging load)
	battery_cap_total = gen_sizes.get(battery_cap_total)
	battery_cap_new = gen_sizes.get(battery_cap_new)
	battery_cap_existing = gen_sizes.get(battery_cap_existing)
	battery_pow_total = gen_sizes.get(battery_pow_total)
	battery_pow_new = gen_sizes.get(battery_pow_new)
	battery_pow_existing = gen_sizes.get(battery_pow_existing)
	if battery_cap_total > 0:	
		batToLoad = pd.Series(reopt_out.get(f'powerBatteryToLoad{mg_num}'))
		gridToBat = np.zeros(8760)
		# TO DO: add logic to update insertion of grid charging when Daniel's islanding framework is complete 	
		gridToBat = pd.Series(reopt_out.get(f'powerGridToBattery{mg_num}'))
		pVToBat = np.zeros(8760)
		if solar_size_total > 0:
			pVToBat = pd.Series(reopt_out.get(f'powerPVToBattery{mg_num}'))
		dieselToBat = np.zeros(8760)
		if diesel_total_calc > 0:
			dieselToBat = pd.Series(reopt_out.get(f'powerDieselToBattery{mg_num}'))
		windToBat = np.zeros(8760)
		if wind_size_total > 0:
			windToBat = pd.Series(reopt_out.get(f'powerWindToBattery{mg_num}'))
		battery_load = batToLoad - gridToBat - pVToBat - dieselToBat - windToBat
	# get DSS objects and loadshapes for new battery
	if battery_cap_new > 0: 
		gen_obs.append({
			'!CMD': 'new',
			'object':f'storage.battery_{gen_bus_name}',
			'bus1':f"{gen_bus_name}.{'.'.join(phase_and_kv['phases'])}",
			'kv':phase_and_kv['kv'],
			'kwrated':f'{battery_pow_new}',
			'phases':len(phase_and_kv['phases']),
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
		# 0-1 scale the power output loadshape to the total generation and multiply by the new kw of that type of generator
		gen_df_builder[f'battery_{gen_bus_name}'] = battery_load/battery_pow_total*battery_pow_new
	# build loadshapes for existing battery generation from BASE_NAME
	if battery_cap_existing > 0:	
		for gen_ob_existing in gen_obs_existing:
			if gen_ob_existing.startswith('battery_'):
				#HACK Implemented: TODO: IF multiple existing battery generator objects are in gen_obs, we need to scale the output loadshapes by their rated kW
				gen_df_builder[f'{gen_ob_existing}'] = battery_load/battery_pow_total*battery_pow_existing
	gen_df_builder.to_csv(GEN_NAME, index=False)
	return gen_obs

# previuosly used func in microgridup.py
# def get_gen_ob_and_shape_from_reopt(REOPT_FOLDER, GEN_NAME, microgrid, diesel_total_calc, BASE_NAME):
# 	''' Get generator objects and shapes from REOpt.
# 	SIDE EFFECTS: creates GEN_NAME generator shape, returns gen_obs
# 	TODO: To implement multiple same-type existing generators within a single microgrid, 
# 	will need to implement searching the tree of FULL_NAME to find kw ratings of existing gens'''
# 	reopt_out = json.load(open(REOPT_FOLDER + '/allOutputData.json'))
# 	gen_df_builder = pd.DataFrame()
# 	gen_obs = []
# 	mg_num = 1
# 	mg_ob = microgrid
# 	gen_bus_name = mg_ob['gen_bus']
# 	gen_obs_existing = mg_ob['gen_obs_existing']
# 	phase_and_kv = mg_phase_and_kv(BASE_NAME, microgrid)
# 	''' Calculate size of new generators at gen_bus based on REopt and existing gen from BASE_NAME for each microgrid.
# 		Existing solar and diesel are supported natively in REopt.
# 		diesel_total_calc is used to set the total amount of diesel generation.
# 		Existing wind and batteries require setting the minimimum generation threshold (windMin, batteryPowerMin, batteryCapacityMin)'''
# 	solar_size_total = reopt_out.get(f'sizePV{mg_num}', 0.0)
# 	solar_size_existing = reopt_out.get(f'sizePVExisting{mg_num}', 0.0)
# 	solar_size_new = solar_size_total - solar_size_existing
# 	wind_size_total = reopt_out.get(f'sizeWind{mg_num}', 0.0) # TO DO: Update size of wind based on existing generation once we find a way to get a loadshape for that wind if REopt recommends no wind
# 	wind_size_existing = reopt_out.get(f'windExisting{mg_num}', 0.0)
# 	if wind_size_total - wind_size_existing > 0:
# 		wind_size_new = wind_size_total - wind_size_existing 
# 	else:
# 		wind_size_new = 0 #TO DO: update logic here to make run more robust to oversized existing wind gen	
# 	diesel_size_REopt = reopt_out.get(f'sizeDiesel{mg_num}', 0.0)
# 	diesel_size_existing = reopt_out.get(f'sizeDieselExisting{mg_num}', 0.0)
# 	# calculate additional diesel to be added to existing diesel gen (if any) to adjust kW based on diesel_sizing()
# 	if diesel_total_calc - diesel_size_existing > 0:
# 		diesel_size_new = diesel_total_calc - diesel_size_existing
# 	else:
# 		diesel_size_new = 0	
# 	battery_cap_total = reopt_out.get(f'capacityBattery{mg_num}', 0.0) 
# 	battery_cap_existing = reopt_out.get(f'batteryKwhExisting{mg_num}', 0.0)
# 	if battery_cap_total - battery_cap_existing > 0:
# 		battery_cap_new = battery_cap_total - battery_cap_existing 
# 	else:
# 		battery_cap_new = 0 #TO DO: update logic here to make run more robust to oversized existing battery generation
# 	battery_pow_total = reopt_out.get(f'powerBattery{mg_num}', 0.0) 
# 	battery_pow_existing = reopt_out.get(f'batteryKwExisting{mg_num}', 0.0)
# 	if battery_pow_total - battery_pow_existing > 0:
# 		battery_pow_new = battery_pow_total - battery_pow_existing 
# 	else:
# 		battery_pow_new = 0 #TO DO: Fix logic so that new batteries cannot add kwh without adding kw
# 	# Build new solar gen objects and loadshapes as recommended by REopt
# 	if solar_size_new > 0:
# 		gen_obs.append({
# 			'!CMD': 'new',
# 			'object':f'generator.solar_{gen_bus_name}',
# 			'bus1':f"{gen_bus_name}.{'.'.join(phase_and_kv['phases'])}",
# 			'phases':len(phase_and_kv['phases']),
# 			'kv':phase_and_kv['kv'],
# 			'kw':f'{solar_size_new}',
# 			'pf':'1'
# 		})
# 		# 0-1 scale the power output loadshape to the total generation kw of that type of generator using pandas
# 		gen_df_builder[f'solar_{gen_bus_name}'] = pd.Series(reopt_out.get(f'powerPV{mg_num}'))/solar_size_total*solar_size_new
# 	# build loadshapes for existing generation from BASE_NAME, inputting the 0-1 solar generation loadshape and scaling by their rated kw
# 	if solar_size_existing > 0:
# 		for gen_ob_existing in gen_obs_existing:
# 			if gen_ob_existing.startswith('solar_'):
# 				gen_df_builder[f'{gen_ob_existing}'] = pd.Series(reopt_out.get(f'powerPV{mg_num}'))/solar_size_total*solar_size_existing 
# 				#HACK Implemented: TODO: IF multiple existing solar generator objects are in gen_obs, we need to scale the output loadshapes by their rated kW 
# 	if diesel_size_new > 0:
# 		gen_obs.append({
# 			'!CMD': 'new',
# 			'object':f'generator.diesel_{gen_bus_name}',
# 			'bus1':f"{gen_bus_name}.{'.'.join(phase_and_kv['phases'])}",
# 			'kv':phase_and_kv['kv'],
# 			'kw':f'{diesel_size_new}',
# 			'phases':len(phase_and_kv['phases']),
# 			'xdp':'0.27',
# 			'xdpp':'0.2',
# 			'h':'2',
# 			'conn':'delta'
# 		})
# 		# 0-1 scale the power output loadshape to the total generation kw of that type of generator
# 		# gen_df_builder[f'diesel_{gen_bus_name}'] = pd.Series(reopt_out.get(f'powerDiesel{mg_num}'))/diesel_size_total # insert the 0-1 diesel generation shape provided by REopt to simulate the outage specified in REopt
# 		# TODO: if using real loadshapes for diesel, need to scale them based on rated kw of the new diesel
# 		gen_df_builder[f'diesel_{gen_bus_name}'] = pd.DataFrame(np.zeros(8760)) # insert an array of zeros for the diesel generation shape to simulate no outage
# 	# build loadshapes for existing generation from BASE_NAME, inputting the 0-1 diesel generation loadshape 
# 	if diesel_size_existing > 0:	
# 		for gen_ob_existing in gen_obs_existing:
# 			if gen_ob_existing.startswith('diesel_'):
# 				# gen_df_builder[f'{gen_ob_existing}'] = pd.Series(reopt_out.get(f'powerDiesel{mg_num}'))/diesel_size_total # insert the 0-1 diesel generation shape provided by REopt to simulate the outage specified in REopt
# 				# TODO: if using real loadshapes for diesel, need to scale them based on rated kw of that individual generator object
# 				gen_df_builder[f'{gen_ob_existing}'] = pd.DataFrame(np.zeros(8760)) # insert an array of zeros for the diesel generation shape to simulate no outage
# 	# get loadshapes for new Wind
# 	if wind_size_new > 0:
# 		gen_obs.append({
# 			'!CMD': 'new',
# 			'object':f'generator.wind_{gen_bus_name}',
# 			'bus1':f"{gen_bus_name}.{'.'.join(phase_and_kv['phases'])}",
# 			'phases':len(phase_and_kv['phases']),
# 			'kv':phase_and_kv['kv'],
# 			'kw':f'{wind_size_new}',
# 			'pf':'1'
# 		})
# 		# 0-1 scale the power output loadshape to the total generation and multiply by the new kw of that type of generator
# 		gen_df_builder[f'wind_{gen_bus_name}'] = pd.Series(reopt_out.get(f'powerWind{mg_num}'))/wind_size_total*wind_size_new
# 	# build loadshapes for existing Wind generation from BASE_NAME
# 	if wind_size_existing > 0:	
# 		for gen_ob_existing in gen_obs_existing:
# 			if gen_ob_existing.startswith('wind_'):
# 				#HACK Implemented: TODO: IF multiple existing wind generator objects are in gen_obs, we need to scale the output loadshapes by their rated kW
# 				gen_df_builder[f'{gen_ob_existing}'] = pd.Series(reopt_out.get(f'powerWind{mg_num}'))/wind_size_total*wind_size_existing
# 	# calculate battery loadshape (serving load - charging load)
# 	if battery_cap_total > 0:	
# 		batToLoad = pd.Series(reopt_out.get(f'powerBatteryToLoad{mg_num}'))
# 		gridToBat = np.zeros(8760)
# 		# TO DO: add logic to update insertion of grid charging when Daniel's islanding framework is complete 	
# 		gridToBat = pd.Series(reopt_out.get(f'powerGridToBattery{mg_num}'))
# 		pVToBat = np.zeros(8760)
# 		if solar_size_total > 0:
# 			pVToBat = pd.Series(reopt_out.get(f'powerPVToBattery{mg_num}'))
# 		dieselToBat = np.zeros(8760)
# 		if diesel_total_calc > 0:
# 			dieselToBat = pd.Series(reopt_out.get(f'powerDieselToBattery{mg_num}'))
# 		windToBat = np.zeros(8760)
# 		if wind_size_total > 0:
# 			windToBat = pd.Series(reopt_out.get(f'powerWindToBattery{mg_num}'))
# 		battery_load = batToLoad - gridToBat - pVToBat - dieselToBat - windToBat
# 	# get DSS objects and loadshapes for new battery
# 	if battery_cap_new > 0: 
# 		gen_obs.append({
# 			'!CMD': 'new',
# 			'object':f'storage.battery_{gen_bus_name}',
# 			'bus1':f"{gen_bus_name}.{'.'.join(phase_and_kv['phases'])}",
# 			'kv':phase_and_kv['kv'],
# 			'kwrated':f'{battery_pow_new}',
# 			'phases':len(phase_and_kv['phases']),
# 			'dispmode':'follow',
# 			'kwhstored':f'{battery_cap_new}',
# 			'kwhrated':f'{battery_cap_new}',
# 			# 'kva':f'{battery_pow_total}',
# 			# 'kvar':f'{battery_pow_total}',
# 			'%charge':'100',
# 			'%discharge':'100',
# 			'%effcharge':'100',
# 			'%effdischarge':'100',
# 			'%idlingkw':'0',
# 			'%r':'0',
# 			'%x':'50',
# 			'%stored':'50'
# 		})
# 		# 0-1 scale the power output loadshape to the total generation and multiply by the new kw of that type of generator
# 		gen_df_builder[f'battery_{gen_bus_name}'] = battery_load/battery_pow_total*battery_pow_new
# 	# build loadshapes for existing battery generation from BASE_NAME
# 	if battery_cap_existing > 0:	
# 		for gen_ob_existing in gen_obs_existing:
# 			if gen_ob_existing.startswith('battery_'):
# 				#HACK Implemented: TODO: IF multiple existing wind generator objects are in gen_obs, we need to scale the output loadshapes by their rated kW
# 				gen_df_builder[f'{gen_ob_existing}'] = battery_load/battery_pow_total*battery_pow_existing
# 	gen_df_builder.to_csv(GEN_NAME, index=False)
# 	return gen_obs



microgrid_1 = {
	'loads': ['634a_data_center','634b_radar','634c_atc_tower'],
	'switch': '632633',
	'gen_bus': '634',
	'gen_obs_existing': ['solar_634_existing'],
	'max_potential': '700' # total kW rating on 634 bus is 500 kW
}

# make a new function to calculate additional diesel costs? COuld this be similar to additional islanding costs as well
# what is the O+M costs and fuel costs
# need a button in mgDesign for cost of fuel that is a pass through we can use in the econ analysis pulling from '/allOutputData.json'




if __name__ == '__main__':
	#diesel_sizing('/allOutputData.json','lehigh_reopt_1',.2, max_net_load('/allOutputData.json','lehigh_reopt_1'))

	# max_net_load('/allOutputData.json','lehigh_reopt_1')
	# max_net_load('/allOutputData.json','lehigh_reopt_2')
	# max_net_load('/allOutputData.json','lehigh_reopt_3')
	# max_net_load('/allOutputData.json','lehigh_reopt_4')

	# phase_and_kv = mg_phase_and_kv('lehigh_base_phased.dss',microgrid_1)
	# print("number of phases:",len(phase_and_kv['phases']))
	
	# print('.'.join(phase_and_kv['phases']))

	gen_sizes_out = get_gen_ob_from_reopt('lehigh_reopt_3', 100)
	print("gen_sizes", gen_sizes_out)

