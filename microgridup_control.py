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
	totalTime = 0

	# get a list of all the generating buses on the different microgrid systems
	buses = []
	for key in microgrids.keys():
		buses.append(microgrids[key].get('gen_bus', ''))

	loadsShed = {}
	loadsShedBasic = ['675b_residential1', '675c_residential1', '652_residential'] #To Do: make this an input to microgrids for any circuit
	# loadsShedBasic = ['','']
	for element in buses:
		if not element in loadsShed.keys():
			loadsShed[element] = {}
		phase = 1
		while phase < 4:
			if not phase in loadsShed[element].keys():
				loadsShed[element][phase] = []
			for loadElement in loadsShedBasic:
				loadsShed[element][phase].append(loadElement)
			phase += 1
	for mg in loadsShed:
		for phase in loadsShed[mg]:
			for loadElement in loadsShed[mg][phase]:
				tree2 = tree.copy()
				for thing in tree2:
					if (tree2[thing].get('name','').startswith(loadElement)):
						tree.pop(thing)
	# isolate the fault
	tree, bestReclosers, badBuses = flisr.cutoffFault(tree, faultedNode, bestReclosers, workDir, radial, buses)

	# 2) get a list of loads associated with each microgrid component
	# and create a loadshape containing all of said loads
	if switchingTime <= lengthOfOutage:

		batteryTime = {}
		dischargeTimes = {}
		chargeTimes = {}
		# make sure we re-run a single step of the simulation as many times as necessary to ensure all loads not shed can be supported
		# first, populate the battery loadshapes
		totalTime, timePassed, busShapesBatteryDischarging, leftOverBusShapesDischarging, leftOverLoadDischarging, totalLoadDischarging, excessPowerTemp, existsLoad = playOneStep(tree, bestReclosers, badBuses, pathToDss, switchingTime, outageStart, outageStart, None, None, None, 0, True, False, None, None, False, None, microgrids)
		# next, populate the solar loadshapes
		totalTime, timePassed, busShapesSolarDischarging, leftOverBusShapesDischarging, leftOverLoadDischarging, totalLoadTemp, excessPowerTemp, existsLoadTemp = playOneStep(tree, bestReclosers, badBuses, pathToDss, switchingTime, outageStart, outageStart, None, leftOverBusShapesDischarging, leftOverLoadDischarging, 0, False, True, totalLoadDischarging, None, False, None, microgrids)
		# next, populate the diesel loadshapes, assuming the battery is discharging.
		totalTimeTemp, timePassed, busShapesDieselDischarging, leftOverBusShapesDischarging, leftOverLoadDischarging, totalLoadTemp, excessPowerTemp, existsLoadTemp = playOneStep(tree, bestReclosers, badBuses, pathToDss, switchingTime, outageStart, outageStart, None, leftOverBusShapesDischarging, leftOverLoadDischarging, 0, False, False, totalLoadDischarging, None, False, None, microgrids)
		# in addition, populate the solar loadshapes, assuming the battery is charging.
		totalTimeTemp, timePassed, busShapesSolarCharging, leftOverBusShapesCharging, leftOverLoadCharging, totalLoadTemp, excessPowerSolar, existsLoadTemp = playOneStep(tree, bestReclosers, badBuses, pathToDss, switchingTime, outageStart, outageStart, None, None, None, 0, False, True, None, None, True, None, microgrids)
		# and, populate the diesel loadshapes, assuming the battery is charging.
		totalTimeTemp, timePassed, busShapesDieselCharging, leftOverBusShapesCharging, leftOverLoadCharging, totalLoadTemp, excessPowerDiesel, existsLoadTemp = playOneStep(tree, bestReclosers, badBuses, pathToDss, switchingTime, outageStart, outageStart, None, leftOverBusShapesCharging, leftOverLoadCharging, 0, False, False, None, None, True, None, microgrids)
		# create an array of zeroes, representing the amount of load supported by the battery when it's charging
		busShapesBatteryCharging = {}
		for bus in busShapesBatteryDischarging:
			for entry in microgrids:
				if bus == microgrids[entry].get('gen_bus', ''):
					chargeRate = float(microgrids[entry].get('kw_rating_battery', ''))
					busShapesBatteryCharging[bus] = [-chargeRate] * (totalTime)
		# print(existsLoad)

		# initialize totalLoad loadshape
		totalLoad = totalLoadDischarging
		busShapesBattery = {}
		busShapesDiesel = {}
		busShapesSolar = {}

		for bus in busShapesBatteryDischarging:
			busShapesBattery[bus] = [[], [], []]
		for bus in busShapesBattery:
			phase = 0
			while phase < 3:
				busShapesBattery[bus][phase] = busShapesBatteryDischarging[bus][phase][0 : outageStart-1]
				phase += 1
		for bus in busShapesSolarDischarging:
			busShapesSolar[bus] = [[], [], []]
		for bus in busShapesSolar:
			phase = 0
			while phase < 3:
				busShapesSolar[bus][phase] = busShapesSolarDischarging[bus][phase][0 : outageStart-1]
				phase += 1
		for bus in busShapesDieselDischarging:
			busShapesDiesel[bus] = [[], [], []]
		for bus in busShapesDiesel:
			phase = 0
			while phase < 3:
				busShapesDiesel[bus][phase] = busShapesDieselDischarging[bus][phase][0 : outageStart-1]
				phase += 1

		buses = createListOfBuses(microgrids, badBuses)
		while len(buses) > 0:
			batteryTime[buses[0]] = outageStart
			while batteryTime[buses[0]] < outageStart + lengthOfOutage:
				minimumDischargeTime = 10000000000000
				batteryControl = {}
				batteryControl[buses[0]] = [[], [], []]
				phase = 0
				while phase < 3:
					if (buses[0] in busShapesBatteryDischarging.keys()) and (buses[0] in busShapesDieselDischarging.keys()):
						if (busShapesBatteryDischarging[buses[0]][phase]) and (busShapesDieselDischarging[buses[0]][phase]):
							index = batteryTime[buses[0]]
							while index < len(busShapesBatteryDischarging[buses[0]][phase]):
								batteryControl[buses[0]][phase].append(totalLoad[buses[0]][phase][index] - totalLoad[buses[0]][phase][batteryTime[buses[0]]])
								# print(totalLoad[buses[0]][phase][index] - excessPower[buses[0]][phase][index] - totalLoad[buses[0]][phase][outageStart] + excessPower[buses[0]][phase][outageStart])
								index += 1
					phase += 1
				phase = 0
				while phase < 3:
					if buses[0] in busShapesBatteryDischarging.keys():
						for entry in microgrids:
							if buses[0] == microgrids[entry].get('gen_bus', ''):
								capacity = float(microgrids[entry].get('kwh_rating_battery', ''))
						if busShapesBatteryDischarging[buses[0]][phase]:
							for element in batteryControl[buses[0]][phase]:
								if element > capacity:
									if batteryControl[buses[0]][phase].index(element) + batteryTime[buses[0]] < minimumDischargeTime:
										minimumDischargeTime = batteryControl[buses[0]][phase].index(element) + batteryTime[buses[0]]
					phase += 1
				if buses[0] in dischargeTimes.keys():
					dischargeTimes[buses[0]].append(minimumDischargeTime)
				else:
					dischargeTimes[buses[0]] = [minimumDischargeTime]
				phase = 0
				while phase < 3:
					if buses[0] in busShapesBattery.keys():
						if busShapesBattery[buses[0]][phase]:
							busShapesBatteryExtra = busShapesBatteryDischarging[buses[0]][phase][batteryTime[buses[0]] : minimumDischargeTime-1]
							busShapesSolarExtra = busShapesSolarDischarging[buses[0]][phase][batteryTime[buses[0]] : minimumDischargeTime-1]
							busShapesDieselExtra = busShapesDieselDischarging[buses[0]][phase][batteryTime[buses[0]] : minimumDischargeTime-1]
							busShapesBattery[buses[0]][phase] = list(busShapesBattery[buses[0]][phase]) + list(busShapesBatteryExtra)
							busShapesSolar[buses[0]][phase] = list(busShapesSolar[buses[0]][phase]) + list(busShapesSolarExtra)
							busShapesDiesel[buses[0]][phase] = list(busShapesDiesel[buses[0]][phase]) + list(busShapesDieselExtra)
					phase += 1
				batteryTime[buses[0]] = minimumDischargeTime
				print('discharge')
				print(minimumDischargeTime)
				
				for entry in microgrids:
					if buses[0] == microgrids[entry].get('gen_bus', ''):
						maximumBattery = float(microgrids[entry].get('kw_rating_battery', ''))

				if batteryTime[buses[0]] < totalTime:
					minimumChargeTime = 10000000000000
					batteryControl = {}
					batteryControl[buses[0]] = [[], [], []]
					phase = 0
					while phase < 3:
						if (buses[0] in busShapesBattery.keys()) and (buses[0] in busShapesDieselCharging.keys()):
							if busShapesDieselCharging[buses[0]][phase]:
								index = batteryTime[buses[0]]
								while index < len(excessPowerDiesel[buses[0]][phase]):
									# print(excessPower[buses[0]][phase][index] - excessPower[buses[0]][phase][batteryTime[buses[0]]])
									# batteryControl[buses[0]][phase].append(excessPowerSolar[buses[0]][phase][index] + excessPowerDiesel[buses[0]][phase][index] - excessPowerSolar[buses[0]][phase][batteryTime[buses[0]]] - excessPowerDiesel[buses[0]][phase][batteryTime[buses[0]]])
									if index == batteryTime[buses[0]]:
										batteryControl[buses[0]][phase].append(maximumBattery)
									else:
										batteryControl[buses[0]][phase].append(maximumBattery + batteryControl[buses[0]][phase][index-batteryTime[buses[0]]-1])
									index += 1
						phase += 1
					phase = 0
					while phase < 3:
						if buses[0] in busShapesBattery.keys():
							for entry in microgrids:
								if buses[0] == microgrids[entry].get('gen_bus', ''):
									capacity = float(microgrids[entry].get('kwh_rating_battery', ''))
							if busShapesBattery[buses[0]][phase]:
								for element in batteryControl[buses[0]][phase]:
									if element > capacity:
										if batteryControl[buses[0]][phase].index(element) + batteryTime[buses[0]] < minimumChargeTime:
											minimumChargeTime = batteryControl[buses[0]][phase].index(element) + batteryTime[buses[0]]
						phase += 1
					if buses[0] in chargeTimes.keys():
						chargeTimes[buses[0]].append(minimumChargeTime)
					else:
						chargeTimes[buses[0]] = [minimumChargeTime]
					phase = 0
					while phase < 3:
						if buses[0] in busShapesBattery.keys():
							if busShapesBattery[buses[0]][phase]:
								busShapesBatteryExtra = busShapesBatteryCharging[buses[0]][batteryTime[buses[0]] : minimumChargeTime-1]
								busShapesSolarExtra = busShapesSolarCharging[buses[0]][batteryTime[buses[0]] : minimumChargeTime-1]
								busShapesDieselExtra = busShapesDieselCharging[buses[0]][phase][batteryTime[buses[0]] : minimumChargeTime-1]
								busShapesBattery[buses[0]][phase] = list(busShapesBattery[buses[0]][phase]) + list(busShapesBatteryExtra)
								busShapesSolar[buses[0]][phase] = list(busShapesSolar[buses[0]][phase]) + list(busShapesSolarExtra)
								busShapesDiesel[buses[0]][phase] = list(busShapesDiesel[buses[0]][phase]) + list(busShapesDieselExtra)
						phase += 1
					batteryTime[buses[0]] = minimumChargeTime
					print('charge')
					print(minimumChargeTime)
			phase = 0
			while phase < 3:
				if buses[0] in busShapesBattery.keys():
					if busShapesBattery[buses[0]][phase]:
						# truncate the arrays so that the battery is only considered during the outage and the main bus is used after the outage
						busShapesBatteryExtra = busShapesBatteryDischarging[buses[0]][phase][outageStart + lengthOfOutage : totalTime]
						busShapesSolarExtra = busShapesSolarDischarging[buses[0]][phase][outageStart + lengthOfOutage : totalTime]
						busShapesDieselExtra = busShapesDieselDischarging[buses[0]][phase][outageStart + lengthOfOutage : totalTime]
						busShapesBattery[buses[0]][phase] = list(busShapesBattery[buses[0]][phase][0 : outageStart + lengthOfOutage - 1]) + list(busShapesBatteryExtra)
						busShapesSolar[buses[0]][phase] = list(busShapesSolar[buses[0]][phase][0 : outageStart + lengthOfOutage - 1]) + list(busShapesSolarExtra)
						busShapesDiesel[buses[0]][phase] = list(busShapesDiesel[buses[0]][phase][0 : outageStart + lengthOfOutage - 1]) + list(busShapesDieselExtra)
				phase += 1
			# print(len(buses))
			del(buses[0])

		# update the amount of time that has passed in the simulation
		timePassed = timePassed + switchingTime
		# loadsShed = None
		# totalTime, timePassed, busShapes, leftOverBusShapes, leftOverLoad, loadsShed, loadsTooHigh = playOneStep(tree, bestReclosers, badBuses, pathToDss, switchingTime, outageStart, outageStart, None, None, None, 0, loadsShed)
		# # update the amount of time that has passed in the simulation
		# timePassed = timePassed + switchingTime
		# for mg in loadsShed:
		# 	for phase in loadsShed[mg]:
		# 		for loadElement in loadsShed[mg][phase]:
		# 			tree2 = tree.copy()
		# 			for thing in tree2:
		# 				if (tree2[thing].get('name','').startswith(loadElement)):
		# 					tree.pop(thing)
		key = 0
		initialTimePassed = outageStart
		while key < len(bestReclosers):
			recloserName = bestReclosers[key].get('name','')
			lineAction = 'open'
			actionsDict[recloserName] = {'timePassed':initialTimePassed, 'lineAction':lineAction}
			key+=1
		actionsDict['calcv'] = {'timePassed':initialTimePassed}

	# # read in the set of tie lines on the system as a dataframe
	# if pathToTieLines != None:
	# 	tieLines = pd.read_csv(pathToTieLines)
	
		# #start the restoration piece of the algorithm
		# index = 0
		# terminate = False
		# goTo4 = False
		# goTo3 = False
		# goTo2 = True
		# while (terminate == False) and ((timePassed+switchingTime) < lengthOfOutage + outageStart):
		# 	# Step 2
		# 	if goTo2 == True:
		# 		goTo2 = False
		# 		goTo3 = True
		# 		unpowered, powered, potentiallyViable = flisr.listPotentiallyViable(tree, tieLines, workDir)
		# 		# print(potentiallyViable)
		# 	# Step 3
		# 	if goTo3 == True:
		# 		goTo3 = False
		# 		goTo4 = True
		# 		openSwitch = flisr.chooseOpenSwitch(potentiallyViable)
		# 	# Step 4
		# 	if goTo4 == True:
		# 		goTo4 = False
		# 		tree, potentiallyViable, tieLines, bestTies, bestReclosers, goTo2, goTo3, terminate, index = flisr.addTieLines(tree, faultedNode, potentiallyViable, unpowered, powered, openSwitch, tieLines, bestTies, bestReclosers, workDir, goTo2, goTo3, terminate, index, radial)
		# 		if goTo2 == True:
		# 			# make sure we re-run a single step of the simulation as many times as necessary to ensure all loads not shed can be supported
		# 			# loadsTooHigh = True
		# 			# while loadsTooHigh == True:
		# 			# 	totalTime, timePassed, busShapes, leftOverBusShapes, leftOverLoad, loadsShed, loadsTooHigh = playOneStep(tree, bestReclosers, badBuses, pathToDss, switchingTime, outageStart, outageStart, None, None, None, 0, loadsShed)
		# 			# 	for mg in loadsShed:
		# 			# 		for phase in loadsShed[mg]:
		# 			# 			for loadElement in loadsShed[mg][phase]:
		# 			# 				tree2 = tree.copy()
		# 			# 				for thing in tree2:
		# 			# 					if (tree2[thing].get('name','').startswith(loadElement)):
		# 			# 						tree.pop(thing)

		# 			totalTime, timePassed, busShapes, leftOverBusShapes, leftOverLoad, loadsShed = playOneStep(tree, bestReclosers, badBuses, pathToDss, switchingTime, timePassed, outageStart, None, None, None, 0, loadsShed)
		# 			# update the amount of time that has passed in the simulation
		# 			timePassed = timePassed + switchingTime
					
					# key = 0
					# while key < len(bestReclosers):
					# 	recloserName = bestReclosers[key].get('name','')
					# 	if recloserName not in actionsDict.keys():
					# 		lineAction = 'open'
					# 		actionsDict[recloserName] = {'timePassed':timePassed, 'lineAction':lineAction}
					# 	key+=1
					# key = 0
					# while key < len(bestTies):
					# 	tieName = bestTies[key].get('name','')
					# 	if tieName not in actionsDict.keys():
					# 		lineAction = 'close'
					# 		actionsDict[tieName] = {'timePassed':timePassed, 'lineAction':lineAction}
					# 	key+=1
					# actionsDict['calcv'] = {'timePassed':timePassed}

	# when the outage is over, switch back to the main sourcebus
	buses = createListOfBuses(microgrids, badBuses)
	# print("list of buses:", buses)
	if totalTime > 0:
		listOfZeroes = [0.00] * (totalTime - (lengthOfOutage + outageStart) + 1)
	
		while len(buses) > 0:
			phase = 0
			while phase < 3:
				if buses[0] in busShapesBattery.keys():
					if busShapesBattery[buses[0]][phase]:
						busShapesBattery[buses[0]][phase] = busShapesBattery[buses[0]][phase][0 : (lengthOfOutage + outageStart)]
						busShapesBattery[buses[0]][phase] = busShapesBattery[buses[0]][phase] + listOfZeroes
				if buses[0] in busShapesSolar.keys():
					if busShapesSolar[buses[0]][phase]:
						busShapesSolar[buses[0]][phase] = busShapesSolar[buses[0]][phase][0 : (lengthOfOutage + outageStart)]
						busShapesSolar[buses[0]][phase] = busShapesSolar[buses[0]][phase] + listOfZeroes
				if buses[0] in busShapesDiesel.keys():
					if busShapesDiesel[buses[0]][phase]:
						busShapesDiesel[buses[0]][phase] = busShapesDiesel[buses[0]][phase][0 : (lengthOfOutage + outageStart)]
						busShapesDiesel[buses[0]][phase] = busShapesDiesel[buses[0]][phase] + listOfZeroes
				phase+=1
			del(buses[0])
	# print(busShapes)
	else:
		busShapes = {}

	# print(busShapesBattery)
	tree = solveSystem(busShapesBattery, busShapesSolar, busShapesDiesel, actionsDict, microgrids, tree, pathToDss, badBuses, bestReclosers, bestTies, lengthOfOutage, outageStart, loadsShed, existsLoad)

def playOneStep(tree, bestReclosers, badBuses, pathToDss, switchingTime, timePassed, outageStart, busShapes, leftOverBusShapes, leftOverLoad, totalTime, isBattery, isSolar, totalLoad, excessPower, isCharging, existsLoad, microgrids):
	'function that prepares a single timestep of the simulation to be solved'
	
	# create a list of the diesel generators
	buses = createListOfBuses(microgrids, badBuses)

	# if there aren't any new diesel generators shapes yet, create them from the beginning!
	if busShapes == None:
		totalTime = 0
		# busShapes is the actual shape for the generators
		busShapes = {}
	if leftOverBusShapes == None:
		# lefOverBusShapes is the amount of load that cannot be supported by a generator so far
		startFromBeginning = True
		leftOverBusShapes = {}
	else:
		startFromBeginning = False
	
	# leftOverLoad keeps track of whether or not there is any amount of unsupported load for a generator with binaries
	if leftOverLoad == None:
		leftOverLoad = {}
	if totalLoad == None:
		totalLoad = {}
	if excessPower == None:
		excessPower = {}
	if existsLoad == None:
		existsLoad = {}

	# initialize the array keeping track of all connected subtrees
	subtrees = {}

	# for each power source
	while len(buses) > 0:
		# create an adjacency list representation of tree connectivity
		adjacList, reclosers, vertices = flisr.adjacencyList(tree)
		bus = buses[0]
		# initialize a dictionary to store the loadshapes
		loadShapes = {}
		isLoad = {}
		# keep track of whether a bus has been seen already
		alreadySeen = False
		# check to see if there is a path between the power source and the fault 
		subtree = flisr.getMaxSubtree(adjacList, bus)
		for key in subtrees:
			if set(subtrees[key]) == set(subtree):
				# if a larger generator is already supplying power, have a smaller generator only pick up the remaining load
				shapes = {}
				leftOverShapes = {}
				shapesNew = {}
				leftOverHere = {}
				totalLoadHere = {}
				excessHere = {}
				maximum = 1.0
				for entry in microgrids:
					if bus == microgrids[entry].get('gen_bus', ''):
						if isBattery:
							maximum = float(microgrids[entry].get('kw_rating_battery', ''))
						else:
							maximum = float(microgrids[entry].get('kw_rating_diesel', ''))
							maximumBattery = microgrids[entry].get('kw_rating_battery', '')
						k = 1
						while k < 4:
							val = 0
							while val < len(leftOverLoad[key][k]):
								if k == 1:
									if not '.1' in shapes.keys():
										shapes['.1'] = []
									if leftOverLoad[key][k][val] == True:
										shapes['.1'].append(leftOverBusShapes[key][k][val])
									else:
										shapes['.1'].append(0.0)
								if k == 2:
									if not '.2' in shapes.keys():
										shapes['.2'] = []
									if leftOverLoad[key][k][val] == True:
										shapes['.2'].append(leftOverBusShapes[key][k][val])
									else:
										shapes['.2'].append(0.0)
								if k == 3:
									if not '.3' in shapes.keys():
										shapes['.3'] = []
									if leftOverLoad[key][k][val] == True:
										shapes['.3'].append(leftOverBusShapes[key][k][val])
									else:
										shapes['.3'].append(0.0)
								val += 1
							k += 1
						for shape in shapes:
							if not shape in shapesNew.keys():
								shapesNew[shape] = []
							if not shape in leftOverShapes.keys():
								leftOverShapes[shape] = []
							if not shape in leftOverHere.keys():
								leftOverHere[shape] = []
							if not shape in totalLoadHere.keys():
								totalLoadHere[shape] = []
							if not shape in excessHere.keys():
								excessHere[shape] = []
							for entry in shapes[shape]:
								if (float(maximum) - float(entry)) >= 0:
									shapesNew[shape].append(float(entry))
									leftOverShapes[shape].append(0.0)
									leftOverHere[shape].append(False)
									if len(totalLoadHere[shape]) == 0:
										totalLoadHere[shape].append(float(entry))
									else:
										totalLoadHere[shape].append(float(entry) + totalLoadHere[shape][len(totalLoadHere[shape]) - 1])
									if len(excessHere[shape]) != 0:
										excessHere[shape].append(float(maximum) - float(entry) + excessHere[shape][len(excessHere[shape]) - 1])
									else:
										excessHere[shape].append(float(maximum) - float(entry))
								else:
									shapesNew[shape].append(float(maximum))
									leftOverShapes[shape].append(float(entry)-float(maximum))
									leftOverHere[shape].append(True)
									if len(totalLoadHere[shape]) == 0:
										totalLoadHere[shape].append(float(maximum))
									else:
										totalLoadHere[shape].append(float(maximum) + totalLoadHere[shape][len(totalLoadHere[shape]) - 1])
									if len(excessHere[shape]) == 0:
										excessHere[shape].append(0.0)
									else:
										excessHere[shape].append(excessHere[shape][len(excessHere[shape]) - 1])
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
		# if the subtree associated with a specific generator hasn't yet been supported by a different generator, add the biggest
		if alreadySeen == False:
			if startFromBeginning == True:
				loadShapes = {}
				# only consider loads in the subtree connected to the generator
				for node in subtree:
					for key in tree.keys():
						obtype = tree[key].get('object','')
						if obtype == 'load' or obtype == 'triplex_load':
							if tree[key].get('parent','').startswith(str(node)):
								# add the loads together to figure out how much needs to be supported in total
								loadshapeName = tree[key].get('yearly', '')
								kvRating = eval(tree[key].get('kv',''))
								kwRating = eval(tree[key].get('kw',''))
								for key1 in tree.keys():
									if tree[key1].get('name','') == loadshapeName:
										if bus == '684':
											print(loadshapeName)
										# print(loadshapeName)
										loadshape = eval(tree[key1].get('mult',''))
										if '.1' in tree[key].get('!CONNCODE',''):
											if '.1' in loadShapes:
												loadShapes['.1'] = [a + b for a, b in zip(loadShapes.get('.1',''), loadshape)]
											else:
												loadShapes['.1'] = [i for i in loadshape]
												isLoad['.1'] = True
										if '.2' in tree[key].get('!CONNCODE',''):
											if '.2' in loadShapes:
												loadShapes['.2'] = [a + b for a, b in zip(loadShapes.get('.2',''), loadshape)]
											else:
												loadShapes['.2'] = [i for i in loadshape]
												isLoad['.2'] = True
										if '.3' in tree[key].get('!CONNCODE',''):
											if '.3' in loadShapes:
												loadShapes['.3'] = [a + b for a, b in zip(loadShapes.get('.3',''), loadshape)]
											else:
												loadShapes['.3'] = [i for i in loadshape]
												isLoad['.3'] = True
				# print(loadShapes['.3'])
			else:
				if leftOverBusShapes:
					# print(leftOverBusShapes)
					loadShapes['.1'] = leftOverBusShapes[buses[0]][0]
					isLoad['.1'] = True
					loadShapes['.2'] = leftOverBusShapes[buses[0]][1]
					isLoad['.2'] = True
					loadShapes['.3'] = leftOverBusShapes[buses[0]][2]
					isLoad['.3'] = True

			if not '.1' in loadShapes:
				loadShapes['.1'] = [0.00] * (totalTime)
				isLoad['.1'] = False
			if not '.2' in loadShapes:
				loadShapes['.2'] = [0.00] * (totalTime)
				isLoad['.2'] = False
			if not '.3' in loadShapes:
				loadShapes['.3'] = [0.00] * (totalTime)
				isLoad['.3'] = False
			# print(loadShapes['.3'])
			# Obtain the loadshape by subtracting off solar from load and populate the loadshape dictionaries
			shapes = {}
			leftOverShapes = {}
			shapesNew = {}
			leftOverHere = {}
			totalLoadHere = {}
			excessHere = {}
			maximum = 1.0
			solarExists = False
			if isSolar == True:
				# check if there exists a solar generator connected to the generating bus of the microgrid under consideration
				for key in tree.keys():
					if tree[key].get('object','').startswith('generator'):
						if tree[key].get('name','').startswith('solar') and tree[key].get('parent','') == bus:
							# get the name of the solar loadshape
							solarshapeName = tree[key].get('yearly','')
							kwRating = float(tree[key].get('kw',''))
							kvRating = float(tree[key].get('kv',''))
							# if this is the first microgrid to support the connected subtree, consider solar. Otherwise, don't.
							if alreadySeen == False:
								for key1 in tree.keys():
									# if the solar loadshape exists in the tree, get the loadshape itself
									if tree[key1].get('name','') == solarshapeName:
										solarshape = eval(tree[key1].get('mult',''))
										solarExists = True
			for entry in microgrids:
				# populate the shapes dictionary with the values of the total load needed to be supported
				if buses[0] == microgrids[entry].get('gen_bus', ''):
					if isBattery:
						maximum = float(microgrids[entry].get('kw_rating_battery', ''))
					else:
						maximum = float(microgrids[entry].get('kw_rating_diesel', ''))
					if isCharging == True:
						maximumBattery = float(microgrids[entry].get('kw_rating_battery', ''))
						# if isLoad['.1'] == True:
						# 	loadShapes['.1'] = [i + maximumBattery for i in loadShapes['.1']]
						# if isLoad['.2'] == True:
						# 	loadShapes['.2'] = [i + maximumBattery for i in loadShapes['.2']]
						# if isLoad['.1'] == True:
						# 	loadShapes['.3'] = [i + maximumBattery for i in loadShapes['.3']]
					if '.1' in loadShapes:
						if len(loadShapes.get('.1','')) > totalTime:
							totalTime = len(loadShapes.get('.1',''))
						shapes['.1'] = loadShapes.get('.1','')
					if '.2' in loadShapes:
						if len(loadShapes.get('.2','')) > totalTime:
							totalTime = len(loadShapes.get('.2',''))
						shapes['.2'] = loadShapes.get('.2','')
					if '.3' in loadShapes:
						if len(loadShapes.get('.3','')) > totalTime:
							totalTime = len(loadShapes.get('.3',''))
						shapes['.3'] = loadShapes.get('.3','')					

			def supportedLoad(maximum, entry, shapesNewEntry, leftOverShapesEntry, leftOverHereEntry, totalLoadHereEntry, excessHereEntry):
				# if the needed power does not exceed the max, it is fully supported by the generator
				if (float(maximum) - float(entry)) >= 0:
					shapesNewEntry.append(float(entry))
					leftOverShapesEntry.append(0.0)
					leftOverHereEntry.append(False)
					if len(totalLoadHereEntry) != 0:
						totalLoadHereEntry.append(float(entry) + totalLoadHereEntry[len(totalLoadHereEntry) - 1])
					else:
						totalLoadHereEntry.append(float(entry))
					if len(excessHereEntry) != 0:
						excessHereEntry.append(float(maximum) - float(entry) + excessHereEntry[len(excessHereEntry) - 1])
					else:
						excessHereEntry.append(float(maximum) - float(entry))
				# otherwise, keep track of how much load cannot be supported so it can be supported by other generators
				else:
					shapesNewEntry.append(float(maximum))
					leftOverShapesEntry.append(float(entry)-float(maximum))
					leftOverHereEntry.append(True)
					if len(totalLoadHereEntry) == 0:
						totalLoadHereEntry.append(float(maximum))
					else:
						totalLoadHereEntry.append(float(maximum) + totalLoadHereEntry[len(totalLoadHereEntry) - 1])
					if len(excessHereEntry) == 0:
						excessHereEntry.append(0.0)
					else:
						excessHereEntry.append(excessHereEntry[len(excessHereEntry) - 1])
				
				return shapesNewEntry, leftOverShapesEntry, leftOverHereEntry, totalLoadHereEntry, excessHereEntry
			
			# check if the needed generation exceeds the maximum potential of the generator.
			for shape in shapes:
				if not shape in shapesNew.keys():
					shapesNew[shape] = []
				if not shape in leftOverShapes.keys():
					leftOverShapes[shape] = []
				if not shape in leftOverHere.keys():
					leftOverHere[shape] = []
				if not shape in totalLoadHere.keys():
					totalLoadHere[shape] = []
				if not shape in excessHere.keys():
					excessHere[shape] = []
				
				entry = 0
				while entry < totalTime:
					if (isSolar == True) and (solarExists == True):
						shapesNew[shape], leftOverShapes[shape], leftOverHere[shape], totalLoadHere[shape], excessHere[shape] = supportedLoad(float(solarshape[entry])/500, shapes[shape][entry], shapesNew[shape], leftOverShapes[shape], leftOverHere[shape], totalLoadHere[shape], excessHere[shape])
					elif (isSolar == True) and (solarExists == False):
						print('uh oh solar')
					else:	
						shapesNew[shape], leftOverShapes[shape], leftOverHere[shape], totalLoadHere[shape], excessHere[shape] = supportedLoad(float(maximum), shapes[shape][entry], shapesNew[shape], leftOverShapes[shape], leftOverHere[shape], totalLoadHere[shape], excessHere[shape])
					entry += 1

		# if it's the beginning of the simulation, fill the whole loadshape
		if timePassed == outageStart:
			listOfZeroes = [0.00] * (totalTime)
			listOfFalse = [False] * (totalTime)
			busShapes[buses[0]] = [listOfZeroes, listOfZeroes, listOfZeroes]
			leftOverBusShapes[buses[0]] = [listOfZeroes, listOfZeroes, listOfZeroes]
			leftOverLoad[buses[0]] = [listOfFalse, listOfFalse, listOfFalse]
			if isBattery == True:
				totalLoad[buses[0]] = [listOfZeroes, listOfZeroes, listOfZeroes]
			else:
				excessPower[buses[0]] = [listOfZeroes, listOfZeroes, listOfZeroes]
			existsLoad[buses[0]] = [isLoad['.1'], isLoad['.2'], isLoad['.3']]
			# print(existsLoad)

		phase = 0
		while phase < 3:
			if buses[0] in busShapes.keys():
				if busShapes[buses[0]][phase]:
					if isBattery:
						totalLoad[buses[0]][phase] = totalLoad[buses[0]][phase][0 : timePassed-1]
						totalLoadHere['.' + str(phase + 1)] = [x - totalLoadHere.get('.' + str(phase + 1),'')[timePassed-1] for x in totalLoadHere.get('.' + str(phase + 1),'')[timePassed-1 : totalTime]]
						totalLoad[buses[0]][phase] = list(totalLoad[buses[0]][phase]) + list(totalLoadHere.get('.' + str(phase + 1),''))
					else:
						excessPower[buses[0]][phase] = excessPower[buses[0]][phase][0 : timePassed-1]
						excessHere['.' + str(phase + 1)] = [x - excessHere.get('.' + str(phase + 1),'')[timePassed-1] for x in excessHere.get('.' + str(phase + 1),'')[timePassed-1 : totalTime]]
						excessPower[buses[0]][phase] = list(excessPower[buses[0]][phase]) + list(excessHere.get('.' + str(phase + 1),''))
			phase += 1
			
		# otherwise, only fill up the values beyond the current timestep
		phase = 0
		while phase < 3:
			if buses[0] in busShapes.keys():
				if busShapes[buses[0]][phase]:
					busShapes[buses[0]][phase] = busShapes[buses[0]][phase][0 : timePassed-1]
					leftOverBusShapes[buses[0]][phase] = leftOverBusShapes[buses[0]][phase][0 : timePassed-1]
					leftOverLoad[buses[0]][phase] = leftOverLoad[buses[0]][phase][0 : timePassed-1]
					shapesNew['.' + str(phase + 1)] = shapesNew.get('.' + str(phase + 1),'')[timePassed : totalTime]
					leftOverShapes['.' + str(phase + 1)] = leftOverShapes.get('.' + str(phase + 1),'')[timePassed : totalTime]
					leftOverHere['.' + str(phase + 1)] = leftOverHere.get('.' + str(phase + 1),'')[timePassed : totalTime]
					busShapes[buses[0]][phase] = list(busShapes[buses[0]][phase]) + list(shapesNew.get('.' + str(phase + 1),''))
					leftOverBusShapes[buses[0]][phase] = list(leftOverBusShapes[buses[0]][phase]) + list(leftOverShapes.get('.' + str(phase + 1),''))
					leftOverLoad[buses[0]][phase] = list(leftOverLoad[buses[0]][phase]) + list(leftOverHere.get('.' + str(phase + 1),''))
			phase+=1
		# add the subtree to the dictionary of all subtrees to note that it is at least partially supported (and we've considered solar)
		subtrees[bus] = subtree
		# remove the bus from the list of buses we still need to consider
		del(buses[0])

	# reverseImportanceOfLoads = ['675b_residential1', '675c_residential1', '652_residential', '692_warehouse2', '611_runway', '675a_hospital']

	# # implement load shedding if total load is unsupported by the total generation
	# allLoads = {}
	# if loadsShed == None:
	# 	loadsShed = {}

	# for element in subtrees.keys():

	# 	# check if there's leftover load on any individual phase of a microgrid system
	# 	# and if there is, get the maximum leftover load value for any timestep
	# 	if element in leftOverBusShapes.keys():
	# 		if not element in loadsShed.keys():
	# 			loadsShed[element] = {}
	# 		phaseTracker = 1
	# 		for phase in leftOverBusShapes[element]:
	# 			if not phaseTracker in loadsShed[element].keys():
	# 				loadsShed[element][phaseTracker] = []
	# 			maxTimeValue = 0.0
	# 			time = 0
	# 			for timeValue in phase:
	# 				time += 1
	# 				if timeValue > 0.0 and timeValue > maxTimeValue:
	# 					maxTimeValue = timeValue
	# 					maxTime = time
	# 					loadsTooHigh = True
	# 				else:
	# 					loadsTooHigh = False
	# 			temp = reverseImportanceOfLoads.copy()

	# 			# continue shedding load until all the loads not shed are supported
	# 			while maxTimeValue > 0.0:

	# 				# fill a dictionary of all loads connected to the microgrid and their corresponding loadshapes			
	# 				for node in subtrees[element]:
	# 					for key in tree.keys():
	# 						obtype = tree[key].get('object','')
	# 						if obtype == 'load' or obtype == 'triplex_load':
	# 							if tree[key].get('parent','').startswith(str(node)):
	# 								parent = tree[key].get('parent','')
	# 								loadshapeName = tree[key].get('yearly', '')
	# 								loadName = tree[key].get('name', '')
	# 								for key1 in tree.keys():
	# 									if tree[key1].get('name','') == loadshapeName:
	# 										loadshape = eval(tree[key1].get('mult',''))
	# 										allLoads[loadName] = loadshape
					
	# 				# shed one load at a time, starting with the least important
	# 				loadElement = temp[0]
	# 				if loadElement in allLoads.keys():
	# 					loadshapeElement = allLoads[loadElement]
	# 					loadsShed[element][phaseTracker].append(loadElement)
	# 					del(temp[0])
	# 					maxTimeValue = maxTimeValue - loadshapeElement[maxTime]
	# 				else:
	# 					del(temp[0])
	# 			phaseTracker += 1


	# totalLoad = {}
	# for key in busShapes.keys():
	# 	totalLoad[key] = []
	# 	for entry in busShapes[key]:
	# 		thisTotalLoad = []
	# 		for key in entry:
	# 			if len(thisTotalLoad) == 0:
	# 				thisTotalLoad.append(key)
	# 			else:
	# 				thisTotalLoad.append(key + thisTotalLoad[len(thisTotalLoad) - 1])
	# 		totalLoad[key].append(thisTotalLoad)
	return totalTime, timePassed, busShapes, leftOverBusShapes, leftOverLoad, totalLoad, excessPower, existsLoad

def solveSystem(busShapesBattery, busShapesSolar, busShapesDiesel, actionsDict, microgrids, tree, pathToDss, badBuses, bestReclosers, bestTies, lengthOfOutage, outageStart, loadsShed, existsLoad):
	'Add diesel generation to the opendss formatted system and solve using OpenDSS'
	# get a sorted list of the buses
	buses = createListOfBuses(microgrids, badBuses)

	# create a list containing diesel generator names, to disable and enable vsources
	dieselList = []
	emptyLoads = []

	# get a tree representation for the .dss file
	treeDSS = dssConvert.dssToTree(pathToDss)

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
		phaseCoefficient = 0
		if bus in existsLoad.keys():
			# print(existsLoad[bus])
			for entry in existsLoad[bus]:
				if entry == True:
					phaseCoefficient += 1
		else:
			phaseCoefficient = 1
		# print(bus)
		# print(phaseCoefficient)
		subtree = flisr.getMaxSubtree(adjacList, bus)
		# if the source is in the subtree, do not consider the specified bus
		if 'sourcebus' in subtree:
			del(buses[0])
			continue
		# consider every phase separately
		# ampData = pd.read_csv(pathToAmps)
		ampsDiesel = 0.0
		ampsBattery = 0.0
		ampsSolar = 0.0
		for thing in treeDSS:
			if thing.get('object','').startswith('generator.diesel_' + str(bus)):
				basekv = float(thing.get('kv', ''))
				kw = float(thing.get('kw',''))
				xdp = float(thing.get('xdp',''))
				xdpp = float(thing.get('xdpp',''))
			if thing.get('object','').startswith('storage.battery_' + str(bus)):
				kv = float(thing.get('kv', ''))
				kw = float(thing.get('kwrated', ''))
			if thing.get('object','').startswith('generator.solar_' + str(bus)):
				kv = float(thing.get('kv', ''))
				kw = float(thing.get('kw', ''))
		phase = 1
		while phase < 4:
			if buses[0] in busShapesBattery.keys():
				if busShapesBattery[buses[0]][phase-1]:
					maxVal = max(busShapesBattery[buses[0]][phase-1])
					if phase == 1:
						angle = '240.000000'
					elif phase == 2:
						angle = '120.000000'
					else:
						angle = '0.000000'
					# add the battery loadshapes to the dictionary of all shapes to be added
					shape_name = 'newbattery_' + str(buses[0]) + '_' + str(phase) + '_shape'
					shape_data = busShapesBattery[bus][phase - 1]
					if not any(shape_data):
						emptyLoads.append('generator.generator_' + shape_name)
						# print(shape_name)
					# l = 0
					# while l < len(shape_data):
					# 	if shape_data[l] != 0.0:
					# 		shape_data[l] = float(shape_data[l]) * math.sqrt(phaseCoefficient)
					# 	l += 1
					shape_insert_list[i] = {
							'!CMD': 'new',
							'object': f'loadshape.{shape_name}',
							'npts': f'{len(shape_data)}',
							'interval': '1',
							'useactual': 'yes',
							'mult': str(list(shape_data)).replace(' ','')
						}
					i+=1
					# add the solar loadshapes to the dictionary of all shapes to be added
					shape_name = 'newsolar_' + str(buses[0]) + '_' + str(phase) + '_shape'
					shape_data = busShapesSolar[bus][phase - 1]
					if not any(shape_data):
						emptyLoads.append('generator.generator_' + shape_name)
						# print(shape_name)
					# l = 0
					# while l < len(shape_data):
					# 	if shape_data[l] != 0.0:
					# 		shape_data[l] = shape_data[l] * math.sqrt(phaseCoefficient)
					# 	l += 1
					shape_insert_list[i] = {
							'!CMD': 'new',
							'object': f'loadshape.{shape_name}',
							'npts': f'{len(shape_data)}',
							'interval': '1',
							'useactual': 'yes',
							'mult': str(list(shape_data)).replace(' ','')
						}
					i+=1
					# add the diesel loadshapes to the dictionary of all shapes to be added
					shape_name = 'newdiesel_' + str(buses[0]) + '_' + str(phase) + '_shape'
					shape_data = busShapesDiesel[bus][phase - 1]
					if not any(shape_data):
						emptyLoads.append(shape_name)
						# print(shape_name)
					l = 0
					while l < len(shape_data):
						if shape_data[l] != 0.0:
							shape_data[l] = float(basekv) / math.sqrt(phaseCoefficient)
						l += 1
					shape_insert_list[i] = {
							'!CMD': 'new',
							'object': f'loadshape.{shape_name}',
							'npts': f'{len(shape_data)}',
							'interval': '1',
							'useactual': 'yes',
							'mult': str(list(shape_data)).replace(' ','')
						}
					i+=1
					# add an isource representation for the batteries to the dictionary of all generators to be added
					gen_name = 'generator.generator_newbattery_' + str(buses[0]) + '_' + str(phase) + '_shape'
					if 'newdiesel_' + str(buses[0]) + '_' + str(phase) + '_shape' not in emptyLoads:
						gen_insert_list[j] = {
								'!CMD': 'new',
								'object': f'{gen_name}',
								'bus1': str(buses[0]) + '.' + str(phase),
								'phases': '1',
								'kv': str(kv),
								'kw': str(kw),
								'yearly': 'newbattery_' + str(buses[0]) + '_' + str(phase) + '_shape'
							}
						j+=1
					# add an isource representation for the diesel generators to the dictionary of all generators to be added
					
					gen_name = 'vsource.vsource_newdiesel_' + str(buses[0]) + '_' + str(phase) + '_shape'
					if 'newdiesel_' + str(buses[0]) + '_' + str(phase) + '_shape' not in emptyLoads:
						dieselList.append(gen_name)
						gen_insert_list[j] = {
								'!CMD': 'new',
								'object': f'{gen_name}',
								'bus1': str(buses[0]) + '.' + str(phase),
								'angle': str(angle),
								'phases': '1',
								'R1': str(float(xdp) * phaseCoefficient),
								'X1': str(float(xdpp) * phaseCoefficient),
								'yearly': 'newdiesel_' + str(buses[0]) + '_' + str(phase) + '_shape'
							}
						j+=1
					# add an isource representation for the solar generation to the dictionary of all generators to be added
					gen_name = 'generator.generator_solar_' + str(buses[0]) + '_' + str(phase) + '_shape'
					if 'newdiesel_' + str(buses[0]) + '_' + str(phase) + '_shape' not in emptyLoads:
						gen_insert_list[j] = {
								'!CMD': 'new',
								'object': f'{gen_name}',
								'bus1': str(buses[0]) + '.' + str(phase),
								'phases': '1',
								# 'angle': str(angle),
								# 'amps': str(ampsSolar),
								'kv': str(kv),
								'kw': str(kw),
								'yearly': 'newsolar_' + str(buses[0]) + '_' + str(phase) + '_shape'
							}
						j+=1
			phase += 1
		# remove the bus so we can move on...
		del (buses[0])

	# make a copy of the original for iterating purposes
	tree2 = treeDSS.copy()
	# remove every other (old) representation of generation in the model
	for thing in tree2:
		if (thing.get('object','').startswith('generator.diesel')) or (thing.get('object','').startswith('generator.solar')) or (thing.get('object','').startswith('storage')) or (thing.get('object','').startswith('generator.wind')):
			treeDSS.remove(thing)
	# remove loads that have been shed
	for mg in loadsShed:
		for phase in loadsShed[mg]:
			for loadElement in loadsShed[mg][phase]:
				for thing in tree2:
					if (thing.get('object','').startswith('load.' + str(loadElement))):
						if thing in treeDSS:
							treeDSS.remove(thing)
	# insert all of the new loadshapes
	for key in shape_insert_list:
		convertedKey = collections.OrderedDict(shape_insert_list[key])
		min_pos = min(shape_insert_list.keys()) + 15
		treeDSS.insert(min_pos, convertedKey)
	max_pos = len(treeDSS) - 19
	# insert all of the new isource generators
	for key in gen_insert_list:
		convertedKey = collections.OrderedDict(gen_insert_list[key])
		treeDSS.insert(max_pos, convertedKey)
		max_pos+=1

	# insert a line telling the file to solve when run by OpenDSS
	# treeDSS.insert(max_pos, {'!CMD': 'solve'})

	# Write new DSS file.
	FULL_NAME = 'lehigh_full_newDiesel.dss' #To Do: update path of dss file to match name of circuit
	dssConvert.treeToDss(treeDSS, FULL_NAME)

	# get a dictionary of all the line openings and closings to be graphed
	actions = {}
	line = ''
	for entry in dieselList:
		# print(entry)
		# print(emptyLoads)
		if str(entry) not in emptyLoads:
			line = line + 'disable ' + str(entry) + '\n'
	actions[0] = line
	actions[1] = line + 'calcv'
	for key in actionsDict:
		if int(actionsDict[key].get('timePassed','')) not in actions.keys():
			if key == 'calcv':
				line = 'calcv'
			else:
				line = str(actionsDict[key].get('lineAction','')) + ' object=line.' + str(key) + ' term=1'
		else:
			if key == 'calcv':
				line = str(actions[int(actionsDict[key].get('timePassed',''))]) + '\n' + 'calcv'
			else:
				line = str(actions[int(actionsDict[key].get('timePassed',''))]) + '\n' + str(actionsDict[key].get('lineAction','')) + ' object=line.' + str(key) + ' term=1'
		actions[int(actionsDict[key].get('timePassed',''))] = line
	line1 = ''
	for entry in dieselList:
		line1 = str(line1) + 'enable ' + str(entry) + '\n'
	actions[int(actionsDict[key].get('timePassed',''))] = line1 + actions[int(actionsDict[key].get('timePassed',''))] 
	
	# at the end of the simulation, re-open all of the reclosers and close all of the open tie lines to reset everything
	key = 0
	max_pos = lengthOfOutage + outageStart
	while key < len(bestReclosers):
		recloserName = bestReclosers[key].get('name','')
		if max_pos not in actions.keys():
			line = 'close object=line.' + f'{recloserName}' + ' term=1'
		else:
			line = str(actions[max_pos]) + '\n' + 'close object=line.' + f'{recloserName}' + ' term=1'
		actions[max_pos] = line
		key+=1
	key = 0
	while key < len(bestTies):
		tieName = bestTies[key].get('name','')
		if max_pos not in actions.keys():
			line = 'open object=line.' + f'{tieName}' + ' term=1'
		else:
			line = str(actions[max_pos]) + '\n' + 'open object=line.' + f'{tieName}' + ' term=1'
		actions[max_pos] = line
		key+=1

	line1 = ''
	for entry in dieselList:
		line1 = str(line1) + 'disable ' + str(entry) + '\n'
	actions[max_pos] = line1 + actions[max_pos] + '\n' + 'calcv'

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
		py.offline.plot(fig, filename=f'{csvName}.plot.html', auto_open=True)
	
	make_chart(f'{FPREFIX}_gen.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'])
	make_chart(f'{FPREFIX}_load.csv', 'Name', 'hour', ['V1(PU)','V2(PU)','V3(PU)'])
	make_chart(f'{FPREFIX}_source.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'])
	make_chart(f'{FPREFIX}_control.csv', 'Name', 'hour', ['Tap(pu)'])

	return(tree)

microgrids = {
	'm1': {
		'loads': ['634a_supermarket','634b_supermarket','634c_supermarket'],
		'switch': '632633',
		'gen_bus': '633',
		'kw_rating_battery': '16',
		'kw_rating_diesel': '1000',
		'kwh_rating_battery': '100'
	},
	'm2': {
		'loads': ['675a_hospital','675b_residential1','675c_residential1'],
		'switch': '671692',
		'gen_bus': '675',
		'kw_rating_battery': '128',
		'kw_rating_diesel': '538.0170262240325',
		'kwh_rating_battery': '553'
	},
	'm3': {
		'loads': ['684_command_center','652_residential'],
		'switch': '671684',
		'gen_bus': '684',
		'gen_obs_existing': ['diesel_684_existing','battery_684_existing'],
		'critical_load_kws': [400,20],
		'kw_rating_battery': '20', # total kW rating on 684 and 652 is 1283 kW
		'kw_rating_diesel': '593.2050653749545',
		'kwh_rating_battery': '65.97158243892608'
		},
	'm4': {
		'loads': ['645_warehouse1','646_med_office'],
		'switch': '632645',
		'gen_bus': '646',
		'kw_rating_battery': '12',
		'kw_rating_diesel': '1000',
		'kwh_rating_battery': '100'
	}
}

play('./4mgs/circuit.dss.omd', './4mgs/circuit_plusmg_3.dss', None, None, microgrids, '670671', False, 60, 120, 30) 