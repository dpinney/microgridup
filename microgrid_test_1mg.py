'''Test file with 1 microgrid matching the loads and existing gens 
in microgrid_test_4mg.py for economic comparison'''

from microgridup import *

if __name__ == '__main__':
	# Input data.
	MODEL_DIR = '1mg'
	BASE_DSS = 'lehigh_base_1mg.dss'
	LOAD_CSV = 'lehigh_load.csv'
	FAULTED_LINE = '670671'
	QSTS_STEPS = 24*20
	FOSSIL_BACKUP_PERCENT = 1
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
		"fuelAvailable": "100000",
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
			'gen_obs_existing': ['solar_634_existing','battery_634_existing','solar_675_existing','fossil_684_existing','battery_684_existing'],
			'critical_load_kws': [70,90,10,150,200,200,400,20,30,70]
		}
	}
	# Run model.
	full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, FOSSIL_BACKUP_PERCENT, REOPT_INPUTS, MICROGRIDS, FAULTED_LINE)