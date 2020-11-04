from omf.solvers import opendss
from omf.solvers.opendss import dssConvert
from omf import distNetViz
from omf import geo
import os

DSS_NAME = 'ieee123_solarRamp.clean.dss'
OMD_NAME = 'ieee123_solarRamp.clean.dss.omd'
ONELINE_NAME = 'ieee123_solarRamp.oneline.html'
MAP_NAME = 'ieee123_solarRamp_map'

# generate an OMD
if not os.path.isfile(OMD_NAME):
	tree = dssConvert.dssToTree(DSS_NAME)
	evil_glm = dssConvert.evilDssTreeToGldTree(tree)
	dssConvert.evilToOmd(evil_glm, OMD_NAME)

# draw the circuit
if not os.path.isfile(ONELINE_NAME):
	distNetViz.viz(OMD_NAME, forceLayout=False, outputPath='.', outputName=ONELINE_NAME, open_file=False)

# draw the map
if not os.path.isdir(MAP_NAME):
	geo.mapOmd(OMD_NAME, MAP_NAME, 'html', openBrowser=False, conversion=False, offline=True)

# voltage and current plotting
opendss.voltagePlot(DSS_NAME, PU=False)
opendss.currentPlot(DSS_NAME)

'''
add (more) DG?
get the loadshapes into opendss.
translate coordinates to florida?
	Could just move the x,y coords
	Could convert in geo.py
	LatLongCoords might be helpful?
'''