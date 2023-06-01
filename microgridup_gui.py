import base64, io, json, multiprocessing, os, platform, shutil, time
import networkx as nx
from collections import OrderedDict
from matplotlib import pyplot as plt
from flask import Flask, flash, request, redirect, render_template, jsonify
from werkzeug.utils import secure_filename
from omf.solvers.opendss import dssConvert
from microgridup_gen_mgs import mg_group, nx_group_branch, nx_group_lukes, nx_bottom_up_branch, nx_critical_load_branch
from microgridup import full
from subprocess import Popen
from flask import send_from_directory
from pathlib import Path

_mguDir = os.path.abspath(os.path.dirname(__file__))
if _mguDir == '/':
	_mguDir = '' #workaround for rooted installs through e.g. docker.
_analysisDir = f'{_mguDir}/data/projects'

app = Flask(__name__, static_folder='data', template_folder='templates')

def list_analyses():
	all_analyses = [x for x in os.listdir(_analysisDir) if os.path.isdir(f'{_analysisDir}/{x}')]
	return all_analyses

@app.route('/')
def home():
	analyses = list_analyses()
	return render_template('template_home.html', analyses=analyses)

@app.route('/load/<analysis>')
def load(analysis):
	ana_files = os.listdir(f'{_analysisDir}/{analysis}')
	if '0crashed.txt' in ana_files:
		return 'Model Crashed. Please delete and recreate.'
	elif '0running.txt' in ana_files:
		return 'Model Running. Please reload to check for completion.'
	elif 'output_final.html' in ana_files:
		return redirect(f'/data/projects/{analysis}/output_final.html')
	else:
		return 'Model is in an inconsistent state. Please delete and recreate.'

@app.route('/edit/<analysis>')
def edit(analysis):
	try:
		with open(f'{_analysisDir}/{analysis}/allInputData.json') as in_data_file:
			in_data = json.load(in_data_file)
	except:
		in_data = None
	return render_template('template_new.html', in_data=in_data)

@app.route('/new')
def newGui():
	with open(f'{_mguDir}/data/static/lehigh_3mg_inputs.json') as default_in_file:
		default_in = json.load(default_in_file)
	return render_template('template_new.html', in_data=default_in)

@app.route('/duplicate', methods=["POST"])
def duplicate():
	analysis = request.json.get('analysis', None)
	new_name = request.json.get('new_name', None)
	analyses = list_analyses()
	if (analysis not in analyses) or (new_name in analyses):
		return 'Duplication failed. Analysis does not exist or the new name is invalid.'
	else:
		shutil.copytree(analysis, f'{_analysisDir}/{new_name}')
		return f'Successfully duplicated {analysis} as {new_name}.'

@app.route('/jsonToDss', methods=['GET','POST'])
def jsonToDss(model_dir=None, lat=None, lon=None, elements=None, test_run=False):
	if not model_dir:
		model_dir = request.form['MODEL_DIR']
	if not lat:
		lat = float(request.form['latitude'])
	if not lon:
		lon = float(request.form['longitude'])
	if not elements:
		elements = json.loads(request.form['json'])
	# Convert to DSS and return loads.
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
			dssString += f'new object=line.{lastFeeder} phases=3 bus1={lastSub}_bus.1.2.3 bus2={lastFeeder}_end.1.2.3 length=1333 units=ft \n'
			busList.append(f'{lastFeeder}_end')
		elif obType == 'load':
			dssString += f'new object=load.{obName.replace(" ","")} bus1={lastFeeder}_end.1 phases=1 conn=wye model=1 kv=2.4 kw=1155 kvar=660 \n'
		elif obType == 'solar':
			dssString += f'new object=generator.{obName.replace(" ","")} bus1={lastFeeder}_end.1 phases=1 kv=0.277 kw=440 pf=1 \n'
		elif obType == 'wind':
			dssString += f'new object=generator.{obName.replace(" ","")} bus1={lastFeeder}_end.1 phases=1 kv=0.277 kw=200 pf=1 \n'
		elif obType == 'battery':
			dssString += f'new object=storage.{obName.replace(" ","")} bus1={lastFeeder}_end.1 phases=1 kv=0.277 kwrated=79 kwhstored=307 kwhrated=307 dispmode=follow %charge=100 %discharge=100 %effcharge=96 %effdischarge=96 \n'
		elif obType == 'diesel':
			dssString += f'new object=generator.{obName.replace(" ","")} bus1={lastFeeder}_end.1.2.3 phases=3 kw=265 pf=1 kv=2.4 xdp=0.27 xdpp=0.2 h=2 \n'	
	# Convert dssString to a networkx graph.
	tree = dssConvert.dssToTree(dssString, is_path=False)
	G = dssConvert.dss_to_networkx('', tree=tree)
	# Set twopi layout to custom coordinates.
	pos = nice_pos(G)
	# Define the scale
	scale_factor = 0.00005
	# Calculate the translation coordinates
	x_offset = lon - (scale_factor * (max(pos.values(), key=lambda x: x[0])[0] - min(pos.values(), key=lambda x: x[0])[0])) / 2
	y_offset = lat - (scale_factor * (max(pos.values(), key=lambda x: x[1])[1] - min(pos.values(), key=lambda x: x[1])[1])) / 2
	# Apply the translation and scaling to the layout
	new_pos = {node: (scale_factor * (x - min(pos.values(), key=lambda x: x[0])[0]) + x_offset, scale_factor * (y - min(pos.values(), key=lambda x: x[1])[1]) + y_offset) for node, (x, y) in pos.items()}
	dssString += 'makebuslist \n'
	for bus in busList:
		new_pos_bus = bus.lower()
		dssString += f'setbusxy bus={bus} y={new_pos[new_pos_bus][1]} x={new_pos[new_pos_bus][0]} \n'
	dssString += 'set voltagebases=[115,4.16,0.48]\ncalcvoltagebases'
	if not os.path.isdir(f'{_mguDir}/uploads'):
		os.mkdir(f'{_mguDir}/uploads')
	dssFilePath = f'{_mguDir}/uploads/BASE_DSS_{model_dir}'
	with open(dssFilePath, "w") as outFile:
		outFile.writelines(dssString)
	loads = getLoads(dssFilePath)
	if not test_run:
		t = dssConvert.dssToTree(dssFilePath)
		return jsonify(loads=loads, filename=dssFilePath)
	else:
		print(f'Test run of jsonToDss() for {model_dir} complete.')
		return dssFilePath

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
			if not os.path.isdir(f'{_mguDir}/uploads'):
				os.mkdir(f'{_mguDir}/uploads')
			file.save(f'{_mguDir}/uploads/BASE_DSS_{model_dir}')
			loads = getLoads(f'{_mguDir}/uploads/BASE_DSS_{model_dir}')
			return jsonify(loads=loads, filename=f'{_mguDir}/uploads/BASE_DSS_{model_dir}')
	return ''

@app.route('/previewPartitions', methods = ['GET','POST'])
def previewPartitions():
	CIRC_FILE = json.loads(request.form['fileName'])
	CRITICAL_LOADS = json.loads(request.form['critLoads'])
	METHOD = json.loads(request.form['method'])
	MGQUANT = int(json.loads(request.form['mgQuantity']))
	G = dssConvert.dss_to_networkx(CIRC_FILE)
	algo_params={}
	if METHOD == 'lukes':
		default_size = int(len(G.nodes())/3)
		MG_GROUPS = nx_group_lukes(G, algo_params.get('size',default_size))
	elif METHOD == 'branch':
		MG_GROUPS = nx_group_branch(G, i_branch=algo_params.get('i_branch',0))
	elif METHOD == 'bottomUp':
		MG_GROUPS = nx_bottom_up_branch(G, num_mgs=MGQUANT, large_or_small='large')
	elif METHOD == 'criticalLoads':
		MG_GROUPS = nx_critical_load_branch(G, CRITICAL_LOADS, num_mgs=MGQUANT, large_or_small='large')
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
	model_dir = request.form['MODEL_DIR']
	print(f'-------------------------------Running {model_dir}.-------------------------------')
	if 'BASE_DSS_NAME' in request.form and 'LOAD_CSV_NAME' in request.form:
		print('we are editing an existing model')
		# editing an existing model
		dss_path = f'{_analysisDir}/{model_dir}/circuit.dss'
		csv_path = f'{_analysisDir}/{model_dir}/loads.csv'
		all_files = 'Using Existing Files'
	else:
		# new files uploaded. 
		all_files = request.files
		# Save the files.
		if not os.path.isdir(f'{_mguDir}/uploads'):
			os.mkdir(f'{_mguDir}/uploads')
		# Note: Uploaded circuit stored separately.
		csv_file = all_files['LOAD_CSV']
		csv_file.save(f'{_mguDir}/uploads/LOAD_CSV_{model_dir}')
		dss_path = f'{_mguDir}/uploads/BASE_DSS_{model_dir}'
		csv_path = f'{_mguDir}/uploads/LOAD_CSV_{model_dir}'
		# Handle uploaded CSVs for HISTORICAL_OUTAGES and criticalLoadShapeFile. Put both in models folder.    
		HISTORICAL_OUTAGES = all_files['HISTORICAL_OUTAGES']
		if HISTORICAL_OUTAGES.filename != '':
			HISTORICAL_OUTAGES.save(f'{_mguDir}/uploads/HISTORICAL_OUTAGES_{model_dir}')
		criticalLoadShapeFile = all_files['criticalLoadShapeFile']
		if criticalLoadShapeFile.filename != '':
			criticalLoadShapeFile.save(f'{_mguDir}/uploads/criticalLoadShapeFile_{model_dir}')
	# Handle arguments to our main function.
	crit_loads = json.loads(request.form['CRITICAL_LOADS'])
	mg_method = request.form['MG_DEF_METHOD']
	MGQUANT = int(json.loads(request.form['mgQuantity']))
	if mg_method == 'loadGrouping':
		pairings = json.loads(request.form['MICROGRIDS'])
		microgrids = mg_group(dss_path, crit_loads, 'loadGrouping', pairings)	
	elif mg_method == 'manual':
		algo_params = json.loads(request.form['MICROGRIDS'])
		print('algo_params',algo_params)
		microgrids = mg_group(dss_path, crit_loads, 'manual', algo_params)
	elif mg_method == 'lukes':
		microgrids = mg_group(dss_path, crit_loads, 'lukes')
	elif mg_method == 'branch':
		microgrids = mg_group(dss_path, crit_loads, 'branch')
	elif mg_method == 'bottomUp':
		microgrids = mg_group(dss_path, crit_loads, 'bottomUp', algo_params={'num_mgs':MGQUANT})
	elif mg_method == 'criticalLoads':
		microgrids = mg_group(dss_path, crit_loads, 'criticalLoads', algo_params={'num_mgs':MGQUANT})
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
		f'{_analysisDir}/{request.form["MODEL_DIR"]}',
		dss_path,
		csv_path,
		float(request.form['QSTS_STEPS']),
		float(request.form['FOSSIL_BACKUP_PERCENT']),
		REOPT_INPUTS,
		microgrids,
		request.form['FAULTED_LINE']
	]
	# Kickoff the run
	new_proc = multiprocessing.Process(target=full, args=mgu_args)
	new_proc.start()
	# Redirect to home after waiting a little for the file creation to happen.
	time.sleep(5)
	return redirect(f'/')

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'dss'}
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
	return nx.drawing.nx_agraph.graphviz_layout(G)
	# return nx.kamada_kawai_layout(G)
	# return nx.spring_layout(G, iterations=500)

def getLoads(path):
	print(f'Working on {path}')
	tree = dssConvert.dssToTree(path)
	loads = [obj.get('object','').split('.')[1] for obj in tree if 'load.' in obj.get('object','')]
	return loads

def _tests():
	lat = 39.7817
	lon = -89.6501
	with open('testfiles/test_params.json') as file:
		test_params = json.load(file)
	MG_MINES = test_params['MG_MINES']
	wizard_dir = [_dir for _dir in MG_MINES if 'wizard' in _dir]
	elements = test_params['elements']
	templateDssTree = test_params['templateDssTree']
	# Testing jsonToDss().
	for _dir in wizard_dir:
		dssFilePath = jsonToDss(_dir, lat, lon, elements, True)
		dssTree = dssConvert.dssToTree(dssFilePath)
		expectedDssTree = templateDssTree
		expectedDssTree[2] = OrderedDict([('!CMD', 'new'), ('object', f'circuit.{_dir.lower()}')])
		# Find index of 'makebuslist' because NetworkX shifts coordinates around each run and it is useless to compare them.
		mbl = [y for y in expectedDssTree if y.get('!CMD') == 'makebuslist']
		idx = expectedDssTree.index(mbl[0])
		assert dssTree[:idx] == expectedDssTree[:idx], f'dssTree did not match expectedDssTree when testing {_dir}.\nExpected output: {expectedDssTree[:idx]}.\nReceived output: {dssTree[:idx]}.'
	return print('Ran all tests for for microgridup_gui.py.')

# Helper app to redirect http -> https
reApp = Flask("HTTPS_REDIRECT")

@reApp.route("/")
def index():
	return "NA"

@reApp.before_request
def before_request():
	# Handle ACME challenges for letsencrypt to keep SSL renewing.
	if '/.well-known/acme-challenge' in request.url:
		try:
			filename = request.url.split('/')[-1]
		except:
			filename = 'none'
		return send_from_directory(f'{_mguDir}.well-known/acme-challenge', filename)
	# Redirect http -> https
	elif request.url.startswith("http://"):
		url = request.url.replace("http://", "https://", 1)
		return redirect(url, code=301)

if __name__ == "__main__":
	if platform.system() == "Darwin":  # MacOS
		os.environ['NO_PROXY'] = '*' # Workaround for macOS proxy behavior
		multiprocessing.set_start_method('forkserver') # Workaround for Catalina exec/fork behavior
	gunicorn_args = ['gunicorn', '-w', '5', '--reload', 'microgridup_gui:app','--worker-class=sync', '--timeout=100']
	mguPath = Path(_mguDir)
	if (mguPath/'ssl').exists() and (mguPath/'logs').exists():
		# if production directories, run in prod mode with logging and ssl.
		gunicorn_args.extend(['--access-logfile', mguPath / 'logs/mgu.access.log', '--error-logfile', mguPath / 'logs/mgu.error.log', '--capture-output'])
		gunicorn_args.extend(['--certfile', mguPath / 'ssl/cert.pem', '--keyfile', mguPath / 'ssl/privkey.pem', '--ca-certs', mguPath/'ssl/fullchain.pem'])
		gunicorn_args.extend(['-b', '0.0.0.0:443'])
		redirProc = Popen(['gunicorn', '-w', '5', '-b', '0.0.0.0:80', 'microgridup_gui:reApp']) # don't need to wait, only wait on main proc.
		appProc = Popen(gunicorn_args)
	else:
		# no production directories, run in dev mode, i.e. no log files, no ssl.
		# app.run(debug=True, host="0.0.0.0") # old flask way, don't use.
		gunicorn_args.extend(['-b', '0.0.0.0:5000'])
		appProc = Popen(gunicorn_args)
	appProc.wait()