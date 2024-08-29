'''
Test file with 1 microgrid for all loads and with multiple existing gens of all types in microgrid_test_4mg.py for economic comparison
'''


import os, sys
from omf.solvers.opendss import dssConvert
import microgridup_gen_mgs as gmg
import microgridup


def test_1mg():
	data = {
		'MODEL_DIR': 'lehigh1mg',
		'BASE_DSS': f'{microgridup.MGU_DIR}/testfiles/lehigh_base_phased.dss',
		'LOAD_CSV': f'{microgridup.MGU_DIR}/testfiles/lehigh_load.csv',
		'QSTS_STEPS': 480,
		'REOPT_INPUTS': {
			'energyCost': 0.12,
			'wholesaleCost': 0.034,
			'demandCost': 20.0,
			'solarCanCurtail': True,
			'solarCanExport': True,
			'urdbLabelSwitch': False,
			'urdbLabel': '5b75cfe95457a3454faf0aea',
			'year': 2017,
			'analysisYears': 25,
			'outageDuration': 48,
			'value_of_lost_load': 100.0,
			'omCostEscalator': 0.025,
			'discountRate': 0.083,
			'solar': True,
			'battery': True,
			'fossil': True,
			'wind': False,
			'solarCost': 1600.0,
			'solarMax': 10000.0,
			'solarMin': 0.0,
			'solarMacrsOptionYears': 0,
			'solarItcPercent': 0.26,
			'batteryCapacityCost': 420.0,
			'batteryCapacityMax': 100000.0,
			'batteryCapacityMin': 0.0,
			'batteryPowerCost': 840.0,
			'batteryPowerMax': 10000.0,
			'batteryPowerMin': 0.0,
			'batteryMacrsOptionYears': 0,
			'batteryItcPercent': 0.0,
			'batteryPowerCostReplace': 410.0,
			'batteryCapacityCostReplace': 200.0,
			'batteryPowerReplaceYear': 10,
			'batteryCapacityReplaceYear': 10,
			'dieselGenCost': 1000.0,
			'dieselMax': 10000.0,
			'dieselMin': 0.0,
			'fuelAvailable': 150000.0,
			'minGenLoading': 0.0,
			'dieselFuelCostGal': 1.5,
			'dieselCO2Factor': 24.1,
			'dieselOMCostKw': 35.0,
			'dieselOMCostKwh': 0.02,
			'dieselOnlyRunsDuringOutage': False,
			'dieselMacrsOptionYears': 0,
			'windCost': 4989.0,
			'windMax': 1000.0,
			'windMin': 0.0,
			'windMacrsOptionYears': 0,
			'windItcPercent': 0.26,
			'maxRuntimeSeconds': 240,
		},
		'MICROGRIDS': {
			'mg0': {
				'gen_bus': '670',
				'gen_obs_existing': [
					'solar_634_existing',
					'solar_675_existing',
					'fossil_684_existing',
					'battery_634_existing',
					'battery_684_existing'
				],
				'loads': [
					'634a_data_center',
					'634b_radar',
					'634c_atc_tower',
					'675a_hospital',
					'675b_residential1',
					'675c_residential1',
					'692_warehouse2',
					'684_command_center',
					'652_residential',
					'611_runway',
					'645_hangar',
					'646_office'
				],
				'parameter_overrides': {
					'reopt_inputs': {}
				},
				'switch': '650632'
			}
		},
		'FAULTED_LINES': ['650632'],
		'OUTAGE_CSV': f'{microgridup.MGU_DIR}/testfiles/lehigh_random_outages.csv',
		'CRITICAL_LOADS': [
			'684_command_center',
			'634a_data_center',
			'634b_radar',
			'634c_atc_tower',
			'692_warehouse2',
			'675a_hospital',
			'675b_residential1',
			'675c_residential1',
			'611_runway',
			'652_residential'
		],
		'DESCRIPTION': '',
		'singlePhaseRelayCost': 300.0,
		'threePhaseRelayCost': 20000.0,
	}
	# Run model.
	microgridup.main(data, invalidate_cache=False, open_results=True)
	if os.path.isfile(f'{microgridup.PROJ_DIR}/{data["MODEL_DIR"]}/0crashed.txt'):
		sys.exit(1)


def test_2mg():
	data = {
		'MODEL_DIR': 'lehigh2mgs',
		'BASE_DSS': f'{microgridup.MGU_DIR}/testfiles/lehigh_base_phased.dss',
		'LOAD_CSV': f'{microgridup.MGU_DIR}/testfiles/lehigh_load.csv',
		'QSTS_STEPS': 480,
		'REOPT_INPUTS': {
			'energyCost': 0.12,
			'wholesaleCost': 0.034,
			'demandCost': 20.0,
			'solarCanCurtail': True,
			'solarCanExport': True,
			'urdbLabelSwitch': False,
			'urdbLabel': '5b75cfe95457a3454faf0aea',
			'year': 2017,
			'analysisYears': 25,
			'outageDuration': 48,
			'value_of_lost_load': 100.0,
			'omCostEscalator': 0.025,
			'discountRate': 0.083,
			'solar': True,
			'battery': True,
			'fossil': True,
			'wind': True,
			'solarCost': 1600.0,
			'solarMax': 10000.0,
			'solarMin': 0.0,
			'solarMacrsOptionYears': 0,
			'solarItcPercent': 0.26,
			'batteryCapacityCost': 420.0,
			'batteryCapacityMax': 10000.0,
			'batteryCapacityMin': 0.0,
			'batteryPowerCost': 840.0,
			'batteryPowerMax': 10000.0,
			'batteryPowerMin': 0.0,
			'batteryMacrsOptionYears': 0,
			'batteryItcPercent': 0.0,
			'batteryPowerCostReplace': 410.0,
			'batteryCapacityCostReplace': 200.0,
			'batteryPowerReplaceYear': 10,
			'batteryCapacityReplaceYear': 10,
			'dieselGenCost': 500.0,
			'dieselMax': 100000.0,
			'dieselMin': 0.0,
			'fuelAvailable': 10000.0,
			'minGenLoading': 0.3,
			'dieselFuelCostGal': 3.0,
			'dieselCO2Factor': 22.4,
			'dieselOMCostKw': 25.0,
			'dieselOMCostKwh': 0.02,
			'dieselOnlyRunsDuringOutage': True,
			'dieselMacrsOptionYears': 0,
			'windCost': 1500.0,
			'windMax': 10000.0,
			'windMin': 0.0,
			'windMacrsOptionYears': 0,
			'windItcPercent': 0.26,
			'maxRuntimeSeconds': 240
		},
		'MICROGRIDS': {
			'mg0': {
				'gen_bus': '634',
				'gen_obs_existing': [],
				'loads': [
					'634a_data_center',
					'634b_radar',
					'634c_atc_tower'
				],
				'parameter_overrides': {
					'reopt_inputs': {}
				},
				'switch': '632633'
			},
			'mg1': {
				'gen_bus': '675',
				'gen_obs_existing': [],
				'loads': [
					'675a_hospital',
					'675b_residential1',
					'675c_residential1',
					'692_warehouse2'
				],
				'parameter_overrides': {
					'reopt_inputs': {}
				},
				'switch': '671692'
			}
		},
		'FAULTED_LINES': ['650632'],
		'OUTAGE_CSV': None,
		'CRITICAL_LOADS': [
			'634a_data_center',
			'634b_radar',
			'634c_atc_tower',
			'675a_hospital',
			'675b_residential1',
			'675c_residential1'
		],
		'DESCRIPTION': '',
		'singlePhaseRelayCost': 300.0,
		'threePhaseRelayCost': 20000.0,
	}
	# Run model.
	microgridup.main(data, invalidate_cache=False, open_results=True)
	if os.path.isfile(f'{microgridup.PROJ_DIR}/{data["MODEL_DIR"]}/0crashed.txt'):
		sys.exit(1)	


def test_3mg():
	data = {
		'MODEL_DIR': 'lehigh3mgs',
		'BASE_DSS': f'{microgridup.MGU_DIR}/testfiles/lehigh_base_phased.dss',
		'LOAD_CSV': f'{microgridup.MGU_DIR}/testfiles/lehigh_load.csv',
		'QSTS_STEPS': 480,
		'REOPT_INPUTS': {
			'energyCost': 0.12,
			'wholesaleCost': 0.0,
			'demandCost': 20.0,
			'solarCanCurtail': True,
			'solarCanExport': True,
			'urdbLabelSwitch': False,
			'urdbLabel': '5b75cfe95457a3454faf0aea',
			'year': 2017,
			'analysisYears': 25,
			'outageDuration': 48,
			'value_of_lost_load': 100.0,
			'omCostEscalator': 0.025,
			'discountRate': 0.083,
			'solar': True,
			'battery': True,
			'fossil': True,
			'wind': False,
			'solarCost': 1600.0,
			'solarMax': 100000.0,
			'solarMin': 0.0,
			'solarMacrsOptionYears': 0,
			'solarItcPercent': 0.26,
			'batteryCapacityCost': 420.0,
			'batteryCapacityMax': 100000.0,
			'batteryCapacityMin': 0.0,
			'batteryPowerCost': 840.0,
			'batteryPowerMax': 100000.0,
			'batteryPowerMin': 0.0,
			'batteryMacrsOptionYears': 0,
			'batteryItcPercent': 0.0,
			'batteryPowerCostReplace': 410.0,
			'batteryCapacityCostReplace': 200.0,
			'batteryPowerReplaceYear': 10,
			'batteryCapacityReplaceYear': 10,
			'dieselGenCost': 1000.0,
			'dieselMax': 100000.0,
			'dieselMin': 0.0,
			'fuelAvailable': 10000.0,
			'minGenLoading': 0.3,
			'dieselFuelCostGal': 3.0,
			'dieselCO2Factor': 22.4,
			'dieselOMCostKw': 25.0,
			'dieselOMCostKwh': 0.02,
			'dieselOnlyRunsDuringOutage': True,
			'dieselMacrsOptionYears': 0,
			'windCost': 4989.0,
			'windMax': 100000.0,
			'windMin': 0.0,
			'windMacrsOptionYears': 0,
			'windItcPercent': 0.26,
			'maxRuntimeSeconds': 240
		},
		'MICROGRIDS': {
			'mg0': {
				'gen_bus': '634',
				'gen_obs_existing': [
					'solar_634_existing',
					'battery_634_existing'
				],
				'loads': [
					'634a_data_center',
					'634b_radar',
					'634c_atc_tower'
				],
				'parameter_overrides': {
					'reopt_inputs': {}
				},
				'switch': '632633'
			},
			'mg1': {
				'gen_bus': '675',
				'gen_obs_existing': [],
				'loads': [
					'675a_hospital',
					'675b_residential1',
					'675c_residential1',
					'692_warehouse2'
				],
				'parameter_overrides': {
					'reopt_inputs': {}
				},
				'switch': '671692'
			},
			'mg2': {
				'gen_bus': '646',
				'gen_obs_existing': [],
				'loads': [
					'645_hangar',
					'646_office'
				],
				'parameter_overrides': {
					'reopt_inputs': {}
				},
				'switch': '632645'
			}
		},
		'FAULTED_LINES': ['650632'],
		'OUTAGE_CSV': None,
		'CRITICAL_LOADS': [
			'634a_data_center',
			'634b_radar',
			'634c_atc_tower',
			'645_hangar',
			'646_office',
			'675a_hospital',
			'675b_residential1',
			'675c_residential1'
		],
		'DESCRIPTION': '',
		'singlePhaseRelayCost': 300.0,
		'threePhaseRelayCost': 20000.0
	}
	# Run model.
	microgridup.main(data, invalidate_cache=False, open_results=True)
	if os.path.isfile(f'{microgridup.PROJ_DIR}/{data["MODEL_DIR"]}/0crashed.txt'):
		sys.exit(1)	


def test_4mg():
	data = {
		'MODEL_DIR': 'lehigh4mgs',
		'BASE_DSS': f'{microgridup.MGU_DIR}/testfiles/lehigh_base_phased.dss',
		'LOAD_CSV': f'{microgridup.MGU_DIR}/testfiles/lehigh_load.csv',
		'QSTS_STEPS': 480,
		'REOPT_INPUTS': {
			'energyCost': 0.12,
			'wholesaleCost': 0.034,
			'demandCost': 20.0,
			'solarCanCurtail': True,
			'solarCanExport': True,
			'urdbLabelSwitch': False,
			'urdbLabel': '5b75cfe95457a3454faf0aea',
			'year': 2017,
			'analysisYears': 25,
			'outageDuration': 48,
			'value_of_lost_load': 100.0,
			'omCostEscalator': 0.025,
			'discountRate': 0.083,
			'solar': True,
			'battery': True,
			'fossil': True,
			'wind': False,
			'solarCost': 1600.0,
			'solarMax': 100000.0,
			'solarMin': 0.0,
			'solarMacrsOptionYears': 0,
			'solarItcPercent': 0.26,
			'batteryCapacityCost': 420.0,
			'batteryCapacityMax': 1000000.0,
			'batteryCapacityMin': 0.0,
			'batteryPowerCost': 840.0,
			'batteryPowerMax': 1000000.0,
			'batteryPowerMin': 0.0,
			'batteryMacrsOptionYears': 0,
			'batteryItcPercent': 0.0,
			'batteryPowerCostReplace': 410.0,
			'batteryCapacityCostReplace': 200.0,
			'batteryPowerReplaceYear': 10,
			'batteryCapacityReplaceYear': 10,
			'dieselGenCost': 1000.0,
			'dieselMax': 1000000.0,
			'dieselMin': 0.0,
			'fuelAvailable': 1000000.0,
			'minGenLoading': 0.0,
			'dieselFuelCostGal': 1.5,
			'dieselCO2Factor': 24.1,
			'dieselOMCostKw': 35.0,
			'dieselOMCostKwh': 0.02,
			'dieselOnlyRunsDuringOutage': False,
			'dieselMacrsOptionYears': 0,
			'windCost': 4989.0,
			'windMax': 100000.0,
			'windMin': 0.0,
			'windMacrsOptionYears': 0,
			'windItcPercent': 0.26,
			'maxRuntimeSeconds': 240
		},
		'MICROGRIDS': {
			'mg0': {
				'gen_bus': '634',
				'gen_obs_existing': [
					'solar_634_existing',
					'battery_634_existing'
				],
				'loads': [
					'634a_data_center',
					'634b_radar',
					'634c_atc_tower'
				],
				'parameter_overrides': {
					'reopt_inputs': {}
				},
				'switch': '632633'
			},
			'mg1': {
				'gen_bus': '675',
				'gen_obs_existing': [
					'solar_675_existing'
				],
				'loads': [
					'675a_hospital',
					'675b_residential1',
					'675c_residential1',
					'692_warehouse2'
				],
				'parameter_overrides': {
					'reopt_inputs': {}
				},
				'switch': '671692'
			},
			'mg2': {
				'gen_bus': '684',
				'gen_obs_existing': [
					'fossil_684_existing',
					'battery_684_existing'
				],
				'loads': [
					'684_command_center',
					'652_residential',
					'611_runway'
				],
				'parameter_overrides': {
					'reopt_inputs': {}
				},
				'switch': '671684'
			},
			'mg3': {
				'gen_bus': '646',
				'gen_obs_existing': [],
				'loads': [
					'645_hangar',
					'646_office'
				],
				'parameter_overrides': {
					'reopt_inputs': {}
				},
				'switch': '632645'
			}
		},
		'FAULTED_LINES': ['650632'],
		'OUTAGE_CSV': f'{microgridup.MGU_DIR}/testfiles/lehigh_random_outages.csv',
		'CRITICAL_LOADS': [
			'684_command_center',
			'634a_data_center',
			'634b_radar',
			'634c_atc_tower',
			'645_hangar',
			'646_office',
			'675a_hospital',
			'675b_residential1',
			'675c_residential1',
			'652_residential'
		],
		'DESCRIPTION': '',
		'singlePhaseRelayCost': 300.0,
		'threePhaseRelayCost': 20000.0
	}
	# Run model.
	microgridup.main(data, invalidate_cache=False, open_results=True)
	if os.path.isfile(f'{microgridup.PROJ_DIR}/{data["MODEL_DIR"]}/0crashed.txt'):
		sys.exit(1)	


def test_auto3mg():
	CIRC_FILE = f'{microgridup.MGU_DIR}/testfiles/lehigh_base_phased.dss'
	G = dssConvert.dss_to_networkx(CIRC_FILE)
	CRITICAL_LOADS = ['645_hangar', '684_command_center', '611_runway', '675a_hospital', '634a_data_center', '634b_radar', '634c_atc_tower']
	ALGO = 'branch' #'lukes'
	MG_GROUPS = gmg.form_mg_groups(G, CRITICAL_LOADS, ALGO)
	omd = dssConvert.dssToOmd(CIRC_FILE, '', RADIUS=0.0004, write_out=False)
	MICROGRIDS = gmg.form_mg_mines(G, MG_GROUPS, omd)
	for mg in MICROGRIDS:
		MICROGRIDS[mg]['parameter_overrides'] = {
			'reopt_inputs': {}
		}
	data = {
		'MODEL_DIR': 'lehighauto_3mg',
		'BASE_DSS': f'{microgridup.MGU_DIR}/testfiles/lehigh_base_phased.dss',
		'LOAD_CSV': f'{microgridup.MGU_DIR}/testfiles/lehigh_load.csv',
		'QSTS_STEPS': 480,
		'REOPT_INPUTS': {
			'energyCost': 0.12,
			'wholesaleCost': 0.0,
			'demandCost': 20.0,
			'solarCanCurtail': True,
			'solarCanExport': True,
			'urdbLabelSwitch': False,
			'urdbLabel': '5b75cfe95457a3454faf0aea',
			'year': 2017,
			'analysisYears': 25,
			'outageDuration': 48,
			'value_of_lost_load': 100.0,
			'omCostEscalator': 0.025,
			'discountRate': 0.083,
			'solar': True,
			'battery': True,
			'fossil': True,
			'wind': False,
			'solarCost': 1600.0,
			'solarMax': 100000.0,
			'solarMin': 0.0,
			'solarMacrsOptionYears': 5,
			'solarItcPercent': 0.26,
			'batteryCapacityCost': 420.0,
			'batteryCapacityMax': 100000.0,
			'batteryCapacityMin': 0.0,
			'batteryPowerCost': 840.0,
			'batteryPowerMax': 100000.0,
			'batteryPowerMin': 0.0,
			'batteryMacrsOptionYears': 7,
			'batteryItcPercent': 0.0,
			'batteryPowerCostReplace': 410.0,
			'batteryCapacityCostReplace': 200.0,
			'batteryPowerReplaceYear': 10,
			'batteryCapacityReplaceYear': 10,
			'dieselGenCost': 1000.0,
			'dieselMax': 100000.0,
			'dieselMin': 0.0,
			'fuelAvailable': 10000.0,
			'minGenLoading': 0.3,
			'dieselFuelCostGal': 3.0,
			'dieselCO2Factor': 22.4,
			'dieselOMCostKw': 25.0,
			'dieselOMCostKwh': 0.02,
			'dieselOnlyRunsDuringOutage': True,
			'dieselMacrsOptionYears': 0,
			'windCost': 4989.0,
			'windMax': 100000.0,
			'windMin': 0.0,
			'windMacrsOptionYears': 5,
			'windItcPercent': 0.26,
			'maxRuntimeSeconds': 240
		},
        # - We have the correct equivalent hard-coded microgrids, but we want to test that the dynamically generated microgrids are correct
        'MICROGRIDS': MICROGRIDS,
		#'MICROGRIDS': { 'mg0': { 'battery_capacity': '10000', 'gen_bus': '633', 'gen_obs_existing': [ 'solar_634_existing', 'battery_634_existing' ], 'loads': [ '634a_data_center', '634b_radar', '634c_atc_tower' ], 'max_potential': '700', 'max_potential_diesel': '1000000', 'switch': '632633', 'parameter_overrides': { 'reopt_inputs': {} } }, 'mg1': { 'battery_capacity': '10000', 'gen_bus': '645', 'gen_obs_existing': [], 'loads': [ '645_hangar', '646_office' ], 'max_potential': '700', 'max_potential_diesel': '1000000', 'switch': '632645', 'parameter_overrides': { 'reopt_inputs': {} } }, 'mg2': { 'battery_capacity': '10000', 'gen_bus': '670', 'gen_obs_existing': [ 'fossil_675_existing' ], 'loads': [ '684_command_center', '692_warehouse2', '675a_hospital', '675b_residential1', '675c_residential1', '611_runway', '652_residential', '670a_residential2', '670b_residential2', '670c_residential2' ], 'max_potential': '700', 'max_potential_diesel': '1000000', 'switch': '632670', 'parameter_overrides': { 'reopt_inputs': {} } } },
		'FAULTED_LINES': ['670671'],
		'OUTAGE_CSV': f'{microgridup.MGU_DIR}/testfiles/lehigh_random_outages.csv',
		'CRITICAL_LOADS': [
			'684_command_center',
			'634a_data_center',
			'634b_radar',
			'634c_atc_tower',
			'645_hangar',
			'675a_hospital',
			'611_runway'
		],
		'DESCRIPTION': '',
		'singlePhaseRelayCost': 300.0,
		'threePhaseRelayCost': 20000.0
	}
	# Run model.
	microgridup.main(data, invalidate_cache=False, open_results=True)
	if os.path.isfile(f'{microgridup.PROJ_DIR}/{data["MODEL_DIR"]}/0crashed.txt'):
		sys.exit(1)	


def test_mackelroy():
	'''
	- We used the iowa240 circuit and bottom-up partitioning with at least 5 microgrids
	- We have an essentially random selection of critical loads
	'''
	data = {
		"MODEL_DIR": "mackelroy",
		"BASE_DSS": f'{microgridup.MGU_DIR}/testfiles/mackelroy.dss',
		"LOAD_CSV": f'{microgridup.MGU_DIR}/testfiles/mackelroy.csv',
		"QSTS_STEPS": 480,
		"REOPT_INPUTS": {
			"energyCost": 0.12,
			"wholesaleCost": 0.034,
			"demandCost": 20.0,
			"solarCanCurtail": True,
			"solarCanExport": True,
			"urdbLabelSwitch": False,
			"urdbLabel": "5b75cfe95457a3454faf0aea",
			"year": 2017,
			"analysisYears": 25,
			"outageDuration": 48,
			"value_of_lost_load": 1.0,
			"omCostEscalator": 0.025,
			"discountRate": 0.083,
			"solar": True,
			"battery": True,
			"fossil": True,
			"wind": False,
			"solarCost": 1600.0,
			"solarMax": 1000000000.0,
			"solarMin": 0.0,
			"solarMacrsOptionYears": 0,
			"solarItcPercent": 0.26,
			"batteryCapacityCost": 420.0,
			"batteryCapacityMax": 1000000.0,
			"batteryCapacityMin": 0.0,
			"batteryPowerCost": 840.0,
			"batteryPowerMax": 1000000000.0,
			"batteryPowerMin": 0.0,
			"batteryMacrsOptionYears": 0,
			"batteryItcPercent": 0.0,
			"batteryPowerCostReplace": 410.0,
			"batteryCapacityCostReplace": 200.0,
			"batteryPowerReplaceYear": 10,
			"batteryCapacityReplaceYear": 10,
			"dieselGenCost": 500.0,
			"dieselMax": 1000000000.0,
			"dieselMin": 0.0,
			"fuelAvailable": 50000.0,
			"minGenLoading": 0.3,
			"dieselFuelCostGal": 3.0,
			"dieselCO2Factor": 22.4,
			"dieselOMCostKw": 10.0,
			"dieselOMCostKwh": 0.0,
			"dieselOnlyRunsDuringOutage": False,
			"dieselMacrsOptionYears": 0,
			"windCost": 4989.0,
			"windMax": 1000000000.0,
			"windMin": 0.0,
			"windMacrsOptionYears": 0,
			"windItcPercent": 0.26,
			"maxRuntimeSeconds": 240
		},
		"MICROGRIDS": {
			"mg0": {
				"gen_bus": "bus3002",
				"gen_obs_existing": [],
				"loads": [
					"load_3002"
				],
				"parameter_overrides": {
					"reopt_inputs": {}
				},
				"switch": "l_3003_3002"
			},
			"mg1": {
				"gen_bus": "bus3004",
				"gen_obs_existing": [],
				"loads": [
					"load_3004"
				],
				"parameter_overrides": {
					"reopt_inputs": {}
				},
				"switch": "l_3003_3004"
			},
			"mg2": {
				"gen_bus": "bus1001",
				"gen_obs_existing": [],
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
				"parameter_overrides": {
					"reopt_inputs": {}
				},
				"switch": "cb_101"
			},
			"mg3": {
				"gen_bus": "bus2001",
				"gen_obs_existing": [],
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
				"parameter_overrides": {
					"reopt_inputs": {}
				},
				"switch": "cb_201"
			},
			"mg4": {
				"gen_bus": "bus3005",
				"gen_obs_existing": [],
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
				"parameter_overrides": {
					"reopt_inputs": {}
				},
				"switch": "l_3003_3005"
			}
		},
		"FAULTED_LINES": [
			"cb_201",
			"cb_101",
			"cb_301"
		],
		"OUTAGE_CSV": None,
		"CRITICAL_LOADS": [
			"load_1006",
			"load_1011",
			"load_1014",
			"load_1016",
			"load_2008",
			"load_2014",
			"load_2016",
			"load_2018",
			"load_2022",
			"load_2024",
			"load_2045",
			"load_2047",
			"load_2049",
			"load_2051",
			"load_2055",
			"load_2059",
			"load_3009",
			"load_3011",
			"load_3013",
			"load_3016",
			"load_3018",
			"load_3020",
			"load_3023",
			"load_3025",
			"load_3027",
			"load_3029",
			"load_3042",
			"load_3044",
			"load_3056",
			"load_3058",
			"load_3060",
			"load_3062",
			"load_3064",
			"load_3066",
			"load_3083",
			"load_3085",
			"load_3087",
			"load_3089",
			"load_3091",
			"load_3094",
			"load_3096",
			"load_3098",
			"load_3101",
			"load_3103",
			"load_3105",
			"load_3108",
			"load_3110",
			"load_3112",
			"load_3115",
			"load_3117",
			"load_3121",
			"load_3124",
			"load_3126",
			"load_3128",
			"load_3130",
			"load_3132",
			"load_3135",
			"load_3137",
			"load_3142",
			"load_3144",
			"load_3146",
			"load_3148",
			"load_3150",
			"load_3152",
			"load_3154",
			"load_3157",
			"load_3159",
			"load_3161",
			"load_1003",
			"load_1005",
			"load_1009",
			"load_1013",
			"load_2003",
			"load_2010",
			"load_2029",
			"load_2032",
			"load_2035",
			"load_2040",
			"load_2042",
			"load_2052",
			"load_2058",
			"load_3004",
			"load_3007",
			"load_3032",
			"load_3034",
			"load_3036",
			"load_3038",
			"load_3047",
			"load_3049",
			"load_3051",
			"load_3054",
			"load_3071",
			"load_3073",
			"load_3077",
			"load_3081"
		],
		"DESCRIPTION": "",
		"singlePhaseRelayCost": 300.0,
		"threePhaseRelayCost": 20000.0
	}
	# Run model.
	microgridup.main(data, invalidate_cache=False, open_results=True)
	if os.path.isfile(f'{microgridup.PROJ_DIR}/{data["MODEL_DIR"]}/0crashed.txt'):
		sys.exit(1)

if __name__ == '__main__':
	test_1mg()
	test_2mg()
	test_3mg()
	test_4mg()
	test_auto3mg()
	# test_mackelroy()