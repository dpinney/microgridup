from omf.solvers import opendss
from omf.solvers.opendss import dssConvert
from omf import distNetViz
from omf import geo
import microgridup_control
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
import datetime

MGU_FOLDER = os.path.dirname(__file__)

def _getByName(tree, name):
    ''' Return first object with name in tree as an OrderedDict. '''
    matches =[]
    for x in tree:
        if x.get('object',''):
            if x.get('object','').split('.')[1] == name:
                matches.append(x)
    return matches[0]

def set_critical_load_percent(LOAD_NAME, microgrid):
	''' Set the critical load percent for REopt by finding the ratio
	of max critical load kws to the max load found in the loadshape of that mg'''
	load_df = pd.read_csv(LOAD_NAME)
	mg_load_df = pd.DataFrame()
	loads = microgrid['loads']
	mg_load_df['load'] = [0 for x in range(8760)]
	for load_name in loads:
		mg_load_df['load'] = mg_load_df['load'] + load_df[load_name]
	max_load = float(mg_load_df.max())
	# print("max_load:", max_load)

	# TO DO: select specific critical loads from circuit.dss if meta data on max kw or loadshapes exist for those loads
	# add up all max kws from critical loads to support during an outage
	max_crit_load = sum(microgrid['critical_load_kws'])
	# print("max_crit_load:", max_crit_load)

	critical_load_percent = max_crit_load/max_load
	# print('critical_load_percent:',critical_load_percent)
	return critical_load_percent, max_crit_load


def reopt_gen_mg_specs(BASE_NAME, LOAD_NAME, REOPT_INPUTS, REOPT_FOLDER, microgrid, critical_load_percent):
	''' Generate the microgrid specs with REOpt.
	SIDE-EFFECTS: generates REOPT_FOLDER'''
	load_df = pd.read_csv(LOAD_NAME)
	if not os.path.isdir(REOPT_FOLDER):
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
		# TODO: Make it safe for the max to be at begining or end of the year
		# find max and index of max in mg_load_df['load']
		max_load = mg_load_df.max()
		#print("max_load:", max_load)
		max_load_index = int(mg_load_df.idxmax())
		#print("max_load_index:", max_load_index)
		# reset the outage timing such that the length of REOPT_INPUTS falls half before and half after the hour of max load
		outage_duration = int(REOPT_INPUTS["outageDuration"])
		if max_load_index + outage_duration/2 > 8760:
			outage_start_hour = 8760 - outage_duration
			# REopt seems not to allow an outage on the last hour of the year
		elif max_load_index - outage_duration/2 < 1:
			outage_start_hour = 2
		else:
			outage_start_hour = max_load_index - outage_duration/2
		#print("outage_start_hour:", str(int(outage_start_hour)))
		allInputData['outage_start_hour'] = str(int(outage_start_hour))
		allInputData['criticalLoadFactor'] = str(critical_load_percent)

		# Pulling coordinates from BASE_NAME.dss into REopt allInputData.json:
		tree = dssConvert.dssToTree(BASE_NAME)
		#print(tree)
		evil_glm = dssConvert.evilDssTreeToGldTree(tree)
		#print(evil_glm)
		# using evil_glm to get around the fact that buses in openDSS are created in memory and do not exist in the BASE_NAME dss file
		for ob in evil_glm.values():
			ob_name = ob.get('name','')
			ob_type = ob.get('object','')
			# pull out long and lat of the gen_bus
			# if ob_type == "bus" and ob_name == "sourcebus":
			if ob_type == "bus" and ob_name == microgrid['gen_bus']:
				ob_lat = ob.get('latitude','')
				ob_long = ob.get('longitude','')
				#print('lat:', float(ob_lat), 'long:', float(ob_long))
				allInputData['latitude'] = float(ob_lat)
				allInputData['longitude'] = float(ob_long)

		# enable following 5 lines when using gen_existing_ref_shapes()
		# force REopt to optimize on wind and solar even if not recommended by REopt optimization
		if allInputData['wind'] == 'on':
			allInputData['windMin'] = '1'
		if allInputData['solar'] == 'on':
			allInputData['solarMin'] = '1'	

		# Pull out and add up kw of all existing generators in the microgrid
		# requires pre-selection of all objects in a given microgrid in microgrids['gen_obs_existing']
		load_map = {x.get('object',''):i for i, x in enumerate(tree)}
		# TODO: update for CHP and other types of generation
		solar_kw_exist = []
		diesel_kw_exist = []
		battery_kw_exist = []
		battery_kwh_exist = []
		wind_kw_exist = []
		gen_obs = microgrid['gen_obs_existing']
		for gen_ob in gen_obs:
			if gen_ob.startswith('solar_'):
				solar_kw_exist.append(float(tree[load_map[f'generator.{gen_ob}']].get('kw')))
			elif gen_ob.startswith('diesel_'):
				diesel_kw_exist.append(float(tree[load_map[f'generator.{gen_ob}']].get('kw')))
			elif gen_ob.startswith('wind_'):
				wind_kw_exist.append(float(tree[load_map[f'generator.{gen_ob}']].get('kw')))
			elif gen_ob.startswith('battery_'):
				battery_kw_exist.append(float(tree[load_map[f'storage.{gen_ob}']].get('kwrated')))
				battery_kwh_exist.append(float(tree[load_map[f'storage.{gen_ob}']].get('kwhrated')))

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
		
		# enable following 9 lines when using gen_existing_ref_shapes()
		# if not already turned on, set solar and wind on to 10 kw to provide loadshapes for existing gen in make_full_dss()
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
		omf.models.__neoMetaModel__.renderTemplateToFile(REOPT_FOLDER)

def max_net_load(inputName, REOPT_FOLDER):
	''' Calculate max net load needing to be covered by diesel 
	generation in an outage. This method assumes only solar, wind and diesel generation 
	when islanded from main grid, with no support from battery in order to model 
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
	# max net load not covered by solar or wind; Equivalent to diesel size needed for uninterupted power throughout the year
	max_net_load = max(load_df['net_load'])
	# diesel size recommended by REopt
	# diesel_REopt = reopt_out.get(f'sizeDiesel{mg_num}', 0.0)
	# print("Max total load for", REOPT_FOLDER, ":", max_total_load)
	# print("Max load needed to be supported by diesel for", REOPT_FOLDER, ":", max_net_load)
	# print("% more kW diesel needed than recommended by REopt for", REOPT_FOLDER, ":", round(100*(max_net_load - diesel_REopt)/diesel_REopt))
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
	# print(diesel_total_calc,"kW diesel_total_calc is", round(100*(diesel_total_calc-diesel_total_REopt)/diesel_total_REopt), "% more kW diesel than recommended by REopt for", REOPT_FOLDER)
	return diesel_total_calc

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
	wind_size_total = reopt_out.get(f'sizeWind{mg_num}', 0.0)
	wind_size_existing = reopt_out.get(f'windExisting{mg_num}', 0.0)
	if wind_size_total - wind_size_existing > 0:
		wind_size_new = wind_size_total - wind_size_existing 
	else:
		wind_size_new = 0.0
	# calculate additional diesel to be added to existing diesel gen (if any) to adjust kW based on diesel_sizing()
	if diesel_total_calc == False:
		diesel_size_total = reopt_out.get(f'sizeDiesel{mg_num}', 0.0)
	else:
		diesel_size_total = diesel_total_calc
	diesel_size_existing = reopt_out.get(f'sizeDieselExisting{mg_num}', 0.0)
	if diesel_size_total - diesel_size_existing > 0:
		diesel_size_new = diesel_size_total - diesel_size_existing
	else:
		diesel_size_new = 0.0	
	# battery capacity refers to the amount of energy that can be stored (kwh)
	battery_cap_total = reopt_out.get(f'capacityBattery{mg_num}', 0.0) 
	battery_cap_existing = reopt_out.get(f'batteryKwhExisting{mg_num}', 0.0)
	if battery_cap_total - battery_cap_existing > 0:
		battery_cap_new = battery_cap_total - battery_cap_existing 
	else:
		battery_cap_new = 0.0 #TO DO: update logic here to make run more robust to oversized existing battery generation
	# battery power refers to the power rating of the battery (kw)
	battery_pow_total = reopt_out.get(f'powerBattery{mg_num}', 0.0) 
	battery_pow_existing = reopt_out.get(f'batteryKwExisting{mg_num}', 0.0)
	if battery_pow_total - battery_pow_existing > 0:
		battery_pow_new = battery_pow_total - battery_pow_existing 
	else:
		battery_pow_new = 0.0 #TO DO: Fix logic so that new batteries cannot add kwh without adding kw

	gen_sizes.update({'solar_size_total':solar_size_total,'solar_size_existing':solar_size_existing, 'solar_size_new':solar_size_new, \
		'wind_size_total':wind_size_total, 'wind_size_existing':wind_size_existing, 'wind_size_new':wind_size_new, \
		'diesel_size_total':diesel_size_total, 'diesel_size_existing':diesel_size_existing, 'diesel_size_new':diesel_size_new, \
		'battery_cap_total':battery_cap_total, 'battery_cap_existing':battery_cap_existing, 'battery_cap_new':battery_cap_new, \
		'battery_pow_total':battery_pow_total, 'battery_pow_existing':battery_pow_existing, 'battery_pow_new':battery_pow_new})
	return gen_sizes #dictionary of all gen sizes

def feedback_reopt_gen_values(BASE_NAME, LOAD_NAME, REOPT_INPUTS, REOPT_FOLDER_BASE, REOPT_FOLDER_FINAL, microgrid, diesel_total_calc, critical_load_percent):
	'''Update max and min generator sizes based on get_gen_ob_from_reopt() and rerun REopt
	SIDE-EFFECTS: generates second REOPT_FOLDER'''
	load_df = pd.read_csv(LOAD_NAME)
	if not os.path.isdir(REOPT_FOLDER_FINAL):
		import omf.models
		shutil.rmtree(REOPT_FOLDER_FINAL, ignore_errors=True)
		omf.models.microgridDesign.new(REOPT_FOLDER_FINAL)
		# Get the microgrid total loads
		mg_load_df = pd.DataFrame()
		loads = microgrid['loads']
		mg_load_df['load'] = [0 for x in range(8760)]
		for load_name in loads:
			mg_load_df['load'] = mg_load_df['load'] + load_df[load_name]
		mg_load_df.to_csv(REOPT_FOLDER_FINAL + '/loadShape.csv', header=False, index=False)
		# Insert loadshape into /allInputData.json
		allInputData = json.load(open(REOPT_FOLDER_FINAL + '/allInputData.json'))
		allInputData['loadShape'] = open(REOPT_FOLDER_FINAL + '/loadShape.csv').read()
		allInputData['fileName'] = 'loadShape.csv'

		# Pulling user defined inputs from REOPT_INPUTS.
		for key in REOPT_INPUTS:
			allInputData[key] = REOPT_INPUTS[key]

		# Set the REopt outage to be centered around the max load in the loadshape
		# TODO: Make it safe for the max to be at begining or end of the year
		# find max and index of max in mg_load_df['load']
		max_load = mg_load_df.max()
		#print("max_load:", max_load)
		max_load_index = int(mg_load_df.idxmax())
		#print("max_load_index:", max_load_index)
		# reset the outage timing such that the length of REOPT_INPUTS falls half before and half after the hour of max load
		outage_duration = int(REOPT_INPUTS["outageDuration"])
		if max_load_index + outage_duration/2 > 8760:
			outage_start_hour = 8760 - outage_duration
			# REopt seems not to allow an outage on the last hour of the year
		elif max_load_index - outage_duration/2 < 1:
			outage_start_hour = 2
		else:
			outage_start_hour = max_load_index - outage_duration/2
		# print("outage_start_hour:", str(int(outage_start_hour)))
		allInputData['outage_start_hour'] = str(int(outage_start_hour))
		allInputData['criticalLoadFactor'] = str(critical_load_percent)

		# Pulling coordinates from BASE_NAME.dss into REopt allInputData.json:
		tree = dssConvert.dssToTree(BASE_NAME)
		#print(tree)
		evil_glm = dssConvert.evilDssTreeToGldTree(tree)
		#print(evil_glm)
		# using evil_glm to get around the fact that buses in openDSS are created in memory and do not exist in the BASE_NAME dss file
		for ob in evil_glm.values():
			ob_name = ob.get('name','')
			ob_type = ob.get('object','')
			# pull out long and lat of the gen_bus
			# if ob_type == "bus" and ob_name == "sourcebus":
			if ob_type == "bus" and ob_name == microgrid['gen_bus']:
				ob_lat = ob.get('latitude','')
				ob_long = ob.get('longitude','')
				#print('lat:', float(ob_lat), 'long:', float(ob_long))
				allInputData['latitude'] = float(ob_lat)
				allInputData['longitude'] = float(ob_long)

		# Update all generator specifications in the microgrid to match outputs of REOPT_FOLDER_BASE
		gen_sizes = get_gen_ob_from_reopt(REOPT_FOLDER_BASE, diesel_total_calc=diesel_total_calc)
		# HACK: comment out the next two lines to turn up Solar quickly for Picatinny analysis
		solar_size_total = gen_sizes.get('solar_size_total')
		solar_size_new = gen_sizes.get('solar_size_new')
		solar_size_existing = gen_sizes.get('solar_size_existing')
		diesel_size_total = gen_sizes.get('diesel_size_total')
		diesel_size_new = gen_sizes.get('diesel_size_new')
		diesel_size_existing = gen_sizes.get('diesel_size_existing')
		wind_size_total = gen_sizes.get('wind_size_total')
		wind_size_new = gen_sizes.get('wind_size_new')
		wind_size_existing = gen_sizes.get('wind_size_existing')
		battery_cap_total = gen_sizes.get('battery_cap_total')
		battery_cap_new = gen_sizes.get('battery_cap_new')
		battery_cap_existing = gen_sizes.get('battery_cap_existing')
		battery_pow_total = gen_sizes.get('battery_pow_total')
		battery_pow_new = gen_sizes.get('battery_pow_new')
		battery_pow_existing = gen_sizes.get('battery_pow_existing')
		# HACK to turn up Solar quickly for Picatinny analysis
		# solar_size_new = diesel_size_new*.4
		# solar_size_total = solar_size_new + solar_size_existing

		if diesel_size_total > 0:
			allInputData['dieselMax'] = diesel_size_total
			allInputData['dieselMin'] = diesel_size_total
			allInputData['genExisting'] = diesel_size_existing
		# handle peculiar logic of solar_size_total from REopt when using gen_existing_ref_shapes()
		# TODO: check on updates to solar outputs from REopt, assuming they align Solar output bevior to be similar to wind, battery, etc
		if solar_size_total == 1:
			allInputData['solarMax'] = 0
			allInputData['solar'] = 'off'
		elif solar_size_total - solar_size_existing == 1:
			allInputData['solarMin'] = 0
			allInputData['solarMax'] = 0
			allInputData['solarExisting'] = solar_size_existing
			allInputData['solar'] = 'on'
		elif solar_size_total > 1: 
			allInputData['solarMin'] = solar_size_total - solar_size_existing
			allInputData['solarMax'] = solar_size_total - solar_size_existing
			allInputData['solarExisting'] = solar_size_existing
			allInputData['solar'] = 'on'
		# if additional battery power is recommended by REopt, remove existing batteries and add in new battery
		if battery_pow_new > 0:
			allInputData['batteryPowerMin'] = battery_pow_total
			allInputData['batteryPowerMax'] = battery_pow_total
			allInputData['batteryKwExisting'] = 0
			# If recommended battery power is larger than existing, then let rerun of REopt suggest the best capacity of the battery instead of tying it to the original existing kwh
			allInputData['batteryCapacityMin'] = 0
			allInputData['batteryCapacityMax'] = 100000
			allInputData['batteryKwhExisting'] = 0
			allInputData['battery'] = 'on'
		# if only additional energy storage (kWh) is recommended, add a battery of same power as existing battery with the recommended additional kWh
		elif battery_cap_new > 0:
			allInputData['batteryPowerMin'] = battery_pow_existing
			allInputData['batteryPowerMax'] = battery_pow_existing
			allInputData['batteryKwExisting'] = battery_pow_existing
			allInputData['batteryCapacityMin'] = battery_cap_total
			allInputData['batteryCapacityMax'] = battery_cap_total
			allInputData['batteryKwhExisting'] = battery_cap_existing
			allInputData['battery'] = 'on'
		# if no new battery storage is recommended, keep existing if it exists
		# Warning: logic for batteries affects behavior of loadshape generation in gen_existing_ref_shapes()
		elif battery_cap_existing > 0:
			allInputData['batteryPowerMin'] = battery_pow_existing
			allInputData['batteryPowerMax'] = battery_pow_existing
			allInputData['batteryKwExisting'] = battery_pow_existing
			allInputData['batteryCapacityMin'] = battery_pow_existing
			allInputData['batteryCapacityMax'] = battery_pow_existing
			allInputData['batteryKwhExisting'] = battery_cap_existing
			allInputData['battery'] = 'on'

		if wind_size_total > 0 and wind_size_total != 1: # enable the dual condition when using gen_existing_ref_shapes()
			allInputData['windMin'] = wind_size_total
			allInputData['windMax'] = wind_size_total
			allInputData['windExisting'] = wind_size_existing
			allInputData['wind'] = 'on' #failsafe to include wind if found in base_dss
		elif wind_size_total == 1: # enable the elif condition when using gen_existing_ref_shapes()
			allInputData['windMax'] = 0
			allInputData['wind'] = 'off'

		# run REopt via microgridDesign
		with open(REOPT_FOLDER_FINAL + '/allInputData.json','w') as outfile:
			json.dump(allInputData, outfile, indent=4)
		omf.models.__neoMetaModel__.runForeground(REOPT_FOLDER_FINAL)
		omf.models.__neoMetaModel__.renderTemplateToFile(REOPT_FOLDER_FINAL)

def mg_phase_and_kv(BASE_NAME, microgrid):
	'''Returns a dict with the phases at the gen_bus and kv 
	of the loads for a given microgrid.
	TODO: If needing to set connection type explicitly, could use this function to check that all "conn=" are the same (wye or empty for default, or delta)'''
	tree = dssConvert.dssToTree(BASE_NAME)
	mg_ob = microgrid
	gen_bus_name = mg_ob['gen_bus']
	mg_loads = mg_ob['loads']
	load_phase_list = []
	gen_bus_kv = []
	load_map = {x.get('object',''):i for i, x in enumerate(tree)}
	for load_name in mg_loads:
		ob = tree[load_map[f'load.{load_name}']]
		# print("mg_phase_and_kv ob:", ob)
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
	# print('out_dict', out_dict)
	return out_dict
	
def build_new_gen_ob_and_shape(REOPT_FOLDER, GEN_NAME, microgrid, BASE_NAME, mg_name, diesel_total_calc=False):
	'''Create new generator objects and shapes. 
	Returns a list of generator objects formatted for reading into openDSS tree.
	SIDE EFFECTS: creates GEN_NAME generator shape
	TODO: To implement multiple same-type existing generators within a single microgrid, 
	will need to implement searching the tree of FULL_NAME to find kw ratings of existing gens'''

	gen_sizes = get_gen_ob_from_reopt(REOPT_FOLDER)
	# print("gen_sizes:", gen_sizes)
	reopt_out = json.load(open(REOPT_FOLDER + '/allOutputData.json'))
	gen_df_builder = pd.DataFrame()
	gen_obs = []
	mg_num = 1
	mg_ob = microgrid
	gen_bus_name = mg_ob['gen_bus']
	gen_obs_existing = mg_ob['gen_obs_existing']
	phase_and_kv = mg_phase_and_kv(BASE_NAME, microgrid)
	
	# Build new solar gen objects and loadshapes
	solar_size_total = gen_sizes.get('solar_size_total')
	solar_size_new = gen_sizes.get('solar_size_new')
	solar_size_existing = gen_sizes.get('solar_size_existing')
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
	diesel_size_total = gen_sizes.get('diesel_size_total')
	diesel_size_new = gen_sizes.get('diesel_size_new')
	diesel_size_existing = gen_sizes.get('diesel_size_existing')
	if diesel_size_new > 0:
		gen_obs.append({
			'!CMD': 'new',
			'object':f'generator.diesel_{gen_bus_name}',
			'bus1':f"{gen_bus_name}.{'.'.join(phase_and_kv['phases'])}",
			'phases':len(phase_and_kv['phases']),
			'kv':phase_and_kv['kv'],
			'kw':f'{diesel_size_new}',
			'xdp':'0.27',
			'xdpp':'0.2',
			'h':'2'
		})
		# 0-1 scale the power output loadshape to the total generation kw of that type of generator
		# gen_df_builder[f'diesel_{gen_bus_name}'] = pd.Series(reopt_out.get(f'powerDiesel{mg_num}'))/diesel_size_total # insert the 0-1 diesel generation shape provided by REopt to simulate the outage specified in REopt
		# TODO: if using real loadshapes for diesel, need to scale them based on rated kw of the new diesel
		gen_df_builder[f'diesel_{gen_bus_name}'] = pd.Series(np.zeros(8760)) # insert an array of zeros for the diesel generation shape to simulate no outage
	# build loadshapes for existing generation from BASE_NAME, inputting the 0-1 diesel generation loadshape 
	if diesel_size_existing > 0:	
		for gen_ob_existing in gen_obs_existing:
			if gen_ob_existing.startswith('diesel_'):
				# gen_df_builder[f'{gen_ob_existing}'] = pd.Series(reopt_out.get(f'powerDiesel{mg_num}'))/diesel_size_total # insert the 0-1 diesel generation shape provided by REopt to simulate the outage specified in REopt
				# TODO: if using real loadshapes for diesel, need to scale them based on rated kw of that individual generator object
				gen_df_builder[f'{gen_ob_existing}'] = pd.Series(np.zeros(8760)) # insert an array of zeros for the diesel generation shape to simulate no outage
	
	# Build new wind gen objects and loadshapes
	wind_size_total = gen_sizes.get('wind_size_total')
	wind_size_new = gen_sizes.get('wind_size_new')
	wind_size_existing = gen_sizes.get('wind_size_existing')
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
	battery_cap_total = gen_sizes.get('battery_cap_total')
	battery_cap_new = gen_sizes.get('battery_cap_new')
	battery_cap_existing = gen_sizes.get('battery_cap_existing')
	battery_pow_total = gen_sizes.get('battery_pow_total')
	battery_pow_new = gen_sizes.get('battery_pow_new')
	battery_pow_existing = gen_sizes.get('battery_pow_existing')
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
	# get DSS objects and loadshapes for new battery
	# if additional battery power is recommended by REopt, give existing batteries loadshape of zeros and add in full sized new battery
	if battery_pow_new > 0:
		# print("build_new_gen() 1a")
		gen_obs.append({
			'!CMD': 'new',
			'object':f'storage.battery_{gen_bus_name}',
			'bus1':f"{gen_bus_name}.{'.'.join(phase_and_kv['phases'])}",
			'phases':len(phase_and_kv['phases']),
			'kv':phase_and_kv['kv'],
			'kwrated':f'{battery_pow_total}',
			'dispmode':'follow',
			'kwhstored':f'{battery_cap_total}',
			'kwhrated':f'{battery_cap_total}',
			'%charge':'100',
			'%discharge':'100',
			'%effcharge':'100',
			'%effdischarge':'100',
			'%idlingkw':'0',
			'%r':'0',
			'%x':'50',
			'%stored':'50'
		})
		# new battery takes the full battery load, as existing is removed from service
		gen_df_builder[f'battery_{gen_bus_name}'] = battery_load
	# if only additional energy storage (kWh) is recommended, add a battery of same power as existing battery with the recommended additional kWh
	elif battery_cap_new > 0:
		# print("build_new_gen() 1b")
		# print("Check that battery_pow_existing (",battery_pow_existing, ") and battery_pow_total (", battery_pow_total, ") are the same")
		gen_obs.append({
			'!CMD': 'new',
			'object':f'storage.battery_{gen_bus_name}',
			'bus1':f"{gen_bus_name}.{'.'.join(phase_and_kv['phases'])}",
			'phases':len(phase_and_kv['phases']),
			'kv':phase_and_kv['kv'],
			'kwrated':f'{battery_pow_existing}', # in this case, battery_pow_existing = battery_pow_total
			'dispmode':'follow',
			'kwhstored':f'{battery_cap_new}',
			'kwhrated':f'{battery_cap_new}',
			'%charge':'100',
			'%discharge':'100',
			'%effcharge':'100',
			'%effdischarge':'100',
			'%idlingkw':'0',
			'%r':'0',
			'%x':'50',
			'%stored':'50'
		})
		# 0-1 scale the power output loadshape to the total storage kwh and multiply by the new energy storage kwh recommended
		gen_df_builder[f'battery_{gen_bus_name}'] = battery_load/battery_cap_total*battery_cap_new
	
	# build loadshapes for existing battery generation from BASE_NAME
	for gen_ob_existing in gen_obs_existing:
		# print("build_new_gen() storage 2", gen_ob_existing)
		if gen_ob_existing.startswith('battery_'):
			# print("build_new_gen() storage 3", gen_ob_existing)
			#TODO: IF multiple existing battery generator objects are in gen_obs, we need to scale the output loadshapes by their rated kW
			# if additional battery power is recommended by REopt, give existing batteries loadshape of zeros as they are deprecated
			if battery_pow_new > 0:
				# print("build_new_gen() storage 4", gen_ob_existing)
				gen_df_builder[f'{gen_ob_existing}'] = pd.Series(np.zeros(8760))
				#TODO: collect this print statement as a warning in the output_template.html 
				warning_message = f'Pre-existing battery {gen_ob_existing} will not be utilized to support loads in microgrid {mg_name}.\n'
				print(warning_message)
				with open("user_warnings.txt", "a") as myfile:
					myfile.write(warning_message)
			# if only additional energy storage (kWh) is recommended, scale the existing shape to the % of kwh storage capacity of the existing battery
			elif battery_cap_new > 0:
				# print("build_new_gen() storage 5", gen_ob_existing)
				gen_df_builder[f'{gen_ob_existing}'] = battery_load/battery_cap_total*battery_cap_existing
			# if no new battery has been built, existing battery takes the full battery load
			else:
	 			# print("build_new_gen() storage 6", gen_ob_existing)
	 			gen_df_builder[f'{gen_ob_existing}'] = battery_load

	gen_df_builder.to_csv(GEN_NAME, index=False)
	return gen_obs


def gen_existing_ref_shapes(REF_NAME, REOPT_FOLDER_BASE, REOPT_FOLDER_FINAL):
	'''Create new generator 1kw reference loadshapes for existing gen located outside of the microgrid in analysis. 
	To run this effectively when not running feedback_reopt_gen_values(), specify REOPT_FOLDER_BASE for both of the final arguments
	SIDE EFFECTS: creates REF_NAME generator reference shape'''
	gen_sizes = get_gen_ob_from_reopt(REOPT_FOLDER_FINAL, diesel_total_calc=False)
	reopt_final_out = json.load(open(REOPT_FOLDER_FINAL + '/allOutputData.json'))
	reopt_base_out = json.load(open(REOPT_FOLDER_BASE + '/allOutputData.json'))
	#reopt_final_out = json.load(open(REOPT_FOLDER_FINAL + '/allOutputData.json'))
	mg_num = 1
	ref_df_builder = pd.DataFrame()

	solar_size_total = gen_sizes.get('solar_size_total')
	# if solar was enabled by user, take shape from REOPT_FOLDER_FINAL and normalize by solar_size_total
	if solar_size_total > 0 and solar_size_total != 1:
		ref_df_builder['solar_ref_shape'] = pd.Series(reopt_final_out.get(f'powerPV{mg_num}'))/solar_size_total
		# print('solar_1')
	# if solar was not enabled by user, take shape from REOPT_FOLDER_BASE
	elif reopt_base_out.get(f'sizePV{mg_num}') == 1:
		ref_df_builder['solar_ref_shape'] = pd.Series(reopt_base_out.get(f'powerPV{mg_num}'))
		# print('solar_2')
	# print('solar_ref_shape', ref_df_builder['solar_ref_shape'].head(20))
	
	wind_size_total = gen_sizes.get('wind_size_total')
	# if wind was enabled by user, take shape from REOPT_FOLDER_FINAL and normalize by wind_size_total
	if wind_size_total > 0 and wind_size_total != 1:
		ref_df_builder['wind_ref_shape'] = pd.Series(reopt_final_out.get(f'powerWind{mg_num}'))/wind_size_total
		# print('wind_1')
	# if wind was not enabled by user, take shape from REOPT_FOLDER_BASE
	elif reopt_base_out.get(f'sizeWind{mg_num}') == 1:
		ref_df_builder['wind_ref_shape'] = pd.Series(reopt_base_out.get(f'powerWind{mg_num}'))
		# print('wind_2')
	# print('wind_ref_shape', ref_df_builder['wind_ref_shape'].head(20))

	ref_df_builder.to_csv(REF_NAME, index=False)


def make_full_dss(BASE_NAME, GEN_NAME, LOAD_NAME, FULL_NAME, REF_NAME, gen_obs, microgrid):
	''' insert generation objects into dss.
	ASSUMPTIONS: 
	SIDE EFFECTS: writes FULL_NAME dss'''
	tree = dssConvert.dssToTree(BASE_NAME)
	# print(tree)
	# make a list of names all existing loadshape objects
	load_map = {x.get('object',''):i for i, x in enumerate(tree)}
	#print(load_map)
	gen_obs_existing = microgrid['gen_obs_existing']

	bus_list_pos = -1
	for i, ob in enumerate(tree):
		if ob.get('!CMD','') == 'makebuslist':
			bus_list_pos = i
	#print("gen_obs after all new gen is built:", gen_obs)
	for ob in gen_obs:
		tree.insert(bus_list_pos, ob)
	# Gather loadshapes and generator duties.
	gen_df = pd.read_csv(GEN_NAME)
	load_df = pd.read_csv(LOAD_NAME)
	# build 1kw reference loadshapes for solar and wind existing gens that are outside of 'microgrid'
	ref_df = pd.read_csv(REF_NAME) # enable when using gen_existing_ref_shapes()
	# print("ref_df:", ref_df.head(20))
	list_of_zeros = [0.0] * 8760
	shape_insert_list = {}


	for i, ob in enumerate(tree):
		try:
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
					# print("2_gen:", ob)
					# if object is outside of microgrid and without a loadshape, give it a valid production loadshape for solar and wind or a loadshape of zeros for diesel
					if ob_name not in gen_obs_existing and f'loadshape.{shape_name}' not in load_map:					
						# print("3_gen:", ob)
						if ob_name.startswith('diesel_'):
							# print("3a_gen:", ob)
							ob['yearly'] = shape_name
							shape_data = list_of_zeros
							shape_insert_list[i] = {
								'!CMD': 'new',
								'object': f'loadshape.{shape_name}',
								'npts': '8760',
								'interval': '1',
								'useactual': 'yes',
								'mult': f'{list(shape_data)}'.replace(' ','')
							}
						elif ob_name.startswith('solar_'):
							# print("3b_gen:", ob)
							ob['yearly'] = shape_name
							# TODO: Fix loadshape to match actual production potential of the generator using a reference shapes from the first run of REopt
							# scale 1kw reference loadshape by kw rating of generator
							shape_data = ref_df['solar_ref_shape']*float(ob['kw'])  # enable when using gen_existing_ref_shapes()
							# print("solar shape data:", shape_name, shape_data.head(20))
							# shape_data = list_of_zeros
							shape_insert_list[i] = {
								'!CMD': 'new',
								'object': f'loadshape.{shape_name}',
								'npts': '8760',
								'interval': '1',
								'useactual': 'yes',
								'mult': f'{list(shape_data)}'.replace(' ','')
								# 'mult': f'{list_of_zeros}'.replace(' ','')
							}
						elif ob_name.startswith('wind_'):
							# print("3c_gen:", ob)
							ob['yearly'] = shape_name
							# TODO: Fix loadshape to match actual production potential of the generator using a reference shapes from the first run of REopt 
							# scale 1kw reference loadshape by kw rating of generator
							shape_data = ref_df['wind_ref_shape']*float(ob['kw']) # enable when using gen_existing_ref_shapes()
							# print("wind shape data:", shape_name, shape_data.head(20))
							# shape_data = list_of_zeros
							shape_insert_list[i] = {
								'!CMD': 'new',
								'object': f'loadshape.{shape_name}',
								'npts': '8760',
								'interval': '1',
								'useactual': 'yes',
								'mult': f'{list(shape_data)}'.replace(' ','')
							}
						#TODO: build in support for all other generator types (CHP)
						#else:
							#pass
					# if generator object is located in the microgrid, insert new loadshape object
					elif ob_name in gen_obs_existing:
						# print("4_gen:", ob)
						# if loadshape object already exists, overwrite the 8760 hour data in ['mult']
						# ASSUMPTION: Existing generators will be reconfigured to be controlled by new microgrid
						if f'loadshape.{shape_name}' in load_map:
							# print("4a_gen:", ob)
							j = load_map.get(f'loadshape.{shape_name}') # indexes of load_map and tree match				
							shape_data = gen_df[ob_name]
							# print("shape data:", shape_name, shape_data.head(20))
							tree[j]['mult'] = f'{list(shape_data)}'.replace(' ','')
							# print("4a_gen achieved insert")
						else:
							# print("4b_gen:", ob)
							ob['yearly'] = shape_name
							shape_data = gen_df[ob_name]
							# print('shape_data', shape_data.head(10))
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
					# print("5_gen:", ob)
					# shape_name = ob_name + '_shape'
					ob['yearly'] = shape_name
					shape_data = gen_df[ob_name]
					# print('shape_data', shape_data.head(10))
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
				# print("1_storage:", ob)
				ob_name = ob_string[8:]
				shape_name = ob_name + '_shape'
				
				# TODO: if actual power production loadshape is available for a given storage object, insert it, else use synthetic loadshapes as defined here
				if ob_name.endswith('_existing'):
					# print("2_storage:", ob)
					# if object is outside of microgrid and without a loadshape, give it a loadshape of zeros
					if ob_name not in gen_obs_existing and f'loadshape.{shape_name}' not in load_map:					
						# print("3_storage:", ob)
						ob['yearly'] = shape_name
						shape_data = list_of_zeros
						shape_insert_list[i] = {
							'!CMD': 'new',
							'object': f'loadshape.{shape_name}',
							'npts': '8760',
							'interval': '1',
							'useactual': 'yes',
							'mult': f'{list(shape_data)}'.replace(' ','')
						}
					
					elif ob_name in gen_obs_existing:
						# print("4_storage:", ob)
						# if loadshape object already exists, overwrite the 8760 hour data in ['mult']
						# ASSUMPTION: Existing generators in gen_obs_existing will be reconfigured to be controlled by new microgrid
						if f'loadshape.{shape_name}' in load_map:
							# print("4a_storage:", ob)
							j = load_map.get(f'loadshape.{shape_name}') # indexes of load_map and tree match				
							shape_data = gen_df[ob_name]
							# print(shape_name, 'shape_data:', shape_data.head(20))
							tree[j]['mult'] = f'{list(shape_data)}'.replace(' ','')
							# print(shape_name, "tree[j]['mult']:", tree[j]['mult'][:20])
							# print("4a_storage achieved insert")
						else:
							# print("4b_storage:", ob)
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
							# print(shape_name, "shapedata:", shape_data.head(20))
							# print("4b_storage achieved insert")
				# insert loadshapes for new storage objects with shape_data in GEN_NAME
				elif f'loadshape.{shape_name}' not in load_map:
					# print("5_storage", ob)
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
		except:
			pass #Old existing gen, ignore.
	# Do shape insertions at proper places
	for key in shape_insert_list:
		min_pos = min(shape_insert_list.keys())
		tree.insert(min_pos, shape_insert_list[key])
	# Write new DSS file.
	dssConvert.treeToDss(tree, FULL_NAME)

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
			trace = plotly.graph_objs.Scatter(
				x = pd.to_datetime(this_series[x], unit = 'h', origin = pd.Timestamp(f'{year}-01-01')), #TODO: make this datetime convert arrays other than hourly or with a different startdate than Jan 1 if needed
				y = this_series[y_name], # ToDo: rounding to 3 decimals here would be ideal, but doing so does not accept Inf values 
				name = ob_name + '_' + y_name,
				hoverlabel = dict(namelength = -1)
			)
			data.append(trace)

	layout = plotly.graph_objs.Layout(
		#title = f'{csvName} Output',
		title = chart_name,
		xaxis = dict(title="Date"),
		yaxis = dict(title=y_axis_name)
		#yaxis = dict(title = str(y_list))
	)
	fig = plotly.graph_objs.Figure(data, layout)

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

def microgrid_report_csv(inputName, outputCsvName, REOPT_FOLDER, microgrid, mg_name, max_crit_load, diesel_total_calc):
	''' Generate a report on each microgrid '''
	reopt_out = json.load(open(REOPT_FOLDER + inputName))
	gen_sizes = get_gen_ob_from_reopt(REOPT_FOLDER, diesel_total_calc=diesel_total_calc)
	solar_size_total = gen_sizes.get('solar_size_total')
	solar_size_new = gen_sizes.get('solar_size_new')
	solar_size_existing = gen_sizes.get('solar_size_existing')
	diesel_size_total = gen_sizes.get('diesel_size_total')
	diesel_size_new = gen_sizes.get('diesel_size_new')
	diesel_size_existing = gen_sizes.get('diesel_size_existing')
	wind_size_total = gen_sizes.get('wind_size_total')
	wind_size_new = gen_sizes.get('wind_size_new')
	wind_size_existing = gen_sizes.get('wind_size_existing')
	battery_cap_total = gen_sizes.get('battery_cap_total')
	battery_cap_new = gen_sizes.get('battery_cap_new')
	battery_cap_existing = gen_sizes.get('battery_cap_existing')
	battery_pow_total = gen_sizes.get('battery_pow_total')
	battery_pow_new = gen_sizes.get('battery_pow_new')
	battery_pow_existing = gen_sizes.get('battery_pow_existing')

	with open(outputCsvName, 'w', newline='') as outcsv:
		writer = csv.writer(outcsv)
		writer.writerow(["Microgrid Name", "Generation Bus", "Minimum 1 hr Load (kW)", "Average 1 hr Load (kW)",
							"Average Daytime 1 hr Load (kW)", "Maximum 1 hr Load (kW)", "Maximum 1 hr Critical Load (kW)", "Existing Diesel (kW)", "New Diesel (kW)",
							"Diesel Fuel Used During Outage (gal)", "Existing Solar (kW)", "New Solar (kW)", 
							"Existing Battery Power (kW)", "New Battery Power (kW)", "Existing Battery Energy Storage (kWh)", 
							"New Battery Energy Storage (kWh)", "Existing Wind (kW)", "New Wind (kW)", 
							"Total Generation on Grid (kW)", "NPV over 25 years ($)", "CapEx ($)", "CapEx after Incentives ($)", 
							"Average Outage Survived (h)"])
		mg_num = 1 # mg_num refers to the key suffix in allOutputData.json from reopt folder
		mg_ob = microgrid
		gen_bus_name = mg_ob['gen_bus']
		load = reopt_out.get(f'load{mg_num}', 0.0)
		min_load = min(load)
		ave_load = sum(load)/len(load)
		np_load = np.array_split(load, 365)
		np_load = np.array(np_load) #a flattened array of 365 arrays of 24 hours each
		daytime_kwh = np_load[:,9:17] #365 8-hour daytime arrays
		avg_daytime_load = np.average(np.average(daytime_kwh, axis=1))
		max_load = max(load)
		max_crit_load = max_crit_load
		diesel_used_gal =reopt_out.get(f'fuelUsedDiesel{mg_num}', 0.0)
		total_gen = diesel_size_total + solar_size_total + battery_pow_total + wind_size_total

		#TODO: Redo post-REopt economic calculations to match updated discounts, taxations, etc
		npv = reopt_out.get(f'savings{mg_num}', 0.0) # overall npv against the business as usual case from REopt
		cap_ex = reopt_out.get(f'initial_capital_costs{mg_num}', 0.0) # description from REopt: Up-front capital costs for all technologies, in present value, excluding replacement costs and incentives
		cap_ex_after_incentives = reopt_out.get(f'initial_capital_costs_after_incentives{mg_num}', 0.0) # description from REopt: Up-front capital costs for all technologies, in present value, excluding replacement costs, including incentives
		
		# TODO: Once incentive structure is finalized, update NPV and cap_ex_after_incentives calculation to include depreciation over time if appropriate
		# TODO: update logic to remove existing batteries if battery_pow_new > 0
		# economic outcomes with the capital costs of existing wind and batteries deducted:
		# npv_existing_gen_adj = npv \
		# 						+ wind_size_existing * reopt_out.get(f'windCost{mg_num}', 0.0) \
		# 						+ battery_cap_existing * reopt_out.get(f'batteryCapacityCost{mg_num}', 0.0) \
		# 						+ battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0)
		cap_ex_existing_gen_adj = cap_ex \
								- wind_size_existing * reopt_out.get(f'windCost{mg_num}', 0.0) \
								- battery_cap_existing * reopt_out.get(f'batteryCapacityCost{mg_num}', 0.0) \
								- battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0)
		#TODO: UPDATE cap_ex_after_incentives_existing_gen_adj in 2022 to erase the 18% cost reduction for wind above 100kW as it will have ended
		# cap_ex_after_incentives_existing_gen_adj = cap_ex_after_incentives \
		# 						- wind_size_existing * reopt_out.get(f'windCost{mg_num}', 0.0)*.82 \
		# 						- battery_cap_existing * reopt_out.get(f'batteryCapacityCost{mg_num}', 0.0) \
		# 						- battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0)
		ave_outage = reopt_out.get(f'avgOutage{mg_num}')
		if ave_outage is not None:
			ave_outage = int(round(ave_outage))
		
		row =[str(mg_name), gen_bus_name, round(min_load), round(ave_load), round(avg_daytime_load), round(max_load), round(max_crit_load),
		round(diesel_size_existing,1), round(diesel_size_new,1), round(diesel_used_gal, 0), round(solar_size_existing,1), 
		round(solar_size_new,1), round(battery_pow_existing,1), round(battery_pow_new,1), round(battery_cap_existing,1), 
		round(battery_cap_new,1), round(wind_size_existing,1), round(wind_size_new,1), round(total_gen,1),
		int(round(npv)), int(round(cap_ex_existing_gen_adj)), int(round(cap_ex_after_incentives)),ave_outage]
		writer.writerow(row)

def microgrid_report_list_of_dicts(inputName, REOPT_FOLDER, microgrid, mg_name, max_crit_load, diesel_total_calc):
	''' Generate a dictionary reports fr each key for all microgrids. '''
	reopt_out = json.load(open(REOPT_FOLDER + inputName))
	gen_sizes = get_gen_ob_from_reopt(REOPT_FOLDER, diesel_total_calc=diesel_total_calc)
	solar_size_total = gen_sizes.get('solar_size_total')
	solar_size_new = gen_sizes.get('solar_size_new')
	solar_size_existing = gen_sizes.get('solar_size_existing')
	diesel_size_total = gen_sizes.get('diesel_size_total')
	diesel_size_new = gen_sizes.get('diesel_size_new')
	diesel_size_existing = gen_sizes.get('diesel_size_existing')
	wind_size_total = gen_sizes.get('wind_size_total')
	wind_size_new = gen_sizes.get('wind_size_new')
	wind_size_existing = gen_sizes.get('wind_size_existing')
	battery_cap_total = gen_sizes.get('battery_cap_total')
	battery_cap_new = gen_sizes.get('battery_cap_new')
	battery_cap_existing = gen_sizes.get('battery_cap_existing')
	battery_pow_total = gen_sizes.get('battery_pow_total')
	battery_pow_new = gen_sizes.get('battery_pow_new')
	battery_pow_existing = gen_sizes.get('battery_pow_existing')
	list_of_mg_dict = []
	mg_dict = {}
	mg_num = 1
	mg_ob = microgrid
	# mg_dict["Microgrid Name"] = str(REOPT_FOLDER[-1]) # previously used sequential numerical naming
	mg_dict["Microgrid Name"] = str(mg_name)
	mg_dict["Generation Bus"] = mg_ob['gen_bus']
	load = reopt_out.get(f'load1', 0.0)
	mg_dict["Minimum 1 hr Load (kW)"] = round(min(load),0)
	mg_dict["Average 1 hr Load (kW)"] = round(sum(load)/len(load),0)
	# build the average daytime load
	np_load = np.array_split(load, 365)
	np_load = np.array(np_load) #a flattened array of 365 arrays of 24 hours each
	daytime_kwh = np_load[:,9:17] #365 8-hour daytime arrays
	mg_dict["Average Daytime 1 hr Load (kW)"] = round(np.average(np.average(daytime_kwh, axis=1)),0)
	mg_dict["Maximum 1 hr Load (kW)"] = round(max(load),0)
	mg_dict["Maximum 1 hr Critical Load (kW)"] = round(max_crit_load,0)
	mg_dict["Existing Diesel (kW)"] = round(diesel_size_existing,0)
	mg_dict["New Diesel (kW)"] = round(diesel_size_new,0)
	mg_dict["Diesel Fuel Used During Outage (gal)"] = round(reopt_out.get(f'fuelUsedDiesel{mg_num}', 0.0),0)
	mg_dict["Existing Solar (kW)"] = round(solar_size_existing ,0)
	mg_dict["New Solar (kW)"] = round(solar_size_total - solar_size_existing,0)
	mg_dict["Existing Battery Power (kW)"] = round(battery_pow_existing,0)
	mg_dict["New Battery Power (kW)"] = round(battery_pow_new,0)
	mg_dict["Existing Battery Energy Storage (kWh)"] = round(battery_cap_existing,0)
	mg_dict["New Battery Energy Storage (kWh)"] = round(battery_cap_new,0)
	mg_dict["Existing Wind (kW)"] = round(wind_size_existing,0)
	mg_dict["New Wind (kW)"] = round(wind_size_new,0)
	total_gen = diesel_size_total + solar_size_total + battery_pow_total + wind_size_total
	mg_dict["Total Generation on Grid (kW)"] = round(total_gen,0)
	npv = reopt_out.get(f'savings{mg_num}', 0.0) # overall npv against the business as usual case from REopt
	cap_ex = reopt_out.get(f'initial_capital_costs{mg_num}', 0.0) # description from REopt: Up-front capital costs for all technologies, in present value, excluding replacement costs and incentives
	cap_ex_after_incentives = reopt_out.get(f'initial_capital_costs_after_incentives{mg_num}', 0.0) # description from REopt: Up-front capital costs for all technologies, in present value, excluding replacement costs, including incentives
	
	#TODO: Once incentive structure is finalized, update NPV and cap_ex_after_incentives calculation to include depreciation over time if appropriate
	# TODO: update logic to remove existing batteries if battery_pow_new > 0
	# economic outcomes with the capital costs of existing wind and batteries deducted:
	# npv_existing_gen_adj = npv \
	# 						+ wind_size_existing * reopt_out.get(f'windCost{mg_num}', 0.0) \
	# 						+ battery_cap_existing * reopt_out.get(f'batteryCapacityCost{mg_num}', 0.0) \
	# 						+ battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0)
	# mg_dict["Net Present Value ($)"] = f'{round(npv_existing_gen_adj):,}'
	mg_dict["NPV over 25 years ($)"] = f'{round(npv):,}'
	cap_ex_existing_gen_adj = cap_ex \
							- wind_size_existing * reopt_out.get(f'windCost{mg_num}', 0.0) \
							- battery_cap_existing * reopt_out.get(f'batteryCapacityCost{mg_num}', 0.0) \
							- battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0)
	mg_dict["CapEx ($)"] = f'{round(cap_ex_existing_gen_adj):,}'
	# cap_ex_after_incentives_existing_gen_adj = cap_ex_after_incentives \
	# 						- wind_size_existing * reopt_out.get(f'windCost{mg_num}', 0.0)*.82 \
	# 						- battery_cap_existing * reopt_out.get(f'batteryCapacityCost{mg_num}', 0.0) \
	# 						- battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0) 
	# mg_dict["CapEx after Incentives ($)"] = f'{round(cap_ex_after_incentives_existing_gen_adj):,}'
	mg_dict["CapEx after Incentives ($)"] = f'{round(cap_ex_after_incentives):,}'
	ave_outage = reopt_out.get(f'avgOutage{mg_num}')
	if ave_outage is not None:
		ave_outage = int(round(ave_outage))
	mg_dict["Average Outage Survived (h)"] = ave_outage

	list_of_mg_dict.append(mg_dict)
	# print(list_of_mg_dict)
	return(list_of_mg_dict)

def summary_stats(reps):
	'''Helper function within full() to take in a dict of lists of the microgrid
	attributes and append a summary value for each attribute'''

	reps['Microgrid Name'].append('Summary')
	reps['Generation Bus'].append('None')
	reps['Minimum 1 hr Load (kW)'].append(round(sum(reps['Minimum 1 hr Load (kW)']),0))
	reps['Average 1 hr Load (kW)'].append(round(sum(reps['Average 1 hr Load (kW)']),0))
	reps['Average Daytime 1 hr Load (kW)'].append(round(sum(reps['Average Daytime 1 hr Load (kW)']),0))
	reps['Maximum 1 hr Load (kW)'].append(round(sum(reps['Maximum 1 hr Load (kW)']),0))
	reps['Maximum 1 hr Critical Load (kW)'].append(round(sum(reps['Maximum 1 hr Critical Load (kW)']),0))
	reps['Existing Diesel (kW)'].append(round(sum(reps['Existing Diesel (kW)']),0))
	reps['New Diesel (kW)'].append(round(sum(reps['New Diesel (kW)']),0))
	reps['Diesel Fuel Used During Outage (gal)'].append(round(sum(reps['Diesel Fuel Used During Outage (gal)']),0))
	reps['Existing Solar (kW)'].append(round(sum(reps['Existing Solar (kW)']),0))
	reps['New Solar (kW)'].append(round(sum(reps['New Solar (kW)']),0))
	reps['Existing Battery Power (kW)'].append(round(sum(reps['Existing Battery Power (kW)']),0))
	reps['New Battery Power (kW)'].append(round(sum(reps['New Battery Power (kW)']),0))
	reps['Existing Battery Energy Storage (kWh)'].append(round(sum(reps['Existing Battery Energy Storage (kWh)']),0))
	reps['New Battery Energy Storage (kWh)'].append(round(sum(reps['New Battery Energy Storage (kWh)']),0))
	reps['Existing Wind (kW)'].append(round(sum(reps['Existing Wind (kW)']),0))
	reps['New Wind (kW)'].append(round(sum(reps['New Wind (kW)']),0))
	reps['Total Generation on Grid (kW)'].append(round(sum(reps['Total Generation on Grid (kW)']),0))
	reps['NPV over 25 years ($)'].append(sum(reps['NPV over 25 years ($)']))
	reps['CapEx ($)'].append(sum(reps['CapEx ($)']))
	reps['CapEx after Incentives ($)'].append(sum(reps['CapEx after Incentives ($)']))
	if all([h != None for h in reps['Average Outage Survived (h)']]):
		reps['Average Outage Survived (h)'].append(round(min(reps['Average Outage Survived (h)']),0))
	else:
		reps['Average Outage Survived (h)'].append(None)
	return(reps)

def main(BASE_NAME, LOAD_NAME, REOPT_INPUTS, microgrid, playground_microgrids, GEN_NAME, REF_NAME, FULL_NAME, OMD_NAME, ONELINE_NAME, MAP_NAME, REOPT_FOLDER_BASE, REOPT_FOLDER_FINAL, BIG_OUT_NAME, QSTS_STEPS, DIESEL_SAFETY_FACTOR, FAULTED_LINE, mg_name, open_results=True):
	critical_load_percent, max_crit_load = set_critical_load_percent(LOAD_NAME, microgrid)
	reopt_gen_mg_specs(BASE_NAME, LOAD_NAME, REOPT_INPUTS, REOPT_FOLDER_BASE, microgrid, critical_load_percent)
	
	# to run microgridup with automatic feedback loop to update diesel size, include the following:
	# net_load = max_net_load('/allOutputData.json', REOPT_FOLDER_BASE)
	# diesel_total_calc = diesel_sizing('/allOutputData.json',REOPT_FOLDER_BASE, DIESEL_SAFETY_FACTOR, net_load)
	# feedback_reopt_gen_values(BASE_NAME, LOAD_NAME, REOPT_INPUTS, REOPT_FOLDER_BASE, REOPT_FOLDER_FINAL, microgrid, diesel_total_calc, critical_load_percent)
	
	# to run microgridup without automated diesel updates nor feedback loop, specify REOPT_FOLDER_BASE instead of REOPT_FOLDER_FINAL in build_new_gen_ob_and_shape(), microgrid_report_csv(), and microgrid_report_list_of_dicts(), the last argument of gen_existing_ref_shapes() and out = template.render() below
	# to run mgup with automated diesel updates, change the references back to REOPT_FOLDER_FINAL
	gen_obs = build_new_gen_ob_and_shape(REOPT_FOLDER_BASE, GEN_NAME, microgrid, BASE_NAME, mg_name, diesel_total_calc=False)
	gen_existing_ref_shapes(REF_NAME, REOPT_FOLDER_BASE, REOPT_FOLDER_BASE)
	make_full_dss(BASE_NAME, GEN_NAME, LOAD_NAME, FULL_NAME, REF_NAME, gen_obs, microgrid)
	dssConvert.dssToOmd(FULL_NAME, OMD_NAME, RADIUS=0.0002)
	# Draw the circuit oneline.
	distNetViz.viz(OMD_NAME, forceLayout=False, outputPath='.', outputName=ONELINE_NAME, open_file=False)
	# Draw the map.
	geo.mapOmd(OMD_NAME, MAP_NAME, 'html', openBrowser=False, conversion=False, offline=True)
	# Powerflow outputs.
	print('QSTS with ', FULL_NAME, 'AND CWD IS ', os.getcwd())
	opendss.newQstsPlot(FULL_NAME,
		stepSizeInMinutes=60, 
		numberOfSteps=QSTS_STEPS,
		keepAllFiles=False,
		actions={
			#24*5:'open object=line.671692 term=1',
			#24*8:'new object=fault.f1 bus1=670.1.2.3 phases=3 r=0 ontime=0.0'
		},
		filePrefix='timeseries'
	)
	# opendss.voltagePlot(FULL_NAME, PU=True)
	# opendss.currentPlot(FULL_NAME)
	#TODO!!!! we're clobbering these outputs each time we run the full workflow. Consider keeping them separate.
	#HACK: If only analyzing a set of generators with a single phase, remove ['P2(kW)','P3(kW)'] of make_chart('timeseries_gen.csv',...) below
	make_chart('timeseries_gen.csv', FULL_NAME, 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], REOPT_INPUTS['year'], QSTS_STEPS, "Generator Output", "kW per hour")
	# for timeseries_load, output ANSI Range A service bands (2,520V - 2,340V for 2.4kV and 291V - 263V for 0.277kV)
	make_chart('timeseries_load.csv', FULL_NAME, 'Name', 'hour', ['V1(PU)','V2(PU)','V3(PU)'], REOPT_INPUTS['year'], QSTS_STEPS, "Load Voltage", "PU", ansi_bands = True)
	make_chart('timeseries_source.csv', FULL_NAME, 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], REOPT_INPUTS['year'], QSTS_STEPS, "Voltage Source Output", "kW per hour")
	make_chart('timeseries_control.csv', FULL_NAME, 'Name', 'hour', ['Tap(pu)'], REOPT_INPUTS['year'], QSTS_STEPS, "Tap Position", "PU")
	# Perform control sim.

	microgridup_control.play(OMD_NAME, BASE_NAME, None, None, playground_microgrids, FAULTED_LINE, False, 60, 120, 30) #TODO: calculate 'max_potential_battery' and other mg parameters specific to microgrid_control.py on the fly from the outputs of REopt
	microgrid_report_csv('/allOutputData.json', f'ultimate_rep_{FULL_NAME}.csv', REOPT_FOLDER_BASE, microgrid, mg_name, max_crit_load, diesel_total_calc=False)
	mg_list_of_dicts_full = microgrid_report_list_of_dicts('/allOutputData.json', REOPT_FOLDER_BASE, microgrid, mg_name, max_crit_load, diesel_total_calc=False)
	# convert mg_list_of_dicts_full to dict of lists for columnar output in output_template.html
	mg_dict_of_lists_full = {key: [dic[key] for dic in mg_list_of_dicts_full] for key in mg_list_of_dicts_full[0]}
	# Create giant consolidated report.
	template = j2.Template(open(f'{MGU_FOLDER}/output_template.html').read())
	out = template.render(
		x='Daniel, David',
		y='Matt',
		summary=mg_dict_of_lists_full,
		inputs={'circuit':BASE_NAME,'loads':LOAD_NAME,'REopt inputs':REOPT_INPUTS,'microgrid':microgrid},
		reopt_folders=[REOPT_FOLDER_BASE]
	)
	#TODO: have an option where we make the template <iframe srcdoc="{{X}}"> to embed the html and create a single file.
	with open(BIG_OUT_NAME,'w') as outFile:
		outFile.write(out)
	if open_results:
		os.system(f'open {BIG_OUT_NAME}')

def full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, DIESEL_SAFETY_FACTOR, REOPT_INPUTS, MICROGRIDS, FAULTED_LINE):
	# CONSTANTS
	MODEL_DSS = 'circuit.dss'
	MODEL_LOAD_CSV = 'loads.csv'
	GEN_NAME = 'generation.csv'
	REF_NAME = 'ref_gen_loads.csv'
	OMD_NAME = 'circuit.dss.omd'
	MAP_NAME = 'circuit_map'
	ONELINE_NAME = 'circuit_oneline.html'
	# Create initial files.
	if not os.path.isdir(MODEL_DIR):
		os.mkdir(MODEL_DIR)
	shutil.copyfile(BASE_DSS, f'{MODEL_DIR}/{MODEL_DSS}')
	shutil.copyfile(LOAD_CSV, f'{MODEL_DIR}/{MODEL_LOAD_CSV}')

	# HACK: work in directory because we're very picky about the current dir.
	os.chdir(MODEL_DIR)
	if os.path.exists("user_warnings.txt"):
		os.remove("user_warnings.txt")
	# Run the analysis
	mgs_name_sorted = sorted(MICROGRIDS.keys())
	for i, mg_name in enumerate(mgs_name_sorted):
		BASE_DSS = MODEL_DSS if i==0 else f'circuit_plusmg_{i-1}.dss'
		main(BASE_DSS, MODEL_LOAD_CSV, REOPT_INPUTS, MICROGRIDS[mg_name], MICROGRIDS, GEN_NAME, REF_NAME, f'circuit_plusmg_{i}.dss', OMD_NAME, ONELINE_NAME, MAP_NAME, f'reopt_base_{i}', f'reopt_final_{i}', f'output_full_{i}.html', QSTS_STEPS, DIESEL_SAFETY_FACTOR, FAULTED_LINE, mg_name, open_results=False)
	# Build Final report
	reports = [x for x in os.listdir('.') if x.startswith('ultimate_rep_')]
	reports.sort()
	reopt_folders = [x for x in os.listdir('.') if x.startswith('reopt_final_')]
	reopt_folders.sort()
	reps = pd.concat([pd.read_csv(x) for x in reports]).to_dict(orient='list')
	stats = summary_stats(reps)
	current_time = datetime.datetime.now() 
	warnings = "None"
	if os.path.exists("user_warnings.txt"):
		with open("user_warnings.txt") as myfile:
			warnings = myfile.read()

	template = j2.Template(open(f'{MGU_FOLDER}/output_template.html').read())
	out = template.render(
		x='Daniel, David',
		y='Matt',
		now=current_time,
		summary=stats,
		inputs={'circuit':BASE_DSS,'loads':LOAD_CSV,'REopt inputs':REOPT_INPUTS,'microgrid':MICROGRIDS}, #TODO: Make the inputs clearer and maybe at the bottom, showing only the appropriate keys from MICROGRIDS as necessary
		reopt_folders=reopt_folders,
		warnings = warnings
	)
	FINAL_REPORT = 'output_final.html'
	with open(FINAL_REPORT,'w') as outFile:
		outFile.write(out)
	os.system(f'open {FINAL_REPORT}')

if __name__ == '__main__':
	print('No Inputs Received')