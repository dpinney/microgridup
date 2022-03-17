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
from plotly.subplots import make_subplots
import math

# OMF imports
import omf
from omf import geo
from omf import distNetViz
from omf.models import __neoMetaModel__
from omf.models.__neoMetaModel__ import *
from omf.models import flisr
from omf.solvers.opendss import dssConvert
from omf.solvers import opendss

def do_manual_balance_approach(outageStart, outageEnd, mg_key, mg_values, dssTree):
	# Manually constructs battery loadshapes for outage and reinserts into tree based on a proportional to kWh basis. 
	gen_bus = mg_values['gen_bus']
	# Do vector subtraction to figure out battery loadshapes. 
	# First get all loads.
	all_mg_loads = [
		ob for ob in dssTree
		if ob.get("object","x.x").split('.')[1] in mg_values["loads"]
		and "load." in ob.get("object")
	]
	if len(all_mg_loads) > 0: # i.e. if we have loads
		load_loadshapes = []
		for load_idx in range(len(all_mg_loads)):
			# Get loadshapes of all renewable generation.
			load_loadshape_name = all_mg_loads[load_idx].get('yearly')
			load_loadshape = [ob.get("mult") for ob in dssTree if ob.get("object") and load_loadshape_name in ob.get("object")]
			list_load_loadshape = [float(shape) for shape in load_loadshape[0][1:-1].split(",")]
			load_loadshapes.append(list_load_loadshape)
		data = np.array(load_loadshapes)
		all_loads_shapes_kw = np.sum(data,0)

	# Second, get all renewable generation.
	all_mg_rengen = [
		ob for ob in dssTree
		if ob.get('bus1','x.x').split('.')[0] == gen_bus
		and ('generator.solar' in ob.get('object') or 'generator.wind' in ob.get('object'))
	]
	if len(all_mg_rengen) > 0: # i.e. if we have rengen
		rengen_loadshapes = []
		for gen_idx in range(len(all_mg_rengen)):
			# Get loadshapes of all renewable generation.
			rengen_loadshape_name = all_mg_rengen[gen_idx].get('yearly')
			rengen_loadshape = [ob.get("mult") for ob in dssTree if ob.get("object") and rengen_loadshape_name in ob.get("object")]
			list_rengen_loadshape = [float(shape) for shape in rengen_loadshape[0][1:-1].split(",")]
			rengen_loadshapes.append(list_rengen_loadshape)
		data = np.array(rengen_loadshapes)
		all_rengen_shapes = np.sum(data,0)
	
	# Third, get battery sizes.
	batt_obj = [
		ob for ob in dssTree
		if ob.get('bus1','x.x').split('.')[0] == gen_bus
		and 'storage' in ob.get('object')
	]
	# If there are multiple batteries at one bus, combine their kW ratings and kWh capacities. 
	batt_kws = []
	batt_kwhs = []
	batt_obj.sort(key=lambda x:float(x.get('kwhrated')))
	# Create lists of all ratings and capacities and their sums. 
	for ob in batt_obj:
		batt_kws.append(float(ob.get("kwrated")))
		batt_kwhs.append(float(ob.get("kwhrated")))
	batt_kw = sum(batt_kws)
	batt_kwh = sum(batt_kwhs)

	# Subtract renewable generation vector from load vector.
	new_batt_loadshape = all_loads_shapes_kw - all_rengen_shapes # NOTE: <-- load – rengen. 3 cases: above 0, 0, less than 0

	# Slice to outage length.
	new_batt_loadshape = new_batt_loadshape[outageStart:outageEnd]

	# Option 1: Find battery's starting capacity based on charge and discharge history by the start of the outage.
	cumulative_existing_batt_shapes = pd.Series()
	# Get existing battery's(ies') loadshapes. 
	for obj in batt_obj:
		batt_loadshape_name = obj.get("yearly")
		full_loadshape = [ob.get("mult") for ob in dssTree if ob.get("object") and batt_loadshape_name in ob.get("object")]
		ds_full_loadshape = pd.Series([float(shape) for shape in full_loadshape[0][1:-1].split(",")])
		cumulative_existing_batt_shapes = cumulative_existing_batt_shapes.add(ds_full_loadshape, fill_value=0)
	starting_capacity = batt_kwh + sum(cumulative_existing_batt_shapes[:outageStart])

	# Option 2: Set starting_capacity to the batt_kwh, assuming the battery starts the outage at full charge. 
	starting_capacity = batt_kwh

	# Currently unused variable for tracking unsupported load in kwh.
	unsupported_load_kwh = 0

	# Discharge battery (allowing for negatives that recharge (until hitting capacity)) until battery reaches 0 charge. Allow starting charge to be configurable. 
	hour = 0
	total_surplus = [] # Curtailed renewable generation (cannot fit in battery) during outage.
	while hour < len(new_batt_loadshape):
		surplus = 0 # Note: this variable stores how much rengen we need to curb per step. Create a cumulative sum to find overall total.
		dischargeable = starting_capacity if starting_capacity < batt_kw else batt_kw
		indicator = new_batt_loadshape[hour] - dischargeable 
		# There is more rengen than load and we can charge our battery (up until reaching batt_kwh).
		if new_batt_loadshape[hour] < 0:
			starting_capacity += abs(new_batt_loadshape[hour])
			if starting_capacity > batt_kwh:
				surplus = starting_capacity - batt_kwh
				starting_capacity = batt_kwh
			new_batt_loadshape[hour] = starting_capacity - (starting_capacity + new_batt_loadshape[hour] + surplus)
		# There is load left to cover and we can discharge the battery to cover it in its entirety. 
		elif indicator < 0:
			starting_capacity -= new_batt_loadshape[hour]
			new_batt_loadshape[hour] *= -1 
		# There is load left to cover after discharging as much battery as possible for the hour. Load isn't supported.
		else:
			new_batt_loadshape[hour] = -1 * dischargeable
			starting_capacity -= dischargeable
			unsupported_load_kwh += indicator
		total_surplus.append(surplus)
		hour += 1
	# print(f"Total curtailed renewable generation during outage for {mg_key} = {sum(total_surplus)}.")

	# Replace each outage portion of the existing battery loadshapes with a proportion of the new loadshape equal to the proportion of the battery's kwh capacity to the total kwh capacity on the bus.
	for idx in range(len(batt_kwhs)):
		factor = batt_kwhs[idx] / batt_kwh
		new_shape = list((new_batt_loadshape * factor)/batt_kws[idx])
		# Get existing battery loadshape
		batt_loadshape_name = batt_obj[idx].get("yearly")
		full_loadshape = [ob.get("mult") for ob in dssTree if ob.get("object") and batt_loadshape_name in ob.get("object")]
		list_full_loadshape = [float(shape) for shape in full_loadshape[0][1:-1].split(",")]
		# Replace outage portion with outage loadshape.
		final_batt_loadshape = list_full_loadshape[:outageStart] + new_shape + list_full_loadshape[outageEnd:]
		# Get index of battery in tree. 
		batt_loadshape_idx = dssTree.index([ob for ob in dssTree if ob.get("object") and batt_loadshape_name in ob.get("object")][0])
		# Replace mult with new loadshape and reinsert into tree.
		dssTree[batt_loadshape_idx]['mult'] = str(final_batt_loadshape).replace(" ","")
	return dssTree, new_batt_loadshape, cumulative_existing_batt_shapes, all_rengen_shapes, total_surplus, all_loads_shapes_kw

def plot_manual_balance_approach(mg_key, year, outageStart, outageEnd, new_batt_loadshape, cumulative_existing_batt_shapes, all_rengen_shapes, total_surplus, all_loads_shapes_kw):
	# Creates plot of manually constructed battery activity, load, and renewable generation (all cumulative).
	lengthOfOutage = outageEnd - outageStart
	data = []
	new_batt_loadshape = list(new_batt_loadshape)
	cumulative_existing_batt_shapes = list(cumulative_existing_batt_shapes)
	storage_shape = cumulative_existing_batt_shapes[:outageStart] + new_batt_loadshape + cumulative_existing_batt_shapes[outageEnd:]
	# Both gen and storage shapes after running battery algorithm.
	rengen_during_outage_post_curtailment = [x-y for x,y in zip(all_rengen_shapes[outageStart:outageEnd],total_surplus)]
	all_rengen_shapes = list(all_rengen_shapes[:outageStart]) + rengen_during_outage_post_curtailment + list(all_rengen_shapes[outageEnd:])
	gen_and_storage_shape = [x-y for x,y in zip(all_rengen_shapes,storage_shape)]
	# According to Matt – rengen should be negative. Generation is negative, load is positive.
	rengen_shapes_for_plot = [-1 * x for x in all_rengen_shapes]

	y_axis_names = ["All loads loadshapes (kW)","All renewable generators loadshapes (kW)","All storage shapes (kW)","Generation and storage (added together)"]
	plotting_variables = [all_loads_shapes_kw[outageStart:outageEnd], rengen_shapes_for_plot[outageStart:outageEnd], storage_shape[outageStart:outageEnd], gen_and_storage_shape[outageStart:outageEnd]]
	start_time = pd.Timestamp(f"{year}-01-01") + pd.Timedelta(hours=outageStart)
	for idx in range(len(plotting_variables)):
		# Traces for gen, load, storage.
		trace = go.Scatter(
			x = pd.to_datetime(range(lengthOfOutage), unit = 'h', origin = start_time), #TODO: make this datetime convert arrays other than hourly or with a different startdate than Jan 1 if needed
			y = plotting_variables[idx],
			showlegend = True,
			name = y_axis_names[idx],
			hoverlabel = dict(namelength = -1)
		)
		data.append(trace)

	# Plots load traces, gen traces, storage traces.
	layout = go.Layout(
		title = f'{mg_key} Generation, Load, and Storage in Fully Renewable Microgrid During Outage',
		xaxis = dict(title = 'Date'),
		yaxis = dict(title = "kW")
	)
	fig = plotly.graph_objs.Figure(data, layout)
	out_name = f'{mg_key}_gen_load_storage.plot.html'
	plotly.offline.plot(fig, filename=out_name, auto_open=False)
	return out_name

def make_chart(csvName, category_name, x, y_list, year, microgrids, tree, chart_name, y_axis_name, ansi_bands=False, batt_cycle_chart=False, fossil_loading_chart=False, vsource_ratings=None, rengen_mgs=None):
	(outageStart, lengthOfOutage, switchingTime) = 60, 120, 30
	outageEnd = outageStart + lengthOfOutage
	gen_data = pd.read_csv(csvName)
	data = []
	unreasonable_voltages = {}
	batt_cycles = {}
	diesel_dict = {}
	mmbtu_dict = {}
	fossil_kwh_output = 0
	batt_kwh_ratings = {}
	fossil_kw_ratings = {}
	fossil_traces = []

	# Info we need from tree: every solar by name with corresponding kw, every wind by name with corresponding kw.
	if rengen_mgs:
		rengen_kw_ratings = {}
		for item in tree:
			if "generator.solar" in item.get("object","x.x") or "generator.wind" in item.get("object","x.x"):
				rengen_kw_ratings[item.get("object").split(".")[1]] = item.get("kw")

		# Define variable to house all rengen element-specific loadshapes organized by microgrid. 
		rengen_proportional_loadshapes = {}
		# Make load loadshape outage patch. Subtract surplus from rengen, add rengen and storage, and compare to load loadshapes. Inequalities = 0, equalities = 1.  
		for mg_key in rengen_mgs:
			# Both gen and storage shapes after running battery algorithm.
			rengen_during_outage_post_curtailment = [x-y for x,y in zip(rengen_mgs[mg_key]["All rengen loadshapes during outage (kw)"],rengen_mgs[mg_key]["Surplus rengen"])]
			gen_and_storage_shape = [round(x-y, 8) for x,y in zip(rengen_during_outage_post_curtailment,rengen_mgs[mg_key]["Cumulative battery loadshape during outage (kw)"])] 
			loadshapes_rounded = [round(num, 8) for num in rengen_mgs[mg_key]["All loads loadshapes during outage (kw)"]]
			generic_mg_loadshape = [1 if x==y else 0 for x,y in zip(gen_and_storage_shape,loadshapes_rounded)]
			rengen_mgs[mg_key]["Generic loadshape (kw)"] = generic_mg_loadshape

			# Divide up cumulative rengen loadshapes during outage proportionally by size to each rengen element. 
			# Define temporary variable to grab the kw ratings of rengen elements specific to current microgrid. 
			mg_specific_rengen = {}
			# Define sub dictionary to be added to collection of all dictionaries.
			mg_proportional_rengen_shapes = {}
			for item in rengen_kw_ratings:
				if microgrids[mg_key]["gen_bus"] in item:
					mg_specific_rengen[item] = float(rengen_kw_ratings[item])
			total_mg_rengen_capacity_kw = sum(mg_specific_rengen.values())
			for element in mg_specific_rengen:
				factor = mg_specific_rengen[element] / total_mg_rengen_capacity_kw
				# Add each element's loadshapes to mg specific dictionary. 
				mg_proportional_rengen_shapes[element] = [x*factor for x in rengen_mgs[mg_key]["All rengen loadshapes during outage (kw)"]]
			# Finally, add all mg specific loadshapes to all mgs dictionary variable.
			rengen_proportional_loadshapes[mg_key] = mg_proportional_rengen_shapes


	# Info we need from tree: every battery by name with corresponding kwhrated, every fossil gen by name with corresponding kw.
	if batt_cycle_chart == True or fossil_loading_chart == True:
		for item in tree:
			if "generator.fossil" in item.get("object","x.x"):
				fossil_kw_ratings[item.get("object").split(".")[1]] = item.get("kw")
			if "storage.battery" in item.get("object","x.x"):
				batt_kwh_ratings[item.get("object").split(".")[1]] = item.get("kwhrated")

	# Similar to above, divide batteries into microgrids, find mg total kwh capacities for storage, and form element specific loadshapes.
	if rengen_mgs:
		# Define variable to house all storage element-specific loadshapes organized by microgrid. 
		storage_proportional_loadshapes = {}
		for mg_key in rengen_mgs:
			# Divide up cumulative storage loadshapes during outage proportionally by size to each storage element. 
			# Define temporary variable to grab the kwh ratings of storage elements specific to current microgrid. 
			mg_specific_storage = {}
			# Define sub dictionary to be added to collection of all dictionaries.
			mg_proportional_storage_shapes = {}
			for item in batt_kwh_ratings:
				if microgrids[mg_key]["gen_bus"] in item:
					mg_specific_storage[item] = float(batt_kwh_ratings[item])
			total_mg_storage_capacity_kwh = sum(mg_specific_storage.values())
			for element in mg_specific_storage:
				factor = mg_specific_storage[element] / total_mg_storage_capacity_kwh
				# Add each element's loadshapes to mg specific dictionary. 
				mg_proportional_storage_shapes[element] = [x*factor for x in rengen_mgs[mg_key]["Cumulative battery loadshape during outage (kw)"]]
			# Finally, add all mg specific loadshapes to all mgs dictionary variable.
			storage_proportional_loadshapes[mg_key] = mg_proportional_storage_shapes

	# Loop through objects in circuit.
	for ob_name in set(gen_data[category_name]): 
		# Set appropriate legend group based on microgrid.
		for key in microgrids:
			if microgrids[key]['gen_bus'] in ob_name or ob_name.split("-")[1] in microgrids[key]["loads"]:
				legend_group = key
				break
			legend_group = "Not_in_MG"

		# Loop through phases.
		for y_name in y_list: 
			# print(f"this is the normal function! ob_name = {ob_name} and y_name = {y_name}")
			this_series = gen_data[gen_data[category_name] == ob_name]

			# Amass data for fuel consumption chart.
			if ("lead_gen_" in ob_name or "fossil_" in ob_name) and not this_series[y_name].isnull().values.any(): 
				additional = sum(abs(this_series[y_name][outageStart:outageEnd])) if "fossil_" in ob_name else sum(this_series[y_name][outageStart:outageEnd])
				fossil_kwh_output += additional
				fossil_kw_rating = fossil_kw_ratings[ob_name.split("-")[1]] if "fossil_" in ob_name else vsource_ratings[ob_name.split("-")[1]]
				fossil_loading_average_decimal = additional / (float(fossil_kw_rating) * lengthOfOutage)
				diesel_consumption_gal_per_hour = (0.065728897 * fossil_loading_average_decimal + 0.003682709) * float(fossil_kw_rating) + (-0.027979695 * fossil_loading_average_decimal + 0.568328949)
				diesel_consumption_outage = diesel_consumption_gal_per_hour * lengthOfOutage
				mmbtu_consumption_mmbtu_per_hour = (0.0112913202545883 * fossil_loading_average_decimal + 0.00171037274039439) * float(fossil_kw_rating) + (-0.0560953826993578* fossil_loading_average_decimal + 0.074238182761738)
				mmbtu_consumption_outage = mmbtu_consumption_mmbtu_per_hour * lengthOfOutage
				if legend_group in diesel_dict.keys():
					diesel_dict[legend_group] += diesel_consumption_outage
				else:
					diesel_dict[legend_group] = diesel_consumption_outage
				if legend_group in mmbtu_dict.keys():
					mmbtu_dict[legend_group] += mmbtu_consumption_outage
				else:
					mmbtu_dict[legend_group] = mmbtu_consumption_outage
				# Make fossil loading percentages traces.
				fossil_percent_loading = [(x / float(fossil_kw_rating)) * -100 for x in this_series[y_name]] if "fossil_" in ob_name else [(x / float(fossil_kw_rating)) * 100 for x in this_series[y_name]]
				fossil_trace = go.Scatter(
					x = pd.to_datetime(this_series[x], unit = 'h', origin = pd.Timestamp(f'{year}-01-01')), #TODO: make this datetime convert arrays other than hourly or with a different startdate than Jan 1 if needed
					y = fossil_percent_loading,
					legendgroup=legend_group,
					legendgrouptitle_text=legend_group,
					showlegend=True,
					name=ob_name + '_' + y_name,
					hoverlabel = dict(namelength = -1)
					)
				fossil_traces.append(fossil_trace)

			# If battery_ and not null values, count battery cycles.
			if "battery_" in ob_name and not this_series[y_name].isnull().values.any():
				if rengen_mgs and legend_group in rengen_mgs:
					curr_series_list = list(this_series[y_name])
					outage_portion = storage_proportional_loadshapes[legend_group][ob_name.split("-")[1]]
					all_batt_loadshapes = curr_series_list[:outageStart] + outage_portion + curr_series_list[outageEnd:]
					batt_kwh_input_output = sum([abs(x) for x in all_batt_loadshapes])
				else:
					batt_kwh_input_output = sum(abs(this_series[y_name]))
				batt_kwh_rating = batt_kwh_ratings[ob_name.split("-")[1]]
				cycles = batt_kwh_input_output / (2 * float(batt_kwh_rating)) 
				batt_cycles[f"{ob_name}_{y_name}"] = cycles

			# Flag loads that don't fall within ansi bands.
			if "_load" in csvName:
				if (this_series[y_name] > 1.1).any() or (this_series[y_name] < 0.9).any():
					unreasonable_voltages[f"{ob_name}_{y_name}"] = ob_name

			# Traces for gen, load, control. 
			name = ob_name + '_' + y_name
			# if name in unreasonable_voltages:
				# name = '[BAD]_' + name
			if "mongenerator" in ob_name:
				y_axis = this_series[y_name] * -1
				# if not this_series[y_name].isnull().values.any():
					# print(f"Maximum generation for {name} = {max(y_axis)}")
			else:
				y_axis = this_series[y_name]
			# Splice over the outage portions if manual balance approach was used (rengen only circuit).
			if rengen_mgs and legend_group in rengen_mgs:
				if "mongenerator-wind" in ob_name or "mongenerator-solar" in ob_name:
					splice = rengen_proportional_loadshapes[legend_group][ob_name.split("-")[1]]
					y_axis = list(y_axis[:outageStart]) + splice + list(y_axis[outageEnd:])
				if "mongenerator-battery" in ob_name:
					splice = storage_proportional_loadshapes[legend_group][ob_name.split("-")[1]]
					y_axis = list(y_axis[:outageStart]) + splice + list(y_axis[outageEnd:])
				if "monload-" in ob_name:
					splice = rengen_mgs[legend_group]["Generic loadshape (kw)"]
					y_axis = list(y_axis[:outageStart]) + splice + list(y_axis[outageEnd:])
				plot_legend_group = f"{legend_group} – Manual Balance Approach used during outage"
			else:
				plot_legend_group = legend_group
			if not this_series[y_name].isnull().values.any():
				trace = go.Scatter(
					x = pd.to_datetime(this_series[x], unit = 'h', origin = pd.Timestamp(f'{year}-01-01')), #TODO: make this datetime convert arrays other than hourly or with a different startdate than Jan 1 if needed
					y = y_axis,
					legendgroup=plot_legend_group,
					legendgrouptitle_text=plot_legend_group,
					showlegend = True,
					name = name,
					hoverlabel = dict(namelength = -1)
				)
				data.append(trace)
	
	# Make fossil genset loading plot. 
	if fossil_loading_chart == True:
		new_layout = go.Layout(
			title = f"Fossil Genset Loading Percentage ({csvName})",
			xaxis = dict(title = 'Date'),
			yaxis = dict(title = 'Fossil Percent Loading')
			)
		fossil_fig = plotly.graph_objs.Figure(fossil_traces, new_layout)
		plotly.offline.plot(fossil_fig, filename=f'{csvName}_fossil_loading.plot.html', auto_open=False)

		# Calculate total fossil genset consumption and make fossil fuel consumption chart. 
		fossil_kwh_output = "{:e}".format(fossil_kwh_output)
		total_gal_diesel = "{:e}".format(sum(diesel_dict.values()))
		total_mmbtu_gas = "{:e}".format(sum(mmbtu_dict.values()))
		# Make fossil fuel consumption chart. 
		diesel_dict = dict(sorted(diesel_dict.items()))
		mmbtu_dict = dict(sorted(mmbtu_dict.items()))

		fig = make_subplots(shared_xaxes=True, specs=[[{"secondary_y": True}]])
		fig.add_trace(go.Bar(x = list(diesel_dict.keys()), y = list(diesel_dict.values()), name="Diesel"), secondary_y=False)
		fig.add_trace(go.Bar(x = list(mmbtu_dict.keys()), y = list(mmbtu_dict.values()), name="Gas"), secondary_y=True)
		fig.update_layout(
		    title_text = f"Diesel and Natural Gas Equivalent Consumption During Outage By Microgrid<br><sup>Total Consumption in Gallons of Diesel = {total_gal_diesel} || Total Consumption in MMBTU Natural Gas = {total_mmbtu_gas}|| Total Ouput in kWh = {fossil_kwh_output}</sup>"
		)
		fig.update_xaxes(title_text="Microgrid")
		fig.update_yaxes(title_text="Gallons of Diesel Equivalent Consumed During Outage", secondary_y=False)
		fig.update_yaxes(title_text="MMBTU of Natural Gas Equivalent Consumed During Outage", secondary_y=True)

		plotly.offline.plot(fig, filename=f'{csvName}_fuel_consumption.plot.html', auto_open=False)

	# Make battery cycles bar chart.
	if batt_cycle_chart == True:
		batt_cycles = dict(sorted(batt_cycles.items()))
		new_trace = go.Bar(
			x = list(batt_cycles.keys()), 
			y = list(batt_cycles.values()) 
		)
		new_layout = go.Layout(
			title = "Battery Cycles During Analysis Period",
			xaxis = dict(title = 'Battery'),
			yaxis = dict(title = 'Cycles')
			)
		new_fig = plotly.graph_objs.Figure(new_trace, new_layout)
		plotly.offline.plot(new_fig, filename=f'{csvName}_battery_cycles.plot.html', auto_open=False)

	# Plots for gen, load, control.
	layout = go.Layout(
		title = f'{chart_name} <br><sup>Dotted black lines indicate outage start and end times</sup>',
		xaxis = dict(title = 'Date'),
		yaxis = dict(title = y_axis_name)
	)
	fig = plotly.graph_objs.Figure(data, layout)
	if ansi_bands == True:
		line_style = {'color':'Red', 'width':3, 'dash':'dashdot'}
		fig.add_hline(y=0.9, line=line_style)
		fig.add_hline(y=1.1, line=line_style)
	# Add outage start and end markers.
	outage_line_style = {'color':'Black', 'width':1, 'dash':'dot'}
	start_time = pd.Timestamp(f"{year}-01-01") + pd.Timedelta(hours=outageStart)
	end_time = pd.Timestamp(f"{year}-01-01") + pd.Timedelta(hours=outageStart) + pd.Timedelta(hours=lengthOfOutage)
	fig.add_vline(x=start_time, line=outage_line_style)
	fig.add_vline(x=end_time, line=outage_line_style)
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
	# Initialize dict of vsource ratings 
	big_gen_ratings = {}
	# Initialize dict of rengen mg labels and data.
	rengen_mgs = {}
	# Keep track of any renewable-only microgrids.
	rengen_fnames = []
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
		all_mg_fossil.sort(key=lambda x:float(x.get('kw')))
		# Insert a vsource for the largest fossil unit in each microgrid.
		if len(all_mg_fossil) > 0: # i.e. if we have a fossil generator
			manual_balance_approach = False
			# vsource variables.
			big_gen_ob = all_mg_fossil[-1]
			big_gen_bus = big_gen_ob.get('bus1')
			big_gen_index = dssTree.index(big_gen_ob)
			safe_busname = big_gen_bus.replace('.','_')
			vsource_ob_and_name = f'vsource.lead_gen_{safe_busname}'
			line_name = f'line.line_for_lead_gen_{safe_busname}'
			new_bus_name = f'bus_for_lead_gen_{safe_busname}.1.2.3'
			#NOTE: vsources use line-to-line voltages, so 3 phase gens get sqrt(3) multiplier
			phase_count = big_gen_ob.get('phases')
			gen_base_kv = float(big_gen_ob['kv'])
			if phase_count == '3':
				gen_base_kv = gen_base_kv * math.sqrt(3)
			# Before removing fossil unit, grab kW rating 
			big_gen_ratings[f"lead_gen_{safe_busname}"] = big_gen_ob.get("kw")
			# Remove fossil unit, add new gen and line
			del dssTree[big_gen_index]
			dssTree.insert(big_gen_index, {'!CMD':'new', 'object':vsource_ob_and_name, 'basekv':str(gen_base_kv), 'bus1':new_bus_name, 'phases':phase_count})
			# dssTree.insert(big_gen_index, {'!CMD':'new', 'object':vsource_ob_and_name, 'basekv':gen_base_kv, 'bus1':new_bus_name, 'pu':1.00, 'r1':0, 'x1':0.0001, 'r0':0, 'x0':0.0001})
			# print("dssTree[big_gen_index]",dssTree[big_gen_index])
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
		else:
			manual_balance_approach = True
		# Manually construct battery loadshapes for outage.
		dssTree, new_batt_loadshape, cumulative_existing_batt_shapes, all_rengen_shapes, total_surplus, all_loads_shapes_kw = do_manual_balance_approach(outageStart, outageEnd, mg_key, mg_values, dssTree)
		# Manual Balance Approach plotting call.
		if manual_balance_approach == True:
			fname = plot_manual_balance_approach(mg_key, 2019, outageStart, outageEnd, new_batt_loadshape, cumulative_existing_batt_shapes, all_rengen_shapes, total_surplus, all_loads_shapes_kw)
			rengen_fnames.append(fname)
			rengen_mgs[mg_key] = {"All loads loadshapes during outage (kw)":list(all_loads_shapes_kw[outageStart:outageEnd]),
			"All rengen loadshapes during outage (kw)":list(all_rengen_shapes[outageStart:outageEnd]),
			"Cumulative battery loadshape during outage (kw)":list(new_batt_loadshape),
			"Surplus rengen":total_surplus}
	# print("big_gen_ratings",big_gen_ratings)
	# print("rengen_mgs",rengen_mgs)
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
	# Merge gen and source csvs for plotting fossil loading percentages
	inputs = [f'{FPREFIX}_gen.csv', f'{FPREFIX}_source.csv']
	# First determine the field names from the top line of each input file
	fieldnames = []
	for filename in inputs:
		with open(filename, "r", newline="") as f_in:
			reader = csv.reader(f_in)
			headers = next(reader)
			for h in headers:
				if h not in fieldnames:
					fieldnames.append(h)
	# Then copy the data
	with open(f"{FPREFIX}_source_and_gen.csv", "w", newline="") as f_out:
		writer = csv.DictWriter(f_out, fieldnames=fieldnames)
		writer.writeheader()
		for filename in inputs:
			with open(filename, "r", newline="") as f_in:
				reader = csv.DictReader(f_in)  # Uses the field names in this file
				for line in reader:
					writer.writerow(line)
	# Generate the output charts.
	# make_chart(f'{FPREFIX}_gen.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], 2019, microgrids, dssTree, "Generator Output", "Average hourly kW", batt_cycle_chart=True)
	make_chart(f'{FPREFIX}_load.csv', 'Name', 'hour', ['V1(PU)','V2(PU)','V3(PU)'], 2019, microgrids, dssTree, "Load Voltage", "PU", ansi_bands=True, rengen_mgs=rengen_mgs)
	# make_chart(f'{FPREFIX}_source.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], 2019, microgrids, dssTree, "Voltage Source Output", "Average hourly kW", vsource_ratings=big_gen_ratings)
	make_chart(f'{FPREFIX}_control.csv', 'Name', 'hour', ['Tap(pu)'], 2019, microgrids, dssTree, "Tap Position", "PU")
	make_chart(f'{FPREFIX}_source_and_gen.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], 2019, microgrids, dssTree, "Generator Output", "Average Hourly kW", batt_cycle_chart=True, fossil_loading_chart=True, vsource_ratings=big_gen_ratings, rengen_mgs=rengen_mgs)
	# Write final output file.
	output_slug = '''	
		<head>
			<style type="text/css">
				* {font-family:sans-serif}
				iframe {width:100%; height:600px; border-color:gray; border-style:solid; border-width:1px 0px 0px 0px}
			</style>
		</head>
		<body style="margin:0px">
			<iframe src="timezcontrol_source_and_gen.csv.plot.html"></iframe>
			<iframe src="timezcontrol_load.csv.plot.html"></iframe>
			<iframe src="timezcontrol_control.csv.plot.html"></iframe>
			<iframe src="timezcontrol_source_and_gen.csv_battery_cycles.plot.html"></iframe>
			<iframe src="timezcontrol_source_and_gen.csv_fossil_loading.plot.html"></iframe>
			<iframe src="timezcontrol_source_and_gen.csv_fuel_consumption.plot.html"></iframe>
		</body>'''
	print(f'Control microgrids count {len(microgrids)} and renewable count {len(rengen_fnames)}')
	for rengen_name in rengen_fnames:
		# insert renewable manual balance plots.
		output_slug = output_slug + f'<iframe src="{rengen_name}"></iframe>'
	with open('output_control.html','w') as outFile:
		outFile.write(output_slug)
	# Undo directory change.
	os.chdir(curr_dir)