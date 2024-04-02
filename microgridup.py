from omf.solvers.opendss import dssConvert
from omf import distNetViz, geo
from omf.runAllTests import _print_header
import microgridup_control
import microgridup_resilience
import microgridup_design
import microgridup_hosting_cap
import shutil
import os
import json
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import csv
import jinja2 as j2
import datetime
import traceback
import sys
import logging

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

def summary_stats(reps, MICROGRIDS):
	'''Helper function within full() to take in a dict of lists of the microgrid
	attributes and append a summary value for each attribute'''
	load_df = pd.read_csv('loads.csv')
	# - Remove any columns that contain hourly indicies instead of kW values
	load_df = load_df.iloc[:, load_df.apply(microgridup_design.is_not_timeseries_column).to_list()]
	load_series = load_df.apply(sum, axis=1)
	reps['Microgrid Name'].append('Summary')
	reps['Generation Bus'].append('None')
	reps['Minimum 1 hr Load (kW)'].append(round(load_series.min()))
	reps['Average 1 hr Load (kW)'].append(round(load_series.mean()))
	reps['Average Daytime 1 hr Load (kW)'].append(round(np.average(np.average(np.array(np.split(load_series.to_numpy(), 365))[:, 9:17], axis=1))))
	reps['Maximum 1 hr Load (kW)'].append(round(load_series.max()))
	reps['Minimum 1 hr Critical Load (kW)'].append(round(sum(reps['Minimum 1 hr Critical Load (kW)'])))
	reps['Average 1 hr Critical Load (kW)'].append(round(sum(reps['Average 1 hr Critical Load (kW)'])))
	reps['Average Daytime 1 hr Critical Load (kW)'].append(round(sum(reps['Average Daytime 1 hr Critical Load (kW)'])))
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
	reps['Emissions (Yr 1 Tons CO2)'].append(round(sum(reps['Emissions (Yr 1 Tons CO2)'])))
	# print("yr1_emis:", yr1_emis)
	emis_reduc_perc = reps['Emissions Reduction (Yr 1 % CO2)']
	yr1_emis = reps['Emissions (Yr 1 Tons CO2)']
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
		reps['Average Outage Survived (h)'].append(round(min(reps['Average Outage Survived (h)']), 0))
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

def check_each_mg_for_reopt_error(number_of_microgrids, logger):
	for number in range(number_of_microgrids):
		path = f'reopt_mg{number}/results.json'
		if os.path.isfile(path):
			with open(path) as file:
				results = json.load(file)
			if results.get('Messages',{}).get('errors',{}):
				error_message_list = results.get('Messages',{}).get('errors',{})
				print(f'Error in REopt folder reopt_mg{number}: {error_message_list}')
				logger.warning(f'Error in REopt folder reopt_mg{number}: {error_message_list}')
			else:
				logger.warning(f'No error messages returned in REopt folder reopt_mg{number}.')
				print(f'No error messages returned in REopt folder reopt_mg{number}.')
		else:
			print(f'An Exception occured but REopt folder reopt_mg{number} does not exist.')
			logger.warning(f'An Exception occured but REopt folder reopt_mg{number} does not exist.')

def full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, REOPT_INPUTS, MICROGRIDS, FAULTED_LINES, DESCRIPTION='', INVALIDATE_CACHE=True, OUTAGE_CSV=None, DELETE_FILES=False, open_results=False):
	''' Generate a full microgrid plan for the given inputs. '''
	# Constants
	MODEL_DSS = 'circuit.dss'
	MODEL_LOAD_CSV = 'loads.csv'
	GEN_NAME = 'generation.csv'
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
			if float(c) != 0:
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
				'FAULTED_LINES':FAULTED_LINES,
				'OUTAGE_CSV':OUTAGE_CSV,
				'CRITICAL_LOADS':CRITICAL_LOADS,
				'CREATION_DATE':CREATION_DATE,
				'DESCRIPTION':DESCRIPTION,
				'INVALIDATE_CACHE':INVALIDATE_CACHE
			}
			json.dump(inputs, inputs_file, indent=4)
		# - Calculate hosting capacity for the initial circuit uploaded by the user or created via the GUI
		microgridup_hosting_cap.run_hosting_capacity(MODEL_DSS)
		# - For each microgrid, use REOPT to calculate the optimal amount of new generation assets and to calculate generation power output
		microgridup_design.run_reopt(MICROGRIDS, logger, REOPT_INPUTS, INVALIDATE_CACHE)
		# - Go through the REOPT results and iteratively add each microgrid's new generation to the original circuit until all of the new generation
		#   has been added
		mg_names_sorted = sorted(MICROGRIDS.keys())
		for i in range(0, len(mg_names_sorted)):
			# - Initially, BASE_DSS is the circuit file that was uploaded by the user to uploads/ or created via the GUI circuit creator. The model
			#   directory gets a copy of this file and names the copy "circuit.dss". The first run of microgridup_hosting_cap.run() uses circuit.dss
			#   with microgrid mg0 to create circuit_plus_mg0.dss. The next run of microgridup_hosting_cap.run() uses circuit_plus_mg0.dss with
			#   microgrid mg1 to create circuit_plus_mg1.dss, etc. Eventually, a final circuit_plus_mgAll.dss is created and that is the final
			#   circuit file we run control simulations on
			mg_name = mg_names_sorted[i]
			if i == 0:
				BASE_DSS = MODEL_DSS
			else:
				BASE_DSS = f'circuit_plus_{mg_names_sorted[i-1]}.dss'
			if i == len(mg_names_sorted) - 1:
				output_dss_filename = 'circuit_plus_mgAll.dss'
			else:
				output_dss_filename = f'circuit_plus_{mg_name}.dss'
			microgridup_hosting_cap.run(f'reopt_{mg_name}', GEN_NAME, MICROGRIDS[mg_name], BASE_DSS, mg_name, MODEL_LOAD_CSV, output_dss_filename, f'mg_add_cost_{mg_name}.csv', logger, REOPT_INPUTS)
		# Make OMD of fully detailed system.
		dssConvert.dssToOmd('circuit_plus_mgAll.dss', OMD_NAME, RADIUS=0.0002)
		# Draw the circuit oneline.
		distNetViz.viz(OMD_NAME, forceLayout=False, outputPath='.', outputName=ONELINE_NAME, open_file=False)
		# Powerflow outputs.
		microgridup_hosting_cap.gen_powerflow_results('circuit_plus_mgAll.dss', REOPT_INPUTS['year'], QSTS_STEPS, logger)
		# Draw the map.
		out = colorby_mgs(OMD_NAME, MICROGRIDS, CRITICAL_LOADS)
		new_path = './color_test.omd'
		omd = json.load(open(OMD_NAME))
		omd['attachments'] = out
		with open('hosting_capacity/color_by.csv') as f:
			omd['attachments']['coloringFiles']['color_by.csv'] = {
				'csv': f.read()
			}
		with open(new_path, 'w+') as out_file:
			json.dump(omd, out_file, indent=4)
		geo.map_omd(new_path, MAP_NAME, open_browser=False)
		# Perform control sim.
		new_mg_for_control = {name:MICROGRIDS[name] for name in mg_names_sorted[0:i+1]}
		with open(f'reopt_{mg_names_sorted[0]}/allInputData.json') as file:
			allInputData = json.load(file)
		outage_start = int(allInputData['outage_start_hour'])
		outage_length = int(allInputData['outageDuration'])
		microgridup_control.play('circuit_plus_mgAll.dss', os.getcwd(), new_mg_for_control, FAULTED_LINES, outage_start, outage_length, logger)
		# Resilience simulation with outages. Optional. Skipped if no OUTAGE_CSV
		if OUTAGE_CSV:
			all_microgrid_loads = [x.get('loads',[]) for x in MICROGRIDS.values()]
			all_loads = [item for sublist in all_microgrid_loads for item in sublist]
			microgridup_resilience.main('outages.csv', 'outages_ADJUSTED.csv', all_loads, 'circuit_plus_mgAll.dss', 'output_resilience.html')
		# Build Final report
		reports = [x for x in os.listdir('.') if x.startswith('ultimate_rep_')]
		reports.sort()
		reps = pd.concat([pd.read_csv(x) for x in reports]).to_dict(orient='list')
		stats = summary_stats(reps, MICROGRIDS)
		mg_add_cost_files = [x for x in os.listdir('.') if x.startswith('mg_add_cost_')]
		mg_add_cost_files.sort()
		# create a row-based list of lists of mg_add_cost_files
		add_cost_rows = []
		for file in mg_add_cost_files:
			df = pd.read_csv(file)
			for row in df.values.tolist():
				add_cost_rows.append(row)
		current_time = datetime.datetime.now() 
		warnings = "None"
		if os.path.exists("user_warnings.txt"):
			with open("user_warnings.txt") as myfile:
				warnings = myfile.read()
		microgridup_design.create_economic_microgrid(MICROGRIDS, logger, REOPT_INPUTS, INVALIDATE_CACHE)
		names_and_folders = {x.split('_')[1]: x for x in sorted([dir_ for dir_ in os.listdir('.') if dir_.startswith('reopt_')])}
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
	except Exception as e:
		print(traceback.format_exc())
		logger.warning(traceback.format_exc())
		os.system(f'touch "{MODEL_DIR}/0crashed.txt"')
		check_each_mg_for_reopt_error(len(MICROGRIDS), logger)
	finally:
		os.chdir(curr_dir)
		os.system(f'rm "{workDir}/0running.txt"')


def _tests():
	''' Unit tests for this module. '''
	with open('testfiles/test_params.json') as file:
		test_params = json.load(file)
	MG_MINES = test_params['MG_MINES']
	REOPT_INPUTS = test_params['REOPT_INPUTS']
	QSTS_STEPS = 480.0
	# Test of full().
	successful_tests = []
	failed_tests = []
	untested = ['3mgs_wizard_lukes', '3mgs_lehigh_lukes']
	for _dir in MG_MINES:
		try:
			_dir.index('wizard')
			FAULTED_LINES = 'reg1'
			mgu_args = [f'{PROJ_FOLDER}/{_dir}', f'{MGU_FOLDER}/testfiles/wizard_base_3mg.dss']
		except ValueError as e:
			FAULTED_LINES = '670671'
			mgu_args = [f'{PROJ_FOLDER}/{_dir}', f'{MGU_FOLDER}/testfiles/lehigh_base_3mg.dss']
		mgu_args.extend([f'{MGU_FOLDER}/testfiles/lehigh_load.csv', QSTS_STEPS, REOPT_INPUTS, MG_MINES[_dir][0], FAULTED_LINES, '', False])
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