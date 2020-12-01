from omf.solvers import opendss
from omf.solvers.opendss import dssConvert
from omf import distNetViz
from omf import geo
import shutil
import os
from pprint import pprint as pp
import json
import pandas as pd
import plotly

# Input paths.
BASE_NAME = 'lehigh_base.dss'
LOAD_NAME = 'lehigh_load.csv'
GEN_NAME = 'lehigh_gen.csv'
# Output paths.
FULL_NAME = 'lehigh_full.dss'
OMD_NAME = 'lehigh.dss.omd'
ONELINE_NAME = 'lehigh.oneline.html'
MAP_NAME = 'lehigh_map'

# Microgrid definitions.
microgrids = {
	'm1': {
		'loads': ['634a_supermarket','634b_supermarket','634c_supermarket'],
		'switch': '632633',
		'gen_bus': '634'
	},
	'm2': {
		'loads': ['675a_residential1','675b_residential1','675c_residential1'],
		'switch': '671692',
		'gen_bus': '675'
	},
	'm3': {
		'loads': ['671_hospital','652_med_apartment'],
		'switch': '671684',
		'gen_bus': '684'
	},
	'm4': {
		'loads': ['645_warehouse1','646_med_office'],
		'switch': '632645',
		'gen_bus': '646'
	}
}

# Generate an OMD.
if not os.path.isfile(OMD_NAME):
	tree = dssConvert.dssToTree(BASE_NAME)
	evil_glm = dssConvert.evilDssTreeToGldTree(tree)
	add_coords = json.load(open('additional_coords.json'))
	# Injecting additional coordinates.
	for ob in evil_glm.values():
		ob_name = ob.get('name','')
		ob_type = ob.get('object','')
		for ob2 in add_coords:
			ob2_name = ob2.get('name','')
			ob2_type = ob2.get('object','')
			if ob_name == ob2_name and ob_type == ob2_type:
				ob['latitude'] = ob2.get('latitude',0)
				ob['longitude'] = ob2.get('longitude',0)
	dssConvert.evilToOmd(evil_glm, OMD_NAME)

# Draw the circuit online.
if not os.path.isfile(ONELINE_NAME):
	distNetViz.viz(OMD_NAME, forceLayout=False, outputPath='.', outputName=ONELINE_NAME, open_file=False)

# Draw the map.
if not os.path.isdir(MAP_NAME):
	geo.mapOmd(OMD_NAME, MAP_NAME, 'html', openBrowser=False, conversion=False, offline=True)

# Insert loadshapes and generator duties.
tree = dssConvert.dssToTree(BASE_NAME)
load_df = pd.read_csv(LOAD_NAME)
gen_df = pd.read_csv(GEN_NAME)
insert_list = {}
for i, ob in enumerate(tree):
	ob_string = ob.get('object','')
	if ob_string.startswith('load.'):
		ob_name = ob_string[5:]
		shape_data = load_df[ob_name]
		shape_name = ob_name + '_shape'
		ob['yearly'] = shape_name
		insert_list[i] = {
			'!CMD': 'new',
			'object': f'loadshape.{shape_name}',
			'npts': f'{len(shape_data)}',
			'interval': '1',
			'useactual': 'yes', #todo: move back to [0,1] shapes?
			'mult': f'{list(shape_data)}'.replace(' ','')
		}
	elif ob_string.startswith('generator.') or ob_string.startswith('battery.'):
		ob_name = ob_string[10:]
		shape_data = gen_df[ob_name]
		shape_name = ob_name + '_shape'
		ob['yearly'] = shape_name
		insert_list[i] = {
			'!CMD': 'new',
			'object': f'loadshape.{shape_name}',
			'npts': f'{len(shape_data)}',
			'interval': '1',
			'useactual': 'no',
			'mult': f'{list(shape_data)}'.replace(' ','')
		}
# Do load insertions at proper places
min_pos = min(insert_list.keys())
for key in insert_list:
	tree.insert(min_pos, insert_list[key])
dssConvert.treeToDss(tree, FULL_NAME)

# Generate the microgrid specs with REOpt here and insert into OpenDSS.
reopt_folder = './lehigh_reopt'
if not os.path.isdir(reopt_folder):
	import omf.models
	shutil.rmtree(reopt_folder, ignore_errors=True)
	omf.models.microgridDesign.new(reopt_folder)
	# Get the microgrid total loads
	mg_load_df = pd.DataFrame()
	for key in microgrids:
		loads = microgrids[key]['loads']
		mg_load_df[key] = [0 for x in range(8760)]
		for load_name in loads:
			mg_load_df[key] = mg_load_df[key] + load_df[load_name]
	mg_load_df.to_csv(reopt_folder + '/loadShape.csv', header=False, index=False)
	# Modify inputs.
	allInputData = json.load(open(reopt_folder + '/allInputData.json'))
	allInputData['loadShape'] = open(reopt_folder + '/loadShape.csv').read()
	allInputData['fileName'] = 'loadShape.csv'
	allInputData['latitude'] = '30.285013'
	allInputData['longitude'] = '-84.071493'
	allInputData['year'] = '2017'
	with open(reopt_folder + '/allInputData.json','w') as outfile:
		json.dump(allInputData, outfile, indent=4)
	omf.models.__neoMetaModel__.runForeground(reopt_folder)
	omf.models.__neoMetaModel__.renderTemplateToFile(reopt_folder)
#TODO: insert reopt gen details into dss model.

# Powerflow outputs.
# opendss.newQstsPlot(FULL_NAME, stepSizeInMinutes=60, numberOfSteps=24*10, keepAllFiles=False, actions={24*5:'open object=line.671692 term=1'})
# opendss.voltagePlot(FULL_NAME, PU=True)
# opendss.currentPlot(FULL_NAME)

# Charting outputs.
def make_chart(csvName, category_name, x, y):
	gen_data = pd.read_csv(csvName)
	data = []
	for ob_name in set(gen_data[category_name]):
		this_series = gen_data[gen_data[category_name] == ob_name]
		trace = plotly.graph_objs.Scatter(
			x = this_series[x],
			y = this_series[y],
			name = ob_name
		)
		data.append(trace)
	layout = plotly.graph_objs.Layout(
		title = f'{csvName} Output',
		xaxis = dict(title = x),
		yaxis = dict(title = y)
	)
	fig = plotly.graph_objs.Figure(data, layout)
	plotly.offline.plot(fig, filename=f'{csvName}.plot.html')
# make_chart('timeseries_gen.csv', 'Name', 'hour', 'P1(kW)')
# make_chart('timeseries_load.csv', 'Name', 'hour', 'V1')
# make_chart('timeseries_source.csv', 'Name', 'hour', 'P1(kW)')
# make_chart('timeseries_control.csv', 'Name', 'hour', 'Tap(pu)')