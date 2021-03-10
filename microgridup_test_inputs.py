from microgridup import *

if __name__ == '__main__':
	# Input data.
	BASE_NAME = 'lehigh_base_test.dss'
	LOAD_NAME = 'lehigh_load.csv'
	QSTS_STEPS = 24*20
	DIESEL_SAFETY_FACTOR = .2
	REOPT_INPUTS = {
		"solar" : "on",
		"wind" : "on",
		"battery" : "on",
		"year" : '2017',
		"energyCost" : "0.12",
		"demandCost" : '20',
		"wholesaleCost" : "0.034",
		"solarCost" : "1600",
		"windCost" : "1000",
		"batteryPowerCost" : "840",
		"batteryCapacityCost" : "420",
		"dieselGenCost": "500",
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
		"outage_start_hour": "200",
		"outageDuration": "48",
		"fuelAvailable": "50000",
		"genExisting": 0,
		"minGenLoading": "0.3",
		"batteryKwExisting": 0,
		"batteryKwhExisting": 0,
		"windExisting": 0,
		"value_of_lost_load": "100",
		"solarCanCurtail": True,
		"solarCanExport": True
	}

	microgrid_test = {
		'loads': ['634a_data_center','634b_radar','634c_atc_tower'],
		'switch': '632633',
		'gen_bus': '634',
		'gen_obs_existing': ['solar_634_existing', 'battery_634_existing', 'wind_634_existing'],
		'max_potential': '700' # total kW rating on 634 bus is 500 kW
	}

	# Output paths.
	GEN_NAME = 'lehigh_gen.csv'
	FULL_NAME_TEST = 'lehigh_full_test.dss'
	OMD_NAME = 'lehigh.dss.omd'
	ONELINE_NAME = 'lehigh.oneline.html'
	MAP_NAME = 'lehigh_map'
	REOPT_FOLDER_TEST = 'lehigh_reopt_test'
	BIG_OUT_NAME_TEST = 'output_full_analysis_lehigh_test.html'

	playground_microgrids = {}
	playground_microgrids['m1'] = microgrid_test

	main(BASE_NAME, LOAD_NAME, REOPT_INPUTS, microgrid_test, playground_microgrids, GEN_NAME, FULL_NAME_TEST, OMD_NAME, ONELINE_NAME, MAP_NAME, REOPT_FOLDER_TEST, BIG_OUT_NAME_TEST, QSTS_STEPS, DIESEL_SAFETY_FACTOR)
