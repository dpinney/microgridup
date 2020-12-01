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

# Input data.
BASE_NAME = 'lehigh_base.dss'
LOAD_NAME = 'lehigh_load.csv'
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
# Output paths.
GEN_NAME = 'lehigh_gen.csv'
FULL_NAME = 'lehigh_full.dss'
OMD_NAME = 'lehigh.dss.omd'
ONELINE_NAME = 'lehigh.oneline.html'
MAP_NAME = 'lehigh_map'

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

# Get generator objects and shapes from REOpt.
reopt_out = json.load(open(reopt_folder + '/allOutputData.json'))
gen_df_builder = pd.DataFrame()
gen_obs = []
for i, mg_ob in enumerate(microgrids.values()):
	mg_num = i + 1
	gen_bus_name = mg_ob['gen_bus']
	solar_size = reopt_out.get(f'sizePV{mg_num}', 0.0)
	wind_size = reopt_out.get(f'sizeWind{mg_num}', 0.0)
	diesel_size = reopt_out.get(f'sizeDiesel{mg_num}', 0.0) #TODO: fix, it's not in the model outputs.
	battery_cap = reopt_out.get(f'capacityBattery{mg_num}', 0.0)
	battery_pow = reopt_out.get(f'powerBattery{mg_num}', 0.0)
	if solar_size > 0:
		gen_obs.append(f'new object=generator.solar_{gen_bus_name} bus1={gen_bus_name}.1.2.3 kv=4.16 kw={solar_size} pf=1')
		gen_df_builder[f'solar_{gen_bus_name}'] = reopt_out.get(f'powerPV{mg_num}')
	if wind_size > 0:
		gen_obs.append(f'new object=generator.wind_{gen_bus_name} bus1={gen_bus_name}.1.2.3 kv=4.16 kw={wind_size} pf=1')
		gen_df_builder[f'wind_{gen_bus_name}'] = reopt_out.get(f'windData{mg_num}')
	if diesel_size > 0:
		gen_obs.append(f'new object=generator.diesel_{gen_bus_name} bus1={gen_bus_name}.1.2.3 kw={diesel_size} pf=1 kv=4.16 xdp=0.27 xdpp=0.2 h=2 conn=delta')
		gen_df_builder[f'diesel_{gen_bus_name}'] = reopt_out.get(f'powerDiesel{mg_num}') #TODO: fix, it's not in the model outputs.
	if battery_cap > 0:
		gen_obs.append(f'new object=storage.battery_{gen_bus_name} phases=3 bus1={gen_bus_name}.1.2.3 kv=4.16 kwhstored={battery_cap} kwhrated={battery_cap} kva={battery_pow} kvar={battery_pow} %charge=100 %discharge=100 %effcharge=100 %effdischarge=100 %idlingkw=1 %r=0 %x=50')
		gen_df_builder[f'battery_{gen_bus_name}'] = reopt_out.get(f'powerBatteryToLoad{mg_num}') #TODO: does this capture all battery behavior?
for col in gen_df_builder.columns:
	gen_df_builder[col] = gen_df_builder[col] / gen_df_builder[col].max()
print('Generation obs to add', gen_obs)
print('Generation shapes', gen_df_builder)
# gen_df_builder.to_csv(GEN_NAME, index=False) #TODO: re-enable once microgridDesign is fixed.

# Gather loadshapes and generator duties.
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

# Do shape insertions at proper places
min_pos = min(insert_list.keys())
for key in insert_list:
	tree.insert(min_pos, insert_list[key])
for ob in gen_obs:
	pass #TODO: insert objects.
dssConvert.treeToDss(tree, FULL_NAME)

# Powerflow outputs.
opendss.newQstsPlot(FULL_NAME, stepSizeInMinutes=60, numberOfSteps=24*10, keepAllFiles=False, actions={24*5:'open object=line.671692 term=1'})
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
make_chart('timeseries_gen.csv', 'Name', 'hour', 'P1(kW)')
make_chart('timeseries_load.csv', 'Name', 'hour', 'V1')
make_chart('timeseries_source.csv', 'Name', 'hour', 'P1(kW)')
make_chart('timeseries_control.csv', 'Name', 'hour', 'Tap(pu)')