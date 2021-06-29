import microgridup
import flask
import platform
import multiprocessing
import os
import shutil
import werkzeug
import microgridup
import json

_myDir = os.path.abspath(os.path.dirname(__file__))

app = flask.Flask(__name__, static_folder='', template_folder='') #TODO: we cannot make these folders the root.

def list_analyses():
	return [x for x in os.listdir(_myDir) if os.path.isdir(x) and os.path.isfile(f'{x}/circuit.dss')] #TODO: fix this gross hack.

@app.route('/')
def home():
	analyses = list_analyses()
	return flask.render_template('template_home.html', analyses=analyses) 

@app.route('/load/<analysis>')
def load(analysis):
	if 'output_final.html' in os.listdir(analysis):
		return flask.redirect(f'/{analysis}/output_final.html')
	else:
		return 'Model Running. Please reload to check for completion.'

@app.route('/new')
def new():
	return flask.render_template('template_new.html')

@app.route('/duplicate/', methods=["POST"])
def duplicate():
	analysis = flask.request.form.get('analysis')
	new_name = flask.request.form.get('new_name')
	analyses = list_analyses()
	if (analysis not in analyses) or (new_name in analyses):
		return 'Duplication failed. Analysis does not exist or the new name is invalid.'
	else:
		shutil.copytree(analysis, new_name)
		return f'Successfully duplicate {analysis} as {new_name}.'

@app.route('/run', methods=["POST"])
def run():
	all_files = flask.request.files
	model_dir = flask.request.form['MODEL_DIR']
	# Save the files.
	if not os.path.isdir(f'{_myDir}/uploads'):
		os.mkdir(f'{_myDir}/uploads')
	dss_file = all_files['BASE_DSS']
	dss_file.save(f'{_myDir}/uploads/BASE_DSS_{model_dir}')
	csv_file = all_files['LOAD_CSV']
	csv_file.save(f'{_myDir}/uploads/LOAD_CSV_{model_dir}')
	# ARGS
	mgu_args = [
		flask.request.form['MODEL_DIR'],
		f'{_myDir}/uploads/BASE_DSS_{model_dir}',
		f'{_myDir}/uploads/LOAD_CSV_{model_dir}',
		float(flask.request.form['QSTS_STEPS']),
		float(flask.request.form['FOSSIL_BACKUP_PERCENT']),
		json.loads(flask.request.form['REOPT_INPUTS']),
		json.loads(flask.request.form['MICROGRIDS']),
		flask.request.form['FAULTED_LINE']
	]
	# Kickoff the run
	new_proc = multiprocessing.Process(target=microgridup.full, args=mgu_args)
	new_proc.start()
	# Simple return message
	return f'<pre>{flask.request.form}\n\n{all_files}</pre>' #TODO:actually kick off a run and handle uploads.

if __name__ == "__main__":
	if platform.system() == "Darwin":  # MacOS
		os.environ['NO_PROXY'] = '*' # Workaround for macOS proxy behavior
		multiprocessing.set_start_method('forkserver') # Workaround for Catalina exec/fork behavior
	app.run(debug=True, host="0.0.0.0")