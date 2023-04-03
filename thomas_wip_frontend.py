import multiprocessing
import os
import shutil
import platform
from pprint import pprint as pp
import time
import networkx as nx
import microgridup
from matplotlib import pyplot as plt
import base64
import io 
import json
from flask import Flask, flash, request, redirect, render_template, jsonify, url_for
from werkzeug.utils import secure_filename
from omf.solvers.opendss import dssConvert
from microgridup_gen_mgs import mg_group, nx_group_branch, nx_group_lukes, nx_bottom_up_branch, nx_critical_load_branch

_myDir = os.path.abspath(os.path.dirname(__file__))

ALLOWED_EXTENSIONS = {'dss'}

app = Flask(__name__, static_folder='', template_folder='') #TODO: we cannot make these folders the root.

def list_analyses():
	return [x for x in os.listdir(_myDir) if os.path.isdir(x) and os.path.isfile(f'{x}/circuit.dss')] #TODO: fix this gross hack.

@app.route('/')
def home():
	analyses = list_analyses()
	return render_template('template_home.html', analyses=analyses)

@app.route('/load/<analysis>')
def load(analysis):
	ana_files = os.listdir(analysis)
	if '0crashed.txt' in ana_files:
		return 'Model Crashed. Please delete and recreate.'
	elif '0running.txt' in ana_files:
		return 'Model Running. Please reload to check for completion.'
	elif 'output_final.html' in ana_files:
		return redirect(f'/{analysis}/output_final.html')
	else:
		return 'Model is in an inconsistent state. Please delete and recreate.'

@app.route('/edit/<analysis>')
def edit(analysis):
	try:
		with open(f'{_myDir}/{analysis}/allInputData.json') as in_data_file:
			in_data = json.load(in_data_file)
	except:
		in_data = None
	return render_template('thomas_wip_frontend.html', in_data=in_data)

@app.route('/new')
def newGui():
	with open(f'{_myDir}/lehigh_3mg_inputs.json') as default_in_file:
		default_in = json.load(default_in_file)
	return render_template('thomas_wip_frontend.html', in_data=default_in)

@app.route('/duplicate', methods=["POST"])
def duplicate():
	analysis = request.json.get('analysis', None)
	new_name = request.json.get('new_name', None)
	analyses = list_analyses()
	if (analysis not in analyses) or (new_name in analyses):
		return 'Duplication failed. Analysis does not exist or the new name is invalid.'
	else:
		shutil.copytree(analysis, new_name)
		return f'Successfully duplicated {analysis} as {new_name}.'

@app.route('/jsonToDss', methods=['GET','POST'])
def jsonToDss():
	model_dir = request.form['MODEL_DIR']
	# model_dir = '3mgs_used_wizard'
	# elements = [{'class': 'substation', 'text': 'sub'}, {'class': 'feeder', 'text': 'regNone'}, {'class': 'load', 'text': '684_command_center'}, {'class': 'load', 'text': '692_warehouse2'}, {'class': 'load', 'text': '611_runway'}, {'class': 'load', 'text': '652_residential'}, {'class': 'load', 'text': '670a_residential2'}, {'class': 'load', 'text': '670b_residential2'}, {'class': 'load', 'text': '670c_residential2'}, {'class': 'feeder', 'text': 'reg0'}, {'class': 'load', 'text': '634a_data_center'}, {'class': 'load', 'text': '634b_radar'}, {'class': 'load', 'text': '634c_atc_tower'}, {'class': 'solar', 'text': 'solar_634_existing'}, {'class': 'battery', 'text': 'battery_634_existing'}, {'class': 'feeder', 'text': 'reg1'}, {'class': 'load', 'text': '675a_hospital'}, {'class': 'load', 'text': '675b_residential1'}, {'class': 'load', 'text': '675c_residential1'}, {'class': 'diesel', 'text': 'fossil_675_existing'}, {'class': 'feeder', 'text': 'reg2'}, {'class': 'load', 'text': '645_hangar'}, {'class': 'load', 'text': '646_office'}]
	lat = float(request.form['latitude'])
	# lat = 39.7817
	lon = float(request.form['longitude'])
	# lon = -89.6501
	print('lat',lat)
	print('lon',lon)

	# Convert to DSS and return loads.
	elements = json.loads(request.form['json'])
	print('elements',elements)
	dssString = f'clear \nset defaultbasefrequency=60 \nnew object=circuit.{model_dir} \n'
	# Name substation bus after substation itself. Name gen bus after the feeder. Having parent/child connections could be a useful shortcut + add robustness.
	lastSub, lastFeeder = None, None
	busList = []
	for ob in elements:
		obType = ob['class']
		obName = ob['text']
		if obType == 'substation':
			lastSub = obName.replace(' ','')
			dssString += f'new object=vsource.{lastSub} basekv=115 bus1={lastSub}_bus.1.2.3 pu=1.00 r1=0 x1=0.0001 r0=0 x0=0.0001 \n'
			busList.append(f'{lastSub}_bus')
		elif obType == 'feeder':
			# Add a feeder, a gen_bus, and a capacitor.
			lastFeeder = obName.replace(' ','')
			dssString += f'new object=line.{lastFeeder} phases=3 bus1={lastSub}_bus.1.2.3 bus2={lastFeeder}_end.1.2.3 length=1333 units=ft \nnew object=capacitor.{lastFeeder} bus1={lastFeeder}_end.1.2.3 phases=3 kvar=600 kv=2.4 \n'
			busList.append(f'{lastFeeder}_end')
		elif obType == 'load':
			dssString += f'new object=load.{obName.replace(" ","")} bus1={lastFeeder}_end.1 phases=1 conn=wye model=1 kv=2.4 kw=1155 kvar=660 \n'
		elif obType == 'solar':
			dssString += f'new object=generator.{obName.replace(" ","")} bus1={lastFeeder}_end.1 phases=1 kv=0.277 kw=440 pf=1 \n'
		elif obType == 'wind':
			dssString += f'new object=generator.{obName.replace(" ","")} bus1={lastFeeder}_end.1 phases=1 kv=0.277 kw=200 pf=1 \n'
		elif obType == 'battery':
			dssString += f'new object=storage.{obName.replace(" ","")} bus1={lastFeeder}_end.1 phases=1 kv=0.277 kwrated=79 kwhstored=307 kwhrated=307 dispmode=follow %charge=100 %discharge=100 %effcharge=96 %effdischarge=96 %idlingkw=0 \n'
		elif obType == 'diesel':
			dssString += f'new object=generator.{obName.replace(" ","")} bus1={lastFeeder}_end.1.2.3 phases=3 kw=265 pf=1 kv=2.4 xdp=0.27 xdpp=0.2 h=2 \n'	
	
	dssString += 'makebuslist \n'
	# TO DO: Find a more elegant networkx solution for scattering nodes around a sub_bus.
	for bus in busList:
		dssString += f'setbusxy bus={bus} y={lat} x={lon} \n'
		lat += 0.0005
		lon += 0.0005
	dssString += 'set voltagebases=[115,4.16,0.48]\ncalcvoltagebases'
	if not os.path.isdir(f'{_myDir}/uploads'):
		os.mkdir(f'{_myDir}/uploads')
	with open(f'{_myDir}/uploads/BASE_DSS_{model_dir}', "w") as outFile:
		outFile.writelines(dssString)
	loads = getLoads(f'{_myDir}/uploads/BASE_DSS_{model_dir}')
	return jsonify(loads=loads, filename=f'{_myDir}/uploads/BASE_DSS_{model_dir}')

@app.route('/uploadDss', methods = ['GET','POST'])
def uploadDss():
	if request.method == 'POST':
		# check if the post request has the file part
		model_dir = request.form['MODEL_DIR']
		if 'file' not in request.files:
			flash('No file part')
			return redirect(request.url)
		file = request.files['file']
		# If the user does not select a file, the browser submits an empty file without a filename.
		if file.filename == '':
			flash('No selected file')
			return redirect(request.url)
		if file and allowed_file(file.filename):
			filename = secure_filename(file.filename)
			if not os.path.isdir(f'{_myDir}/uploads'):
				os.mkdir(f'{_myDir}/uploads')
			file.save(f'{_myDir}/uploads/BASE_DSS_{model_dir}')
			loads = getLoads(file.filename)
			return jsonify(loads=loads, filename=f'{_myDir}/uploads/BASE_DSS_{model_dir}')
	return ''

@app.route('/previewPartitions', methods = ['GET','POST'])
def previewPartitions():
	CIRC_FILE = json.loads(request.form['fileName'])
	CRITICAL_LOADS = json.loads(request.form['critLoads'])
	METHOD = json.loads(request.form['method'])
	print(CIRC_FILE, CRITICAL_LOADS, METHOD)

	G = dssConvert.dss_to_networkx(CIRC_FILE)
	algo_params={}

	if METHOD == 'lukes':
		default_size = int(len(G.nodes())/3)
		MG_GROUPS = nx_group_lukes(G, algo_params.get('size',default_size))
	elif METHOD == 'branch':
		MG_GROUPS = nx_group_branch(G, i_branch=algo_params.get('i_branch',0))
	elif METHOD == 'bottomUp':
		MG_GROUPS = nx_bottom_up_branch(G, num_mgs=5, large_or_small='large')
	elif METHOD == 'criticalLoads':
		MG_GROUPS = nx_critical_load_branch(G, CRITICAL_LOADS, num_mgs=3, large_or_small='large')
	else:
		print('Invalid algorithm. algo must be "branch", "lukes", "bottomUp", or "criticalLoads". No mgs generated.')
		return {}

	plt.switch_backend('Agg')
	plt.figure(figsize=(15,9))
	pos_G = nice_pos(G)
	n_color_map = node_group_map(G, MG_GROUPS)
	nx.draw(G, with_labels=True, pos=pos_G, node_color=n_color_map)

	pic_IObytes = io.BytesIO()
	plt.savefig(pic_IObytes,  format='png')
	pic_IObytes.seek(0)
	pic_hash = base64.b64encode(pic_IObytes.read())
	return pic_hash

@app.route('/run', methods=["POST"])
def run():
	print('request.form',request.form)
	model_dir = request.form['MODEL_DIR']
	if 'BASE_DSS_NAME' in request.form and 'LOAD_CSV_NAME' in request.form:
		print('we are editing an existing model')
		# editing an existing model
		dss_path = f'{_myDir}/{model_dir}/circuit.dss'
		csv_path = f'{_myDir}/{model_dir}/loads.csv'
		all_files = 'Using Existing Files'
	else:
		# new files uploaded. 
		all_files = request.files
		print('all_files',all_files)
		# Save the files.
		if not os.path.isdir(f'{_myDir}/uploads'):
			os.mkdir(f'{_myDir}/uploads')
		# Note: Uploaded circuit stored separately.
		# dss_file = all_files['BASE_DSS']
		# dss_file.save(f'{_myDir}/uploads/BASE_DSS_{model_dir}')
		csv_file = all_files['LOAD_CSV']
		csv_file.save(f'{_myDir}/uploads/LOAD_CSV_{model_dir}')
		dss_path = f'{_myDir}/uploads/BASE_DSS_{model_dir}'
		csv_path = f'{_myDir}/uploads/LOAD_CSV_{model_dir}'
		# Handle uploaded CSVs for HISTORICAL_OUTAGES and criticalLoadShapeFile. Put both in models folder.    
		HISTORICAL_OUTAGES = all_files['HISTORICAL_OUTAGES']
		if HISTORICAL_OUTAGES.filename != '':
			HISTORICAL_OUTAGES.save(f'{_myDir}/uploads/HISTORICAL_OUTAGES_{model_dir}')
			# HISTORICAL_OUTAGES_path = f'{_myDir}/uploads/HISTORICAL_OUTAGES_{model_dir}'
		criticalLoadShapeFile = all_files['criticalLoadShapeFile']
		if criticalLoadShapeFile.filename != '':
			criticalLoadShapeFile.save(f'{_myDir}/uploads/criticalLoadShapeFile_{model_dir}')
			# criticalLoadShapeFile_path = f'{_myDir}/uploads/criticalLoadShapeFile_{model_dir}'
	# Handle arguments to our main function.
	crit_loads = json.loads(request.form['CRITICAL_LOADS'])
	print('crit_loads',crit_loads)
	mg_method = request.form['MG_DEF_METHOD']
	if mg_method == 'loadGrouping':
		pairings = json.loads(request.form['MICROGRIDS'])
		print('pairings',pairings)
		microgrids = mg_group(dss_path, crit_loads, 'loadGrouping', pairings)	
	elif mg_method == 'manual':
		algo_params = json.loads(request.form['MICROGRIDS'])
		microgrids = mg_group(dss_path, crit_loads, 'manual', algo_params)
	elif mg_method == 'lukes':
		microgrids = mg_group(dss_path, crit_loads, 'lukes')
	elif mg_method == 'branch':
		microgrids = mg_group(dss_path, crit_loads, 'branch')
	elif mg_method == 'bottomUp':
		microgrids = mg_group(dss_path, crit_loads, 'bottomUp')
	elif mg_method == 'criticalLoads':
		microgrids = mg_group(dss_path, crit_loads, 'criticalLoads')
	# Form REOPT_INPUTS. 
	REOPT_INPUTS = {
		# 'latitude':request.form['latitude'],
		# 'longitude':request.form['longitude'],
		'energyCost':request.form['energyCost'],
		'wholesaleCost':request.form['wholesaleCost'],
		'demandCost':request.form['demandCost'],
		'solarCanCurtail':(request.form['solarCanCurtail'] == 'true'),
		'solarCanExport':(request.form['solarCanExport'] == 'true'),
		# 'urdbLabelSwitch':request.form['urdbLabelSwitch'],
		# 'urdbLabel':request.form['urdbLabel'],
		'criticalLoadFactor':request.form['criticalLoadFactor'],
		'year':request.form['year'],
		# 'analysisYears':request.form['analysisYears'],
		'outageDuration':request.form['outageDuration'],
		# 'DIESEL_SAFETY_FACTOR':request.form['DIESEL_SAFETY_FACTOR'],
		# 'outage_start_hour':request.form['outage_start_hour'],
		# 'userCriticalLoadShape':request.form['userCriticalLoadShape'],
		'value_of_lost_load':request.form['value_of_lost_load'],
		# 'omCostEscalator':request.form['omCostEscalator'],
		# 'discountRate':request.form['discountRate'],

		'solar':request.form['solar'],
		'battery':request.form['battery'],
		# 'fossil':request.form['fossil'],
		'wind':request.form['wind'],
		'solarCost':request.form['solarCost'],
		'solarExisting':request.form['solarExisting'],
		'solarMax':request.form['solarMax'],
		'solarMin':request.form['solarMin'],
		# 'solarMacrsOptionYears':request.form['solarMacrsOptionYears'],
		# 'solarItcPercent':request.form['solarItcPercent'],
		'batteryCapacityCost':request.form['batteryCapacityCost'],
		'batteryCapacityMax':request.form['batteryCapacityMax'],
		'batteryCapacityMin':request.form['batteryCapacityMin'],
		'batteryKwhExisting':request.form['batteryKwhExisting'],
		'batteryPowerCost':request.form['batteryPowerCost'],
		'batteryPowerMax':request.form['batteryPowerMax'],
		'batteryPowerMin':request.form['batteryPowerMin'],
		'batteryKwExisting':request.form['batteryKwExisting'],
		# 'batteryMacrsOptionYears':request.form['batteryMacrsOptionYears'],
		# 'batteryItcPercent':request.form['batteryItcPercent'],
		# 'batteryPowerCostReplace':request.form['batteryPowerCostReplace'],
		# 'batteryCapacityCostReplace':request.form['batteryCapacityCostReplace'],
		# 'batteryPowerReplaceYear':request.form['batteryPowerReplaceYear'],
		# 'batteryCapacityReplaceYear':request.form['batteryCapacityReplaceYear'],
		'dieselGenCost':request.form['dieselGenCost'],
		'dieselMax':request.form['dieselMax'],
		# 'dieselMin':request.form['dieselMin'],
		'fuelAvailable':request.form['fuelAvailable'],
		'genExisting':request.form['genExisting'],
		'minGenLoading':request.form['minGenLoading'],
		# 'dieselFuelCostGal':request.form['dieselFuelCostGal'],
		# 'dieselCO2Factor':request.form['dieselCO2Factor'],
		# 'dieselOMCostKw':request.form['dieselOMCostKw'],
		# 'dieselOMCostKwh':request.form['dieselOMCostKwh'],
		# 'dieselOnlyRunsDuringOutage':request.form['dieselOnlyRunsDuringOutage'],
		# 'dieselMacrsOptionYears':request.form['dieselMacrsOptionYears'],
		'windCost':request.form['windCost'],
		'windExisting':request.form['windExisting'],
		'windMax':request.form['windMax'],
		'windMin':request.form['windMin'],
		# 'windMacrsOptionYears':request.form['windMacrsOptionYears'],
		# 'windItcPercent':request.form['windItcPercent'],
	}
	mgu_args = [
		request.form['MODEL_DIR'],
		dss_path,
		csv_path,
		float(request.form['QSTS_STEPS']),
		float(request.form['FOSSIL_BACKUP_PERCENT']),
		REOPT_INPUTS,
		microgrids,
		request.form['FAULTED_LINE']
	]
	print('thomas gui mgu_args',mgu_args)
	# Kickoff the run
	new_proc = multiprocessing.Process(target=microgridup.full, args=mgu_args)
	new_proc.start()
	# Redirect to home after waiting a little for the file creation to happen.
	time.sleep(5)
	return redirect(f'/')


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def gen_col_map(item_ob, map_dict, default_col):
	'''generate a color map for nodes or edges'''
	return [map_dict.get(n, default_col) for n in item_ob]

def node_group_map(graph, parts, color_list=['red','orange','yellow','green','blue','indigo','violet']):
	''' color map for notes in a group of [parts]. '''
	color_map = {}
	for i, group in enumerate(parts):
		for item in group:
			color_map[item] = color_list[i % len(color_list)]
	n_color_map = gen_col_map(graph.nodes(), color_map, 'gray')
	return n_color_map

def nice_pos(G):
	''' return nice positions for charting G. '''
	return nx.drawing.nx_agraph.graphviz_layout(G, prog="twopi", args="")

def getLoads(path):
	tree = dssConvert.dssToTree(path)
	loads = [obj.get('object','').split('.')[1] for obj in tree if 'load.' in obj.get('object','')]
	return loads

if __name__ == "__main__":
	if platform.system() == "Darwin":  # MacOS
		os.environ['NO_PROXY'] = '*' # Workaround for macOS proxy behavior
		multiprocessing.set_start_method('forkserver') # Workaround for Catalina exec/fork behavior

		# mgu_args = ['3mgs_used_wizard', '/Users/thomasjankovic/microgridup/uploads/BASE_DSS_3mgs_used_wizard', '/Users/thomasjankovic/microgridup/uploads/LOAD_CSV_3mgs_used_wizard', 480.0, 0.5, {'energyCost': '0.12', 'wholesaleCost': '0.034', 'demandCost': '20', 'solarCanCurtail': True, 'solarCanExport': True, 'criticalLoadFactor': '1', 'year': '2017', 'outageDuration': '48', 'value_of_lost_load': '1', 'solar': 'on', 'battery': 'on', 'wind': 'off', 'solarCost': '1600', 'solarExisting': '0', 'solarMax': '100000', 'solarMin': '0', 'batteryCapacityCost': '420', 'batteryCapacityMax': '1000000', 'batteryCapacityMin': '0', 'batteryKwhExisting': '0', 'batteryPowerCost': '840', 'batteryPowerMax': '1000000', 'batteryPowerMin': '0', 'batteryKwExisting': '0', 'dieselGenCost': '500', 'dieselMax': '1000000', 'fuelAvailable': '50000', 'genExisting': '0', 'minGenLoading': '0.3', 'windCost': '4989', 'windExisting': '0', 'windMax': '100000', 'windMin': '0'}, {'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': ['reg0'], 'gen_bus': 'reg0_end', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1'], 'switch': ['reg1'], 'gen_bus': 'reg1_end', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['645_hangar', '646_office'], 'switch': ['reg2'], 'gen_bus': 'reg2_end', 'gen_obs_existing': [], 'critical_load_kws': [1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}, '670671']
		# new_proc = multiprocessing.Process(target=microgridup.full, args=mgu_args)
		# new_proc.start()
		# microgridup.full(mgu_args[0],mgu_args[1], mgu_args[2], mgu_args[3], mgu_args[4], mgu_args[5], mgu_args[6], mgu_args[7])

		# jsonToDss()
	app.run(debug=True, host="0.0.0.0")