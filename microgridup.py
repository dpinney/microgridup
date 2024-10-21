import os, json, datetime, traceback, re, sys, logging, shutil, copy
from types import MappingProxyType
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import jinja2 as j2
from omf.solvers.opendss import dssConvert
from omf import distNetViz, geo
from omf.runAllTests import _print_header
import microgridup_control
import microgridup_design
import microgridup_hosting_cap
import microgridup_resilience


# - All path referencing should be done though these constants in this module
MGU_DIR = os.path.abspath(os.path.dirname(__file__))
if MGU_DIR == '/':
	# - Workaround for docker root installs
	MGU_DIR = ''
PROJ_DIR = f'{MGU_DIR}/data/projects'


def main(data, invalidate_cache=True, open_results=False):
	'''
	Generate a full microgrid plan from the given inputs

	:param data: a dictionary that is essentially a copy of the POST-ed user-submitted data for running a model (i.e. request.form)
	:type data: dict
	:param invalidate_cache: whether to erase existing REopt results if they exist
	:type invalidate_cache: bool
	:param open_results: whether to open the results in the browser
	:type open_results: bool
	:rtype: None
	'''
	# - Assert the data has the expected schema
	assert isinstance(data, dict)
	assert 'MODEL_DIR' in data
	# - MODEL_DIR must be a name, not a directory
	assert data['MODEL_DIR'].find('/') == -1
	assert 'BASE_DSS' in data
	assert 'LOAD_CSV' in data
	assert 'QSTS_STEPS' in data
	assert 'FAULTED_LINES' in data
	assert isinstance(data['FAULTED_LINES'], list)
	assert 'OUTAGE_CSV' in data
	assert 'CRITICAL_LOADS' in data
	assert isinstance(data['CRITICAL_LOADS'], list)
	assert 'DESCRIPTION' in data
	assert 'MICROGRIDS' in data
	assert isinstance(data['MICROGRIDS'], dict)
	assert 'singlePhaseRelayCost' in data
	assert 'threePhaseRelayCost' in data
	assert 'REOPT_INPUTS' in data
	assert isinstance(data['REOPT_INPUTS'], dict)
	# - jsCircuitModel is an optional key
	assert len(data.keys()) == 12 or (len(data.keys()) == 13 and 'jsCircuitModel' in data)
	assert isinstance(invalidate_cache, bool)
	assert isinstance(open_results, bool)
	# Quick check to ensure MODEL_DIR contains only lowercase alphanumeric and dashes. No spaces or underscores.
	pattern = re.compile(r'^[a-z0-9-]+$')
	assert bool(pattern.match(data['MODEL_DIR'])), f'MODEL_DIR may only contain lowercase alphanumeric characters and dashes. Received MODEL_DIR: {data["MODEL_DIR"]}'
	# - Format the data
	#   - TODO: move maxRuntimeSeconds out of REOPT_INPUTS
	data['QSTS_STEPS'] = int(data['QSTS_STEPS'])
	data['singlePhaseRelayCost'] = float(data['singlePhaseRelayCost'])
	data['threePhaseRelayCost'] = float(data['threePhaseRelayCost'])
	absolute_model_directory = f'{PROJ_DIR}/{data["MODEL_DIR"]}'
	inputs = {
		'MODEL_DIR': data['MODEL_DIR'],
		'BASE_DSS': f'{absolute_model_directory}/circuit.dss', # Is this key needed?
		'LOAD_CSV': f'{absolute_model_directory}/loads.csv', # Is this key needed?
		'QSTS_STEPS': data['QSTS_STEPS'],
		'REOPT_INPUTS': data['REOPT_INPUTS'],
		'MICROGRIDS': data['MICROGRIDS'],
		'FAULTED_LINES': data['FAULTED_LINES'],
		'OUTAGE_CSV': None if data['OUTAGE_CSV'] is None else f'{absolute_model_directory}/outages.csv',
		'CRITICAL_LOADS': data['CRITICAL_LOADS'],
		'CREATION_DATE': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
		'DESCRIPTION': data['DESCRIPTION'],
		'singlePhaseRelayCost': data['singlePhaseRelayCost'],
		'threePhaseRelayCost': data['threePhaseRelayCost']
	}
	if 'jsCircuitModel' in data:
		inputs['jsCircuitModel'] = data['jsCircuitModel']
	# - Set up the model directory and environment
	# Create initial files.
	if not os.path.isdir(absolute_model_directory):
		os.mkdir(absolute_model_directory)
	# HACK: work in directory because we're very picky about the current dir.
	curr_dir = os.getcwd()
	if curr_dir != absolute_model_directory:
		os.chdir(absolute_model_directory)
	if os.path.exists("user_warnings.txt"):
		os.remove("user_warnings.txt")
	# - Dump the inputs for future reference. MappingProxyObjects can't be seralized, so use the original mutable data
	with open('allInputData.json', 'w') as inputs_file:
		json.dump(inputs, inputs_file, indent=4)
	# - Now that the data object has been set up, we shouldn't need to change it anymore, so create an immutable copy to pass around
	immutable_data = get_immutable_dict(data)
	# Setup logging.
	log_file = f'{absolute_model_directory}/logs.log'
	if os.path.exists(log_file):
		open(log_file, 'w').close()
	logger = setup_logging(log_file)
	logger.warning(f'Logging status updates for {absolute_model_directory}.')
	# - Copy files from /uploads into model_dir
	_copy_files_from_uploads_into_model_dir(immutable_data['BASE_DSS'], f'{absolute_model_directory}/circuit.dss', logger)
	_copy_files_from_uploads_into_model_dir(immutable_data['LOAD_CSV'], f'{absolute_model_directory}/loads.csv', logger)
	if immutable_data['OUTAGE_CSV'] is not None:
		_copy_files_from_uploads_into_model_dir(immutable_data['OUTAGE_CSV'], f'{absolute_model_directory}/outages.csv', logger)
	os.system(f'touch "{absolute_model_directory}/0running.txt"')
	try:
		os.remove(f"{absolute_model_directory}/0crashed.txt")
	except FileNotFoundError:
		pass
	# Run the full MicrogridUP analysis.
	try:
		# - Calculate hosting capacity for the initial circuit uploaded by the user or created via the GUI
		microgridup_hosting_cap.run_hosting_capacity()
		# - For each microgrid, use REOPT to calculate the optimal amount of new generation assets and to calculate generation power output
		microgridup_design.run_reopt(data, logger, invalidate_cache)
		# - Go through the REOPT results and iteratively add each microgrid's new generation to the original circuit until all of the new generation
		#   has been added
		mg_names_sorted = sorted(immutable_data['MICROGRIDS'].keys())
		for i in range(0, len(mg_names_sorted)):
			# - Initially, dss_filename is the circuit file that was uploaded by the user to uploads/ or created via the GUI circuit creator. The model
			#   directory gets a copy of this file and names the copy "circuit.dss". The first run of microgridup_hosting_cap.run() uses circuit.dss
			#   with microgrid mg0 to create circuit_plus_mg0.dss. The next run of microgridup_hosting_cap.run() uses circuit_plus_mg0.dss with
			#   microgrid mg1 to create circuit_plus_mg1.dss, etc. Eventually, a final circuit_plus_mgAll.dss is created and that is the final
			#   circuit file we run control simulations on
			mg_name = mg_names_sorted[i]
			if i == 0:
				input_dss_filename = 'circuit.dss'
			else:
				input_dss_filename = f'circuit_plus_{mg_names_sorted[i-1]}.dss'
			if i == len(mg_names_sorted) - 1:
				output_dss_filename = 'circuit_plus_mgAll.dss'
			else:
				output_dss_filename = f'circuit_plus_{mg_name}.dss'
			microgridup_hosting_cap.run(immutable_data, mg_name, input_dss_filename, output_dss_filename, logger)
		# Make OMD of fully detailed system.
		dssConvert.dssToOmd('circuit_plus_mgAll.dss', 'circuit.dss.omd', RADIUS=0.0002)
		# Draw the circuit oneline.
		distNetViz.viz('circuit.dss.omd', forceLayout=False, outputPath='.', outputName='circuit_oneline.html', open_file=False)
		# Powerflow outputs.
		microgridup_hosting_cap.gen_powerflow_results(immutable_data['REOPT_INPUTS']['year'], immutable_data['QSTS_STEPS'], logger)
		# Draw the map.
		out = colorby_mgs('circuit.dss.omd', immutable_data['MICROGRIDS'], immutable_data['CRITICAL_LOADS'])
		new_path = './color_test.omd'
		omd = json.load(open('circuit.dss.omd'))
		omd['attachments'] = out
		with open('hosting_capacity/color_by_traditional.csv') as f:
			omd['attachments']['coloringFiles']['color_by.csv'] = {
				'csv': f.read()
			}
		with open(new_path, 'w+') as out_file:
			json.dump(omd, out_file, indent=4)
		geo.map_omd(new_path, 'circuit_map', open_browser=False)
		with open(f'reopt_{mg_names_sorted[0]}/allInputData.json') as file:
			allInputData = json.load(file)
		outage_start = int(allInputData['outage_start_hour'])
		outage_length = int(allInputData['outageDuration'])
		# - Perform a control sim on circuit_plug_mgAll.dss
		try:
			microgridup_control.play(immutable_data, outage_start, outage_length, logger)
		except ValueError as e:
			error_message = str(e)
			print(error_message)
			logger.warning(error_message)
			with open('output_control.html', 'w') as file:
				file.write(f"<html><body><h1>Error</h1><p>{error_message}</p></body></html>")
		# Resilience simulation with outages. Optional. Skipped if no OUTAGE_CSV
		if immutable_data['OUTAGE_CSV']:
			all_microgrid_loads = [x.get('loads',[]) for x in immutable_data['MICROGRIDS'].values()]
			all_loads = [item for sublist in all_microgrid_loads for item in sublist]
			microgridup_resilience.main('outages.csv', 'outages_ADJUSTED.csv', all_loads, 'circuit_plus_mgAll.dss', 'output_resilience.html')
		# Build Final report
		reports = [x for x in os.listdir('.') if x.startswith('ultimate_rep_')]
		reports.sort()
		reps = pd.concat([pd.read_csv(x) for x in reports]).to_dict(orient='list')
		stats = summary_stats(reps)
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
		microgridup_design.create_economic_microgrid(immutable_data, logger, invalidate_cache)
		names_and_folders = {x.split('_')[1]: x for x in sorted([dir_ for dir_ in os.listdir('.') if dir_.startswith('reopt_')])}
		# generate a decent chart of additional generation.
		chart_html = summary_charts(stats)
		# Write out overview iframe
		with open(f'{MGU_DIR}/templates/template_overview.html') as file:
			over_template = j2.Template(file.read())
		over = over_template.render(
			chart_html=chart_html,
			summary=stats,
			add_cost_rows = add_cost_rows,
			warnings = warnings,
			now=current_time,
			inputs=inputs) #TODO: we will generate a frozen view of the input screen instead of just dumping inputs here.
		with open('overview.html', 'w') as overfile:
			overfile.write(over)
		# Write view_inputs iframe
		with open(f'allInputData.json') as f:
			in_data = json.load(f)
		with open(f'{MGU_DIR}/templates/template_new.html') as f:
			view_inputs_template = j2.Template(f.read())
		# - Encode the circuit model properly
		if 'jsCircuitModel' in in_data:
			jsCircuitModel = []
			for s in json.loads(in_data['jsCircuitModel']):
				jsCircuitModel.append(json.loads(s))
			in_data['jsCircuitModel'] = jsCircuitModel
		view_inputs_html = view_inputs_template.render(in_data=in_data, iframe_mode=True)
		with open('view_inputs.html', 'w') as f:
			f.write(view_inputs_html)
		# Write full output
		with open(f'{MGU_DIR}/templates/template_output.html') as file:
			template = j2.Template(file.read())
		out = template.render(
			raw_files = _walkTree('.'),
			model_name =  data['MODEL_DIR'],
			mg_names_and_reopt_folders = names_and_folders,
			resilience_show = (data['OUTAGE_CSV'] is not None),
			timeseries_control_csv_plot_html_show = os.path.isfile('timeseries_control.csv.plot.html'))
		with open('output_final.html','w') as outFile:
			outFile.write(out)
		if open_results:
			os.system(f'open output_final.html')
	except Exception as e:
		print(traceback.format_exc())
		logger.warning(traceback.format_exc())
		os.system(f'touch "{absolute_model_directory}/0crashed.txt"')
		check_each_mg_for_reopt_error(immutable_data['MICROGRIDS'], logger)
	finally:
		os.chdir(curr_dir)
		os.system(f'rm "{absolute_model_directory}/0running.txt"')


def setup_logging(log_file, mg_name=None):
	logger = logging.getLogger(f'reopt_{mg_name}') if mg_name else logging.getLogger()
	logger.setLevel(logging.WARNING)
	formatter = logging.Formatter('%(asctime)s %(processName)-10s %(name)s %(message)s')
	file_handler = logging.FileHandler(log_file)
	file_handler.setFormatter(formatter)
	logger.addHandler(file_handler)
	return logger


def _walkTree(dirName):
	listOfFiles = []
	for (dirpath, _, filenames) in os.walk(dirName):
		listOfFiles += [os.path.join(dirpath, file) for file in filenames]
	return listOfFiles


def summary_stats(reps):
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
	assert isinstance(omd_path, str)
	assert isinstance(mg_group_dictionary, MappingProxyType)
	assert isinstance(critical_loads, tuple)
	attachments_keys = {
		"coloringFiles": {
			"microgridColoring.csv": {
				"csv": "<content>",
				"colorOnLoadColumnIndex": "1"
			}
		}
	}
	output_csv = 'bus,mg_color,crit_color\n'
	all_mg_elements = microgridup_control.get_all_mg_elements(None, mg_group_dictionary, omd_path)
	all_colorable_elements = get_all_colorable_elements(None, omd_path)
	seen = set()
	for mg_key in mg_group_dictionary:
		all_items = list(all_mg_elements[mg_key])
		for item in all_items:
			critical_binary = 1 if item in critical_loads else 0
			output_csv += item + ',' + str(mg_key) + ',' + str(critical_binary) + '\n'
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


def check_each_mg_for_reopt_error(MICROGRIDS, logger):
	for mg in MICROGRIDS:
		path = f'reopt_{mg}/results.json'
		if os.path.isfile(path):
			with open(path) as file:
				results = json.load(file)
			if results.get('Messages',{}).get('errors',{}):
				error_message_list = results.get('Messages',{}).get('errors',{})
				print(f'Error in REopt folder reopt_{mg}: {error_message_list}')
				logger.warning(f'Error in REopt folder reopt_{mg}: {error_message_list}')
			else:
				logger.warning(f'No error messages returned in REopt folder reopt_{mg}.')
				print(f'No error messages returned in REopt folder reopt_{mg}.')
		else:
			print(f'An Exception occured but results.json in REopt folder reopt_{mg} does not exist.')
			logger.warning(f'An Exception occured but results.json in REopt folder reopt_{mg} does not exist.')


def get_immutable_dict(data):
	'''
	Get an immutable copy of the data. Functions later in the call stack shouldn't need to modify the data. They should only need to read pieces of it
	to write some output. Working with an immutable dict is a way to maintain sanity as it gets passed around among all of our functions. This
	function is recommened, but is not required (i.e. it could be commented-out and ignored completely)

	:param data: all of the data we need to run our model
	:type data: dict
	:return: an immutable proxy to the data
	:rtype: MappingProxyType
	'''
	assert isinstance(data, dict)
	data_copy = copy.deepcopy(data)
	def dfs_helper(d):
		'''
		Use DFS to make all nested dicts and lists immutable
		'''
		stack = []
		stack.append((None, None, d))
		while len(stack) > 0:
			mutable_obj = stack[len(stack) - 1][2]
			if isinstance(mutable_obj, dict):
				for k, v in mutable_obj.items():
					if isinstance(v, dict) or isinstance(v, list):
						stack.append((mutable_obj, k, v))
			elif isinstance(mutable_obj, list):
				for idx in range(len(mutable_obj)):
					v = mutable_obj[idx]
					if isinstance(v, dict) or isinstance(v, list):
						stack.append((mutable_obj, k, v))
			if mutable_obj == stack[len(stack) - 1][2]:
				parent, k, v = stack.pop()
				if parent is None:
					# - I assume that the outermost data structure will always be a dict, not a list
					return MappingProxyType(v)
				else:
					if isinstance(v, list):
						parent[k] = tuple(v)
					elif isinstance(v, dict):
						parent[k] = MappingProxyType(v)
	return dfs_helper(data_copy)


def _copy_files_from_uploads_into_model_dir(src_filepath, dst_filepath, logger):
	'''
	:param src_filepath: the filepath of the src file (i.e. a file in /uploads)
	:type src_filepath: str
	:param dst_path: the filepath of the dst file (i.e. a file in a model directory)
	:type dst_filepath: str
	:param logger: a logger
	:type logger: Logger
	:rtype: None
	'''
	assert isinstance(src_filepath, str)
	assert isinstance(dst_filepath, str)
	assert isinstance(logger, logging.Logger)
	try:
		shutil.copyfile(src_filepath, dst_filepath)
	except shutil.SameFileError:
		dst_filename = dst_filepath.split('/')[-1]
		print(f'Rerunning existing project. "{dst_filename}" not moved.')
		logger.warning(f'Rerunning existing project. "{dst_filename}" file not moved.')


def _tests():
	data = {
		'MODEL_DIR': '<replace me>',
		'BASE_DSS': '<replace_me>',
		'LOAD_CSV': f'{MGU_DIR}/testfiles/lehigh_load.csv',
		'QSTS_STEPS': 480,
		'REOPT_INPUTS': {
			'energyCost': 0.12,
			'wholesaleCost': 0.034,
			'demandCost': 20.0,
			'solarCanCurtail': True,
			'solarCanExport': True,
			'urdbLabelSwitch': False,
			'urdbLabel': '5b75cfe95457a3454faf0aea',
			'year': 2017,
			'analysisYears': 25,
			'outageDuration': 48,
			'value_of_lost_load': 100.0,
			'omCostEscalator': 0.025,
			'discountRate': 0.083,
			'solar': True,
			'battery': True,
			'fossil': True,
			'wind': False,
			'solarCost': 1600.0,
			'solarMax': 10000.0,
			'solarMin': 0.0,
			'solarMacrsOptionYears': 0,
			'solarItcPercent': 0.26,
			'batteryCapacityCost': 420.0,
			'batteryCapacityMax': 100000.0,
			'batteryCapacityMin': 0.0,
			'batteryPowerCost': 840.0,
			'batteryPowerMax': 10000.0,
			'batteryPowerMin': 0.0,
			'batteryMacrsOptionYears': 0,
			'batteryItcPercent': 0.0,
			'batteryPowerCostReplace': 410.0,
			'batteryCapacityCostReplace': 200.0,
			'batteryPowerReplaceYear': 10,
			'batteryCapacityReplaceYear': 10,
			'dieselGenCost': 1000.0,
			'dieselMax': 10000.0,
			'dieselMin': 0.0,
			'fuelAvailable': 150000.0,
			'minGenLoading': 0.3,
			'dieselFuelCostGal': 1.5,
			'dieselCO2Factor': 24.1,
			'dieselOMCostKw': 35.0,
			'dieselOMCostKwh': 0.02,
			'dieselOnlyRunsDuringOutage': False,
			'dieselMacrsOptionYears': 0,
			'windCost': 4989.0,
			'windMax': 1000.0,
			'windMin': 0.0,
			'windMacrsOptionYears': 0,
			'windItcPercent': 0.26,
			'maxRuntimeSeconds': 240,
		},
		'MICROGRIDS': '<replace me>',
		'FAULTED_LINES': '<replace me>',
		'OUTAGE_CSV': None,
		'CRITICAL_LOADS': [
			'634a_data_center',
			'634b_radar',
			'634c_atc_tower',
			'675a_hospital',
			'675b_residential1',
			'675c_residential1',
			"645_hangar",
			"646_office",
			#'692_warehouse2',
			#'611_runway',
			#'652_residential'
			#'684_command_center',
		],
		'DESCRIPTION': '',
		'singlePhaseRelayCost': 300.0,
		'threePhaseRelayCost': 20000.0,
	}
	# Test of main()
	successful_tests = []
	failed_tests = []
	untested = ['3mgs_wizard_lukes', '3mgs_lehigh_lukes']
	with open('testfiles/test_params.json') as file:
		test_params = json.load(file)
	# - It appears that, for these tests, all we need from test_params.json are the microgrid definitions. We can ignore everything else
	MICROGRIDS = test_params['MICROGRIDS']
	for model_name in MICROGRIDS:
		data['MODEL_DIR'] = model_name
		data['MICROGRIDS'] = MICROGRIDS[model_name][0]
		try:
			model_name.index('wizard')
			data['BASE_DSS'] = f'{MGU_DIR}/testfiles/wizard_base_3mg.dss'
			data['FAULTED_LINES'] = ['reg1']
		except ValueError as e:
			data['BASE_DSS'] = f'{MGU_DIR}/testfiles/lehigh_base_phased.dss'
			data['FAULTED_LINES'] = ['670671']
		print(f'---------------------------------------------------------\nBeginning end-to-end backend test of {model_name}.\n---------------------------------------------------------')
        # - These tests don't run in GitHub, so it's okay to take longer and actually run REopt
		main(data, invalidate_cache=True)
		if untested.count(model_name) == 0 and os.path.isfile(f'{PROJ_DIR}/{model_name}/0crashed.txt'):
			failed_tests.append(model_name)
		else:
			successful_tests.append(model_name)
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