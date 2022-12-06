import os
from pprint import pprint as pp
import networkx as nx
import pygraphviz
from matplotlib import pyplot as plt
import base64
import io 
import json
from flask import Flask, flash, request, redirect, url_for, render_template
from werkzeug.utils import secure_filename
from omf.solvers.opendss import dssConvert
from microgridup_gen_mgs import nx_group_branch, nx_group_lukes, nx_bottom_up_branch, nx_critical_load_branch
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
	# Convert to DSS and return loads.
	elements = request.get_json()
	dssString = 'clear \nset defaultbasefrequency=60 \n'
	for ob in elements:
		obType = ob['class']
		obName = ob['text']
		if obType == 'sub':
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
	with open("creation.dss", "w") as outFile:
		outFile.writelines(dssString)
	loads = getLoads('creation.dss')
	return json.dumps(loads)

@app.route('/uploadajax', methods = ['GET','POST'])
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
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
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            print(filename)
            loads = getLoads(file.filename)
            print('dumps',json.dumps(loads))
            return json.dumps(loads)
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
	print('path',path)
	tree = dssConvert.dssToTree(path)
	loads = [obj.get('object','').split('.')[1] for obj in tree if 'load.' in obj.get('object','')]
	print('loads',loads)
	return loads

if __name__ == "__main__":
	app.run(debug=True)
