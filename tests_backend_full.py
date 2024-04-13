'''Test file with 1 microgrid for all loads and with multiple existing gens of all types
in microgrid_test_4mg.py for economic comparison'''

from microgridup import *
import microgridup_gen_mgs as gmg
from omf.solvers.opendss import dssConvert

def test_1mg():
	# Input data.
	MODEL_DIR = f'{PROJ_FOLDER}/lehigh1mg'
	BASE_DSS = f'{MGU_FOLDER}/testfiles/lehigh_base_1mg.dss'
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
	}
	MICROGRIDS = {
		'mg0': {
			'critical_load_kws': [70, 90, 10, 150, 200, 200, 400, 20, 30, 70, 0, 0],
			'gen_bus': '670',
			'gen_obs_existing': ['solar_634_existing','solar_675_existing','fossil_684_existing', 'fossil_646_existing', 'battery_634_existing', 'battery_684_existing'],
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
	BASE_DSS = f'{MGU_FOLDER}/testfiles/lehigh_base_2mg.dss'
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
		"mgParameterOverrides": {"mg0":{}, "mg1":{}}
	}
	MICROGRIDS = {
		'mg0': {
			'critical_load_kws': [70, 90, 10],
			'gen_bus': '634',
		 	'gen_obs_existing': ['wind_634_existing'],
			'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'],
			'switch': '632633'
		},
		'mg1': {
			'critical_load_kws': [150, 200, 200, 0],
			'gen_bus': '675',
			'gen_obs_existing': ['battery_675_existing', 'battery_675_2_existing'],
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
	BASE_DSS = f'{MGU_FOLDER}/testfiles/lehigh_base_3mg.dss'
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
		"mgParameterOverrides": {"mg0":{}, "mg1":{}, "mg2":{}}
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
			'gen_obs_existing': ['fossil_675_existing'],
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
	BASE_DSS = f'{MGU_FOLDER}/testfiles/lehigh_base_4mg.dss'
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
		"mgParameterOverrides": {"mg0":{}, "mg1":{}, "mg2":{}, "mg3":{}}
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
			'gen_obs_existing': ['battery_646_existing'],
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
	CIRC_FILE = f'{MGU_FOLDER}/testfiles/lehigh_base_3mg.dss'
	CRITICAL_LOADS = ['645_hangar', '684_command_center', '611_runway', '675a_hospital', '634a_data_center', '634b_radar', '634c_atc_tower']
	MODEL_DIR = f'{PROJ_FOLDER}/lehighauto_3mg'
	BASE_DSS = f'{MGU_FOLDER}/testfiles/lehigh_base_3mg.dss'
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
		"mgParameterOverrides": {"mg0":{}, "mg1": {}, "mg2":{}}
	}
	ALGO = 'branch' #'lukes'
	G = dssConvert.dss_to_networkx(CIRC_FILE)
	omd = dssConvert.dssToOmd(CIRC_FILE, '', RADIUS=0.0004, write_out=False)
	MG_GROUPS = gmg.form_mg_groups(CIRC_FILE, CRITICAL_LOADS, ALGO)
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

if __name__ == '__main__':
	test_1mg()
	test_2mg()
	test_3mg()
	test_4mg()
	test_auto3mg()