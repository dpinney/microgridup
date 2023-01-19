import multiprocessing
import os
from pprint import pprint as pp
import time
import networkx as nx
import microgridup
from matplotlib import pyplot as plt
import base64
import io 
import json
from flask import Flask, flash, request, redirect, render_template, jsonify
from werkzeug.utils import secure_filename
from omf.solvers.opendss import dssConvert
from microgridup_gen_mgs import mg_group, nx_group_branch, nx_group_lukes, nx_bottom_up_branch, nx_critical_load_branch
_myDir = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = _myDir
ALLOWED_EXTENSIONS = {'dss'}

app = Flask(__name__, static_folder='', template_folder='') #TODO: we cannot make these folders the root.
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def newGui():
	with open(f'{_myDir}/lehigh_3mg_inputs.json') as default_in_file:
		default_in = json.load(default_in_file)
	return render_template('thomas_wip_frontend.html', in_data=default_in)

@app.route('/jsonToDss', methods=['GET','POST'])
def jsonToDss():
	model_dir = request.form['MODEL_DIR']
	# Convert to DSS and return loads.
	elements = json.loads(request.form['json'])
	dssString = 'clear \nset defaultbasefrequency=60 \n'
	for ob in elements:
		obType = ob['class']
		obName = ob['text']
		if obType == 'substation':
			dssString += f'new object=vsource.{obName.replace(" ","")} basekv=4.16 pu=1.00 r1=0 x1=0.0001 r0=0 x0=0.0001 \n'
		elif obType == 'feeder':
			dssString += f'new object=transformer.{obName.replace(" ","")} phases=3 windings=2 xhl=2 conns=[wye,wye] kvs=[4.16,0.480] kvas=[500,500] %rs=[0.55,0.55] xht=1 xlt=1 \n'
		elif obType == 'load':
			dssString += f'new object=load.{obName.replace(" ","")} phases=1 conn=wye model=1 kv=2.4 kw=1155 kvar=660 \n'
		elif obType == 'solar':
			dssString += f'new object=generator.{obName.replace(" ","")} phases=3 kv=2.4 kw=800 pf=1 \n'
		elif obType == 'wind':
			dssString += f'new object=generator.{obName.replace(" ","")} phases=1 kv=2.4 kw=50 pf=1 \n'
		elif obType == 'battery':
			dssString += f'new object=storage.{obName.replace(" ","")} phases=1 kv=2.4 kwrated=20 kwhstored=100 kwhrated=100 dispmode=follow %charge=100 %discharge=100 %effcharge=96 %effdischarge=96 %idlingkw=0 \n'
		elif obType == 'diesel':
			dssString += f'new object=generator.{obName.replace(" ","")} phases=1 kw=81 pf=1 kv=2.4 xdp=0.27 xdpp=0.2 h=2 \n'	
	dssString += 'set voltagebases=[115,4.16,0.48]\ncalcvoltagebases'
	if not os.path.isdir(f'{_myDir}/uploads'):
		os.mkdir(f'{_myDir}/uploads')
	# file.save(f'{_myDir}/uploads/BASE_DSS_{model_dir}')
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
			# file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
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
	model_dir = request.form['MODEL_DIR']
	if 'BASE_DSS_NAME' in request.form and 'LOAD_CSV_NAME' in request.form:
		print('we are editing an existing model')
		# editing an existing model
		dss_path = f'{_myDir}/{model_dir}/circuit.dss'
		csv_path = f'{_myDir}/{model_dir}/loads.csv'
		all_files = 'Using Existing Files'
	else:
		# new files uploaded
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
	# Handle arguments to our main function.
	crit_loads = json.loads(request.form['CRITICAL_LOADS'])
	mg_method = request.form['MG_DEF_METHOD']
	if mg_method == 'manual':
		microgrids = json.loads(request.form['MICROGRIDS'])
	elif mg_method == 'lukes':
		microgrids = mg_group(dss_path, crit_loads, 'lukes')
	elif mg_method == 'branch':
		microgrids = mg_group(dss_path, crit_loads, 'branch')
	elif mg_method == 'bottomUp':
		microgrids = mg_group(dss_path, crit_loads, 'bottomUp')
	elif mg_method == 'criticalLoads':
		microgrids = mg_group(dss_path, crit_loads, 'criticalLoads')
	# Form REOPT_INPUTS. TODO: Handle uploaded CSVs for HISTORICAL_OUTAGES and criticalLoadShapeFile. Put both in models folder.    
	REOPT_INPUTS = {
		'latitude':request.form['latitude'],
		'longitude':request.form['longitude'],
		'energyCost':request.form['energyCost'],
		'wholesaleCost':request.form['wholesaleCost'],
		'demandCost':request.form['demandCost'],
		'solarCanCurtail':request.form['solarCanCurtail'],
		'solarCanExport':request.form['solarCanExport'],
		'urdbLabelSwitch':request.form['urdbLabelSwitch'],
		'urdbLabel':request.form['urdbLabel'],
		'criticalLoadFactor':request.form['criticalLoadFactor'],
		'year':request.form['year'],
		'analysisYears':request.form['analysisYears'],
		'outageDuration':request.form['outageDuration'],
		'DIESEL_SAFETY_FACTOR':request.form['DIESEL_SAFETY_FACTOR'],
		'outage_start_hour':request.form['outage_start_hour'],
		'userCriticalLoadShape':request.form['userCriticalLoadShape'],
		'value_of_lost_load':request.form['value_of_lost_load'],
		'omCostEscalator':request.form['omCostEscalator'],
		'discountRate':request.form['discountRate'],

		'solar':request.form['solar'],
		'battery':request.form['battery'],
		'fossil':request.form['fossil'],
		'wind':request.form['wind'],
		'solarCost':request.form['solarCost'],
		'solarExisting':request.form['solarExisting'],
		'solarMax':request.form['solarMax'],
		'solarMin':request.form['solarMin'],
		'solarMacrsOptionYears':request.form['solarMacrsOptionYears'],
		'solarItcPercent':request.form['solarItcPercent'],
		'batteryCapacityCost':request.form['batteryCapacityCost'],
		'batteryCapacityMax':request.form['batteryCapacityMax'],
		'batteryCapacityMin':request.form['batteryCapacityMin'],
		'batteryKwhExisting':request.form['batteryKwhExisting'],
		'batteryPowerCost':request.form['batteryPowerCost'],
		'batteryPowerMax':request.form['batteryPowerMax'],
		'batteryKwExisting':request.form['batteryKwExisting'],
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
		'genExisting':request.form['genExisting'],
		'minGenLoading':request.form['minGenLoading'],
		'dieselFuelCostGal':request.form['dieselFuelCostGal'],
		'dieselCO2Factor':request.form['dieselCO2Factor'],
		'dieselOMCostKw':request.form['dieselOMCostKw'],
		'dieselOMCostKwh':request.form['dieselOMCostKwh'],
		'dieselOnlyRunsDuringOutage':request.form['dieselOnlyRunsDuringOutage'],
		'dieselMacrsOptionYears':request.form['dieselMacrsOptionYears'],
		'windCost':request.form['windCost'],
		'windExisting':request.form['windExisting'],
		'windMax':request.form['windMax'],
		'windMin':request.form['windMin'],
		'windMacrsOptionYears':request.form['windMacrsOptionYears'],
		'windItcPercent':request.form['windItcPercent'],
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
	# Kickoff the run
	new_proc = multiprocessing.Process(target=microgridup.full, args=mgu_args)
	new_proc.start()
	# Redirect to home after waiting a little for the file creation to happen.
	time.sleep(3)
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
	app.run(debug=True)
