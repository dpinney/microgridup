'''Test file with 1 microgrid for all loads and with multiple existing gens of all types
in microgrid_test_4mg.py for economic comparison'''

from microgridup import *
import microgridup_gen_mgs as gmg
from omf.solvers.opendss import dssConvert

def test_1mg():
	# Input data.
	MODEL_DIR = f'{PROJ_FOLDER}/lehigh1mg'
	BASE_DSS = f'{MGU_FOLDER}/testfiles/lehigh_base_phased.dss'
	LOAD_CSV = f'{MGU_FOLDER}/testfiles/lehigh_load.csv'
	FAULTED_LINES = '650632' # Why this line, which is not closing off the genbus from source?
	QSTS_STEPS = 24*20
	OUTAGE_CSV = f'{MGU_FOLDER}/testfiles/lehigh_random_outages.csv'
	REOPT_INPUTS = {
		# latitude
		# longitude
		"energyCost" : "0.12",
		"wholesaleCost" : "0.034", # To turn off energy export/net-metering, set wholesaleCost to "0" and excess PV gen will be curtailed
		"demandCost" : '20',
		"solarCanCurtail": True,
		"solarCanExport": True,
		"urdbLabelSwitch": "off",
		# "urdbLabel" : '5b75cfe95457a3454faf0aea', # EPEC General Service TOU Rate https://openei.org/apps/IURDB/rate/view/5b75cfe95457a3454faf0aea#1__Basic_Information
		"year" : '2017',
		"analysisYears": "25",
		"outageDuration": "48",
		"value_of_lost_load": "100",
		"single_phase_relay_cost": 300,
		"three_phase_relay_cost": 20000,
		# omCostEscalator
		"discountRate" : '0.083',
		"solar" : "on",
		"battery" : "on",
		"fossil": "on",
		"wind" : "off",
		"solarCost" : "1600",
		"solarMax": "10000",
		"solarMin": 0,
		# solarMacrsOptionYears
		# solarItcPercent
		"batteryCapacityCost" : "420",
		"batteryCapacityMax": "10000",
		"batteryCapacityMin": 0,
		"batteryPowerCost" : "840",
		"batteryPowerMax": "10000",
		"batteryPowerMin": 0,
		# batteryMacrsOptionYears
		# batteryItcPercent
		"batteryPowerCostReplace" : "410",
		"batteryCapacityCostReplace" : "200",
		"batteryPowerReplaceYear": '10', # year at which batteryPowerCostReplace (the inverter) is reinstalled, one time
		"batteryCapacityReplaceYear": '10', # year at which batteryCapacityCostReplace (the battery cells) is reinstalled, one time
		"dieselGenCost": "1000",
		"dieselMax": "10000",
		# dieselMin
		"fuelAvailable": "150000",
		"minGenLoading": 0,
		"dieselFuelCostGal": 1.5, # assuming 4.5 $/MMBtu = 1 $/gal diesel
		"dieselCO2Factor": 24.1,
		"dieselOMCostKw": 35,
		"dieselOMCostKwh": .02,
		"dieselOnlyRunsDuringOutage": False,
		# dieselMacrsOptionYears
		"windCost" : "4989",
		"windMax": "1000",
		"windMin": 0,
		# windMacrsOptionYears
		# windItcPercent
		"mgParameterOverrides": {"mg0":{}},
		"maxRuntimeSeconds": "240"
	}
	MICROGRIDS = {
		'mg0': {
			'critical_load_kws': [70, 90, 10, 150, 200, 200, 400, 20, 30, 70, 0, 0],
			'gen_bus': '670',
			'gen_obs_existing': ['solar_634_existing','solar_675_existing', 'fossil_684_existing', 'battery_634_existing', 'battery_684_existing'],
			'loads': ['634a_data_center', '634b_radar', '634c_atc_tower', '675a_hospital', '675b_residential1', '675c_residential1', '692_warehouse2', '684_command_center', '652_residential', '611_runway', '645_hangar', '646_office'],
			'switch': '650632',
		}
	}
	# Run model.
	full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, REOPT_INPUTS, MICROGRIDS, FAULTED_LINES, DESCRIPTION='', INVALIDATE_CACHE=False, OUTAGE_CSV=OUTAGE_CSV, DELETE_FILES=False, open_results=True)
	if os.path.isfile(f'{MODEL_DIR}/0crashed.txt'):
		sys.exit(1)

def test_2mg():
	# Input data.
	MODEL_DIR = f'{PROJ_FOLDER}/lehigh2mgs'
	BASE_DSS = f'{MGU_FOLDER}/testfiles/lehigh_base_phased.dss'
	LOAD_CSV = f'{MGU_FOLDER}/testfiles/lehigh_load.csv'
	FAULTED_LINES = '650632'
	QSTS_STEPS = 24*20
	REOPT_INPUTS = {
		# latitude
		# longitude
		"energyCost" : "0.12",
		"wholesaleCost" : "0.034", # To turn off energy export/net-metering, set wholesaleCost to "0" and excess PV gen will be curtailed
		"demandCost" : '20',
		"solarCanCurtail": True,
		"solarCanExport": True,
		"urdbLabelSwitch": "off",
		# "urdbLabel" : '5b75cfe95457a3454faf0aea', # EPEC General Service TOU Rate https://openei.org/apps/IURDB/rate/view/5b75cfe95457a3454faf0aea#1__Basic_Information		
		"year" : '2017',
		"analysisYears": "25",
		"outageDuration": "48",
		"value_of_lost_load": "100",
		"single_phase_relay_cost": 300,
		"three_phase_relay_cost": 20000,
		# omCostEscalator
		"discountRate" : '0.083',
		"solar" : "on",
		"battery" : "on",
		"fossil": "on", 
		"wind" : "on",
		"solarCost" : "1600",
		"solarMax": "10000",
		"solarMin": 0,
		# solarMacrsOptionYears
		# solarItcPercent
		"batteryCapacityCost" : "420",
		"batteryCapacityMax": "10000",
		"batteryCapacityMin": 0,
		"batteryPowerCost" : "840",
		"batteryPowerMax": "10000",
		"batteryPowerMin": 0,
		# batteryMacrsOptionYears
		# batteryItcPercent
		"batteryPowerCostReplace" : "410",
		"batteryCapacityCostReplace" : "200",
		"batteryPowerReplaceYear": '10', # year at which batteryPowerCostReplace (the inverter) is reinstalled, one time
		"batteryCapacityReplaceYear": '10', # year at which batteryCapacityCostReplace (the battery cells) is reinstalled, one time
		"dieselGenCost": "500",
		"dieselMax": "100000",
		# dieselMin
		"fuelAvailable": "10000",
		"minGenLoading": "0.3",
		"dieselFuelCostGal": 3, # assuming 4.5 $/MMBtu = 1 $/gal diesel
		"dieselCO2Factor": 22.4,
		"dieselOMCostKw": 25,
		"dieselOMCostKwh": 0.02,
		"dieselOnlyRunsDuringOutage": True,
		# dieselMacrsOptionYears
		"windCost" : "1500",
		"windMax": "10000",
		"windMin": 0,
		# windMacrsOptionYears
		# windItcPercent
		"mgParameterOverrides": {"mg0":{}, "mg1":{}},
		"maxRuntimeSeconds": "240"
	}
	MICROGRIDS = {
		'mg0': {
			'critical_load_kws': [70, 90, 10],
			'gen_bus': '634',
		 	'gen_obs_existing': [],
			'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'],
			'switch': '632633'
		},
		'mg1': {
			'critical_load_kws': [150, 200, 200, 0],
			'gen_bus': '675',
			'gen_obs_existing': [],
			'loads': ['675a_hospital', '675b_residential1', '675c_residential1', '692_warehouse2'],
			'switch': '671692'
		}
	}
	# Run model.
	full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, REOPT_INPUTS, MICROGRIDS, FAULTED_LINES, DESCRIPTION='', INVALIDATE_CACHE=False, OUTAGE_CSV=None, DELETE_FILES=False, open_results=True)
	if os.path.isfile(f'{MODEL_DIR}/0crashed.txt'):
		sys.exit(1)

def test_3mg():
	# Input data.
	MODEL_DIR = f'{PROJ_FOLDER}/lehigh3mgs'
	BASE_DSS = f'{MGU_FOLDER}/testfiles/lehigh_base_phased.dss'
	LOAD_CSV = f'{MGU_FOLDER}/testfiles/lehigh_load.csv'
	FAULTED_LINES = '650632'
	QSTS_STEPS = 24*20
	REOPT_INPUTS = {
		# latitude
		# longitude
		"energyCost": "0.12",
		"wholesaleCost" : "0", # To turn off energy export/net-metering, set wholesaleCost to "0" and excess PV gen will be curtailed
		"demandCost": '20',
		"solarCanCurtail": True,
		"solarCanExport": True,
		"urdbLabelSwitch": "off",
		# "urdbLabel" : '5b75cfe95457a3454faf0aea', # EPEC General Service TOU Rate https://openei.org/apps/IURDB/rate/view/5b75cfe95457a3454faf0aea#1__Basic_Information
		"year": '2017',
		"analysisYears": "25",
		"outageDuration": "48",
		"value_of_lost_load": "100",
		"single_phase_relay_cost": 300,
		"three_phase_relay_cost": 20000,
		# omCostEscalator
		"discountRate" : '0.083',
		"solar": "on",
		"battery": "on",
		"fossil": "on",
		"wind": "off",
		"solarCost" : "1600",
		"solarMax": "100000",
		"solarMin": 0,
		# solarMacrsOptionYears
		# solarItcPercent
		"batteryCapacityCost" : "420",
		"batteryCapacityMax": "100000",
		"batteryCapacityMin": 0,
		"batteryPowerCost" : "840",
		"batteryPowerMax": "100000",
		"batteryPowerMin": 0,
		# batteryMacrsOptionYears
		# batteryItcPercent
		"batteryPowerCostReplace" : "410",
		"batteryCapacityCostReplace" : "200",
		"batteryPowerReplaceYear": '10', # year at which batteryPowerCostReplace (the inverter) is reinstalled, one time
		"batteryCapacityReplaceYear": '10', # year at which batteryCapacityCostReplace (the battery cells) is reinstalled, one time		
		"dieselGenCost": "1000",
		"dieselMax": "100000",
		# dieselMin
		"fuelAvailable": "10000",
		"minGenLoading": "0.3",
		"dieselFuelCostGal": 3, # assuming 4.5 $/MMBtu = 1 $/gal diesel
		"dieselCO2Factor": 22.4,
		"dieselOMCostKw": 25,
		"dieselOMCostKwh": 0.02,
		"dieselOnlyRunsDuringOutage": True,
		# dieselMacrsOptionYears
		"windCost" : "4989",
		"windMax": "100000",
		"windMin": 0,
		"mgParameterOverrides": {"mg0":{}, "mg1":{}, "mg2":{}},
		"maxRuntimeSeconds": "240"
	}
	MICROGRIDS = {
		'mg0': {
			'critical_load_kws': [70, 90, 10],
			'gen_bus': '634',
			'gen_obs_existing': ['solar_634_existing','battery_634_existing'],
			'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'],
			'switch': '632633'
		},
		'mg1': {
			'critical_load_kws': [150, 200, 200, 0],
			'gen_bus': '675',
			'gen_obs_existing': [],
			'loads': ['675a_hospital', '675b_residential1', '675c_residential1', '692_warehouse2'],
			'switch': '671692'
		},
		'mg2': {
			'critical_load_kws': [30, 70],
			'gen_bus': '646',
			'gen_obs_existing': [], #['fossil_684_existing'],
			'loads': ['645_hangar','646_office'],
			'switch': '632645',
		}
	}
	# Run model.
	full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, REOPT_INPUTS, MICROGRIDS, FAULTED_LINES, DESCRIPTION='', INVALIDATE_CACHE=False, OUTAGE_CSV=None, DELETE_FILES=False, open_results=True)
	if os.path.isfile(f'{MODEL_DIR}/0crashed.txt'):
		sys.exit(1)

def test_4mg():
	# Input data.
	MODEL_DIR = f'{PROJ_FOLDER}/lehigh4mgs'
	BASE_DSS = f'{MGU_FOLDER}/testfiles/lehigh_base_phased.dss'
	LOAD_CSV = f'{MGU_FOLDER}/testfiles/lehigh_load.csv'
	FAULTED_LINES = '650632'
	QSTS_STEPS = 24*20
	OUTAGE_CSV = f'{MGU_FOLDER}/testfiles/lehigh_random_outages.csv'
	REOPT_INPUTS = {
		# latitude
		# longitude
		"energyCost": "0.12",
		"wholesaleCost": "0.034", # To turn off energy export/net-metering, set wholesaleCost to "0" and excess PV gen will be curtailed
		"demandCost": '20',
		"solarCanCurtail": True,
		"solarCanExport": True,
		"urdbLabelSwitch": "off",
		# "urdbLabel" : '5b75cfe95457a3454faf0aea', # EPEC General Service TOU Rate https://openei.org/apps/IURDB/rate/view/5b75cfe95457a3454faf0aea#1__Basic_Information
		"year": '2017',
		"analysisYears": "25",
		"outageDuration": "48",
		"value_of_lost_load": "100",
		"single_phase_relay_cost": 300,
		"three_phase_relay_cost": 20000,
		# omCostEscalator
		"discountRate": '0.083',
		"solar": "on",
		"battery": "on",
		"fossil": "on",
		"wind" : "off",
		"solarCost" : "1600",
		"solarMax": "100000",
		"solarMin": 0,
		# solarMacrsOptionYears
		# solarItcPercent
		"batteryCapacityCost" : "420",
		"batteryCapacityMax": "1000000",
		"batteryCapacityMin": 0,
		"batteryPowerCost" : "840",
		"batteryPowerMax": "1000000",
		"batteryPowerMin": 0,
		# batteryMacrsOptionYears
		# batteryItcPercent
		"batteryPowerCostReplace" : "410",
		"batteryCapacityCostReplace" : "200",
		"batteryPowerReplaceYear": '10', # year at which batteryPowerCostReplace (the inverter) is reinstalled, one time
		"batteryCapacityReplaceYear": '10', # year at which batteryCapacityCostReplace (the battery cells) are reinstalled, one time
		"dieselGenCost": "1000",
		"dieselMax": "1000000",
		# dieselMin
		"fuelAvailable": "1000000",
		"minGenLoading": "0",
		"dieselFuelCostGal": 1.5, # assuming 4.5 $/MMBtu = 1 $/gal diesel
		"dieselCO2Factor": 24.1,
		"dieselOMCostKw": 35,
		"dieselOMCostKwh": .02,
		"dieselOnlyRunsDuringOutage": False,
		# dieselMacrsOptionYears
		"windCost" : "4989",
		"windMax": "100000",
		"windMin": 0,
		# windMacrsOptionYears
		# windItcPercent
		"mgParameterOverrides": {"mg0":{}, "mg1":{}, "mg2":{}, "mg3":{}},
		"maxRuntimeSeconds": "240"
	}
	MICROGRIDS = {
		'mg0': {
			'critical_load_kws': [70, 90, 10],
			'gen_bus': '634',
			'gen_obs_existing': ['solar_634_existing','battery_634_existing'],
			'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'],
			'switch': '632633'
		},
		'mg1': {
			'critical_load_kws': [150, 200, 200, 0],
			'gen_bus': '675',
			'gen_obs_existing': ['solar_675_existing'],
			'loads': ['675a_hospital', '675b_residential1', '675c_residential1', '692_warehouse2'],
			'switch': '671692',
		},
		'mg2': {
			'critical_load_kws': [400, 20, 0],
			'gen_bus': '684',
			'gen_obs_existing': ['fossil_684_existing','battery_684_existing'],
			'loads': ['684_command_center','652_residential','611_runway'],
			'switch': '671684',
		},
		'mg3': {
			'critical_load_kws': [30, 70],
			'gen_bus': '646',
			'gen_obs_existing': [],
			'loads': ['645_hangar','646_office'],
			'switch': '632645',
		}
	}
	# Run model.
	full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, REOPT_INPUTS, MICROGRIDS, FAULTED_LINES, DESCRIPTION='', INVALIDATE_CACHE=False, OUTAGE_CSV=OUTAGE_CSV, DELETE_FILES=False, open_results=True)
	if os.path.isfile(f'{MODEL_DIR}/0crashed.txt'):
		sys.exit(1)

def test_auto3mg():
	# Input data.
	CIRC_FILE = f'{MGU_FOLDER}/testfiles/lehigh_base_phased.dss'
	CRITICAL_LOADS = ['645_hangar', '684_command_center', '611_runway', '675a_hospital', '634a_data_center', '634b_radar', '634c_atc_tower']
	MODEL_DIR = f'{PROJ_FOLDER}/lehighauto_3mg'
	BASE_DSS = f'{MGU_FOLDER}/testfiles/lehigh_base_phased.dss'
	LOAD_CSV = f'{MGU_FOLDER}/testfiles/lehigh_load.csv'
	FAULTED_LINES = '670671'
	QSTS_STEPS = 24*20
	OUTAGE_CSV = f'{MGU_FOLDER}/testfiles/lehigh_random_outages.csv'
	REOPT_INPUTS = {
		# latitude
		# longitude
		"energyCost": "0.12",
		"wholesaleCost": "0", # To turn off energy export/net-metering, set wholesaleCost to "0" and excess PV gen will be curtailed
		"demandCost": '20',
		"solarCanCurtail": True,
		"solarCanExport": True,
		"urdbLabelSwitch": "off",
		# "urdbLabel" : '5b75cfe95457a3454faf0aea', # EPEC General Service TOU Rate https://openei.org/apps/IURDB/rate/view/5b75cfe95457a3454faf0aea#1__Basic_Information
		"year" : '2017',
		"analysisYears": "25",
		"outageDuration": "48",
		"value_of_lost_load": "100",
		"single_phase_relay_cost": 300,
		"three_phase_relay_cost": 20000,
		# omCostEscalator
		"discountRate" : '0.083',
		"solar": "on",
		"battery": "on",
		"fossil": "on",
		"wind" : "off",
		"solarCost" : "1600",
		"solarMax": "100000",
		"solarMin": 0,
		# solarMacrsOptionYears
		# solarItcPercent
		"batteryCapacityCost" : "420",
		"batteryCapacityMax": "100000",
		"batteryCapacityMin": 0,
		"batteryPowerCost" : "840",
		"batteryPowerMax": "100000",
		"batteryPowerMin": 0,
		# batteryMacrsOptionYears
		# batteryItcPercent
		"batteryPowerCostReplace" : "410",
		"batteryCapacityCostReplace" : "200",
		"batteryPowerReplaceYear": '10', # year at which batteryPowerCostReplace (the inverter) is reinstalled, one time
		"batteryCapacityReplaceYear": '10', # year at which batteryCapacityCostReplace (the battery cells) is reinstalled, one time		
		"dieselGenCost": "1000",
		"dieselMax": "100000",
		# dieselMin
		"fuelAvailable": "10000",
		"minGenLoading": "0.3",
		"dieselFuelCostGal": 3, # assuming 4.5 $/MMBtu = 1 $/gal diesel
		"dieselCO2Factor": 22.4,
		"dieselOMCostKw": 25,
		"dieselOMCostKwh": 0.02,
		"dieselOnlyRunsDuringOutage": True,
		# dieselMacrsOptionYears
		"windCost" : "4989",
		"windMax": "100000",
		"windMin": 0,
		# windMacrsOptionYears
		# windItcPercent
		"mgParameterOverrides": {"mg0":{}, "mg1": {}, "mg2":{}},
		"maxRuntimeSeconds": "240"
	}
	ALGO = 'branch' #'lukes'
	G = dssConvert.dss_to_networkx(CIRC_FILE)
	omd = dssConvert.dssToOmd(CIRC_FILE, '', RADIUS=0.0004, write_out=False)
	MG_GROUPS = gmg.form_mg_groups(G, CRITICAL_LOADS, ALGO)
	MICROGRIDS = gmg.form_mg_mines(G, MG_GROUPS, CRITICAL_LOADS, omd)
	# MICROGRIDS = {
	# 	'mg0': {
	# 		'loads': ['634a_data_center','634b_radar','634c_atc_tower'],
	# 		'switch': '632633',
	# 		'gen_bus': '634',
	# 		'gen_obs_existing': ['solar_634_existing','battery_634_existing'],
	# 		'critical_load_kws': [70,90,10]
	# 	},
	# 	'mg1': {
	# 		'loads': ['675a_hospital','675b_residential1','675c_residential1','692_warehouse2'],
	# 		'switch': '671692',
	# 		'gen_bus': '675',
	# 		'gen_obs_existing': ['fossil_675_existing'],
	# 		'critical_load_kws': [150,200,200]
	# 	},
	# 	'mg2': {
	# 		'loads': ['645_hangar','646_office'],
	# 		'switch': '632645',
	# 		'gen_bus': '646',
	# 		'gen_obs_existing': [], #['fossil_684_existing'],
	# 		'critical_load_kws': [30,70]
	# 	}
	# }
	# Run model.
	full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, REOPT_INPUTS, MICROGRIDS, FAULTED_LINES, DESCRIPTION='', INVALIDATE_CACHE=False, OUTAGE_CSV=OUTAGE_CSV, DELETE_FILES=False, open_results=True)
	if os.path.isfile(f'{MODEL_DIR}/0crashed.txt'):
		sys.exit(1)

def test_mackelroy():
	'''
	- We used the iowa240 circuit and bottom-up partitioning with at least 5 microgrids
	- We have an essentially random selection of critical loads
	'''
	MODEL_DIR = f'{PROJ_FOLDER}/mackelroy'
	BASE_DSS = f'{MGU_FOLDER}/testfiles/mackelroy.dss'
	LOAD_CSV = f'{MGU_FOLDER}/testfiles/mackelroy.csv'
	QSTS_STEPS = 24*20
	REOPT_INPUTS = {
		"energyCost": "0.12",
		"wholesaleCost": "0.034",
		"demandCost": "20",
		"solarCanCurtail": True,
		"solarCanExport": True,
		"urdbLabelSwitch": "off",
		"urdbLabel": "5b75cfe95457a3454faf0aea",
		"year": "2017",
		"analysisYears": "25",
		"outageDuration": "48",
		"value_of_lost_load": "1",
		"single_phase_relay_cost": "300",
		"three_phase_relay_cost": "20000",
		"omCostEscalator": "0.025",
		"discountRate": "0.083",
		"solar": "on",
		"battery": "on",
		"fossil": "on",
		"wind": "off",
		"solarCost": "1600",
		"solarMax": "1000000000",
		"solarMin": "0",
		"solarMacrsOptionYears": "5",
		"solarItcPercent": "0.26",
		"batteryCapacityCost": "420",
		"batteryCapacityMax": "1000000",
		"batteryCapacityMin": "0",
		"batteryPowerCost": "840",
		"batteryPowerMax": "1000000000",
		"batteryPowerMin": "0",
		"batteryMacrsOptionYears": "7",
		"batteryItcPercent": "0",
		"batteryPowerCostReplace": "410",
		"batteryCapacityCostReplace": "200",
		"batteryPowerReplaceYear": "10",
		"batteryCapacityReplaceYear": "10",
		"dieselGenCost": "500",
		"dieselMax": "1000000000",
		"dieselMin": "0",
		"fuelAvailable": "50000",
		"minGenLoading": "0.3",
		"dieselFuelCostGal": "3",
		"dieselCO2Factor": "22.4",
		"dieselOMCostKw": "10",
		"dieselOMCostKwh": "0",
		"dieselOnlyRunsDuringOutage": False,
		"dieselMacrsOptionYears": "0",
		"windCost": "4989",
		"windMax": "1000000000",
		"windMin": "0",
		"windMacrsOptionYears": "5",
		"windItcPercent": "0.26",
		"mgParameterOverrides": { "mg0": {}, "mg1": {}, "mg2": {}, "mg3": {}, "mg4": {} },
		"maxRuntimeSeconds": "240" 
	}
	MICROGRIDS = {
	"mg0": {
		"loads": [
			"load_3002"
		],
		"switch": "l_3003_3002",
		"gen_bus": "bus3002",
		"gen_obs_existing": [],
		"critical_load_kws": [
			0.0
		],
		"max_potential": "700",
		"max_potential_diesel": "1000000",
		"battery_capacity": "10000"
	},
	"mg1": {
			"loads": [
				"load_3004"
			],
			"switch": "l_3003_3004",
			"gen_bus": "bus3004",
			"gen_obs_existing": [],
			"critical_load_kws": [
				3.117
			],
			"max_potential": "700",
			"max_potential_diesel": "1000000",
			"battery_capacity": "10000"
		},
		"mg2": {
			"loads": [
				"load_1006",
				"load_1007",
				"load_1011",
				"load_1012",
				"load_1014",
				"load_1015",
				"load_1016",
				"load_1017",
				"load_1003",
				"load_1004",
				"load_1005",
				"load_1008",
				"load_1009",
				"load_1010",
				"load_1013"
			],
			"switch": "cb_101",
			"gen_bus": "bus1001",
			"gen_obs_existing": [],
			"critical_load_kws": [
				5.04,
				0.0,
				3.125,
				0.0,
				0.458,
				0.0,
				3.083,
				0.0,
				15.29,
				0.0,
				4.916,
				0.0,
				17.081,
				0.0,
				1.537
			],
			"max_potential": "700",
			"max_potential_diesel": "1000000",
			"battery_capacity": "10000"
		},
		"mg3": {
			"loads": [
				"load_2008",
				"load_2009",
				"load_2014",
				"load_2015",
				"load_2016",
				"load_2017",
				"load_2018",
				"load_2020",
				"load_2022",
				"load_2023",
				"load_2024",
				"load_2025",
				"load_2028",
				"load_2031",
				"load_2045",
				"load_2046",
				"load_2047",
				"load_2048",
				"load_2049",
				"load_2050",
				"load_2051",
				"load_2054",
				"load_2055",
				"load_2056",
				"load_2059",
				"load_2060",
				"load_2002",
				"load_2003",
				"load_2005",
				"load_2010",
				"load_2011",
				"load_2029",
				"load_2030",
				"load_2032",
				"load_2034",
				"load_2035",
				"load_2037",
				"load_2040",
				"load_2041",
				"load_2042",
				"load_2043",
				"load_2052",
				"load_2053",
				"load_2058"
			],
			"switch": "cb_201",
			"gen_bus": "bus2001",
			"gen_obs_existing": [],
			"critical_load_kws": [
				2.067,
				0.0,
				2.816,
				0.0,
				1.64,
				0.0,
				2.809,
				0.0,
				2.728,
				0.0,
				2.549,
				0.0,
				0.0,
				0.0,
				2.175,
				0.0,
				5.512,
				0.0,
				3.538,
				0.0,
				5.778,
				0.0,
				4.26,
				0.0,
				2.635,
				0.0,
				0.0,
				14.286,
				0.0,
				2.29,
				0.0,
				9.427,
				0.0,
				2.217,
				0.0,
				3.931,
				0.0,
				81.76,
				0.0,
				4.223,
				0.0,
				40.029,
				0.0,
				31.48
			],
			"max_potential": "700",
			"max_potential_diesel": "1000000",
			"battery_capacity": "10000"
		},
		"mg4": {
			"loads": [
				"load_3009",
				"load_3010",
				"load_3011",
				"load_3012",
				"load_3013",
				"load_3014",
				"load_3016",
				"load_3017",
				"load_3018",
				"load_3019",
				"load_3020",
				"load_3021",
				"load_3023",
				"load_3024",
				"load_3025",
				"load_3026",
				"load_3027",
				"load_3028",
				"load_3029",
				"load_3041",
				"load_3042",
				"load_3043",
				"load_3044",
				"load_3045",
				"load_3056",
				"load_3057",
				"load_3058",
				"load_3059",
				"load_3060",
				"load_3061",
				"load_3062",
				"load_3063",
				"load_3064",
				"load_3065",
				"load_3066",
				"load_3067",
				"load_3083",
				"load_3084",
				"load_3085",
				"load_3086",
				"load_3087",
				"load_3088",
				"load_3089",
				"load_3090",
				"load_3091",
				"load_3093",
				"load_3094",
				"load_3095",
				"load_3096",
				"load_3097",
				"load_3098",
				"load_3099",
				"load_3101",
				"load_3102",
				"load_3103",
				"load_3104",
				"load_3105",
				"load_3106",
				"load_3108",
				"load_3109",
				"load_3110",
				"load_3111",
				"load_3112",
				"load_3114",
				"load_3115",
				"load_3116",
				"load_3117",
				"load_3120",
				"load_3121",
				"load_3122",
				"load_3123",
				"load_3124",
				"load_3125",
				"load_3126",
				"load_3127",
				"load_3128",
				"load_3129",
				"load_3130",
				"load_3131",
				"load_3132",
				"load_3134",
				"load_3135",
				"load_3136",
				"load_3137",
				"load_3138",
				"load_3139",
				"load_3141",
				"load_3142",
				"load_3143",
				"load_3144",
				"load_3145",
				"load_3146",
				"load_3147",
				"load_3148",
				"load_3149",
				"load_3150",
				"load_3151",
				"load_3152",
				"load_3153",
				"load_3154",
				"load_3155",
				"load_3157",
				"load_3158",
				"load_3159",
				"load_3160",
				"load_3161",
				"load_3162",
				"load_3006",
				"load_3007",
				"load_3031",
				"load_3032",
				"load_3033",
				"load_3034",
				"load_3035",
				"load_3036",
				"load_3037",
				"load_3038",
				"load_3039",
				"load_3047",
				"load_3048",
				"load_3049",
				"load_3050",
				"load_3051",
				"load_3052",
				"load_3054",
				"load_3070",
				"load_3071",
				"load_3072",
				"load_3073",
				"load_3074",
				"load_3077",
				"load_3078",
				"load_3081"
			],
			"switch": "l_3003_3005",
			"gen_bus": "bus3005",
			"gen_obs_existing": [],
			"critical_load_kws": [
				4.064,
				0.0,
				7.419,
				0.0,
				2.539,
				0.0,
				6.246,
				0.0,
				5.351,
				0.0,
				5.984,
				0.0,
				4.344,
				0.0,
				6.546,
				0.0,
				7.116,
				0.0,
				2.494,
				0.0,
				7.719,
				0.0,
				4.119,
				0.0,
				3.796,
				0.0,
				3.475,
				0.0,
				3.63,
				0.0,
				0.929,
				0.0,
				7.792,
				0.0,
				3.257,
				0.0,
				3.831,
				0.0,
				6.765,
				0.0,
				4.101,
				0.0,
				0.836,
				0.0,
				2.536,
				0.0,
				3.12,
				0.0,
				2.842,
				0.0,
				6.461,
				0.0,
				2.387,
				0.0,
				6.718,
				0.0,
				3.052,
				0.0,
				2.175,
				0.0,
				9.577,
				0.0,
				9.339,
				0.0,
				7.794,
				0.0,
				3.688,
				0.0,
				2.845,
				0.0,
				0.0,
				3.261,
				0.0,
				6.249,
				0.0,
				3.688,
				0.0,
				3.657,
				0.0,
				11.56,
				0.0,
				7.005,
				0.0,
				13.759,
				0.0,
				0.0,
				0.0,
				4.017,
				0.0,
				0.482,
				0.0,
				1.616,
				0.0,
				9.987,
				0.0,
				2.602,
				0.0,
				1.934,
				0.0,
				4.836,
				0.0,
				9.74,
				0.0,
				9.776,
				0.0,
				2.744,
				0.0,
				0.0,
				9.425,
				0.0,
				5.709,
				0.0,
				4.776,
				0.0,
				4.026,
				0.0,
				6.13,
				0.0,
				10.213,
				0.0,
				1.671,
				0.0,
				2.412,
				0.0,
				2.471,
				0.0,
				2.163,
				0.0,
				2.297,
				0.0,
				41.037,
				0.0,
				1.581
			],
			"max_potential": "700",
			"max_potential_diesel": "1000000",
			"battery_capacity": "10000"
		}
	}
	FAULTED_LINES = '670671'
	full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, REOPT_INPUTS, MICROGRIDS, FAULTED_LINES, DESCRIPTION='', INVALIDATE_CACHE=False, OUTAGE_CSV=None, DELETE_FILES=False, open_results=True)
	if os.path.isfile(f'{MODEL_DIR}/0crashed.txt'):
		sys.exit(1)

if __name__ == '__main__':
	test_1mg()
	test_2mg()
	test_3mg()
	test_4mg()
	test_auto3mg()
	test_mackelroy()