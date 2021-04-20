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

def reopt_gen_mg_specs(BASE_NAME, LOAD_NAME, REOPT_INPUTS, REOPT_FOLDER, microgrid):
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

		# Pull out and add up kw of all exostong generators in the microgrid
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
		
		# if not already turned on, set solar and wind on to 10 kw to provide loadshapes for existing gen in make_full_dss()
		# if allInputData['wind'] == 'off':
		# 	allInputData['wind'] = 'on'
		# 	allInputData['windMax'] = '10'
		# 	allInputData['windMin'] = '10'
		# if allInputData['solar'] == 'off':
		# 	allInputData['solar'] = 'on'
		# 	allInputData['solarMax'] = '10'
		# 	allInputData['solarMin'] = '10'

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
	#print("Max total load for", REOPT_FOLDER, ":", max_total_load)
	#print("Max load needed to be supported by diesel for", REOPT_FOLDER, ":", max_net_load)
	#print("% more kW diesel needed than recommended by REopt for", REOPT_FOLDER, ":", round(100*(max_net_load - diesel_REopt)/diesel_REopt))
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
	#print(diesel_total_calc,"kW diesel_total_calc is", round(100*(diesel_total_calc-diesel_total_REopt)/diesel_total_REopt), "% more kW diesel than recommended by REopt for", REOPT_FOLDER)
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
	wind_size_total = reopt_out.get(f'sizeWind{mg_num}', 0.0) # TO DO: Update size of wind based on existing generation once we find a way to get a loadshape for that wind if REopt recommends no wind
	wind_size_existing = reopt_out.get(f'windExisting{mg_num}', 0.0)
	if wind_size_total - wind_size_existing > 0:
		wind_size_new = wind_size_total - wind_size_existing 
	else:
		wind_size_new = 0.0 #TO DO: update logic here to make run more robust to oversized existing wind gen	
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

def feedback_reopt_gen_values(BASE_NAME, LOAD_NAME, REOPT_INPUTS, REOPT_FOLDER_BASE, REOPT_FOLDER_FINAL, microgrid, diesel_total_calc):
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
		print("outage_start_hour:", str(int(outage_start_hour)))
		allInputData['outage_start_hour'] = str(int(outage_start_hour))

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

		# Update all generator specifications in the microgrid from outputs of REOPT_FOLDER_BASE
		gen_sizes = get_gen_ob_from_reopt(REOPT_FOLDER_BASE, diesel_total_calc=diesel_total_calc)
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

		if diesel_size_total > 0:
			allInputData['dieselMax'] = diesel_size_total
			allInputData['dieselMin'] = diesel_size_total
			allInputData['genExisting'] = diesel_size_existing
		if solar_size_total > 0: #and solar_size_total != 10: # enable the dual condition to let user decide whether to optimize on solar or not
			allInputData['solarMin'] = solar_size_total
			allInputData['solarMax'] = solar_size_total
			allInputData['solarExisting'] = solar_size_existing
			allInputData['solar'] = 'on'
		if battery_cap_total > 0:
			allInputData['batteryPowerMin'] = battery_pow_total
			allInputData['batteryPowerMax'] = battery_pow_total
			allInputData['batteryKwExisting'] = battery_pow_existing
			allInputData['batteryCapacityMin'] = battery_cap_total
			allInputData['batteryCapacityMax'] = battery_cap_total
			allInputData['batteryKwhExisting'] = battery_cap_existing
			allInputData['battery'] = 'on'
		if wind_size_total > 0: #and wind_size_total != 10: # enable the dual condition to let user decide whether to optimize on wind or not
			allInputData['windMin'] = wind_size_total
			allInputData['windMax'] = wind_size_total
			allInputData['windExisting'] = wind_size_existing
			allInputData['wind'] = 'on' #failsafe to include wind if found in base_dss
			 # TO DO: update logic if windMin, windExisting and other generation variables are enabled to be set by the user as inputs
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
	#print('out_dict', out_dict)
	return out_dict
	
def build_new_gen_ob_and_shape(REOPT_FOLDER, GEN_NAME, microgrid, BASE_NAME, diesel_total_calc=False):
	'''Create new generator objects and shapes. 
	Returns a list of generator objects formatted for reading into openDSS tree.
	SIDE EFFECTS: creates GEN_NAME generator shape
	TODO: To implement multiple same-type existing generators within a single microgrid, 
	will need to implement searching the tree of FULL_NAME to find kw ratings of existing gens'''

	gen_sizes = get_gen_ob_from_reopt(REOPT_FOLDER)
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
		gen_df_builder[f'diesel_{gen_bus_name}'] = pd.DataFrame(np.zeros(8760)) # insert an array of zeros for the diesel generation shape to simulate no outage
	# build loadshapes for existing generation from BASE_NAME, inputting the 0-1 diesel generation loadshape 
	if diesel_size_existing > 0:	
		for gen_ob_existing in gen_obs_existing:
			if gen_ob_existing.startswith('diesel_'):
				# gen_df_builder[f'{gen_ob_existing}'] = pd.Series(reopt_out.get(f'powerDiesel{mg_num}'))/diesel_size_total # insert the 0-1 diesel generation shape provided by REopt to simulate the outage specified in REopt
				# TODO: if using real loadshapes for diesel, need to scale them based on rated kw of that individual generator object
				gen_df_builder[f'{gen_ob_existing}'] = pd.DataFrame(np.zeros(8760)) # insert an array of zeros for the diesel generation shape to simulate no outage
	
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
	# TO DO: in the case of new kw but not new kwh (or vice versa) recommedned by feedback_reopt(), integrate a way to add new batteries with a minimal kwh and kw so that powerflow can be performed
	if battery_cap_new > 0: # or battery_pow_new > 0: 
		gen_obs.append({
			'!CMD': 'new',
			'object':f'storage.battery_{gen_bus_name}',
			'bus1':f"{gen_bus_name}.{'.'.join(phase_and_kv['phases'])}",
			'phases':len(phase_and_kv['phases']),
			'kv':phase_and_kv['kv'],
			'kwrated':f'{battery_pow_new}',
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

def make_full_dss(BASE_NAME, GEN_NAME, LOAD_NAME, FULL_NAME, gen_obs, microgrid):
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
	shape_insert_list = {}
	load_df = pd.read_csv(LOAD_NAME)
	list_of_zeros = [0.0] * 8760
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
							shape_data = list_of_zeros
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
							shape_data = list_of_zeros
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
						# if loadshape object already exists, erase it from tree and insert a new one
						# ASSUMPTION: Existing generators will be reconfigured to be controlled by new microgrid
						if f'loadshape.{shape_name}' in load_map:
							# print("4a_gen:", ob)
							j = load_map.get(f'loadshape.{shape_name}') # indexes of load_map and tree match
							tree.pop(j) # this will erase an existing loadshape object of the same name in the tree so that a new on can be entered
							shape_data = gen_df[ob_name]
							# print('shape_data', shape_data.head(10))
							# NOTE: enter the loadshape at index j, equivalent to where it previously was located
							shape_insert_list[j] = {
								'!CMD': 'new',
								'object': f'loadshape.{shape_name}',
								'npts': f'{len(shape_data)}',
								'interval': '1',
								'useactual': 'yes',
								'mult': f'{list(shape_data)}'.replace(' ','')
							}
							# print("4a achieved insert")
						else:
							ob['yearly'] = shape_name
							# print("ob['yearly']:", ob['yearly'])
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
					# print("ob['yearly']:", ob['yearly'])
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
				# print('ob_name:', ob_name)
				shape_name = ob_name + '_shape'
				# print('shape_name:', shape_name)
				
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
							#'mult': f'{list_of_zeros}'.replace(' ','')
						}
					
					elif ob_name in gen_obs_existing:
						# print("4_storage:", ob)
						# if loadshape object already exists, erase it from tree and insert a new one
						# ASSUMPTION: Existing generators will be reconfigured to be controlled by new microgrid
						if f'loadshape.{shape_name}' in load_map:
							# print("4a_storage:", ob)
							j = load_map.get(f'loadshape.{shape_name}') # indexes of load_map and tree match
							tree.pop(j) # this will erase an existing loadshape object of the same name in the tree so that a new on can be entered
							shape_data = gen_df[ob_name]
							# print('shape_data', shape_data.head(10))
							# enter the loadshape at index j, equivalent to where it previously was located
							shape_insert_list[j] = {
								'!CMD': 'new',
								'object': f'loadshape.{shape_name}',
								'npts': f'{len(shape_data)}',
								'interval': '1',
								'useactual': 'yes',
								'mult': f'{list(shape_data)}'.replace(' ','')
							}
						# 	# print("4a achieved insert")
						# if f'loadshape.{shape_name}' in load_map:
						# 	print("4a_storage:", ob)
						# 	j = load_map.get(f'loadshape.{shape_name}') # indexes of load_map and tree match				
						# 	shape_data = gen_df[ob_name]
						# 	print('shape_data', shape_data.head(10))
						# 	tree[j]['mult'] = f'{list(shape_data)}'.replace(' ','')
						# 	print("4a_storage achieved insert")
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

def make_chart(csvName, category_name, x, y_list, year, qsts_steps, ansi_bands=False):
	''' Charting outputs. '''
	gen_data = pd.read_csv(csvName)
	data = [] 
	for ob_name in set(gen_data[category_name]):
		for y_name in y_list:
			this_series = gen_data[gen_data[category_name] == ob_name]
			trace = plotly.graph_objs.Scatter(
				x = pd.to_datetime(this_series[x], unit = 'h', origin = pd.Timestamp(f'{year}-01-01')), #TODO: make this datetime convert arrays other than hourly or with a different startdate than Jan 1 if needed
				y = this_series[y_name], # ToDo: rounding to 3 decimals here would be ideal, but doing so does not accept Inf values 
				name = ob_name + '_' + y_name,
				hoverlabel = dict(namelength = -1)
			)
			data.append(trace)

	layout = plotly.graph_objs.Layout(
		title = f'{csvName} Output',
		# xaxis = dict(title = x),
		xaxis = dict(title="Time"),
		yaxis = dict(title = str(y_list))
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

def microgrid_report_csv(inputName, outputCsvName, REOPT_FOLDER, microgrid, diesel_total_calc):
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
		writer.writerow(["Microgrid Name", "Generation Bus", "Minimum Load (kWh)", "Average Load (kWh)",
							"Average Daytime Load (kWh)", "Maximum Load (kWh)", "Existing Diesel (kW)", "Recommended New Diesel (kW)",
							"Diesel Fuel Used During Outage (gal)", "Existing Solar (kW)", "Recommended New Solar (kW)", 
							"Existing Battery Power (kW)", "Recommended New Battery Power (kW)", "Existing Battery Capacity (kWh)", 
							"Recommended New Battery Capacity (kWh)", "Existing Wind (kW)", "Recommended New Wind (kW)", 
							"Total Generation on Grid (kW)", "NPV ($)", "CapEx ($)", "CapEx after Incentives ($)", 
							"Average Outage Survived (h)"])
		mg_num = 1
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
		diesel_used_gal =reopt_out.get(f'fuelUsedDiesel{mg_num}', 0.0)
		total_gen = diesel_size_total + solar_size_total + battery_pow_total + wind_size_total

		#TODO: Redo post-REopt economic calculations to match updated discounts, taxations, etc
		npv = reopt_out.get(f'savings{mg_num}', 0.0) # overall npv against the business as usual case from REopt
		cap_ex = reopt_out.get(f'initial_capital_costs{mg_num}', 0.0) # description from REopt: Up-front capital costs for all technologies, in present value, excluding replacement costs and incentives
		cap_ex_after_incentives = reopt_out.get(f'initial_capital_costs_after_incentives{mg_num}', 0.0) # description from REopt: Up-front capital costs for all technologies, in present value, excluding replacement costs, including incentives
		
		# TODO: Once incentive structure is finalized, update NPV and cap_ex_after_incentives calculation to include depreciation over time if appropriate
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
		
		row =[str(REOPT_FOLDER[-1]), gen_bus_name, round(min_load,0), round(ave_load,0), round(avg_daytime_load,1), round(max_load,0),
		round(diesel_size_existing,1), round(diesel_size_new,1), round(diesel_used_gal, 0), round(solar_size_existing,1), 
		round(solar_size_new,1), round(battery_pow_existing,1), round(battery_pow_new,1), round(battery_cap_existing,1), 
		round(battery_cap_new,1), round(wind_size_existing,1), round(wind_size_new,1), round(total_gen,1),
		int(round(npv)), int(round(cap_ex_existing_gen_adj)), int(round(cap_ex_after_incentives)),ave_outage]
		writer.writerow(row)

def microgrid_report_list_of_dicts(inputName, REOPT_FOLDER, microgrid, diesel_total_calc):
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
	mg_dict["Microgrid Name"] = str(REOPT_FOLDER[-1])
	mg_dict["Generation Bus"] = mg_ob['gen_bus']
	load = reopt_out.get(f'load1', 0.0)
	mg_dict["Minimum Load (kWh)"] = round(min(load),0)
	mg_dict["Average Load (kWh)"] = round(sum(load)/len(load),0)
	# build the average daytime load
	np_load = np.array_split(load, 365)
	np_load = np.array(np_load) #a flattened array of 365 arrays of 24 hours each
	daytime_kwh = np_load[:,9:17] #365 8-hour daytime arrays
	mg_dict["Average Daytime Load (kWh)"] = round(np.average(np.average(daytime_kwh, axis=1)),0)
	mg_dict["Maximum Load (kWh)"] = round(max(load),0)
	mg_dict["Existing Diesel (kW)"] = round(diesel_size_existing,0)
	mg_dict["Recommended New Diesel (kW)"] = round(diesel_size_new,0)
	mg_dict["Diesel Fuel Used During Outage (gal)"] = round(reopt_out.get(f'fuelUsedDiesel{mg_num}', 0.0),0)
	mg_dict["Existing Solar (kW)"] = round(solar_size_existing ,0)
	mg_dict["Recommended New Solar (kW)"] = round(solar_size_total - solar_size_existing,0)
	mg_dict["Existing Battery Power (kW)"] = round(battery_pow_existing,0)
	mg_dict["Recommended New Battery Power (kW)"] = round(battery_pow_new,0)
	mg_dict["Existing Battery Capacity (kWh)"] = round(battery_cap_existing,0)
	mg_dict["Recommended New Battery Capacity (kWh)"] = round(battery_cap_new,0)
	mg_dict["Existing Wind (kW)"] = round(wind_size_existing,0)
	mg_dict["Recommended New Wind (kW)"] = round(wind_size_new,0)
	total_gen = diesel_size_total + solar_size_total + battery_pow_total + wind_size_total
	mg_dict["Total Generation on Grid (kW)"] = round(total_gen,0)
	npv = reopt_out.get(f'savings{mg_num}', 0.0) # overall npv against the business as usual case from REopt
	cap_ex = reopt_out.get(f'initial_capital_costs{mg_num}', 0.0) # description from REopt: Up-front capital costs for all technologies, in present value, excluding replacement costs and incentives
	cap_ex_after_incentives = reopt_out.get(f'initial_capital_costs_after_incentives{mg_num}', 0.0) # description from REopt: Up-front capital costs for all technologies, in present value, excluding replacement costs, including incentives
	
	#TODO: Once incentive structure is finalized, update NPV and cap_ex_after_incentives calculation to include depreciation over time if appropriate
	# economic outcomes with the capital costs of existing wind and batteries deducted:
	# npv_existing_gen_adj = npv \
	# 						+ wind_size_existing * reopt_out.get(f'windCost{mg_num}', 0.0) \
	# 						+ battery_cap_existing * reopt_out.get(f'batteryCapacityCost{mg_num}', 0.0) \
	# 						+ battery_pow_existing * reopt_out.get(f'batteryPowerCost{mg_num}', 0.0)
	# mg_dict["Net Present Value ($)"] = f'{round(npv_existing_gen_adj):,}'
	mg_dict["Net Present Value ($)"] = f'{round(npv):,}'
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

def main(BASE_NAME, LOAD_NAME, REOPT_INPUTS, microgrid, playground_microgrids, GEN_NAME, FULL_NAME, OMD_NAME, ONELINE_NAME, MAP_NAME, REOPT_FOLDER_BASE, REOPT_FOLDER_FINAL, BIG_OUT_NAME, QSTS_STEPS, DIESEL_SAFETY_FACTOR, open_results=True):
	reopt_gen_mg_specs(BASE_NAME, LOAD_NAME, REOPT_INPUTS, REOPT_FOLDER_BASE, microgrid)
	
	# to run microgridup with automatic feedback loop, include the following:
	net_load = max_net_load('/allOutputData.json', REOPT_FOLDER_BASE)
	diesel_total_calc = diesel_sizing('/allOutputData.json',REOPT_FOLDER_BASE, DIESEL_SAFETY_FACTOR, net_load)
	feedback_reopt_gen_values(BASE_NAME, LOAD_NAME, REOPT_INPUTS, REOPT_FOLDER_BASE, REOPT_FOLDER_FINAL, microgrid, diesel_total_calc)
	
	# to run microgridup without automated diesel updates nor feedback loop, specify REOPT_FOLDER_BASE instead of REOPT_FOLDER_FINAL in build_new_gen_ob_and_shape(), microgrid_report_csv(), and microgrid_report_list_of_dicts() and out = template.render() below
	gen_obs = build_new_gen_ob_and_shape(REOPT_FOLDER_FINAL, GEN_NAME, microgrid, BASE_NAME, diesel_total_calc=False)
	make_full_dss(BASE_NAME, GEN_NAME, LOAD_NAME, FULL_NAME, gen_obs, microgrid)
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
	make_chart('timeseries_gen.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], REOPT_INPUTS['year'], QSTS_STEPS) #TODO: pull year using reopt_out.get(f'year{mg_num}', 0.0) from allOutputData.json after refactor
	# for timeseries_load, output ANSI Range A service bands (2,520V - 2,340V for 2.4kV and 291V - 263V for 0.277kV)
	make_chart('timeseries_load.csv', 'Name', 'hour', ['V1(PU)','V2(PU)','V3(PU)'], REOPT_INPUTS['year'], QSTS_STEPS, ansi_bands = True)
	make_chart('timeseries_source.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], REOPT_INPUTS['year'], QSTS_STEPS)
	make_chart('timeseries_control.csv', 'Name', 'hour', ['Tap(pu)'], REOPT_INPUTS['year'], QSTS_STEPS)
	# Perform control sim.
	microgridup_control.play(OMD_NAME, BASE_NAME, None, None, playground_microgrids, '670671', False, 1, 120, 30) #TODO: unify the microgrids data structure.
	microgrid_report_csv('/allOutputData.json', f'ultimate_rep_{FULL_NAME}.csv', REOPT_FOLDER_FINAL, microgrid, diesel_total_calc=False)
	mg_list_of_dicts_full = microgrid_report_list_of_dicts('/allOutputData.json', REOPT_FOLDER_FINAL, microgrid, diesel_total_calc=False)
	# convert mg_list_of_dicts_full to dict of lists for columnar output in output_template.html
	mg_dict_of_lists_full = {key: [dic[key] for dic in mg_list_of_dicts_full] for key in mg_list_of_dicts_full[0]}
	# Create giant consolidated report.
	template = j2.Template(open(f'{MGU_FOLDER}/output_template.html').read())
	out = template.render(
		x='Daniel, David',
		y='Matt',
		summary=mg_dict_of_lists_full,
		inputs={'circuit':BASE_NAME,'loads':LOAD_NAME,'REopt inputs':REOPT_INPUTS,'microgrid':microgrid},
		reopt_folders=[REOPT_FOLDER_FINAL]
	)
	#TODO: have an option where we make the template <iframe srcdoc="{{X}}"> to embed the html and create a single file.
	with open(BIG_OUT_NAME,'w') as outFile:
		outFile.write(out)
	if open_results:
		os.system(f'open {BIG_OUT_NAME}')

def full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, DIESEL_SAFETY_FACTOR, REOPT_INPUTS, MICROGRIDS):
	# CONSTANTS
	MODEL_DSS = 'circuit.dss'
	MODEL_LOAD_CSV = 'loads.csv'
	GEN_NAME = 'generation.csv'
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
	# Run the analysis
	mgs_name_sorted = sorted(MICROGRIDS.keys())
	for i, mg_name in enumerate(mgs_name_sorted):
		# STEP_FULL_NAME = MODEL_DSS if i==0 else f'circuit_plusmg_{i-1}.dss'
		BASE_DSS = MODEL_DSS if i==0 else f'circuit_plusmg_{i-1}.dss'
		main(BASE_DSS, MODEL_LOAD_CSV, REOPT_INPUTS, MICROGRIDS[mg_name], MICROGRIDS, GEN_NAME, f'circuit_plusmg_{i}.dss', OMD_NAME, ONELINE_NAME, MAP_NAME, f'reopt_base_{i}', f'reopt_final_{i}', f'output_full_{i}.html', QSTS_STEPS, DIESEL_SAFETY_FACTOR, open_results=False)
	# Final report
	reports = [x for x in os.listdir('.') if x.startswith('ultimate_rep_')]
	reopt_folders = [x for x in os.listdir('.') if x.startswith('reopt_final_')]
	reps = pd.concat([pd.read_csv(x) for x in reports]).to_dict(orient='list')
	template = j2.Template(open(f'{MGU_FOLDER}/output_template.html').read())
	out = template.render(
		x='Daniel, David',
		y='Matt',
		summary=reps,
		inputs={'circuit':BASE_DSS,'loads':LOAD_CSV,'REopt inputs':REOPT_INPUTS,'microgrid':MICROGRIDS},
		reopt_folders=reopt_folders
	)
	FINAL_REPORT = 'output_final.html'
	with open(FINAL_REPORT,'w') as outFile:
		outFile.write(out)
	os.system(f'open {FINAL_REPORT}')

if __name__ == '__main__':
	print('No Inputs Received')