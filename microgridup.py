from omf.solvers import opendss
from omf.solvers.opendss import dssConvert
from omf import distNetViz
from omf import geo
import microgridup_control
import microgridup_resilience
import microgridup_design
import microgridup_hosting_cap
import shutil
import os
import json
import pandas as pd
import plotly
import plotly.graph_objects as go
import csv
import jinja2 as j2
import datetime
import traceback

MGU_FOLDER = os.path.abspath(os.path.dirname(__file__))
if MGU_FOLDER == '/':
	MGU_FOLDER = '' #workaround for docker root installs
PROJ_FOLDER = f'{MGU_FOLDER}/data/projects'

def _getByName(tree, name):
    ''' Return first object with name in tree as an OrderedDict. '''
    matches =[]
    for x in tree:
        if x.get('object',''):
            if x.get('object','').split('.')[1] == name:
                matches.append(x)
    return matches[0]

def _walkTree(dirName):
	listOfFiles = []
	for (dirpath, _, filenames) in os.walk(dirName):
		listOfFiles += [os.path.join(dirpath, file) for file in filenames]
	return listOfFiles

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
		yaxis = {'ticksuffix': " kW"}
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
		yaxis = {'ticksuffix': " kW/kWh"}
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
		yaxis = {'tickprefix': "$"}
	)
	money_summary_html = money_summary_fig.to_html(default_height=chart_height)
	all_html = money_summary_html + gen_load_html + gen_mix_html
	return all_html

def main(BASE_NAME, LOAD_NAME, REOPT_INPUTS, microgrid, playground_microgrids, GEN_NAME, REF_NAME, FULL_NAME, OMD_NAME, ONELINE_NAME, MAP_NAME, REOPT_FOLDER_FINAL, BIG_OUT_NAME, QSTS_STEPS, FAULTED_LINE, mg_name, ADD_COST_NAME, FOSSIL_BACKUP_PERCENT, DIESEL_SAFETY_FACTOR = False, final_run=False):
	''' Add a single microgrid to a microgrid plan. '''
	max_crit_load = microgridup_design.run(LOAD_NAME, microgrid, mg_name, BASE_NAME, REOPT_INPUTS, REOPT_FOLDER_FINAL, FOSSIL_BACKUP_PERCENT)
	mg_list_of_dicts_full = microgridup_hosting_cap.run(REOPT_FOLDER_FINAL, GEN_NAME, microgrid, BASE_NAME, mg_name, REF_NAME, LOAD_NAME, FULL_NAME, ADD_COST_NAME, max_crit_load, diesel_total_calc=False)
	# Generate a nice microgrid design output.
	microgridup_design.microgrid_design_output(REOPT_FOLDER_FINAL + '/allOutputData.json', REOPT_FOLDER_FINAL + '/allInputData.json', REOPT_FOLDER_FINAL + '/cleanMicrogridDesign.html')
	if final_run:
		# Make OMD.
		dssConvert.dssToOmd(FULL_NAME, OMD_NAME, RADIUS=0.0002)
		# Draw the circuit oneline.
		distNetViz.viz(OMD_NAME, forceLayout=False, outputPath='.', outputName=ONELINE_NAME, open_file=False)
		# Draw the map.
		# geo.mapOmd(OMD_NAME, MAP_NAME, 'html', openBrowser=False, conversion=False)
		geo.map_omd(OMD_NAME, MAP_NAME, open_browser=False)
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
		#HACK: If only analyzing a set of generators with a single phase, remove ['P2(kW)','P3(kW)'] of make_chart('timeseries_gen.csv',...) below
		make_chart('timeseries_gen.csv', FULL_NAME, 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], REOPT_INPUTS['year'], QSTS_STEPS, "Generator Output", "Average hourly kW")
		# for timeseries_load, output ANSI Range A service bands (2,520V - 2,340V for 2.4kV and 291V - 263V for 0.277kV)
		make_chart('timeseries_load.csv', FULL_NAME, 'Name', 'hour', ['V1(PU)','V2(PU)','V3(PU)'], REOPT_INPUTS['year'], QSTS_STEPS, "Load Voltage", "PU", ansi_bands = True)
		make_chart('timeseries_source.csv', FULL_NAME, 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], REOPT_INPUTS['year'], QSTS_STEPS, "Voltage Source Output", "Average hourly kW")
		try:
			make_chart('timeseries_control.csv', FULL_NAME, 'Name', 'hour', ['Tap(pu)'], REOPT_INPUTS['year'], QSTS_STEPS, "Tap Position", "PU")
		except:
			pass #TODO: better detection of missing control data.
		# Perform control sim.
		microgridup_control.play(FULL_NAME, os.getcwd(), playground_microgrids, FAULTED_LINE)
		# convert mg_list_of_dicts_full to dict of lists for columnar output in output_template.html
		mg_dict_of_lists_full = {key: [dic[key] for dic in mg_list_of_dicts_full] for key in mg_list_of_dicts_full[0]}
		# Create consolidated report per mg.
		mg_add_cost_dict_of_lists = pd.read_csv(ADD_COST_NAME).to_dict(orient='list')

def full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, FOSSIL_BACKUP_PERCENT, REOPT_INPUTS, MICROGRIDS, FAULTED_LINE, CRITICAL_LOADS=None, DIESEL_SAFETY_FACTOR=False, DELETE_FILES=False, open_results=False, OUTAGE_CSV=None):
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
	try:
		shutil.copyfile(BASE_DSS, f'{MODEL_DIR}/{MODEL_DSS}')
		shutil.copyfile(LOAD_CSV, f'{MODEL_DIR}/{MODEL_LOAD_CSV}')
		if OUTAGE_CSV:
			shutil.copyfile(OUTAGE_CSV, f'{MODEL_DIR}/outages.csv')
		os.system(f'touch {MODEL_DIR}/0running.txt')
		try:
			os.remove("0crashed.txt")
		except:
			pass
	except:
		print('Rerunning existing project. DSS and CSV files not moved.')
	if DELETE_FILES:
		for fname in [BASE_DSS, LOAD_CSV]:
			try:
				os.remove(fname)
			except:
				print(f'failed to delete {fname}')
	# HACK: work in directory because we're very picky about the current dir.
	curr_dir = os.getcwd()
	workDir = os.path.abspath(MODEL_DIR)
	if curr_dir != workDir:
		os.chdir(workDir)
	if os.path.exists("user_warnings.txt"):
		os.remove("user_warnings.txt")
	CREATION_DATE_unformatted = datetime.datetime.now()
	CREATION_DATE = CREATION_DATE_unformatted.strftime('%Y-%m-%d %H:%M:%S')
	# Dump the inputs for future reference.
	try:
		with open('allInputData.json','w') as inputs_file:
			inputs = {
				'MODEL_DIR':MODEL_DIR,
				'BASE_DSS':BASE_DSS,
				'LOAD_CSV':LOAD_CSV,
				'QSTS_STEPS':QSTS_STEPS,
				'FOSSIL_BACKUP_PERCENT':FOSSIL_BACKUP_PERCENT,
				'REOPT_INPUTS':REOPT_INPUTS,
				'MICROGRIDS':MICROGRIDS,
				'FAULTED_LINE':FAULTED_LINE,
				'DIESEL_SAFETY_FACTOR':DIESEL_SAFETY_FACTOR,
				'OUTAGE_CSV':OUTAGE_CSV,
				'CRITICAL_LOADS':CRITICAL_LOADS,
				'CREATION_DATE':CREATION_DATE
			}
			json.dump(inputs, inputs_file, indent=4)
		# Run the project.
		mgs_name_sorted = sorted(MICROGRIDS.keys())
		for i, mg_name in enumerate(mgs_name_sorted):
			BASE_DSS = MODEL_DSS if i==0 else f'circuit_plusmg_{i-1}.dss'
			new_mg_names = mgs_name_sorted[0:i+1]
			new_mg_for_control = {name:MICROGRIDS[name] for name in new_mg_names}
			final_run = True if i == len(mgs_name_sorted) - 1 else False
			main(BASE_DSS, MODEL_LOAD_CSV, REOPT_INPUTS, MICROGRIDS[mg_name], new_mg_for_control, GEN_NAME, REF_NAME, f'circuit_plusmg_{i}.dss', OMD_NAME, ONELINE_NAME, MAP_NAME, f'reopt_final_{i}', f'output_full_{i}.html', QSTS_STEPS, FAULTED_LINE, mg_name, f'mg_add_cost_{i}.csv', FOSSIL_BACKUP_PERCENT, DIESEL_SAFETY_FACTOR, final_run=final_run)
		# Resilience simulation with outages. Optional. Skipped if no OUTAGE_CSV
		if OUTAGE_CSV:
			all_microgrid_loads = [x.get('loads',[]) for x in MICROGRIDS.values()]
			all_loads = [item for sublist in all_microgrid_loads for item in sublist]
			mg_count = len(MICROGRIDS.keys())
			microgridup_resilience.main('outages.csv', 'outages_ADJUSTED.csv', all_loads, f'circuit_plusmg_{mg_count-1}.dss', 'output_resilience.html')
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
		# over_template = j2.Template(open(f'{MGU_FOLDER}/template_overview.html').read())
		over = over_template.render(
			chart_html=chart_html,
			summary=stats,
			add_cost_rows = add_cost_rows,
			warnings = warnings,
			now=current_time,
			inputs=inputs, #TODO: Make the inputs clearer and maybe at the bottom, showing only the appropriate keys from MICROGRIDS as necessary
		)
		with open('overview.html', 'w') as overfile:
			overfile.write(over)
		# Write full output
		with open(f'{MGU_FOLDER}/templates/template_output.html') as file:
			template = j2.Template(file.read())
		# template = j2.Template(open(f'{MGU_FOLDER}/template_output.html').read())
		out = template.render(
			raw_files = _walkTree('.'),
			model_name =  os.path.basename(MODEL_DIR), # just the filename here please.
			mg_names_and_reopt_folders = names_and_folders,
			resilience_show = (OUTAGE_CSV is not None)
		)
		with open(FINAL_REPORT,'w') as outFile:
			outFile.write(out)
		if open_results:
			os.system(f'open {FINAL_REPORT}')
	except Exception:
		print(traceback.format_exc())
		os.system(f'touch "{MODEL_DIR}/0crashed.txt"')
	finally:
		os.chdir(curr_dir)
		os.system(f'rm "{workDir}/0running.txt"')

def _tests():
	with open('testfiles/test_params.json') as file:
		test_params = json.load(file)
	MG_MINES = test_params['MG_MINES']
	REOPT_INPUTS = test_params['REOPT_INPUTS']
	QSTS_STEPS = 480.0
	FOSSIL_BACKUP_PERCENT = 0.5
	FAULTED_LINE = '670671'
	CRITICAL_LOADS = test_params['crit_loads']
	# Test of full().
	for _dir in MG_MINES:
		mgu_args = [f'{PROJ_FOLDER}/{_dir}', f'{MGU_FOLDER}/uploads/BASE_DSS_{_dir}', f'{MGU_FOLDER}/uploads/LOAD_CSV_{_dir}', QSTS_STEPS, FOSSIL_BACKUP_PERCENT, REOPT_INPUTS, MG_MINES[_dir][0], FAULTED_LINE, CRITICAL_LOADS]
		print(f'---------------------------------------------------------\nBeginning end-to-end backend test of {_dir}.\n---------------------------------------------------------')
		full(*mgu_args)
	return print('Ran all tests for microgridup.py.')

if __name__ == '__main__':
	_tests()