from omf.solvers.opendss import dssConvert
from omf import distNetViz
from omf import geo
from omf.runAllTests import _print_header
import microgridup_control
import microgridup_resilience
import microgridup_design
import microgridup_hosting_cap
import shutil
import os
import json
import pandas as pd
import plotly.graph_objects as go
import csv
import jinja2 as j2
import datetime
import traceback
import sys
import logging
import random
import concurrent.futures
from omf.solvers.REopt import REOPT_API_KEYS

MGU_FOLDER = os.path.abspath(os.path.dirname(__file__))
if MGU_FOLDER == '/':
	MGU_FOLDER = '' #workaround for docker root installs
PROJ_FOLDER = f'{MGU_FOLDER}/data/projects'

def setup_logging(log_file):
    logger = logging.getLogger('custom_logger')
    logger.setLevel(logging.WARNING)
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger

def _walkTree(dirName):
	listOfFiles = []
	for (dirpath, _, filenames) in os.walk(dirName):
		listOfFiles += [os.path.join(dirpath, file) for file in filenames]
	return listOfFiles

def summary_stats(reps, MICROGRIDS, MODEL_LOAD_CSV):
	'''Helper function within full() to take in a dict of lists of the microgrid
	attributes and append a summary value for each attribute'''
	# print("reps['Maximum 1 hr Load (kW)']",reps['Maximum 1 hr Load (kW)'])
	# add up all of the loads in MICROGRIDS into one loadshape
	# used previously to call items out of mg_name: gen_bus_name = mg_ob['gen_bus']
	# grab all the load names from all of the microgrids analyzed
	mg_load_names = []
	for mg in MICROGRIDS:
		for load_name in MICROGRIDS[mg]['loads']:
			mg_load_names.append(load_name)
	# add up all of the loads in MICROGRIDS into one loadshape
	loads = pd.read_csv(MODEL_LOAD_CSV)
	loads['full_load']= loads[mg_load_names].sum(axis=1)
	#print('loads.head()', loads.head())
	max_load = int(loads['full_load'].max())
	min_load = int(loads['full_load'].min())
	avg_load = int(loads['full_load'].mean())
	reps['Microgrid Name'].append('Summary')
	reps['Generation Bus'].append('None')
	# minimum coincident load across all mgs
	reps['Minimum 1 hr Load (kW)'].append(round(min_load))
	reps['Average 1 hr Load (kW)'].append(round(avg_load))
	reps['Average Daytime 1 hr Load (kW)'].append(round(sum(reps['Average Daytime 1 hr Load (kW)'])))
	# maximum coincident load acorss all mgs
	reps['Maximum 1 hr Load (kW)'].append(round(max_load))
	reps['Maximum 1 hr Critical Load (kW)'].append(round(sum(reps['Maximum 1 hr Critical Load (kW)'])))
	reps['Existing Fossil Generation (kW)'].append(round(sum(reps['Existing Fossil Generation (kW)'])))
	reps['New Fossil Generation (kW)'].append(round(sum(reps['New Fossil Generation (kW)'])))
	# reps['Diesel Fuel Used During Outage (gal)'].append(round(sum(reps['Diesel Fuel Used During Outage (gal)'])))
	reps['Existing Solar (kW)'].append(round(sum(reps['Existing Solar (kW)'])))
	reps['New Solar (kW)'].append(round(sum(reps['New Solar (kW)'])))
	reps['Existing Battery Power (kW)'].append(round(sum(reps['Existing Battery Power (kW)'])))
	reps['Existing Battery Energy Storage (kWh)'].append(round(sum(reps['Existing Battery Energy Storage (kWh)'])))
	reps['New Battery Power (kW)'].append(round(sum(reps['New Battery Power (kW)'])))
	reps['New Battery Energy Storage (kWh)'].append(round(sum(reps['New Battery Energy Storage (kWh)'])))
	reps['Existing Wind (kW)'].append(round(sum(reps['Existing Wind (kW)'])))
	reps['New Wind (kW)'].append(round(sum(reps['New Wind (kW)'])))
	reps['Total Generation on Microgrid (kW)'].append(round(sum(reps['Total Generation on Microgrid (kW)'])))
	# calculate weighted average % renewables across all microgrids
	renewables_perc_list = reps['Renewable Generation (% of Annual kWh)']
	avg_load_list = reps['Average 1 hr Load (kW)']
	wgtd_avg_renewables_perc = sum([renewables_perc_list[i]/100 * avg_load_list[i] for i in range(len(renewables_perc_list))])/sum(avg_load_list[:-1])*100 # remove the final item of avg_load, which is the sum of the list entries from 'Average 1 hr Load (kW)' above
	# print("wgtd_avg_renewables_perc:", wgtd_avg_renewables_perc)
	reps['Renewable Generation (% of Annual kWh)'].append(round(wgtd_avg_renewables_perc))
	# using yr 1 emissions and percent reductions, calculate a weighted average of % reduction in emissions for yr 1
	yr1_emis = reps['Emissions (Yr 1 Tons CO2)']
	reps['Emissions (Yr 1 Tons CO2)'].append(round(sum(reps['Emissions (Yr 1 Tons CO2)'])))
	# print("yr1_emis:", yr1_emis)
	emis_reduc_perc = reps['Emissions Reduction (Yr 1 % CO2)']
	total_tons_list = [yr1_emis[i]/(1-emis_reduc_perc[i]/100) for i in range(len(emis_reduc_perc))]
	reduc_tons_list = [a*b/100 for a,b in zip(total_tons_list,emis_reduc_perc)]
	reduc_percent_yr1 = sum(reduc_tons_list)/sum(total_tons_list)*100
	reps['Emissions Reduction (Yr 1 % CO2)'].append(round(reduc_percent_yr1))
	reps['Net Present Value ($)'].append(sum(reps['Net Present Value ($)']))
	reps['CapEx ($)'].append(sum(reps['CapEx ($)']))
	reps['CapEx after Tax Incentives ($)'].append(sum(reps['CapEx after Tax Incentives ($)']))
	reps['O+M Costs (Yr 1 $ before tax)'].append(sum(reps['O+M Costs (Yr 1 $ before tax)']))
	# if all([h != None for h in reps['Minimum Outage Survived (h)']]):
	# 	reps['Minimum Outage Survived (h)'].append(round(min(reps['Minimum Outage Survived (h)']),0))
	# else:
	# 	reps['Minimum Outage Survived (h)'].append(None)
	if all([h != None for h in reps['Average Outage Survived (h)']]):
		reps['Average Outage Survived (h)'].append(round(min(reps['Average Outage Survived (h)']),0))
	else:
		reps['Average Outage Survived (h)'].append(None)
	# print(reps)
	return reps

def summary_charts(stats):
	''' Generate HTML for summary overview charts. '''
	# Global chart material
	column_labels = stats['Microgrid Name']
	legend_spec = {'orientation':'h', 'xanchor':'left'}#, 'x':0, 'y':-0.2}
	chart_height = '400px'
	# Load and Generation Chart
	gen_load_fig = go.Figure(
		data=[
			go.Bar(
				name = 'Peak Load',
				x=column_labels,
				y=stats['Maximum 1 hr Load (kW)'],
			), go.Bar(
				name='Peak Crit. Load',
				x=column_labels,
				y=stats['Maximum 1 hr Critical Load (kW)'],
			), go.Bar(
				name='Total Generation',
				x=column_labels,
				y=stats['Total Generation on Microgrid (kW)'],
			)
		]
	)
	gen_load_fig.update_layout(
		title = 'Microgrid Load and Generation',
		legend = legend_spec,
		yaxis = {'ticksuffix': " kW"},
		font=dict(
			family="sans-serif",
			color="black"
		)
	)
	gen_load_html = gen_load_fig.to_html(default_height=chart_height)
	# Renewable versus fossil chart.
	gen_mix_fig = go.Figure(
		data=[
			go.Bar(
				name = 'Existing Solar',
				x=column_labels,
				y=stats['Existing Solar (kW)'],
				visible='legendonly'
			), go.Bar(
				name='New Solar',
				x=column_labels,
				y=stats['New Solar (kW)'],
			), go.Bar(
				name='Existing Wind',
				x=column_labels,
				y=stats['Existing Wind (kW)'],
				visible='legendonly'
			), go.Bar(
				name='New Wind',
				x=column_labels,
				y=stats['New Wind (kW)'],
			), go.Bar(
				name='Existing Storage (kWh)',
				x=column_labels,
				y=stats['Existing Battery Energy Storage (kWh)'],
				visible='legendonly'
			), go.Bar(
				name='New Storage',
				x=column_labels,
				y=stats['New Battery Energy Storage (kWh)'],
			), go.Bar(
				name='Existing Fossil',
				x=column_labels,
				y=stats['Existing Fossil Generation (kW)'],
				visible='legendonly'
			), go.Bar(
				name='New Fossil',
				x=column_labels,
				y=stats['New Fossil Generation (kW)'],
			)
		]
	)
	gen_mix_fig.update_layout(
		title = 'Microgrid Generation Mix, Existing and New',
		legend = legend_spec,
		yaxis = {'ticksuffix': " kW/kWh"},
		font = dict(
			family="sans-serif",
			color="black"
		)
	)
	gen_mix_html = gen_mix_fig.to_html(default_height=chart_height)
	# Financial Summary
	money_summary_fig = go.Figure(
		data=[
			go.Bar(
				name = 'Net Present Value',
				x=column_labels,
				y=stats['Net Present Value ($)'],
			), go.Bar(
				name='O+M Costs (Y1 before tax)',
				x=column_labels,
				y=stats['O+M Costs (Yr 1 $ before tax)'],
				visible='legendonly'
			), go.Bar(
				name='CapEx',
				x=column_labels,
				y=stats['CapEx ($)'],
				visible='legendonly'
			), go.Bar(
				name='CapEx After Tax Incentives',
				x=column_labels,
				y=stats['CapEx after Tax Incentives ($)'],
			)
		]
	)
	money_summary_fig.update_layout(
		title = 'Financial Summary',
		legend = legend_spec,
		yaxis = {'tickprefix': "$"},
		font = dict(
			family="sans-serif",
			color="black"
		)
	)
	money_summary_html = money_summary_fig.to_html(default_height=chart_height)
	all_html = money_summary_html + gen_load_html + gen_mix_html
	return all_html

def colorby_mgs(omd_path, mg_group_dictionary, critical_loads):
    ''' generate a colorby CSV/JSON that works with omf.geo map interface.
    To use, set omd['attachments'] = function JSON output'''
    attachments_keys = {
        "coloringFiles": {
            "microgridColoring.csv": {
                "csv": "<content>",
                "colorOnLoadColumnIndex": "1"
            }
        }
    }
    mg_keys = mg_group_dictionary.keys()
    color_step = float(1/(len(mg_keys) + 1))
    output_csv = 'bus,mg_color,crit_color\n'
    all_mg_elements = microgridup_control.get_all_mg_elements(None, mg_group_dictionary, omd_path)
    all_colorable_elements = get_all_colorable_elements(None, omd_path)
    seen = set()
    for i, mg_key in enumerate(mg_group_dictionary):
        my_color = (i+1) * color_step
        all_items = list(all_mg_elements[mg_key])
        for item in all_items:
            critical_binary = 1 if item in critical_loads else 0
            output_csv += item + ',' + str(my_color) + ',' + str(critical_binary) + '\n'
            seen.add(item)
    # Color all circuit elements that aren't in an mg/critical as 0.
    for item in all_colorable_elements:
        name = item.get('bus') if item['!CMD'] == 'setbusxy' else item.get('object').split('.')[1]
        if name not in seen:
            output_csv += name + ',' + str(0) + ',' + str(0) + '\n'
    attachments_keys['coloringFiles']['microgridColoring.csv']['csv'] = output_csv
    return attachments_keys

def get_all_colorable_elements(dss_path, omd_path=None):
    if not dss_path:
        tree = dssConvert.omdToTree(omd_path)
        colorable_elements = [x for x in tree if x['!CMD'] in ('new','edit','setbusxy') and 'loadshape' not in x.get('object','') and 'line' not in x.get('object','')]
    else:
        tree = dssConvert.dssToTree(dss_path)
    colorable_elements = [x for x in tree if x['!CMD'] in ('new','edit','setbusxy') and 'loadshape' not in x.get('object','') and 'line' not in x.get('object','')]
    return colorable_elements

def full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, REOPT_INPUTS, MICROGRIDS, FAULTED_LINE, DESCRIPTION='', INVALIDATE_CACHE=True, OUTAGE_CSV=None, DELETE_FILES=False, open_results=False):
	''' Generate a full microgrid plan for the given inputs. '''
	# Constants
	MODEL_DSS = 'circuit.dss'
	MODEL_LOAD_CSV = 'loads.csv'
	GEN_NAME = 'generation.csv'
	REF_NAME = 'ref_gen_loads.csv'
	OMD_NAME = 'circuit.dss.omd'
	MAP_NAME = 'circuit_map'
	ONELINE_NAME = 'circuit_oneline.html'
	FINAL_REPORT = 'output_final.html'
	# Create initial files.
	if not os.path.isdir(MODEL_DIR):
		os.mkdir(MODEL_DIR)
	# Setup logging.
	log_file = f'{MODEL_DIR}/logs.txt'
	if os.path.exists(log_file):
		open(log_file, 'w').close()
	logger = setup_logging(log_file)
	logger.warning(f'Logging status updates for {MODEL_DIR}.')
	try:
		shutil.copyfile(BASE_DSS, f'{MODEL_DIR}/{MODEL_DSS}')
	except:
		print('Rerunning existing project. DSS file not moved.')
		logger.warning('Rerunning existing project. DSS file not moved.')
	try:
		shutil.copyfile(LOAD_CSV, f'{MODEL_DIR}/{MODEL_LOAD_CSV}')
	except:
		print('Rerunning existing project. Load CSV file not moved.')
		logger.warning('Rerunning existing project. Load CSV file not moved.')
	if OUTAGE_CSV:
		try:
			shutil.copyfile(OUTAGE_CSV, f'{MODEL_DIR}/outages.csv')
		except:
			print('Rerunning existing project. Outages CSV file not moved.')
			logger.warning('Rerunning existing project. Outages CSV file not moved.')
	os.system(f'touch "{MODEL_DIR}/0running.txt"')
	try:
		os.remove(f"{MODEL_DIR}/0crashed.txt")
	except:
		pass
	if DELETE_FILES:
		for fname in [BASE_DSS, LOAD_CSV]:
			try:
				os.remove(fname)
			except:
				print(f'failed to delete {fname}')
				logger.warning(f'failed to delete {fname}')
	# HACK: work in directory because we're very picky about the current dir.
	curr_dir = os.getcwd()
	workDir = os.path.abspath(MODEL_DIR)
	if curr_dir != workDir:
		os.chdir(workDir)
	if os.path.exists("user_warnings.txt"):
		os.remove("user_warnings.txt")
	CREATION_DATE = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	# Find cricital loads from microgrids data structure.
	CRITICAL_LOADS = []
	for mg in MICROGRIDS:
		loads = MICROGRIDS[mg]['loads']
		critical_load_kws = MICROGRIDS[mg]['critical_load_kws']
		for l, c in zip(loads, critical_load_kws):
			if c != 0 or c != '0':
				CRITICAL_LOADS.append(l)
	# Run the full MicrogridUP analysis.
	try:
		# Dump the inputs for future reference.
		with open('allInputData.json','w') as inputs_file:
			inputs = {
				'MODEL_DIR':MODEL_DIR,
				'BASE_DSS':f'{MODEL_DIR}/{MODEL_DSS}',
				'LOAD_CSV':f'{MODEL_DIR}/{MODEL_LOAD_CSV}',
				'QSTS_STEPS':QSTS_STEPS,
				'REOPT_INPUTS':REOPT_INPUTS,
				'MICROGRIDS':MICROGRIDS,
				'FAULTED_LINE':FAULTED_LINE,
				'OUTAGE_CSV':OUTAGE_CSV,
				'CRITICAL_LOADS':CRITICAL_LOADS,
				'CREATION_DATE':CREATION_DATE,
				'DESCRIPTION':DESCRIPTION,
				'INVALIDATE_CACHE':INVALIDATE_CACHE,
				'HISTORICAL_OUTAGES':f'{MODEL_DIR}/outages.csv' if OUTAGE_CSV else None
			}
			json.dump(inputs, inputs_file, indent=4)
		# Generate the per-microgrid results and add each to the circuit iteratively.
		# - Multi-threaded REopt execution
		run_reopt_threads(MODEL_DIR, MICROGRIDS, logger, REOPT_INPUTS, INVALIDATE_CACHE)
		mgs_name_sorted = sorted(MICROGRIDS.keys())
		for i, mg_name in enumerate(mgs_name_sorted):
			BASE_DSS = MODEL_DSS if i==0 else f'circuit_plusmg_{i-1}.dss'
			max_crit_load = sum(MICROGRIDS[mg_name]['critical_load_kws'])
			microgridup_hosting_cap.run(f'reopt_final_{i}', GEN_NAME, MICROGRIDS[mg_name], BASE_DSS, mg_name, REF_NAME, MODEL_LOAD_CSV, f'circuit_plusmg_{i}.dss', f'mg_add_cost_{i}.csv', max_crit_load, logger)
		# Make OMD of fully detailed system.
		dssConvert.dssToOmd(f'circuit_plusmg_{i}.dss', OMD_NAME, RADIUS=0.0002)
		# Draw the circuit oneline.
		distNetViz.viz(OMD_NAME, forceLayout=False, outputPath='.', outputName=ONELINE_NAME, open_file=False)
		# Draw the map.
		out = colorby_mgs(OMD_NAME, MICROGRIDS, CRITICAL_LOADS)
		new_path = './color_test.omd'
		omd = json.load(open(OMD_NAME))
		omd['attachments'] = out
		with open(new_path, 'w+') as out_file:
			json.dump(omd, out_file, indent=4)
		geo.map_omd(new_path, MAP_NAME, open_browser=False)
		# geo.map_omd(OMD_NAME, MAP_NAME, open_browser=False)
		# Powerflow outputs.
		microgridup_hosting_cap.gen_powerflow_results(f'circuit_plusmg_{i}.dss', REOPT_INPUTS['year'], QSTS_STEPS, logger)
		# Perform control sim.
		new_mg_for_control = {name:MICROGRIDS[name] for name in mgs_name_sorted[0:i+1]}
		microgridup_control.play(f'circuit_plusmg_{i}.dss', os.getcwd(), new_mg_for_control, FAULTED_LINE, logger)
		# Resilience simulation with outages. Optional. Skipped if no OUTAGE_CSV
		if OUTAGE_CSV:
			all_microgrid_loads = [x.get('loads',[]) for x in MICROGRIDS.values()]
			all_loads = [item for sublist in all_microgrid_loads for item in sublist]
			microgridup_resilience.main('outages.csv', 'outages_ADJUSTED.csv', all_loads, f'circuit_plusmg_{i}.dss', 'output_resilience.html')
		# Build Final report
		reports = [x for x in os.listdir('.') if x.startswith('ultimate_rep_')]
		reports.sort()
		reopt_folders = [x for x in os.listdir('.') if x.startswith('reopt_final_')]
		reopt_folders.sort()
		reps = pd.concat([pd.read_csv(x) for x in reports]).to_dict(orient='list')
		stats = summary_stats(reps, MICROGRIDS, MODEL_LOAD_CSV)
		mg_add_cost_files = [x for x in os.listdir('.') if x.startswith('mg_add_cost_')]
		mg_add_cost_files.sort()
		# create a row-based list of lists of mg_add_cost_files
		add_cost_rows = []
		for file in mg_add_cost_files:
			with open(file, "r") as f:
				reader = csv.reader(f, delimiter=',')
				next(reader, None) #skip the header
				for row in reader:
					add_cost_rows.append([row[0],row[1],row[2],int(row[3])])
		current_time = datetime.datetime.now() 
		warnings = "None"
		if os.path.exists("user_warnings.txt"):
			with open("user_warnings.txt") as myfile:
				warnings = myfile.read()
		# generate file map
		mg_names = list(MICROGRIDS.keys())
		names_and_folders = {x[0]:x[1] for x in zip(mg_names, reopt_folders)}
		# generate a decent chart of additional generation.
		chart_html = summary_charts(stats)
		# Write out overview iframe
		with open(f'{MGU_FOLDER}/templates/template_overview.html') as file:
			over_template = j2.Template(file.read())
		over = over_template.render(
			chart_html=chart_html,
			summary=stats,
			add_cost_rows = add_cost_rows,
			warnings = warnings,
			now=current_time,
			inputs=inputs, #TODO: we will generate a frozen view of the input screen instead of just dumping inputs here.
		)
		with open('overview.html', 'w') as overfile:
			overfile.write(over)
		# Write view_inputs iframe
		with open(f'allInputData.json') as f:
			in_data = json.load(f)
			in_data['MODEL_DIR'] = in_data['MODEL_DIR'].split('/')[-1]
		with open(f'{MGU_FOLDER}/templates/template_new.html') as f:
			view_inputs_template = j2.Template(f.read())
		view_inputs_html = view_inputs_template.render(in_data=in_data, iframe_mode=True)
		with open('view_inputs.html', 'w') as f:
			f.write(view_inputs_html)
		# Write full output
		with open(f'{MGU_FOLDER}/templates/template_output.html') as file:
			template = j2.Template(file.read())
		out = template.render(
			raw_files = _walkTree('.'),
			model_name =  os.path.basename(MODEL_DIR),
			mg_names_and_reopt_folders = names_and_folders,
			resilience_show = (OUTAGE_CSV is not None),
			timeseries_control_csv_plot_html_show = os.path.isfile('timeseries_control.csv.plot.html'),
		)
		with open(FINAL_REPORT,'w') as outFile:
			outFile.write(out)
		if open_results:
			os.system(f'open {FINAL_REPORT}')
	except Exception:
		print(traceback.format_exc())
		logger.warning(traceback.format_exc())
		os.system(f'touch "{MODEL_DIR}/0crashed.txt"')
	finally:
		os.chdir(curr_dir)
		os.system(f'rm "{workDir}/0running.txt"')


def run_reopt_threads(model_dir, microgrids, logger, reopt_inputs, invalidate_cache):
	'''
	:param model_dir: the path to the outermost model directory of the circuit shared by all of the microgrids
	:type model_dir: string
	:param microgrids: all of the microgrid definitions (as defined by microgrid_gen_mgs.py) for the given circuit
	:type microgrids: dict
	:param logger: a logger
	:type logger: logger
	:param reopt_inputs: REopt inputs that must be set by the user. All microgrids for a given circuit share these same REopt parameters. All threads
	    should only read from this dict, so it's fine that they're sharing the same dict
	:type reopt_inputs: dict
	:param invalidate_cache: whether to ignore an existing directory of cached REopt results for all of the microgrids of a circuit
	:return: don't return anything once all the threads have completed. Instead, just read the corresponding allInputData.json and allOutputData.json
		file for each microgrid to build a new DSS file in microgridup_hosting_cap.py
	:rtype: None

	This function will not retry a REopt thread that returned an exception due to an optimization timeout. Instead, it will immediately raise the
	optimization timeout exception. This function will retry a REopt thread that returned an exception due to something other than an optimization
	timeout.
	'''
	assert isinstance(model_dir, str)
	assert isinstance(microgrids, dict)
	assert isinstance(logger, logging.Logger)
	assert isinstance(reopt_inputs, dict)
	assert isinstance(invalidate_cache, bool)
	# - Shuffle the api keys so we don't use them in the same order every time
	api_keys = random.sample(REOPT_API_KEYS, len(REOPT_API_KEYS))
	# - Generate the correct arguments for each REopt thread to be run
	thread_argument_lists = []
	for i, mg_name in enumerate(sorted(microgrids.keys())):
		# - Generate a set of arguments for a single thread
		thread_argument_lists.append([model_dir, microgrids[mg_name], i, logger, reopt_inputs, mg_name, api_keys[i % len(api_keys)], invalidate_cache])
	# - Retry a thread that throws an exception
	future_lists = ([], [])
	argument_lists = (thread_argument_lists, [])
	with concurrent.futures.ThreadPoolExecutor() as executor:
		for args_list in argument_lists[0]:
			future_lists[0].append(executor.submit(run_reopt_thread, *args_list))
		for future_list_idx, future_list in enumerate(future_lists):
			for f in concurrent.futures.as_completed(future_list):
				if f.exception() is not None:
					# - omf.__neoMetaModel__.py captures any exception thrown by a model's work() function and writes it to stderr.txt within the
					#   model's working directory. Any exception detected here is caused by a side-effect of REopt failing, namely that
					#   reopt_final_i/allOutputData.json does not exist. But that file could not exist for various reasons, and we only retry a thread
					#   if it did not fail due to an optimization timeout. Therefore, we have to read stderr.txt to get the original exception
					#   information
					future_idx = future_list.index(f)
					args_list = argument_lists[future_list_idx][future_idx]
					stderr_filepath = f'reopt_final_{args_list[2]}/stderr.txt'
					if os.path.isfile(stderr_filepath):
						with open(stderr_filepath) as f:
							string = f.read()
							if string.find('Optimization exceeded timeout') > -1:
								raise Exception(f'Thread for microgrid "{args_list[5]}" for circuit "{args_list[0]}" failed due to REopt reaching an optimization timeout of 420 seconds.')
					# - If the thread failed due to some other reason, retry it once
					if future_list_idx + 1 < len(future_lists):
						# - Always invalidate the cache when retrying
						args_list[-1] = True
						future_lists[future_list_idx + 1].append(executor.submit(run_reopt_thread, *args_list))
						argument_lists[future_list_idx + 1].append(args_list)

def run_reopt_thread(model_dir, microgrid, microgrid_index, logger, reopt_inputs, mg_name, api_key, invalidate_cache):
	print('THIS DIR FOR THREADS', os.getcwd())
	existing_generation_dict = microgridup_hosting_cap.get_microgrid_existing_generation_dict('circuit.dss', microgrid)
	lat, lon = microgridup_hosting_cap.get_microgrid_coordinates('circuit.dss', microgrid)
	microgridup_design.run(model_dir, f'reopt_final_{microgrid_index}', microgrid, logger, reopt_inputs, mg_name, lat, lon, existing_generation_dict, api_key, invalidate_cache)

def _tests():
	''' Unit tests for this module. '''
	with open('testfiles/test_params.json') as file:
		test_params = json.load(file)
	MG_MINES = test_params['MG_MINES']
	REOPT_INPUTS = test_params['REOPT_INPUTS']
	QSTS_STEPS = 480.0
	FAULTED_LINE = '670671'
	# Test of full().
	successful_tests = []
	failed_tests = []
	untested = ['3mgs_wizard_lukes', '3mgs_lehigh_lukes']
	for _dir in MG_MINES:
		try:
			_dir.index('wizard')
			mgu_args = [f'{PROJ_FOLDER}/{_dir}', f'{MGU_FOLDER}/testfiles/wizard_base_3mg.dss']
		except ValueError as e:
			mgu_args = [f'{PROJ_FOLDER}/{_dir}', f'{MGU_FOLDER}/testfiles/lehigh_base_3mg.dss']
		mgu_args.extend([f'{MGU_FOLDER}/testfiles/lehigh_load.csv', QSTS_STEPS, REOPT_INPUTS, MG_MINES[_dir][0], FAULTED_LINE, '', False])
		print(f'---------------------------------------------------------\nBeginning end-to-end backend test of {_dir}.\n---------------------------------------------------------')
		full(*mgu_args)
		if untested.count(_dir) == 0 and os.path.isfile(f'{PROJ_FOLDER}/{_dir}/0crashed.txt'):
			failed_tests.append(_dir)
		else:
			successful_tests.append(_dir)
	_print_header('Successful Tests Report')
	print(f'Number of successful tests: {len(successful_tests)}')
	print(successful_tests)
	_print_header('Failed Tests Report')
	print(f'Number of failed tests: {len(failed_tests)}')
	print(failed_tests)
	_print_header('Untested Circuits Report')
	print(f'Number of untested circuits: {len(untested)}')
	print(untested)
	if len(failed_tests) > 0:
		sys.exit(1) # trigger failure
	print('\nSuccessfully completed tests for microgridup.py.')

if __name__ == '__main__':
	_tests()