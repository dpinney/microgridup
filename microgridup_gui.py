import microgridup
import flask
import platform
import multiprocessing
import os

_myDir = os.path.abspath(os.path.dirname(__file__))

app = flask.Flask(__name__, static_folder='', template_folder='') #TODO: we cannot make these folders the root.

@app.route('/')
def home():
	analyses = [x for x in os.listdir(_myDir) if os.path.isdir(x) and os.path.isfile(f'{x}/circuit.dss')] #TODO: fix this gross hack.
	return flask.render_template('template_home.html', analyses=analyses) 

@app.route('/load/<analysis>')
def load(analysis):
	#TODO: check if the model is running or complete.
	return flask.redirect(f'/{analysis}/output_final.html')

@app.route('/new')
def new():
	return flask.render_template('template_new.html') #TODO: actually handle uploads https://pythonbasics.org/flask-upload-file/

@app.route('/run', methods=["POST"])
def run_post():
	return flask.request.form #TODO:actually kick off a run.

if __name__ == "__main__":
	if platform.system() == "Darwin":  # MacOS
		os.environ['NO_PROXY'] = '*' # Workaround for above in python3.
		multiprocessing.set_start_method('forkserver') # Workaround for new Catalina exec/fork behavior
	app.run(debug=True, host="0.0.0.0")