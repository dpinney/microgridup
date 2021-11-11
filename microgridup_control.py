import random, re, datetime, json, os, tempfile, shutil, csv, math, base64
from os.path import join as pJoin
import subprocess
import pandas as pd
import numpy as np
import scipy
import collections
from scipy import spatial
import scipy.stats as st
from sklearn.preprocessing import LabelEncoder
import matplotlib.pyplot as plt
import plotly
import plotly.graph_objects as go
from plotly.tools import make_subplots

# OMF imports
import omf
from omf import geo
from omf import distNetViz
from omf.models import __neoMetaModel__
from omf.models.__neoMetaModel__ import *
from omf.models import flisr
from omf.solvers.opendss import dssConvert
from omf.solvers import opendss

def make_chart(csvName, category_name, x, y_list, year, microgrids, tree, ansi_bands=False, batt_cycle_chart=True, fossil_loading_chart=True):
	'helper function to create plots from newQstsPlot'
	# read in the Omd file for diesel generation kW capacities 
	gen_bus = {}
	for key in microgrids:
		gen_bus[key] = microgrids[key]['gen_bus']
	gen_data = pd.read_csv(csvName)
	data = []
	batt_cycles = {}
	diesel_loading_series = {}
	fossil_traces = []
	unreasonable_voltages = {}
	diesel_kwh_output = 0
	for ob_name in set(gen_data[category_name]): # grid instrument 
		# tally up total diesel genset output
		if "fossil" in ob_name and "_source" in csvName:
			diesel_kwh_output = diesel_kwh_output + sum(gen_data[gen_data[category_name] == ob_name]['V1'])
		# add grid instrument to legend group corresponding with appropriate microgrid
		for key in microgrids:
			if microgrids[key]['gen_bus'] in ob_name:
				#batt_kwh_rating = microgrids[key]['kwh_rating_battery']
				batt_kwh_rating = 1000
				legend_group = key
				break
			legend_group = "Not_in_MG"
		for y_name in y_list: # phases
			this_series = gen_data[gen_data[category_name] == ob_name] # slice of csv for particular object
			# note loads with voltages aren't within ANSI bands
			if "_load" in csvName:
				if (this_series[y_name] > 1.1).any() or (this_series[y_name] < 0.9).any():
					unreasonable_voltages[f"{ob_name}_{y_name}"] = ob_name
			# if fossil generation, create series representing loading percentage
			try: #TODO: fix this code. it breaks if there are too few or too many diesel gensets.
				if ("fossil" in ob_name and "_gen" in csvName) and not this_series[y_name].isnull().values.any():
					for item in tree:
						if item.get('name') == ob_name:
							diesel_kw_rating = item['kw']
							break
					diesel_percent_loading = [x / float(diesel_kw_rating) for x in this_series[y_name]]
					diesel_percent_loading = 0.0
					diesel_loading_series[f"{ob_name}_{y_name}"] = diesel_percent_loading
					# traces for fossil loading percentages 
					new_trace = go.Scatter(
						x = this_series[x],
						y = diesel_percent_loading,
						legendgroup=legend_group,
						legendgrouptitle_text=legend_group,
						showlegend=True,
						name=ob_name + '_' + y_name,
						hoverlabel = dict(namelength = -1)
						)
					fossil_traces.append(new_trace)
			except:
				pass
			# find total input_output of battery generators and divide by twice the kwh rating (microgrid dependent)
			try: #TODO: fix this. Errors on too many/too few batteries.
				if "battery" in ob_name and not this_series[y_name].isnull().values.any():
					batt_kwh_input_output = sum(abs(this_series[y_name]))
					try:
						cycles = batt_kwh_input_output / (2 * float(batt_kwh_rating))
					except:
						cycles = 0 #TODO: fix this.
			except:
				pass
			# normal traces
			name = ob_name + '_' + y_name
			if name in unreasonable_voltages:
				name = '[BAD]_' + name
			trace = go.Scatter(
				x = this_series[x],
				y = this_series[y_name],
				legendgroup=legend_group,
				legendgrouptitle_text=legend_group,
				showlegend = True,
				name = name,
				hoverlabel = dict(namelength = -1)
			)
			data.append(trace)
			try: #TODO: fix this
				if "battery" in ob_name and not this_series[y_name].isnull().values.any():
					batt_cycles[f"{ob_name}_{y_name}"] = cycles
			except:
				pass
	# create second optional battery cycle chart if specificied in function call.
	# if batt_cycle_chart == True and "gen" in csvName:
	if batt_cycle_chart == True and bool(batt_cycles):
		new_trace = go.Bar(
			x = list(batt_cycles.keys()), 
			y = list(batt_cycles.values()) 
		)
		new_layout = go.Layout(
			title = "Battery Cycles",
			xaxis = dict(title = 'Battery'),
			yaxis = dict(title = 'Cycles')
			)
		new_fig = plotly.graph_objs.Figure(new_trace, new_layout)
		plotly.offline.plot(new_fig, filename=f'{csvName}_battery_cycles.plot.html', auto_open=False)
	# create third optional fossil gen loading chart if specified in function call.
	if fossil_loading_chart == True and fossil_traces:
		new_layout = go.Layout(
			title = "Fossil Genset Loading Percentage",
			xaxis = dict(title = 'Time'),
			yaxis = dict(title = 'Fossil Percent Loading')
			)
		fossil_fig = plotly.graph_objs.Figure(fossil_traces, new_layout)
		plotly.offline.plot(fossil_fig, filename=f'{csvName}_fossil_loading.plot.html', auto_open=False)
	# calculate fuel consumption
	fuel_consumption_rate_gallons_per_kwh = 1 # <-- TO DO: is this a preset or an input?
	diesel = fuel_consumption_rate_gallons_per_kwh * diesel_kwh_output
	if "_source" in csvName:
		title = f'{csvName} Output. Fossil consumption of gensets = {diesel}'
	else:
		title = f'{csvName} Output'
	layout = go.Layout(
		title = title,
		xaxis = dict(title = 'hour'),
		yaxis = dict(title = str(y_list))
	)
	fig = plotly.graph_objs.Figure(data, layout)
	if ansi_bands == True:
		line_style = {'color':'Red', 'width':3, 'dash':'dashdot'}
		fig.add_hline(y=0.9, line=line_style)
		fig.add_hline(y=1.1, line=line_style)
	plotly.offline.plot(fig, filename=f'{csvName}.plot.html', auto_open=False)
	# print("batt_cycles",batt_cycles)
	# print("diesel_loading_series",diesel_loading_series)
	# print("unreasonable_voltages",unreasonable_voltages)

def play(pathToDss, workDir, microgrids, faultedLine):
	# TODO: do we need non-default outage timing?
	(outageStart, lengthOfOutage, switchingTime) = 60, 120, 30
	outageEnd = outageStart + lengthOfOutage
	actions = {}
	print('CONTROLLING ON', microgrids)
	# microgridup.py changes our directory to the one containing the currently running analysis. This is to help opendss run. If we're running this function by itself, we need to chdir into the workDir argument.
	curr_dir = os.getcwd()
	workDir = os.path.abspath(workDir)
	if curr_dir != workDir:
		os.chdir(workDir)
	# Read in the circuit information.
	dssTree = dssConvert.dssToTree(pathToDss)
	# Add the fault, modeled as a 3 phase open, to the actions.
	actions[outageStart] = f'''
		open object=line.{faultedLine} term=1
		open object=line.{faultedLine} term=2
		open object=line.{faultedLine} term=3
	'''
	actions[outageEnd] = f'''
		close object=line.{faultedLine} term=1
		close object=line.{faultedLine} term=2
		close object=line.{faultedLine} term=3
	'''
	# Add per-microgrid objects, edits and actions.
	for mg_key, mg_values in microgrids.items():
		# Add load shed.
		load_list = mg_values['loads']
		crit_list = mg_values['critical_load_kws']
		load_crit_pairs = zip(load_list, crit_list)
		for load_name, load_kw in load_crit_pairs:
			try:
				this_load = opendss._getByName(dssTree, load_name)
				old_kw = this_load['kw']
				this_load['kw'] = str(load_kw)
				print(f'reduced {load_name} from {old_kw} to {load_kw}')
			except:
				pass
		# Have all microgrids switch out of the circuit during fault.
		switch_name = mg_values['switch']
		actions[outageStart] += f'''
			open object=line.{switch_name} term=1
			open object=line.{switch_name} term=2
			open object=line.{switch_name} term=3
		'''
		actions[outageEnd] += f'''
			close object=line.{switch_name} term=1
			close object=line.{switch_name} term=2
			close object=line.{switch_name} term=3
		'''
		# Get all microgrid fossil units, sorted by size
		gen_bus = mg_values['gen_bus']
		all_mg_fossil = [
			ob for ob in dssTree
			if ob.get('bus1','x.x').split('.')[0] == gen_bus
			and 'fossil' in ob.get('object')
		]
		all_mg_fossil.sort(key=lambda x:x.get('kw'))
		# Insert a vsource for the largest fossil unit in each microgrid.
		if len(all_mg_fossil) > 0: # i.e. if we have a fossil generator
			big_gen_ob = all_mg_fossil[0]
			big_gen_bus = big_gen_ob.get('bus1')
			big_gen_index = dssTree.index(big_gen_ob)
			safe_busname = big_gen_bus.replace('.','_')
			safe_new_name = f'vsource.lead_gen_{safe_busname}'
			#TODO: debug vsource behavior. Runs but creates bizarre behavior.
			#new object=vsource.secondsource basekv=4.16 bus1=680.1.2.3 pu=1.00 r1=0 x1=0.0001 r0=0 x0=0.0001
			# dssTree.insert(big_gen_index, {'!CMD':'new', 'object':safe_new_name, 'bus1':big_gen_bus, 'enabled':'n', 'phases':'1'})
			# Enable/disable the diesel vsources during the outage via actions.
			# actions[outageStart] += f'''
			# 	enable object=vsource.{safe_new_name}
			# 	disable object={big_gen_ob['object']}
			# '''
			# actions[outageEnd] += f'''
			# 	disable object=vsource.{safe_new_name}
			# 	enable object={big_gen_ob['object']}
			# '''
	# Write the adjusted opendss file with new kw, generators.
	dssConvert.treeToDss(dssTree, 'circuit_control.dss')
	# Run the simulation
	FPREFIX = 'timezcontrol'
	opendss.newQstsPlot( #TODO: retry with new_newQstsPlot because original crashes with lots of vsources
		'circuit_control.dss',
		stepSizeInMinutes=60, 
		numberOfSteps=300,
		keepAllFiles=False,
		actions=actions,
		filePrefix=FPREFIX
	)
	# Generate the output charts.
	make_chart(f'{FPREFIX}_gen.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], 2019, microgrids, dssTree)
	make_chart(f'{FPREFIX}_load.csv', 'Name', 'hour', ['V1(PU)','V2(PU)','V3(PU)'], 2019, microgrids, dssTree, ansi_bands=True)
	make_chart(f'{FPREFIX}_source.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], 2019, microgrids, dssTree)
	make_chart(f'{FPREFIX}_control.csv', 'Name', 'hour', ['Tap(pu)'], 2019, microgrids, dssTree)
	# Undo directory change.
	os.chdir(curr_dir)