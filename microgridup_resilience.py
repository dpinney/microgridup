from omf.solvers import opendss
from omf.solvers.opendss import dssConvert
import random
from random import randint
from numpy.random import exponential
from datetime import datetime as dt
from datetime import timedelta as td
from omf.models.outageCost import stats
import csv
import pandas as pd
import plotly.graph_objects as go
import os
from omf.models.microgridControl import customerCost1, utilityOutageTable

OUTAGE_CSV_COLS = ['ComponentAff', 'Start', 'Finish', 'Duration_min', 'Meters Affected']
CRIT_OUT_LEN_MINUTES = 10*24*60 #TODO: use outage len
#TODO: what if the fault is inside the microgrid!?

def __test_getting_affloads(affected_obj='692675', test_file='lehigh_base_phased.dss'):
	''' Test getting loads affected by an outage on a TREE. '''
	tree = dssConvert.dssToTree(test_file)
	sub_obs = opendss.get_subtree_obs(affected_obj, tree)
	print('SUB_OBS', len(sub_obs), sub_obs)
	sub_loads = [x['object'][5:] for x in sub_obs if x.get('object','').startswith('load.')]
	print('SUBLOAD_NAMES', len(sub_loads), sub_loads)

def _write_csv(filename, fields, rows):
	''' Helper function to write a CSV. '''
	with open(filename, 'w') as csvfile:
		csvwriter = csv.writer(csvfile)
		csvwriter.writerow(fields)
		csvwriter.writerows(rows)

def _random_outage(tree):
	''' Generate single random outage on a tree, return affected loads. '''
	all_line_names = [x.get('object')[5:] for x in tree if x.get('object','').startswith('line.')]
	# for lehigh: all_line_names = ['670671','645646','692675','684611','684652','671692','632633','671684','632645','632670','650632','671680']
	out_line = random.choice(all_line_names)
	duration = exponential(scale=100)
	start_date = f'{randint(2015, 2021)}-{randint(1,12)}-{randint(1,28)} {randint(0,23)}:{randint(0,59)}:{randint(0,59)}'
	start_date_dt = dt.strptime(start_date, '%Y-%m-%d %H:%M:%S')
	end_date_dt = start_date_dt + td(minutes=duration)
	end_date = dt.strftime(end_date_dt, '%Y-%-m-%-d %-H:%M:%S') # yuck! stftime and strptime have different format string syntaxes
	obs_affected = opendss.get_subtree_obs(out_line, tree)
	loads_affected = [x['object'][5:] for x in obs_affected if x.get('object','').startswith('load.')]
	return [out_line, start_date, end_date, duration, ' '.join(loads_affected)]

def _many_random_outages(count, out_filename, in_dss):
	''' Create <count> outages for the Lehigh circuit. '''
	tree = dssConvert.dssToTree(in_dss)
	print(tree)
	rows = []
	for x in range(count):
		rows.append(_random_outage(tree))
	_write_csv(out_filename, OUTAGE_CSV_COLS, rows)

def gen_supported_csv(in_path, out_path, mg_supported_loads, tree):
	''' Generate a modified outage list factoring out outages that would have been averted by microgrids. '''
	out_df = pd.read_csv(in_path)
	rows = out_df.values.tolist()
	# print(raw_data)
	for row in rows:
		sub_obs = opendss.get_subtree_obs(row[0], tree)
		sub_loads = [x['object'][5:] for x in sub_obs if x.get('object','').startswith('load.')]
		not_supported = [x for x in sub_loads if x not in mg_supported_loads]
		# print(f'orig {len(sub_loads)} not supp {len(not_supported)} specifically {not_supported}')
		row[4] = ' '.join(not_supported)
	# print(rows)
	_write_csv(out_path, OUTAGE_CSV_COLS, rows)

def main(in_csv, out_csv, mg_supported_loads, in_dss, out_html):
	''' Output for resilience before/after microgrid deployment. '''
	# Generate resilience statistics SAIDI/SAIFI/etc.
	tree = dssConvert.dssToTree(in_dss)
	load_count = len([x for x in tree if x.get('object','').startswith('load.')])
	print('LOAD COUNT', load_count)
	gen_supported_csv(in_csv, out_csv, mg_supported_loads, tree)
	raw_df = pd.read_csv(in_csv)
	new_df = pd.read_csv(out_csv)
	out_stats_raw = stats(raw_df, '200', str(load_count)) #interuption of less than '200' seconds considered momentary.
	out_stats_new = stats(new_df, '200', str(load_count))
	stats_labels = ['SAIDI','SAIFI','CAIDI','ASAI','MAIFI']
	legend_spec = {'orientation':'h', 'xanchor':'left'}#, 'x':0, 'y':-0.2}
	stats_fig = go.Figure(
		data=[
			go.Bar(
				name = 'Without Microgrid',
				x=stats_labels,
				y=[round(x,3) for x in out_stats_raw],
			), go.Bar(
				name='Microgrid',
				x=stats_labels,
				y=[round(x,3) for x in out_stats_new],
			)
		]
	)
	stats_fig.update_layout(
		title = 'Original and Adjusted Resilience Metrics',
		legend = legend_spec
	)
	# Generate outage table
	df_init = pd.read_csv(in_csv) 
	df_with_mg = pd.read_csv(out_csv)
	df_with_mg = df_with_mg.rename(columns={
		'Duration_min':'Microgrid Duration_min',
		'Meters Affected':'Microgrid Meters Affected'
	}).drop(['ComponentAff', 'Start', 'Finish'], 1)
	df_full = pd.concat([df_init, df_with_mg], axis=1)
	df_full['Date'] = pd.to_datetime(df_full['Start']).dt.date
	print(df_full.head())
	df_full['Meter Count'] = [0 if str(x).lower() == "nan" else len(str(x).split()) for x in df_full['Meters Affected']]
	df_full['Microgrid Meter Count'] = [0 if str(x).lower() == "nan" else len(str(x).split()) for x in df_full['Microgrid Meters Affected']]
	df_full['Customer Outage Minutes'] = [x[0]*x[1] for x in zip(df_full['Meter Count'],df_full['Duration_min'])]
	df_full['Microgrid Customer Outage Minutes'] = [x[0]*x[1] for x in zip(df_full['Microgrid Meter Count'],df_full['Microgrid Duration_min'])]
	table_html = '<h1>Full Outage History and Microgrid Adjustments</h1>' + df_full.to_html()
	# Generate 
	fig = go.Figure(
		data=[
			go.Bar(
				name = 'Customer Outage Minutes',
				x=[str(x)[0:7] for x in df_full['Date']], # aggregate to the month level.
				y=[float(x) for x in df_full['Customer Outage Minutes']],
			), go.Bar(
				name='Microgrid Customer Outage Minutes',
				x=[str(x)[0:7] for x in df_full['Date']], # aggregate to the month level.
				y=[float(x) for x in df_full['Microgrid Customer Outage Minutes']],
			)
		]
	)
	fig.update_layout(
		title = 'Outage Timeline, Original and Microgrid',
		legend = legend_spec
	)
	chart_html = fig.to_html(default_height='600px')
	stats_chart_html = stats_fig.to_html(default_height='300px')
	style_string = '<head><style>* {font-family:sans-serif}; .dataframe {width:100%; border-collapse:collapse; overflow-x:scroll}</style></head>'
	# TODO: fix table styling, transition to jinja2 template.
	with open(out_html,'w') as outFile:
		outFile.write(style_string + '\n' + stats_chart_html + '\n' + chart_html + '\n' + table_html)

def customer_outage_cost(csv_path):
	rows = [x.split(',') for x in open(csv_path).readlines()]
	header = rows[0]
	values = rows[1:]
	# print(header, values)
	for in_row in values:
		payload = in_row[1:5]
		print(in_row[0], payload)
		out = customerCost1(*payload)
		print(out)

def utility_outage_cost_TEST():
	# utilityOutageTable(average_lost_kwh, profit_on_energy_sales, restoration_cost, hardware_cost, outageDuration, output_dir)
	utilcost = utilityOutageTable([1000,1000,1000], 0.02, 5000, 9000, 5, None) #None = tempfile output.
	print(utilcost)

def _tests():
	_many_random_outages(100, './testfiles/lehigh_random_outages999.csv', './testfiles/lehigh_base_phased.dss')
	utility_outage_cost_TEST()
	# customer_outage_cost(f'{omf.omfDir}/static/testFiles/customerInfo.csv')
	main('./testfiles/lehigh_random_outages.csv', './testfiles/lehigh_random_outages_ADJUSTED.csv', ['634a_data_center','634b_radar','634c_atc_tower','675a_hospital','675b_residential1','675c_residential1','692_warehouse2'], './testfiles/lehigh_base_phased.dss', 'zoutput.html')
	os.system('open zoutput.html')

if __name__ == '__main__':
	_tests()