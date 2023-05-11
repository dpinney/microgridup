'''Test file with 1 microgrid for all loads and with multiple existing gens of all types
in microgrid_test_4mg.py for economic comparison'''

from microgridup import *
import microgridup_gen_mgs as gmg

def test_1mg():
	# Input data.
	MODEL_DIR = f'{PROJ_FOLDER}/1mg'
	BASE_DSS = f'{MGU_FOLDER}/testfiles/lehigh_base_1mg.dss'
	LOAD_CSV = f'{MGU_FOLDER}/testfiles/lehigh_load.csv'
	FAULTED_LINE = '650632' # Why this line, which is not closing off the genbus from source?
	QSTS_STEPS = 24*20
	FOSSIL_BACKUP_PERCENT = 1
	OUTAGE_CSV = f'{MGU_FOLDER}/testfiles/lehigh_random_outages.csv'
	# DIESEL_SAFETY_FACTOR = 0 # DIESEL_SAFETY_FACTOR is not currenty in use; Revisit once we have a strategy for load growth
	REOPT_INPUTS = {
		"solar" : "on",
		"wind" : "off",
		"battery" : "on",
		"year" : '2017',
		"analysisYears": "25",
		"discountRate" : '0.083',
		"energyCost" : "0.12",
		"demandCost" : '20',
		"urdbLabelSwitch": "off",
		# "urdbLabel" : '5b75cfe95457a3454faf0aea', # EPEC General Service TOU Rate https://openei.org/apps/IURDB/rate/view/5b75cfe95457a3454faf0aea#1__Basic_Information
		"wholesaleCost" : "0.034", # To turn off energy export/net-metering, set wholesaleCost to "0" and excess PV gen will be curtailed
		"solarCost" : "1600",
		"windCost" : "4989",
		"batteryPowerCost" : "840",
		"batteryCapacityCost" : "420",
		"batteryPowerCostReplace" : "410",
		"batteryCapacityCostReplace" : "200",
		"batteryPowerReplaceYear": '10', # year at which batteryPowerCostReplace (the inverter) is reinstalled, one time
		"batteryCapacityReplaceYear": '10', # year at which batteryCapacityCostReplace (the battery cells) is reinstalled, one time
		"dieselGenCost": "1000",
		"solarMin": 0,
		"windMin": 0,
		"batteryPowerMin": 0,
		"batteryCapacityMin": 0,
		"solarMax": "10000",
		"windMax": "1000",
		"batteryPowerMax": "10000",
		"batteryCapacityMax": "10000",
		"dieselMax": "10000",
		"solarExisting": 0,
		"criticalLoadFactor": "1",
		#"outage_start_hour": "200",
		"outageDuration": "48",
		"fuelAvailable": "150000",
		"genExisting": 0,
		"minGenLoading": 0,
		"batteryKwExisting": 0,
		"batteryKwhExisting": 0,
		"windExisting": 0,
		"dieselFuelCostGal": 1.5, # assuming 4.5 $/MMBtu = 1 $/gal diesel
		"dieselCO2Factor": 24.1,
		"dieselOMCostKw": 35,
		"dieselOMCostKwh": .02,
		"value_of_lost_load": "100",
		"solarCanCurtail": True,
		"solarCanExport": True,
		"dieselOnlyRunsDuringOutage": False
	}
	MICROGRIDS = {
		'mg0': {
			'loads': ['634a_data_center','634b_radar','634c_atc_tower','675a_hospital','675b_residential1','675c_residential1','692_warehouse2','684_command_center','652_residential','611_runway','645_hangar','646_office'],
			'switch': '650632',
			'gen_bus': '670',
			'gen_obs_existing': ['solar_634_existing','solar_675_existing','fossil_684_existing', 'fossil_646_existing', 'battery_634_existing', 'battery_684_existing'],
			'critical_load_kws': [70,90,10,150,200,200,400,20,30,70,0,0]
		}
	}
	# Run model.
	full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, FOSSIL_BACKUP_PERCENT, REOPT_INPUTS, MICROGRIDS, FAULTED_LINE, open_results=True, OUTAGE_CSV=OUTAGE_CSV)

def test_2mg():
	# Input data.
	MODEL_DIR = f'{PROJ_FOLDER}/2mgs'
	BASE_DSS = f'{MGU_FOLDER}/testfiles/lehigh_base_2mg.dss'
	LOAD_CSV = f'{MGU_FOLDER}/testfiles/lehigh_load.csv'
	FAULTED_LINE = '650632'
	QSTS_STEPS = 24*20
	FOSSIL_BACKUP_PERCENT = 0
	# DIESEL_SAFETY_FACTOR = 0 # DIESEL_SAFETY_FACTOR is not currenty in use; Revisit once we have a strategy for load growth
	REOPT_INPUTS = {
		"solar" : "on",
		"wind" : "on",
		"battery" : "on",
		"year" : '2017',
		"analysisYears": "25",
		"discountRate" : '0.083',
		"energyCost" : "0.12",
		"demandCost" : '20',
		"urdbLabelSwitch": "off",
		# "urdbLabel" : '5b75cfe95457a3454faf0aea', # EPEC General Service TOU Rate https://openei.org/apps/IURDB/rate/view/5b75cfe95457a3454faf0aea#1__Basic_Information		
		"wholesaleCost" : "0.034", # To turn off energy export/net-metering, set wholesaleCost to "0" and excess PV gen will be curtailed
		"solarCost" : "1600",
		"windCost" : "1500",
		"batteryPowerCost" : "840",
		"batteryCapacityCost" : "420",
		"batteryPowerCostReplace" : "410",
		"batteryCapacityCostReplace" : "200",
		"batteryPowerReplaceYear": '10', # year at which batteryPowerCostReplace (the inverter) is reinstalled, one time
		"batteryCapacityReplaceYear": '10', # year at which batteryCapacityCostReplace (the battery cells) is reinstalled, one time
		"dieselGenCost": "500",
		"solarMin": 0,
		"windMin": 0,
		"batteryPowerMin": 0,
		"batteryCapacityMin": 0,
		"solarMax": "10000",
		"windMax": "10000",
		"batteryPowerMax": "10000",
		"batteryCapacityMax": "10000",
		"dieselMax": "100000",
		"solarExisting": 0,
		"criticalLoadFactor": "1",
		# "outage_start_hour": "200",
		"outageDuration": "48",
		"fuelAvailable": "10000",
		"genExisting": 0,
		"minGenLoading": "0.3",
		"batteryKwExisting": 0,
		"batteryKwhExisting": 0,
		"windExisting": 0,
		"dieselFuelCostGal": 3, # assuming 4.5 $/MMBtu = 1 $/gal diesel
		"dieselCO2Factor": 22.4,
		"dieselOMCostKw": 25,
		"dieselOMCostKwh": 0.02,
		"value_of_lost_load": "100",
		"solarCanCurtail": True,
		"solarCanExport": True,
		"dieselOnlyRunsDuringOutage": True
	}
	MICROGRIDS = {
		'mg0': {
			'loads': ['634a_data_center','634b_radar','634c_atc_tower'],
			'switch': '632633',
			'gen_bus': '634',
		 	'gen_obs_existing': ['wind_634_existing'],
			'critical_load_kws': [70,90,10]
		},
		'mg1': {
			'loads': ['675a_hospital','675b_residential1','675c_residential1','692_warehouse2'],
			'switch': '671692',
			'gen_bus': '675',
			'gen_obs_existing': ['battery_675_existing', 'battery_675_2_existing'],
			'critical_load_kws': [150,200,200]
		}
	}
	# Run model.
	full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, FOSSIL_BACKUP_PERCENT, REOPT_INPUTS, MICROGRIDS, FAULTED_LINE, open_results=True)

def test_3mg():
	# Input data.
	MODEL_DIR = f'{PROJ_FOLDER}/3mgs'
	BASE_DSS = f'{MGU_FOLDER}/testfiles/lehigh_base_3mg.dss'
	LOAD_CSV = f'{MGU_FOLDER}/testfiles/lehigh_load.csv'
	FAULTED_LINE = '650632'
	QSTS_STEPS = 24*20
	FOSSIL_BACKUP_PERCENT = .5
	# DIESEL_SAFETY_FACTOR = 0 # DIESEL_SAFETY_FACTOR is not currenty in use; Revisit once we have a strategy for load growth 
	REOPT_INPUTS = {
		"solar" : "on",
		"wind" : "off",
		"battery" : "on",
		"year" : '2017',
		"analysisYears": "25",
		"discountRate" : '0.083',
		"energyCost" : "0.12",
		"demandCost" : '20',
		"urdbLabelSwitch": "off",
		# "urdbLabel" : '5b75cfe95457a3454faf0aea', # EPEC General Service TOU Rate https://openei.org/apps/IURDB/rate/view/5b75cfe95457a3454faf0aea#1__Basic_Information
		"wholesaleCost" : "0", # To turn off energy export/net-metering, set wholesaleCost to "0" and excess PV gen will be curtailed
		"solarCost" : "1600",
		"windCost" : "4989",
		"batteryPowerCost" : "840",
		"batteryCapacityCost" : "420",
		"batteryPowerCostReplace" : "410",
		"batteryCapacityCostReplace" : "200",
		"batteryPowerReplaceYear": '10', # year at which batteryPowerCostReplace (the inverter) is reinstalled, one time
		"batteryCapacityReplaceYear": '10', # year at which batteryCapacityCostReplace (the battery cells) is reinstalled, one time		
		"dieselGenCost": "1000",
		"solarMin": 0,
		"windMin": 0,
		"batteryPowerMin": 0,
		"batteryCapacityMin": 0,
		"solarMax": "100000",
		"windMax": "100000",
		"batteryPowerMax": "100000",
		"batteryCapacityMax": "100000",
		"dieselMax": "100000",
		"solarExisting": 0,
		"criticalLoadFactor": "1",
		# "outage_start_hour": "200",
		"outageDuration": "48",
		"fuelAvailable": "10000",
		"genExisting": 0,
		"minGenLoading": "0.3",
		"batteryKwExisting": 0,
		"batteryKwhExisting": 0,
		"windExisting": 0,
		"dieselFuelCostGal": 3, # assuming 4.5 $/MMBtu = 1 $/gal diesel
		"dieselCO2Factor": 22.4,
		"dieselOMCostKw": 25,
		"dieselOMCostKwh": 0.02,
		"value_of_lost_load": "100",
		"solarCanCurtail": True,
		"solarCanExport": True,
		"dieselOnlyRunsDuringOutage": True
	}
	MICROGRIDS = {
		'mg0': {
			'loads': ['634a_data_center','634b_radar','634c_atc_tower'],
			'switch': '632633',
			'gen_bus': '634',
			'gen_obs_existing': ['solar_634_existing','battery_634_existing'],
			'critical_load_kws': [70,90,10]
		},
		'mg1': {
			'loads': ['675a_hospital','675b_residential1','675c_residential1','692_warehouse2'],
			'switch': '671692',
			'gen_bus': '675',
			'gen_obs_existing': ['fossil_675_existing'],
			'critical_load_kws': [150,200,200]
		},
		'mg2': {
			'loads': ['645_hangar','646_office'],
			'switch': '632645',
			'gen_bus': '646',
			'gen_obs_existing': [], #['fossil_684_existing'],
			'critical_load_kws': [30,70]
		}
	}
	# Run model.
	full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, FOSSIL_BACKUP_PERCENT, REOPT_INPUTS, MICROGRIDS, FAULTED_LINE, open_results=True)

def test_4mg():
	# Input data.
	MODEL_DIR = f'{PROJ_FOLDER}/4mgs'
	BASE_DSS = f'{MGU_FOLDER}/testfiles/lehigh_base_4mg.dss'
	LOAD_CSV = f'{MGU_FOLDER}/testfiles/lehigh_load.csv'
	FAULTED_LINE = '650632'
	QSTS_STEPS = 24*20
	FOSSIL_BACKUP_PERCENT = 1
	OUTAGE_CSV = f'{MGU_FOLDER}/testfiles/lehigh_random_outages.csv'
	# DIESEL_SAFETY_FACTOR = 0 # DIESEL_SAFETY_FACTOR is not currenty in use; Revisit once we have a strategy for load growth
	REOPT_INPUTS = {
		"solar" : "on",
		"wind" : "off",
		"battery" : "on",
		"year" : '2017',
		"analysisYears": "25",
		"discountRate" : '0.083',
		"energyCost" : "0.12",
		"demandCost" : '20',
		"urdbLabelSwitch": "off",
		# "urdbLabel" : '5b75cfe95457a3454faf0aea', # EPEC General Service TOU Rate https://openei.org/apps/IURDB/rate/view/5b75cfe95457a3454faf0aea#1__Basic_Information
		"wholesaleCost" : "0.034", # To turn off energy export/net-metering, set wholesaleCost to "0" and excess PV gen will be curtailed
		"solarCost" : "1600",
		"windCost" : "4989",
		"batteryPowerCost" : "840",
		"batteryCapacityCost" : "420",
		"batteryPowerCostReplace" : "410",
		"batteryCapacityCostReplace" : "200",
		"batteryPowerReplaceYear": '10', # year at which batteryPowerCostReplace (the inverter) is reinstalled, one time
		"batteryCapacityReplaceYear": '10', # year at which batteryCapacityCostReplace (the battery cells) are reinstalled, one time
		"dieselGenCost": "1000",
		"solarMin": 0,
		"windMin": 0,
		"batteryPowerMin": 0,
		"batteryCapacityMin": 0,
		"solarMax": "100000",
		"windMax": "100000",
		"batteryPowerMax": "1000000",
		"batteryCapacityMax": "1000000",
		"dieselMax": "1000000",
		"solarExisting": 0,
		"criticalLoadFactor": "1",
		#"outage_start_hour": "200",
		"outageDuration": "48",
		"fuelAvailable": "1000000",
		"genExisting": 0,
		"minGenLoading": "0",
		"batteryKwExisting": 0,
		"batteryKwhExisting": 0,
		"windExisting": 0,
		"dieselFuelCostGal": 1.5, # assuming 4.5 $/MMBtu = 1 $/gal diesel
		"dieselCO2Factor": 24.1,
		"dieselOMCostKw": 35,
		"dieselOMCostKwh": .02,
		"value_of_lost_load": "100",
		"solarCanCurtail": True,
		"solarCanExport": True,
		"dieselOnlyRunsDuringOutage": False
		# "batteryMacrsOptionYears": 0
	}
	MICROGRIDS = {
		'mg0': {
			'loads': ['634a_data_center','634b_radar','634c_atc_tower'],
			'switch': '632633',
			'gen_bus': '634',
			'gen_obs_existing': ['solar_634_existing','battery_634_existing'],
			'critical_load_kws': [70,90,10]
		},
		'mg1': {
			'loads': ['675a_hospital','675b_residential1','675c_residential1','692_warehouse2'],
			'switch': '671692',
			'gen_bus': '675',
			'gen_obs_existing': ['solar_675_existing'],
			'critical_load_kws': [150,200,200,0]
		},
		'mg2': {
			'loads': ['684_command_center','652_residential','611_runway'],
			'switch': '671684',
			'gen_bus': '684',
			'gen_obs_existing': ['fossil_684_existing','battery_684_existing'],
			'critical_load_kws': [400,20,0]
		},
		'mg3': {
			'loads': ['645_hangar','646_office'],
			'switch': '632645',
			'gen_bus': '646',
			'gen_obs_existing': ['battery_646_existing'],
			'critical_load_kws': [30,70]
		}
	}
	# Run model.
	full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, FOSSIL_BACKUP_PERCENT, REOPT_INPUTS, MICROGRIDS, FAULTED_LINE, open_results=True, OUTAGE_CSV=OUTAGE_CSV)

def test_auto3mg():
	# Input data.
	CIRC_FILE = f'{MGU_FOLDER}/testfiles/lehigh_base_3mg.dss'
	CRITICAL_LOADS = ['645_hangar','684_command_center', '611_runway','675a_hospital','634a_data_center', '634b_radar', '634c_atc_tower']
	MODEL_DIR = f'{PROJ_FOLDER}/auto3mg'
	BASE_DSS = f'{MGU_FOLDER}/testfiles/lehigh_base_3mg.dss'
	LOAD_CSV = f'{MGU_FOLDER}/testfiles/lehigh_load.csv'
	FAULTED_LINE = '670671'
	QSTS_STEPS = 24*20
	FOSSIL_BACKUP_PERCENT = .5
	OUTAGE_CSV = f'{MGU_FOLDER}/testfiles/lehigh_random_outages.csv'
	# DIESEL_SAFETY_FACTOR = 0 # DIESEL_SAFETY_FACTOR is not currenty in use; Revisit once we have a strategy for load growth 
	REOPT_INPUTS = {
		"solar" : "on",
		"wind" : "off",
		"battery" : "on",
		"year" : '2017',
		"analysisYears": "25",
		"discountRate" : '0.083',
		"energyCost" : "0.12",
		"demandCost" : '20',
		"urdbLabelSwitch": "off",
		# "urdbLabel" : '5b75cfe95457a3454faf0aea', # EPEC General Service TOU Rate https://openei.org/apps/IURDB/rate/view/5b75cfe95457a3454faf0aea#1__Basic_Information
		"wholesaleCost" : "0", # To turn off energy export/net-metering, set wholesaleCost to "0" and excess PV gen will be curtailed
		"solarCost" : "1600",
		"windCost" : "4989",
		"batteryPowerCost" : "840",
		"batteryCapacityCost" : "420",
		"batteryPowerCostReplace" : "410",
		"batteryCapacityCostReplace" : "200",
		"batteryPowerReplaceYear": '10', # year at which batteryPowerCostReplace (the inverter) is reinstalled, one time
		"batteryCapacityReplaceYear": '10', # year at which batteryCapacityCostReplace (the battery cells) is reinstalled, one time		
		"dieselGenCost": "1000",
		"solarMin": 0,
		"windMin": 0,
		"batteryPowerMin": 0,
		"batteryCapacityMin": 0,
		"solarMax": "100000",
		"windMax": "100000",
		"batteryPowerMax": "100000",
		"batteryCapacityMax": "100000",
		"dieselMax": "100000",
		"solarExisting": 0,
		"criticalLoadFactor": "1",
		# "outage_start_hour": "200",
		"outageDuration": "48",
		"fuelAvailable": "10000",
		"genExisting": 0,
		"minGenLoading": "0.3",
		"batteryKwExisting": 0,
		"batteryKwhExisting": 0,
		"windExisting": 0,
		"dieselFuelCostGal": 3, # assuming 4.5 $/MMBtu = 1 $/gal diesel
		"dieselCO2Factor": 22.4,
		"dieselOMCostKw": 25,
		"dieselOMCostKwh": 0.02,
		"value_of_lost_load": "100",
		"solarCanCurtail": True,
		"solarCanExport": True,
		"dieselOnlyRunsDuringOutage": True
	}
	ALGO = 'branch' #'lukes'
	MICROGRIDS = gmg.mg_group(CIRC_FILE, CRITICAL_LOADS, 'branch')
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
	full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, FOSSIL_BACKUP_PERCENT, REOPT_INPUTS, MICROGRIDS, FAULTED_LINE, open_results=True, OUTAGE_CSV=OUTAGE_CSV)

if __name__ == '__main__':
	test_1mg()
	# test_2mg()
	# test_3mg()
	# test_4mg()
	# test_auto3mg()