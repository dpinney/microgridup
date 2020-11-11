from omf.solvers import opendss
from omf.solvers.opendss import dssConvert
from omf import distNetViz
from omf import geo
import os

DSS_NAME = 'lehigh.dss'
OMD_NAME = 'lehigh.dss.omd'
ONELINE_NAME = 'lehigh.oneline.html'
MAP_NAME = 'lehigh_map'

# generate an OMD
if not os.path.isfile(OMD_NAME):
	tree = dssConvert.dssToTree(DSS_NAME)
	evil_glm = dssConvert.evilDssTreeToGldTree(tree)
	dssConvert.evilToOmd(evil_glm, OMD_NAME)
	#todo: edit load coordinates.

# draw the circuit
if not os.path.isfile(ONELINE_NAME):
	distNetViz.viz(OMD_NAME, forceLayout=False, outputPath='.', outputName=ONELINE_NAME, open_file=False)

# draw the map
if not os.path.isdir(MAP_NAME):
	geo.mapOmd(OMD_NAME, MAP_NAME, 'html', openBrowser=False, conversion=False, offline=True)

# voltage and current plotting
opendss.voltagePlot(DSS_NAME, PU=False)
opendss.currentPlot(DSS_NAME)

def the_whole_shebang(allInputData, modelDir, resilientDist=False):
	if resilientDist:
		allInputData['omd'] = resilientDist()
		design_options = microgridDesign(candidate_gens_from_circuit)
	else:
		design_options = microgridDesign(set_of_loads_on_circuit)
	for option in design_options:
		derInterconnection(option) # Optional: weed out all the circuits in option that fail the screens.
	for option in design_options:
		microgridControl(option)
	return allOutputData

'''
translate coordinates to florida?
	Could just move the x,y coords
	Could convert in geo.py
	LatLongCoords might be helpful?
'''