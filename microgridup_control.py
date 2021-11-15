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

def make_chart(csvName, category_name, x, y_list, year, microgrids, tree, ansi_bands=False, batt_cycle_chart=False, fossil_loading_chart=False):
	gen_data = pd.read_csv(csvName)
	data = []
	unreasonable_voltages = {}
	batt_cycles = {}
	fossil_kwh_output = 0
	batt_kwh_ratings = {}
	fossil_kw_ratings = {}
	fossil_traces = []
	
	# info we need from tree: every battery by name with corresponding kwhrated, every fossil gen by name with corresponding kw 
	if batt_cycle_chart == True or fossil_loading_chart == True:
		for item in tree:
			if "generator.fossil" in item.get("object","x.x"):
				fossil_kw_ratings[item.get("object").split(".")[1]] = item.get("kw")
			if "storage.battery" in item.get("object","x.x"):
				batt_kwh_ratings[item.get("object").split(".")[1]] = item.get("kwhrated")
		# print("fossil_kw_ratings",fossil_kw_ratings)
		# print("batt_kwh_ratings",batt_kwh_ratings)

	# loop through objects in circuit
	for ob_name in set(gen_data[category_name]): 

		# set appropriate legend group based on microgrid 
		for key in microgrids:
			if microgrids[key]['gen_bus'] in ob_name:
				legend_group = key
				break
			legend_group = "Not_in_MG"

		# loop through phases
		for y_name in y_list: 
			this_series = gen_data[gen_data[category_name] == ob_name]

			# if fossil and not null values, add total output to running tally
			if "fossil" in ob_name and not this_series[y_name].isnull().values.any():
				fossil_kwh_output += sum(this_series[y_name])
				# also divide all outputs by capacity to find genset loading percentage
				fossil_kw_rating = fossil_kw_ratings[ob_name.split("-")[1]]
				fossil_percent_loading = [x / float(fossil_kw_rating) for x in this_series[y_name]]
				# add traces for fossil loading percentages to graph variable
				fossil_trace = go.Scatter(
					x = this_series[x],
					y = fossil_percent_loading,
					legendgroup=legend_group,
					legendgrouptitle_text=legend_group,
					showlegend=True,
					name=ob_name + '_' + y_name,
					hoverlabel = dict(namelength = -1)
					)
				fossil_traces.append(fossil_trace)

			# if battery and not null values, count battery cycles 
			if "battery" in ob_name and not this_series[y_name].isnull().values.any():
				batt_kwh_input_output = sum(abs(this_series[y_name]))
				batt_kwh_rating = batt_kwh_ratings[ob_name.split("-")[1]]
				cycles = batt_kwh_input_output / (2 * float(batt_kwh_rating)) 
				batt_cycles[f"{ob_name}_{y_name}"] = cycles
				# print("batt_kwh_input_output",batt_kwh_input_output,"batt_kwh_rating",batt_kwh_rating,"cycles",cycles)

			# flag loads that don't fall within ansi bands
			if "_load" in csvName:
				if (this_series[y_name] > 1.1).any() or (this_series[y_name] < 0.9).any():
					unreasonable_voltages[f"{ob_name}_{y_name}"] = ob_name

			# traces for gen, load, source, control
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
	
	# make fossil genset loading plot
	if fossil_loading_chart == True:
		new_layout = go.Layout(
			title = "Fossil Genset Loading Percentage",
			xaxis = dict(title = 'Time'),
			yaxis = dict(title = 'Fossil Percent Loading')
			)
		fossil_fig = plotly.graph_objs.Figure(fossil_traces, new_layout)
		plotly.offline.plot(fossil_fig, filename=f'{csvName}_fossil_loading.plot.html', auto_open=False)

	# make battery cycles bar chart
	if batt_cycle_chart == True:
		# print("csvName",csvName, "batt_cycles",batt_cycles)
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

	# calculate total fossil genset consumption
	fuel_consumption_rate_gallons_per_kwh = 1 # <-- TO DO: is this a preset or an input?
	total_fossil = fuel_consumption_rate_gallons_per_kwh * fossil_kwh_output
	# add total fossil genset consumption to source plot title 
	if "_source" in csvName or "_gen" in csvName:
		title = f'{csvName} Output. Fossil consumption of gensets = {total_fossil}'
	else:
		title = f'{csvName} Output'

	# plots for gen, load, source, control
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
	actions[1] = ''
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
			# vsource variables.
			big_gen_ob = all_mg_fossil[-1]
			big_gen_bus = big_gen_ob.get('bus1')
			big_gen_index = dssTree.index(big_gen_ob)
			safe_busname = big_gen_bus.replace('.','_')
			vsource_ob_and_name = f'vsource.lead_gen_{safe_busname}'
			line_name = f'line.line_for_lead_gen_{safe_busname}'
			new_bus_name = f'bus_for_lead_gen_{safe_busname}.1.2.3'
			base_kv = big_gen_ob.get('kv','3.14')
			# Remove fossil unit, add new gen and line
			del dssTree[big_gen_index]
			dssTree.insert(big_gen_index, {'!CMD':'new', 'object':vsource_ob_and_name, 'bus1':new_bus_name, 'basekv':base_kv})
			dssTree.insert(big_gen_index, {'!CMD':'new', 'object':line_name, 'bus1':big_gen_bus, 'bus2':new_bus_name, 'switch':'yes'})
			# Disable the new lead gen by default.
			actions[1] += f'''
				open {line_name}
				calcv
			'''
			#Enable/disable the diesel vsources during the outage via actions.
			actions[outageStart] += f'''
				close {line_name}
				calcv
			'''
			actions[outageEnd] += f'''
				open {line_name}
				calcv
			'''
	# Additional calcv to make sure the simulation runs.
	actions[outageStart] += f'calcv\n'
	actions[outageEnd] += f'calcv\n'
	# Write the adjusted opendss file with new kw, generators.
	dssConvert.treeToDss(dssTree, 'circuit_control.dss')
	# Run the simulation
	FPREFIX = 'timezcontrol'
	opendss.newQstsPlot(
		'circuit_control.dss',
		stepSizeInMinutes=60, 
		numberOfSteps=300,
		keepAllFiles=False,
		actions=actions,
		filePrefix=FPREFIX
	)
	# Generate the output charts.
	make_chart(f'{FPREFIX}_gen.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], 2019, microgrids, dssTree, batt_cycle_chart=True, fossil_loading_chart=True)
	make_chart(f'{FPREFIX}_load.csv', 'Name', 'hour', ['V1(PU)','V2(PU)','V3(PU)'], 2019, microgrids, dssTree, ansi_bands=True)
	make_chart(f'{FPREFIX}_source.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], 2019, microgrids, dssTree)
	make_chart(f'{FPREFIX}_control.csv', 'Name', 'hour', ['Tap(pu)'], 2019, microgrids, dssTree)
	# Undo directory change.
	os.chdir(curr_dir)