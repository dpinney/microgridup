from omf.solvers import opendss
from omf.solvers.opendss import dssConvert
from omf import distNetViz
from omf import geo
import omf.models
import shutil
import os
from pprint import pprint as pp
import json
import pandas as pd
import plotly

# File paths.
DSS_NAME = 'lehigh.dss'
OMD_NAME = 'lehigh.dss.omd'
ONELINE_NAME = 'lehigh.oneline.html'
MAP_NAME = 'lehigh_map'

# Microgrid definitions.
microgrids = {
	'm1': {
		'loads': ['634a','634b','634c'],
		'switch': '632633',
		'gen_bus': '634'
	},
	'm2': {
		'loads': ['675a','675b','675c'],
		'switch': '671692',
		'gen_bus': '675'
	},
	'm3': {
		'loads': ['611','652'],
		'switch': '671684',
		'gen_bus': '684'
	},
	'm4': {
		'loads': ['645','646'],
		'switch': '632645',
		'gen_bus': '646'
	}
}

# Generate an OMD.
if not os.path.isfile(OMD_NAME):
	tree = dssConvert.dssToTree(DSS_NAME)
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

# Insert loadshapes.
# tree = dssConvert.dssToTree(DSS_NAME)
# for ob in tree:
# 	if ob.get('object','') == 'loadshape.solarramp':
# 		ob['mult'] = '[1,2,3]'
# pp([dict(x) for x in tree])
# dssConvert.treeToDss(tree, 'lehigh_shapes.dss'):

# Generate the microgrid specs with REOpt here and insert into OpenDSS.
# reopt_folder = './lehigh_reopt'
# shutil.rmtree(reopt_folder, ignore_errors=True)
# omf.models.microgridDesign.new(reopt_folder)
#TODO: insert modification of allInputData.json here.
# omf.models.__neoMetaModel__.runForeground(reopt_folder)
#TODO: insert reopt gen details into dss model.

# Powerflow outputs.
opendss.newQstsPlot(DSS_NAME, stepSizeInMinutes=60, numberOfSteps=24*10, keepAllFiles=False)
# opendss.qstsPlot(DSS_NAME, stepSizeInMinutes=60, numberOfSteps=100, getVolts=True, getLoads=True, getGens=True)
# opendss.voltagePlot(DSS_NAME, PU=True)
# opendss.currentPlot(DSS_NAME)

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

'''
get a battery loadshape (schedule)...
translate coordinates to florida?
	Could just move the x,y coords
	Could convert in geo.py
	LatLongCoords might be helpful?
'''