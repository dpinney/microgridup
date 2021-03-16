import random, re, datetime, json, os, tempfile, shutil, csv, math, base64
from os.path import join as pJoin
import subprocess
import pandas as pd
import numpy as np
import scipy
import collections
from scipy import spatial
import scipy.stats as st
from sklearn.preprocessing import LabelEncoder
import matplotlib.pyplot as plt
import plotly as py
import plotly.graph_objs as go
from plotly.tools import make_subplots

# OMF imports
import omf
from omf import geo
from omf import distNetViz
from omf.models import __neoMetaModel__
from omf.models.__neoMetaModel__ import *
from omf.models import flisr
from omf.solvers.opendss import dssConvert
from omf.solvers import opendss

# Model metadata:
# tooltip = 'outageCost calculates reliability metrics and creates a leaflet graph based on data from an input csv file.'
# modelName, template = __neoMetaModel__.metadata(__file__)
# hidden = True

def createListOfBuses(microgrids, badBuses):
	'helper function to get a list of microgrid diesel generators'
	
	# sort the diesel generators of the microgrids by maximum potential
	sortvals = {}
	for key in microgrids:
		sortvals[key] = microgrids[key].get('max_potential','')
	sortvals = sorted(sortvals.items(), key=lambda x: x[1], reverse=True)

	# create a list of the diesel buses
	buses = []
	for key in sortvals:
		buses.append(microgrids[key[0]].get('gen_bus', ''))
	buses = [x for x in buses if x not in badBuses]
	return buses

def play(pathToOmd, pathToDss, pathToTieLines, workDir, microgrids, faultedLine, radial, outageStart, lengthOfOutage, switchingTime):
	# 1) isolate the fault (using step one of flisr model)
	if not workDir:
		workDir = tempfile.mkdtemp()
		print('@@@@@@', workDir)

	# read in the tree
	with open(pathToOmd) as inFile:
		tree = json.load(inFile)['tree']

	# find a node associated with the faulted line
	faultedNode = ''
	faultedNode2 = ''
	for key in tree.keys():
		if tree[key].get('name','') == faultedLine:
			faultedNode = tree[key]['from']
			faultedNode2 = tree[key]['to']

	# initialize the list of ties closed and reclosers opened
	bestTies = []
	bestReclosers = []
	actionsDict = {}

	# get a list of all the generating buses on the different microgrid systems
	buses = []
	for key in microgrids.keys():
		buses.append(microgrids[key].get('gen_bus', ''))
	
	# isolate the fault
	tree, bestReclosers, badBuses = flisr.cutoffFault(tree, faultedNode, bestReclosers, workDir, radial, buses)

	# 2) get a list of loads associated with each microgrid component
	# and create a loadshape containing all of said loads
	if switchingTime <= lengthOfOutage:
		totalTime, timePassed, busShapes, leftOverBusShapes, leftOverLoad = playOneStep(tree, bestReclosers, badBuses, pathToDss, switchingTime, outageStart, outageStart, None, None, None, 0)

		key = 0
		initialTimePassed = outageStart
		while key < len(bestReclosers):
			recloserName = bestReclosers[key].get('name','')
			lineAction = 'open'
			actionsDict[recloserName] = {'timePassed':initialTimePassed, 'lineAction':lineAction}
			initialTimePassed+=1
			key+=1

	# read in the set of tie lines on the system as a dataframe
	if pathToTieLines != None:
		tieLines = pd.read_csv(pathToTieLines)
	
		#start the restoration piece of the algorithm
		index = 0
		terminate = False
		goTo4 = False
		goTo3 = False
		goTo2 = True
		while (terminate == False) and ((timePassed+switchingTime) < lengthOfOutage):
			# Step 2
			if goTo2 == True:
				goTo2 = False
				goTo3 = True
				unpowered, powered, potentiallyViable = flisr.listPotentiallyViable(tree, tieLines, workDir)
				# print(potentiallyViable)
			# Step 3
			if goTo3 == True:
				goTo3 = False
				goTo4 = True
				openSwitch = flisr.chooseOpenSwitch(potentiallyViable)
			# Step 4
			if goTo4 == True:
				goTo4 = False
				tree, potentiallyViable, tieLines, bestTies, bestReclosers, goTo2, goTo3, terminate, index = flisr.addTieLines(tree, faultedNode, potentiallyViable, unpowered, powered, openSwitch, tieLines, bestTies, bestReclosers, workDir, goTo2, goTo3, terminate, index, radial)
				if goTo2 == True:
					totalTime, timePassed, busShapes, leftOverBusShapes, leftOverLoad = playOneStep(tree, bestReclosers, badBuses, pathToDss, switchingTime, timePassed, outageStart, busShapes, leftOverBusShapes, leftOverLoad, totalTime)
					key = 0
					while key < len(bestReclosers):
						recloserName = bestReclosers[key].get('name','')
						if recloserName not in actionsDict.keys():
							lineAction = 'open'
							actionsDict[recloserName] = {'timePassed':timePassed, 'lineAction':lineAction}
						key+=1
					key = 0
					while key < len(bestTies):
						tieName = bestTies[key].get('name','')
						if tieName not in actionsDict.keys():
							lineAction = 'close'
							actionsDict[tieName] = {'timePassed':timePassed, 'lineAction':lineAction}
						key+=1

	# when the outage is over, switch back to the main sourcebus
	buses = createListOfBuses(microgrids, badBuses)

	listOfZeroes = [0] * (totalTime-lengthOfOutage-4)

	while len(buses) > 0:
		phase = 0
		while phase < 3:
			if buses[0] in busShapes.keys():
				if busShapes[buses[0]][phase]:
					busShapes[buses[0]][phase] = busShapes[buses[0]][phase][0 : lengthOfOutage]
					busShapes[buses[0]][phase] = busShapes[buses[0]][phase] + listOfZeroes
					busShapes[buses[0]][phase] = [x / 1 for x in busShapes[buses[0]][phase]]
			phase+=1
		del(buses[0])
	# print(busShapes)

	tree = solveSystem(busShapes, actionsDict, microgrids, tree, pathToDss, badBuses, bestReclosers, bestTies, lengthOfOutage)

def playOneStep(tree, bestReclosers, badBuses, pathToDss, switchingTime, timePassed, outageStart, busShapes, leftOverBusShapes, leftOverLoad, totalTime):
	'function that prepares a single timestep of the simulation to be solved'
	
	# create a list of the diesel generators
	buses = createListOfBuses(microgrids, badBuses)

	# if there aren't any new diesel generators shapes yet, create them from the beginning!
	if busShapes == None:
		totalTime = 0
		# busShapes is the actual shape for the diesel generators
		busShapes = {}
		# lefOverBusShapes is the amount of load that cannot be supported by a generator (used for networking)
		leftOverBusShapes = {}
		# leftOverLoad keeps track of whether or not there is any amount of unsupported load for a generator with binaries
		leftOverLoad = {}

	# initialize the array keeping track of all connected subtrees
	subtrees = {}

	# for each power source
	while len(buses) > 0:
		# create an adjacency list representation of tree connectivity
		adjacList, reclosers, vertices = flisr.adjacencyList(tree)
		bus = buses[0]
		# initialize a dictionary to store the loadshapes
		loadShapes = {}
		# keep track of whether a bus has been seen already
		alreadySeen = False
		# check to see if there is a path between the power source and the fault 
		subtree = flisr.getMaxSubtree(adjacList, bus)
		for key in subtrees:
			if set(subtrees[key]) == set(subtree):
				# if a larger generator is already supplying power, have a smaller generator only pick up the remaining load
				dieselShapes = {}
				leftOverShapes = {}
				dieselShapesNew = {}
				leftOverHere = {}
				maximum = 1.0
				for entry in microgrids:
					if bus == microgrids[entry].get('gen_bus', ''):
						maximum = microgrids[entry].get('max_potential', '')
						k = 0
						while k < 3:
							val = 0
							while val < len(leftOverLoad[key][k]):
								if k == 0:
									if not '.1' in dieselShapes.keys():
										dieselShapes['.1'] = []
									if leftOverLoad[key][k][val] == True:
										dieselShapes['.1'].append(leftOverBusShapes[key][k][val])
									else:
										dieselShapes['.1'].append(0.0)
								if k == 1:
									if not '.2' in dieselShapes.keys():
										dieselShapes['.2'] = []
									if leftOverLoad[key][k][val] == True:
										dieselShapes['.2'].append(leftOverBusShapes[key][k][val])
									else:
										dieselShapes['.2'].append(0.0)
								if k == 2:
									if not '.3' in dieselShapes.keys():
										dieselShapes['.3'] = []
									if leftOverLoad[key][k][val] == True:
										dieselShapes['.3'].append(leftOverBusShapes[key][k][val])
									else:
										dieselShapes['.3'].append(0.0)
								val += 1
							k += 1
						for shape in dieselShapes:
							if not shape in dieselShapesNew.keys():
								dieselShapesNew[shape] = []
							if not shape in leftOverShapes.keys():
								leftOverShapes[shape] = []
							if not shape in leftOverHere.keys():
								leftOverHere[shape] = []
							for entry in dieselShapes[shape]:
								if (float(maximum) - float(entry)) >= 0:
									dieselShapesNew[shape].append(float(entry))
									leftOverShapes[shape].append(0.0)
									leftOverHere[shape].append(False)
								else:
									dieselShapesNew[shape].append(float(maximum))
									leftOverShapes[shape].append(float(entry)-float(maximum))
									leftOverHere[shape].append(True)
				# note that the generator has already been seen in this round of the algorithm
				alreadySeen = True
				# add the connected subtree to the dictionary of all subtrees
				subtrees[bus] = subtree
				# remove the old bus from the dictionary of subtrees to avoid repetition/bugs
				subtrees.pop(key)
		# if the subtree associated with a generator is connected to the sourcebus, we don't need to supply any power with the generator
		if 'sourcebus' in subtree:
			del(buses[0])
			continue
		# if the subtree associated with a specific diesel generator hasn't yet been supported by a different diesel generator, add the biggest
		if alreadySeen == False:
			# only consider loads in the subtree connected to the generator
			for node in subtree:
				for key in tree.keys():
					obtype = tree[key].get('object','')
					if obtype == 'load' or obtype == 'triplex_load':
						if tree[key].get('parent','').startswith(str(node)):
							# add the loads together to figure out how much needs to be supported in total
							loadshapeName = tree[key].get('yearly', '')
							for key1 in tree.keys():
								if tree[key1].get('name','') == loadshapeName:
									loadshape = eval(tree[key1].get('mult',''))
									if '.1' in tree[key].get('!CONNCODE',''):
										if '.1' in loadShapes:
											loadShapes['.1'] = [a + b for a, b in zip(loadShapes.get('.1',''), loadshape)]
										else: loadShapes['.1'] = loadshape
									if '.2' in tree[key].get('!CONNCODE',''):
										if '.2' in loadShapes:
											loadShapes['.2'] = [a + b for a, b in zip(loadShapes.get('.2',''), loadshape)]
										else: loadShapes['.2'] = loadshape
									if '.3' in tree[key].get('!CONNCODE',''):
										if '.3' in loadShapes:
												loadShapes['.3'] = [a + b for a, b in zip(loadShapes.get('.3',''), loadshape)]
										else: loadShapes['.3'] = loadshape
			# Obtain the diesel loadshape by subtracting off solar from load and populate the loadshape dictionaries
			dieselShapes = {}
			leftOverShapes = {}
			dieselShapesNew = {}
			leftOverHere = {}
			maximum = 1.0
			# check if there exists a solar generator connected to the generating bus of the microgrid under consideration
			solarExists = False
			for key in tree.keys():
				if tree[key].get('object','').startswith('generator'):
					if tree[key].get('name','').startswith('solar') and tree[key].get('parent','') == bus:
						# get the name of the solar loadshape
						solarshapeName = tree[key].get('yearly','')
						# if this is the first microgrid to support the connected subtree, consider solar. Otherwise, don't.
						if alreadySeen == False:
							for key1 in tree.keys():
								# if the solar loadshape exists in the tree, get the loadshape itself
								if tree[key1].get('name','') == solarshapeName:
									solarshape = eval(tree[key1].get('mult',''))
									solarExists = True
			for entry in microgrids:
				# populate the dieselShapes dictionary with the values of solar subtracted from total load needed to be supported
				if buses[0] == microgrids[entry].get('gen_bus', ''):
					maximum = microgrids[entry].get('max_potential', '')
					if '.1' in loadShapes:
						if len(loadShapes.get('.1','')) > totalTime:
							totalTime = len(loadShapes.get('.1',''))
						if solarExists == True:
							dieselShapes['.1'] = [a - b for a, b in zip(loadShapes.get('.1',''), solarshape)]
						else:
							dieselShapes['.1'] = loadShapes.get('.1','')
					if '.2' in loadShapes:
						if len(loadShapes.get('.2','')) > totalTime:
							totalTime = len(loadShapes.get('.2',''))
						if solarExists == True:
							dieselShapes['.2'] = [a - b for a, b in zip(loadShapes.get('.2',''), solarshape)]
						else:
							dieselShapes['.2'] = loadShapes.get('.2','')
					if '.3' in loadShapes:
						if len(loadShapes.get('.3','')) > totalTime:
							totalTime = len(loadShapes.get('.3',''))
						if solarExists == True:
							dieselShapes['.3'] = [a - b for a, b in zip(loadShapes.get('.3',''), solarshape)]
						else:
							dieselShapes['.3'] = loadShapes.get('.3','')
			# check if the needed diesel generation exceeds the maximum potential of the generator.
			for shape in dieselShapes:
				if not shape in dieselShapesNew.keys():
					dieselShapesNew[shape] = []
				if not shape in leftOverShapes.keys():
					leftOverShapes[shape] = []
				if not shape in leftOverHere.keys():
					leftOverHere[shape] = []
				# if the needed power does not exceed the max, it is fully supported by the diesel
				for entry in dieselShapes[shape]:
					if (float(maximum) - float(entry)) >= 0:
						dieselShapesNew[shape].append(float(entry))
						leftOverShapes[shape].append(0.0)
						leftOverHere[shape].append(False)
					# otherwise, keep track of how much load cannot be supported so it can be supported by other generators
					else:
						dieselShapesNew[shape].append(float(maximum))
						leftOverShapes[shape].append(float(entry)-float(maximum))
						leftOverHere[shape].append(True)
		# if it's the beinning of the simulation, fill the whole loadshape
		if timePassed == outageStart:
			listOfZeroes = [0] * (totalTime)
			listOfFalse = [False] * (totalTime)
			busShapes[buses[0]] = [listOfZeroes, listOfZeroes, listOfZeroes]
			leftOverBusShapes[buses[0]] = [listOfZeroes, listOfZeroes, listOfZeroes]
			leftOverLoad[buses[0]] = [listOfFalse, listOfFalse, listOfFalse]
		# otherwise, only fill up the values beyond the current timestep
		phase = 0
		while phase < 3:
			if buses[0] in busShapes.keys():
				if busShapes[buses[0]][phase]:
					busShapes[buses[0]][phase] = busShapes[buses[0]][phase][0 : timePassed]
					leftOverBusShapes[buses[0]][phase] = leftOverBusShapes[buses[0]][phase][0 : timePassed]
					leftOverLoad[buses[0]][phase] = leftOverLoad[buses[0]][phase][0 : timePassed]
					dieselShapesNew['.' + str(phase + 1)] = dieselShapesNew.get('.' + str(phase + 1),'')[timePassed : totalTime]
					leftOverShapes['.' + str(phase + 1)] = leftOverShapes.get('.' + str(phase + 1),'')[timePassed : totalTime]
					leftOverHere['.' + str(phase + 1)] = leftOverHere.get('.' + str(phase + 1),'')[timePassed : totalTime]
					busShapes[buses[0]][phase] = list(busShapes[buses[0]][phase]) + list(dieselShapesNew.get('.' + str(phase + 1),''))
					leftOverBusShapes[buses[0]][phase] = list(leftOverBusShapes[buses[0]][phase]) + list(leftOverShapes.get('.' + str(phase + 1),''))
					leftOverLoad[buses[0]][phase] = list(leftOverLoad[buses[0]][phase]) + list(leftOverHere.get('.' + str(phase + 1),''))
			phase+=1
		# add the subtree to the dictionary of all subtrees to note that it is at least partially supported (and we've considered solar)
		subtrees[bus] = subtree
		# remove the bus from the list of buses we still need to consider
		del(buses[0])

	reverseImportanceOfLoads = ['675b_residential1', '675c_residential1', '652_residential', '692_warehouse2', '611_runway', '675a_hospital']

	# implement load shedding if total load is unsupported by the total generation
	allLoads = {}
	for element in subtrees.keys():

		# check if there's leftover load on any individual phase of a microgrid system
		# and if there is, get the maximum leftover load
		if element in leftOverBusShapes.keys():
			for phase in leftOverBusShapes[element]:
				maxTimeValue = 0.0
				time = 0
				for timeValue in phase:
					time += 1
					if timeValue > 0.0 and timeValue > maxTimeValue:
						maxTimeValue = timeValue
						maxTime = time

				# continue shedding load until all the loads not shed are supported
				while maxTimeValue > 0.0:

					# fill a dictionary of all loads connected to the microgrid and their corresponding loadshapes			
					for node in subtrees[element]:
						for key in tree.keys():
							obtype = tree[key].get('object','')
							if obtype == 'load' or obtype == 'triplex_load':
								if tree[key].get('parent','').startswith(str(node)):
									parent = tree[key].get('parent','')
									loadshapeName = tree[key].get('yearly', '')
									loadName = tree[key].get('name', '')
									for key1 in tree.keys():
										if tree[key1].get('name','') == loadshapeName:
											loadshape = eval(tree[key1].get('mult',''))
											allLoads[loadName] = loadshape
					
					# shed one load at a time, starting with the least important
					loadElement = reverseImportanceOfLoads[0]
			

	# update the amount of time that has passed in the simulation
	timePassed = timePassed + switchingTime
	return totalTime, timePassed, busShapes, leftOverBusShapes, leftOverLoad

def solveSystem(busShapes, actionsDict, microgrids, tree, pathToDss, badBuses, bestReclosers, bestTies, lengthOfOutage):
	'Add diesel generation to the opendss formatted system and solve using OpenDSS'
	
	# get a sorted list of the buses
	buses = createListOfBuses(microgrids, badBuses)

	# indices for keeping track of which entries have been updated already
	i = 0
	j = 0

	# initialize dictionaries to store the shapes that are to be inserted into the .dss file
	shape_insert_list = {}
	gen_insert_list = {}

	# for every generating bus
	while len(buses) > 0:
		# get the connected subtree
		adjacList, reclosers, vertices = flisr.adjacencyList(tree)
		bus = buses[0]
		subtree = flisr.getMaxSubtree(adjacList, bus)
		# if the source is in the subtree, do not consider the specified bus
		if 'sourcebus' in subtree:
			del(buses[0])
			continue
		# consider every phase separately
		phase = 1
		while phase < 4:
			if buses[0] in busShapes.keys():
				if busShapes[buses[0]][phase-1]:
					if phase == 1:
						angle = '240.000000'
						amps = '219.969000'
					elif phase == 2:
						angle = '120.000000'
						amps = '65.000000'
					else:
						angle = '0.000000'
						amps = '169.120000'
					# add the diesel loadshapes to the dictionary of all shapes to be added
					shape_name = 'newdiesel_' + str(buses[0]) + '_' + str(phase) + '_shape'
					shape_data = busShapes[bus][phase - 1]
					shape_insert_list[i] = {
							'!CMD': 'new',
							'object': f'loadshape.{shape_name}',
							'npts': f'{len(shape_data)}',
							'interval': '1',
							'useactual': 'yes',
							'mult': str(list(shape_data)).replace(' ','')
						}
					i+=1
					# add an isource representation for the diesel generators to the dictionary of all generators to be added
					gen_name = 'isource.isource_newdiesel' + str(buses[0]) + '_' + str(phase) + '_shape'
					gen_insert_list[j] = {
							'!CMD': 'new',
							'object': f'{gen_name}',
							'bus1': str(buses[0]) + '.' + str(phase),
							'phases': '1',
							'angle': str(angle),
							'amps': str(amps),
							'daily': 'newdiesel_' + str(buses[0]) + '_' + str(phase) + '_shape'
						}
					j+=1
					# add an isource representation for the solar generation to the dictionary of all generators to be added
					gen_name = 'isource.isource_solar' + str(buses[0]) + '_' + str(phase) + '_shape'
					gen_insert_list[j] = {
							'!CMD': 'new',
							'object': f'{gen_name}',
							'bus1': str(buses[0]) + '.' + str(phase),
							'phases': '1',
							'angle': str(angle),
							'amps': str(amps),
							'daily': 'solar_' + str(buses[0]) + '_shape'
						}
					j+=1
			phase += 1
		# remove the bus so we can move on...
		del (buses[0])

	# get a tree representation for the .dss file
	treeDSS = dssConvert.dssToTree(pathToDss)
	# make a copy of the original for iterating purposes
	tree2 = treeDSS.copy()
	# remove every other (old) representation of generation in the model
	for thing in tree2:
		if (thing.get('object','').startswith('generator')) or (thing.get('object','').startswith('storage')):
			treeDSS.remove(thing)
	# insert all of the new loadshapes
	for key in shape_insert_list:
		convertedKey = collections.OrderedDict(shape_insert_list[key])
		min_pos = min(shape_insert_list.keys()) + 1
		treeDSS.insert(min_pos, convertedKey)
	max_pos = 100000000
	# insert all of the new isource generators
	for key in gen_insert_list:
		convertedKey = collections.OrderedDict(gen_insert_list[key])
		treeDSS.insert(max_pos, convertedKey)
		max_pos+=1

	# insert a line telling the file to solve when run by OpenDSS
	treeDSS.insert(max_pos, {'!CMD': 'solve'})

	# Write new DSS file.
	FULL_NAME = 'lehigh_full_newDiesel.dss'
	dssConvert.treeToDss(treeDSS, FULL_NAME)

	# get a dictionary of all the line openings and closings to be graphed
	actions = {}
	for key in actionsDict:
		line = str(actionsDict[key].get('lineAction','')) + ' object=line.' + str(key) + ' term=1'
		actions[int(actionsDict[key].get('timePassed',''))] = line
	
	# at the end of the simulation, re-open all of the reclosers and close all of the open tie lines to reset everything
	key = 0
	max_pos = lengthOfOutage
	while key < len(bestReclosers):
		recloserName = bestReclosers[key].get('name','')
		line = 'close object=line.' + f'{recloserName}' + ' term=1'
		actions[max_pos] = line
		max_pos+=1
		key+=1
	key = 0
	while key < len(bestTies):
		tieName = bestTies[key].get('name','')
		line = 'open object=line.' + f'{tieName}' + ' term=1'
		actions[max_pos] = line
		max_pos+=1
		key+=1

	# graph everything with newQstsPlot
	FPREFIX = 'timezcontrol'
	opendss.newQstsPlot(FULL_NAME,
		stepSizeInMinutes=60, 
		numberOfSteps=300,
		keepAllFiles=False,
		actions=actions,
		filePrefix=FPREFIX
	)

	def make_chart(csvName, category_name, x, y_list):
		'helper function to create plots from newQstsPlot'
		gen_data = pd.read_csv(csvName)
		data = []
		for ob_name in set(gen_data[category_name]):
			for y_name in y_list:
				this_series = gen_data[gen_data[category_name] == ob_name]
				trace = py.graph_objs.Scatter(
					x = this_series[x],
					y = this_series[y_name],
					name = ob_name + '_' + y_name,
					hoverlabel = dict(namelength = -1)
				)
				data.append(trace)
		layout = py.graph_objs.Layout(
			title = f'{csvName} Output',
			xaxis = dict(title = 'hour'),
			yaxis = dict(title = str(y_list))
		)
		fig = py.graph_objs.Figure(data, layout)
		py.offline.plot(fig, filename=f'{csvName}.plot.html', auto_open=False)
	
	# make_chart(f'{FPREFIX}_gen.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'])
	make_chart(f'{FPREFIX}_load.csv', 'Name', 'hour', ['V1(PU)','V2(PU)','V3(PU)'])
	make_chart(f'{FPREFIX}_source.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'])
	make_chart(f'{FPREFIX}_control.csv', 'Name', 'hour', ['Tap(pu)'])

	return(tree)

microgrids = {
	'm1': {
		'loads': ['634a_supermarket','634b_supermarket','634c_supermarket'],
		'switch': '632633',
		'gen_bus': '634',
		'max_potential': '70'
	},
	'm2': {
		'loads': ['675a_hospital','675b_residential1','675c_residential1'],
		'switch': '671692',
		'gen_bus': '675',
		'max_potential': '90'
	},
	'm3': {
		'loads': ['671_command_center','652_med_apartment'],
		'switch': '671684',
		'gen_bus': '684',
		'max_potential': '65'
	},
	'm4': {
		'loads': ['645_warehouse1','646_med_office'],
		'switch': '632645',
		'gen_bus': '646',
		'max_potential': '80'
	}
}

play('./lehigh.dss.omd', './lehigh_full.dss', None, None, microgrids, '670671', False, 60, 120, 30) 