import base64, io, json, multiprocessing, os, platform, shutil, datetime, time
import networkx as nx
from collections import OrderedDict
from matplotlib import pyplot as plt
from flask import Flask, request, redirect, render_template, jsonify, url_for
from omf.solvers.opendss import dssConvert
from microgridup_gen_mgs import mg_group, nx_group_branch, nx_group_lukes, nx_bottom_up_branch, nx_critical_load_branch
from microgridup import full
from subprocess import Popen
from flask import send_from_directory
from pathlib import Path
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from blueprint import data_dir_blueprint

_mguDir = os.path.abspath(os.path.dirname(__file__))
if _mguDir == '/':
	_mguDir = '' #workaround for rooted installs through e.g. docker.
_projectDir = f'{_mguDir}/data/projects'

app = Flask(__name__)
# - Use a blueprint to add another directory to serve static assets (i.e. the "data/" directory)
app.register_blueprint(data_dir_blueprint)
auth = HTTPBasicAuth()

users = {} # if blank then no authentication.
users_path = f'{_mguDir}/data/static/users.json'
if os.path.exists(users_path):
	user_json = json.load(open(users_path))
	users = {k:generate_password_hash(user_json[k]) for k in user_json}

# authenticate every request if user json available.
@app.before_request
@auth.login_required
def before_request_func():
	pass #print("Performing Authentication")

@auth.verify_password
def verify_password(username, password):
	if users != {}:
		if username in users and check_password_hash(users.get(username), password):
			return username
	else:
		return username
	
@app.route('/get_logs/<model_name>')
def get_logs(model_name):
    # Read the logs from the corresponding log file.
    log_file = os.path.join('data/projects', model_name, 'logs.txt')
    if os.path.exists(log_file):
        with open(log_file, 'r') as file:
            logs = file.readlines()
    else:
        logs = []
    return jsonify({"logs": logs})

def list_projects():
	projects = [x for x in os.listdir(_projectDir) if os.path.isdir(f'{_projectDir}/{x}')]
	project_timestamps = {}
	project_descriptions = {}
	
	for project in projects:
		input_data_path = os.path.join(_projectDir, project, 'allInputData.json')
		if os.path.exists(input_data_path):
			with open(input_data_path) as json_file:
				data = json.load(json_file)
				if 'CREATION_DATE' in data and data['CREATION_DATE']:
					timestamp = datetime.datetime.strptime(data['CREATION_DATE'], '%Y-%m-%d %H:%M:%S')
					project_timestamps[project] = timestamp
				if 'DESCRIPTION' in data and data['DESCRIPTION']:
					project_descriptions[project] = data['DESCRIPTION']
	return projects, project_timestamps, project_descriptions

@app.route('/')
def home():
	projects, project_timestamps, project_descriptions = list_projects()
	return render_template('template_home.html', projects=projects, project_timestamps=project_timestamps, project_descriptions=project_descriptions)

@app.route('/rfile/<project>/<filename>')
def rfile(project, filename):
	return send_from_directory(f'{_projectDir}/{project}', filename)

@app.route('/load/<project>')
def load(project):
	ana_files = os.listdir(f'{_projectDir}/{project}')
	input_data_path = os.path.join(_projectDir, project, 'allInputData.json')
	if os.path.exists(input_data_path):
		with open(input_data_path) as json_file:
			data = json.load(json_file)
	else:
		print('Error: Input data failed to save.')
	if '0running.txt' in ana_files:
		return render_template('template_in_progress.html', model_name=project, in_data=data, crashed=False)
	elif '0crashed.txt' in ana_files:
		return render_template('template_in_progress.html', model_name=project, in_data=data, crashed=True)
	elif 'output_final.html' in ana_files:
		return redirect(f'/data/projects/{project}/output_final.html')
	else:
		return 'Model is in an inconsistent state. Please delete and recreate.'
	
@app.route('/check_status/<project>')
def check_status(project):
	'''Used by template_in_progress.html to redirect to output_final.html once it exists.'''
	files = os.listdir(f'{_projectDir}/{project}')
	if 'output_final.html' in files and '0running.txt' not in files and '0crashed.txt' not in files:
		return jsonify(status='complete', url=f'/data/projects/{project}/output_final.html')
	elif '0crashed.txt' in files:
		return jsonify(status='crashed')
	else:
	    return jsonify(status='in_progress')

@app.route('/edit/<project>')
def edit(project):
	try:
		with open(f'{_projectDir}/{project}/allInputData.json') as in_data_file:
			in_data = json.load(in_data_file)
			in_data['MODEL_DIR'] = in_data['MODEL_DIR'].split('/')[-1]
	except:
		in_data = None
	return render_template('template_new.html', in_data=in_data, iframe_mode=False, editing=True)

@app.route('/delete/<project>')
def delete(project):
	full_path = f'{_projectDir}/{project}'
	if os.path.exists(full_path) and os.path.isdir(full_path):
		shutil.rmtree(full_path)
	else:
		return 'Directory does not exist or is not a directory.'
	return redirect(url_for('home'))

@app.route('/new')
def newGui():
	with open(f'{_mguDir}/static/lehigh_3mg_inputs.json') as default_in_file:
		default_in = json.load(default_in_file)
	return render_template('template_new.html', in_data=default_in, iframe_mode=False, editing=False)

@app.route('/duplicate', methods=["POST"])
def duplicate():
	project = request.json.get('project', None)
	new_name = request.json.get('new_name', None)
	projects, project_timestamps, project_descriptions = list_projects()
	if (project not in projects) or (new_name in projects):
		return 'Duplication failed. Project does not exist or the new name is invalid.'
	else:
		shutil.copytree(f'{_projectDir}/{project}', f'{_projectDir}/{new_name}')
		with open(f'data/projects/{new_name}/allInputData.json') as file:
			inputs = json.load(file)
		inputs['MODEL_DIR'] = inputs['MODEL_DIR'].replace(project, new_name)
		inputs['BASE_DSS'] = inputs['BASE_DSS'].replace(project, new_name)
		inputs['LOAD_CSV'] = inputs['LOAD_CSV'].replace(project, new_name)
		with open(f'data/projects/{new_name}/allInputData.json', 'w') as file:
			json.dump(inputs, file, indent=4)
		return f'Successfully duplicated {project} as {new_name}.'

@app.route('/jsonToDss', methods=['GET','POST'])
def jsonToDss(model_dir=None, lat=None, lon=None, elements=None, test_run=False, on_edit_flow=None):
	if not model_dir:
		model_dir = request.form['MODEL_DIR']
	if not lat:
		lat = float(request.form['latitude'])
	if not lon:
		lon = float(request.form['longitude'])
	if not elements:
		elements = json.loads(request.form['json'])
	if not on_edit_flow:
		on_edit_flow = request.form['on_edit_flow']
	if on_edit_flow == 'false':
		if os.path.isdir(f'{_mguDir}/data/projects/{model_dir}'):
			print('Invalid Model Name.')
			return jsonify(error=f'A model named "{model_dir}" already exists. Please choose a different Model Name.'), 400 # Name was already taken.

	# Convert to DSS and return loads.
	dssString = f'clear \nset defaultbasefrequency=60 \nnew object=circuit.{model_dir} \n'
	busList = []
	# Name substation bus after substation itself. Name gen bus after the feeder
	for ob in elements:
		obType = ob['type']
		obName = ob['name']
		suffix = '' if obName.endswith('_existing') else '_existing'
		if obType == 'substation': 
			dssString += f'new object=vsource.{obName} basekv=2.4 bus1={obName}_bus.1.2.3 pu=1.00 r1=0 x1=0.0001 r0=0 x0=0.0001 \n'
			busList.append(f'{obName}_bus')
		elif obType == 'feeder':
			dssString += f'new object=line.{obName} phases=3 bus1={ob["parent"]}_bus.1.2.3 bus2={obName}_end.1.2.3 length=1333 units=ft \n'
			busList.append(f'{obName}_end')
		elif obType == 'load':
			dssString += f'new object=load.{obName} bus1={ob["parent"]}_end.1.2.3 phases=3 conn=wye model=1 kv=2.4 kw={ob["kw"]} kvar=660 \n'
		elif obType == 'solar':
			prefix = '' if obName.startswith('solar_') else 'solar_'
			dssString += f'new object=generator.{prefix}{obName}{suffix} bus1={ob["parent"]}_end.1.2.3 phases=3 kv=2.4 kw={ob["kw"]} pf=1 \n'
		elif obType == 'wind':
			prefix = '' if obName.startswith('wind_') else 'wind_'
			dssString += f'new object=generator.{prefix}{obName}{suffix} bus1={ob["parent"]}_end.1.2.3 phases=3 kv=2.4 kw={ob["kw"]} pf=1 \n'
		elif obType == 'battery':
			prefix = '' if obName.startswith('battery_') else 'battery_'
			dssString += f'new object=storage.{prefix}{obName}{suffix} bus1={ob["parent"]}_end.1.2.3 phases=3 kv=2.4 kwrated={ob["kw"]} kwhstored={ob["kwh"]} kwhrated={ob["kwh"]} dispmode=follow %charge=100 %discharge=100 %effcharge=96 %effdischarge=96 \n'
		elif obType == 'fossil':
			prefix = '' if obName.startswith('fossil_') else 'fossil_'
			dssString += f'new object=generator.{prefix}{obName}{suffix} bus1={ob["parent"]}_end.1.2.3 phases=3 kw={ob["kw"]} pf=1 kv=2.4 xdp=0.27 xdpp=0.2 h=2 \n'
		else:
			raise Exception(f'Unknown object type "{obType}"')
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

@app.route('/uploadDss', methods = ['POST'])
def uploadDss():
	model_dir = request.form['MODEL_DIR']
	# Check to see if user is on edit flow. If user is not on edit flow, ensure that model_dir is not already in data/projects.
	on_edit_flow = request.form['on_edit_flow']
	if on_edit_flow == 'false':
		if os.path.isdir(f'{_mguDir}/data/projects/{model_dir}'):
			return jsonify(error=f'A model named "{model_dir}" already exists. Please choose a different Model Name.'), 400 # Name was already taken.
	# Check if the post request has the file part.
	if 'BASE_DSS_NAME' not in request.files:
		return jsonify(error='No file part'), 400  # Return a JSON response with 400 Bad Request status.
	file = request.files['BASE_DSS_NAME']
	# If the user does not select a file, the browser submits an empty file without a filename.
	if file.filename == '':
		return jsonify(error='No selected file'), 400  # Return a JSON response with 400 Bad Request status.
	if file and allowed_file(file.filename):
		if not os.path.isdir(f'{_mguDir}/uploads'):
			os.mkdir(f'{_mguDir}/uploads')
		file.save(f'{_mguDir}/uploads/BASE_DSS_{model_dir}')
		loads = getLoads(f'{_mguDir}/uploads/BASE_DSS_{model_dir}')
		return jsonify(loads=loads, filename=f'{_mguDir}/uploads/BASE_DSS_{model_dir}')
	return jsonify(error='Invalid file'), 400  # Return a JSON response with 400 Bad Request status for invalid files.

@app.route('/getLoadsFromExistingFile', methods=['POST'])
def getLoadsFromExistingFile():
	# path = request.form.get('path')
	model_dir = request.form['MODEL_DIR']
	path = f'{_mguDir}/data/projects/{model_dir}/circuit.dss'
	loads = getLoads(path)
	return jsonify(loads=loads)

@app.route('/previewOldPartitions', methods=['POST'])
def previewOldPartitions():
	data = request.get_json()
	# filename = data['filename']
	model_dir = data['MODEL_DIR']
	filename = f'{_mguDir}/data/projects/{model_dir}/circuit.dss'
	MG_MINES = data['MG_MINES']
	G = dssConvert.dss_to_networkx(filename)

	parts = []
	for mg in MG_MINES:
		cur_mg = []
		cur_mg.extend([load for load in MG_MINES[mg].get('loads')])
		# cur_mg.append(MG_MINES[mg].get('switch'))
		cur_mg.append(MG_MINES[mg].get('gen_bus'))
		cur_mg.extend([load for load in MG_MINES[mg].get('gen_obs_existing')])
		parts.append(cur_mg)

	# Make and save plot, convert to base64 hash, send to frontend.
	plt.switch_backend('Agg')
	plt.figure(figsize=(15,9))
	pos_G = nice_pos(G)
	# Add here later: function to convert MG_MINES to algo_params[pairings] for passing to manual_groups(). Would be more accurate when passed to node_group_map() than parts.
	n_color_map = node_group_map(G, parts)
	nx.draw(G, with_labels=True, pos=pos_G, node_color=n_color_map)
	pic_IObytes = io.BytesIO()
	plt.savefig(pic_IObytes,  format='png')
	pic_IObytes.seek(0)
	pic_hash = base64.b64encode(pic_IObytes.getvalue()).decode('utf-8')
	return jsonify({'pic_hash': pic_hash, 'MG_MINES': MG_MINES})

@app.route('/previewPartitions', methods = ['GET','POST'])
@app.route('/edit/previewPartitions', methods = ['GET','POST'])
def previewPartitions():
	CIRC_FILE = json.loads(request.form['fileName'])
	if not CIRC_FILE.startswith('/'):
		CIRC_FILE = str(Path(_projectDir).resolve(True) / json.loads(request.form['modelDir']) / CIRC_FILE)
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
	MG_MINES = mg_group(CIRC_FILE, CRITICAL_LOADS, METHOD, algo_params={'num_mgs':MGQUANT})
	for mg in MG_MINES:
		if not MG_MINES[mg]['switch']:
			print(f'Selected partitioning method produced invalid results. Please choose a different partitioning method.')
			return jsonify('Invalid partitioning method')
	plt.switch_backend('Agg')
	plt.figure(figsize=(15,9))
	pos_G = nice_pos(G)
	n_color_map = node_group_map(G, MG_GROUPS)
	nx.draw(G, with_labels=True, pos=pos_G, node_color=n_color_map)
	pic_IObytes = io.BytesIO()
	plt.savefig(pic_IObytes,  format='png')
	pic_IObytes.seek(0)
	pic_hash = base64.b64encode(pic_IObytes.read()).decode('ascii')
	return jsonify({'pic_hash': pic_hash, 'MG_MINES': MG_MINES})

@app.route('/run', methods=["POST"])
def run():
	# Make the uploads directory if it doesn't already exist.
	if not os.path.isdir(f'{_mguDir}/uploads'):
		os.mkdir(f'{_mguDir}/uploads')
	# Get directory, get files, and print status.
	model_dir = request.form['MODEL_DIR']
	all_files = request.files
	print(f'-------------------------------Running {model_dir}.-------------------------------')

	# Check to see if new loads were uploaded. If so, add those to uploads folder. Set path to uploads folder.
	if all_files.get('LOAD_CSV'):
		print('New loads uploaded.')
		csv_file = all_files['LOAD_CSV']
		csv_file.save(f'{_mguDir}/uploads/LOAD_CSV_{model_dir}')
		csv_path = f'{_mguDir}/uploads/LOAD_CSV_{model_dir}'
	elif request.form['LOAD_CSV_NAME']:
		# If we're reusing an old loads or dss file, set path to project directory.
		print('Reusing loads.csv in project directory.')
		csv_path = f'{_mguDir}/data/projects/{model_dir}/loads.csv'
	else:
		print('Error: unable to set path to loads csv.')
	
	# Check to see if new dss was uploaded. If so, add to uploads folder. Set path to uploads folder. If reusing a circuit, set dss path to circuit.dss in project directory.
	dss_indicator = request.form['DSS_PATH']
	if dss_indicator == 'Direct to uploads folder.':
		dss_path = f'{_mguDir}/uploads/BASE_DSS_{model_dir}'
		print('New circuit uploaded.')
	else:
		dss_path = f'{_mguDir}/data/projects/{model_dir}/circuit.dss'
		print('Reusing circuit.dss in project directory.')

	# Check to see if user uploaded new outages. If so, add to upload folder. Set path to uploads folder.
	outages_indicator = request.form['OUTAGES_PATH']
	if outages_indicator == 'Check files':
		# No file is being reused.
		outages_filename = all_files['HISTORICAL_OUTAGES'].filename
		if outages_filename != '':
			# New outages file that must be saved.
			all_files['HISTORICAL_OUTAGES'].save(f'{_mguDir}/uploads/HISTORICAL_OUTAGES_{model_dir}')
			outages_path = f'{_mguDir}/uploads/HISTORICAL_OUTAGES_{model_dir}'
			have_outages = True
			print('New outages uploaded.')
		else:
			# No outages file.
			print('No outages uploaded.')
			have_outages = False
	else:
		# If we're reusing an old outages file, set path to project directory.
		outages_path = f'{_mguDir}/{model_dir}/outages.csv'
		have_outages = True
		print('Reusing outages.csv in project directory.')

	# Handle arguments to our main function.
	crit_loads = json.loads(request.form['CRITICAL_LOADS'])
	mg_method = request.form['MG_DEF_METHOD']
	MGQUANT = int(json.loads(request.form['mgQuantity']))
	if mg_method == 'loadGrouping':
		pairings = json.loads(request.form['MICROGRIDS'])
		microgrids = mg_group(dss_path, crit_loads, 'loadGrouping', pairings)	
	elif mg_method == 'manual':
		algo_params = json.loads(request.form['MICROGRIDS'])
		microgrids = mg_group(dss_path, crit_loads, 'manual', algo_params)
	elif mg_method == 'lukes':
		microgrids = mg_group(dss_path, crit_loads, 'lukes')
	elif mg_method == 'branch':
		microgrids = mg_group(dss_path, crit_loads, 'branch')
	elif mg_method == 'bottomUp':
		microgrids = mg_group(dss_path, crit_loads, 'bottomUp', algo_params={'num_mgs':MGQUANT})
	elif mg_method == 'criticalLoads':
		microgrids = mg_group(dss_path, crit_loads, 'criticalLoads', algo_params={'num_mgs':MGQUANT})
	elif mg_method == '': 
		microgrids = json.loads(request.form['MICROGRIDS'])
	# Form REOPT_INPUTS. 
	REOPT_INPUTS = {
		'energyCost':request.form['energyCost'],
		'wholesaleCost':request.form['wholesaleCost'],
		'demandCost':request.form['demandCost'],
		'solarCanCurtail':(request.form['solarCanCurtail'] == 'true'),
		'solarCanExport':(request.form['solarCanExport'] == 'true'),
		'urdbLabelSwitch':request.form['urdbLabelSwitch'],
		'urdbLabel':request.form['urdbLabel'],
		'year':request.form['year'],
		'analysisYears':request.form['analysisYears'],
		'outageDuration':request.form['outageDuration'],
		'value_of_lost_load':request.form['value_of_lost_load'],
		'single_phase_relay_cost':request.form['single_phase_relay_cost'],
		'three_phase_relay_cost':request.form['three_phase_relay_cost'],
		'omCostEscalator':request.form['omCostEscalator'],
		'discountRate':request.form['discountRate'],
		'solar':request.form['solar'],
		'battery':request.form['battery'],
		'fossil':request.form['fossil'],
		'wind':request.form['wind'],
		'solarCost':request.form['solarCost'],
		'solarMax':request.form['solarMax'],
		'solarMin':request.form['solarMin'],
		'solarMacrsOptionYears':request.form['solarMacrsOptionYears'],
		'solarItcPercent':request.form['solarItcPercent'],
		'batteryCapacityCost':request.form['batteryCapacityCost'],
		'batteryCapacityMax':request.form['batteryCapacityMax'],
		'batteryCapacityMin':request.form['batteryCapacityMin'],
		'batteryPowerCost':request.form['batteryPowerCost'],
		'batteryPowerMax':request.form['batteryPowerMax'],
		'batteryPowerMin':request.form['batteryPowerMin'],
		'batteryMacrsOptionYears':request.form['batteryMacrsOptionYears'],
		'batteryItcPercent':request.form['batteryItcPercent'],
		'batteryPowerCostReplace':request.form['batteryPowerCostReplace'],
		'batteryCapacityCostReplace':request.form['batteryCapacityCostReplace'],
		'batteryPowerReplaceYear':request.form['batteryPowerReplaceYear'],
		'batteryCapacityReplaceYear':request.form['batteryCapacityReplaceYear'],
		'dieselGenCost':request.form['dieselGenCost'],
		'dieselMax':request.form['dieselMax'],
		'dieselMin':request.form['dieselMin'],
		'fuelAvailable':request.form['fuelAvailable'],
		'minGenLoading':request.form['minGenLoading'],
		'dieselFuelCostGal':request.form['dieselFuelCostGal'],
		'dieselCO2Factor':request.form['dieselCO2Factor'],
		'dieselOMCostKw':request.form['dieselOMCostKw'],
		'dieselOMCostKwh':request.form['dieselOMCostKwh'],
		'dieselOnlyRunsDuringOutage':(request.form['dieselOnlyRunsDuringOutage'] == 'true'),
		'dieselMacrsOptionYears':request.form['dieselMacrsOptionYears'],
		'windCost':request.form['windCost'],
		'windMax':request.form['windMax'],
		'windMin':request.form['windMin'],
		'windMacrsOptionYears':request.form['windMacrsOptionYears'],
		'windItcPercent':request.form['windItcPercent'],
		'mgParameterOverrides': json.loads(request.form['mgParameterOverrides'])
	}
	mgu_args = [
		f'{_projectDir}/{request.form["MODEL_DIR"]}',
		dss_path,
		csv_path,
		float(request.form['QSTS_STEPS']),
		REOPT_INPUTS,
		microgrids,
		request.form['FAULTED_LINES'],
		request.form['DESCRIPTION'],
		True,
		outages_path if have_outages else None
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
	for e in elements:
		e['type'] = e['class']
		e['name'] = e['text']
	templateDssTree = [OrderedDict(item) for item in test_params['templateDssTree']]
	# Testing jsonToDss().
	for _dir in wizard_dir:
		dssFilePath = jsonToDss(_dir, lat, lon, elements, True, 'true')
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