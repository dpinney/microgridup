'''Test to confirm full renewable backup with no fossil generation and existing wind'''

from microgridup import *

if __name__ == '__main__':
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
