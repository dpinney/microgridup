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

	phase_and_kv = mg_phase_and_kv('lehigh_base_phased.dss',microgrid_1)
	print("number of phases:",len(phase_and_kv['phases']))
	
	print('.'.join(phase_and_kv['phases']))

