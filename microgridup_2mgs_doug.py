from microgridup import *

if __name__ == '__main__':
	# Input data.
	BASE_NAME = 'lehigh_base_phased_doug.dss'
	LOAD_NAME = 'lehigh_load.csv'
	QSTS_STEPS = 24*20
	DIESEL_SAFETY_FACTOR = .2
	REOPT_INPUTS = {
		"solar" : "on",
		"wind" : "off",
		"battery" : "on",
		"year" : '2017',
		"energyCost" : "0.12",
		"demandCost" : '20',
		"wholesaleCost" : "0.034",
		"solarCost" : "1600",
		"windCost" : "4989",
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

	microgrid_1 = {
		'loads': ['634a_data_center','634b_radar','634c_atc_tower'],
		'switch': '632633',
		'gen_bus': '634',
		'gen_obs_existing': ['solar_634_existing', 'battery_634_existing'],
		'max_potential': '700'
	}

	# Output paths.
	GEN_NAME = 'lehigh_gen.csv'
	FULL_NAME_1 = 'lehigh_full_doug_1.dss'
	OMD_NAME = 'lehigh.dss.omd'
	ONELINE_NAME = 'lehigh.oneline.html'
	MAP_NAME = 'lehigh_map'
	REOPT_FOLDER_BASE_1 = 'lehigh_reopt_base_doug_1'
	REOPT_FOLDER_FINAL_1 = 'lehigh_reopt_final_doug_1'
	BIG_OUT_NAME_1 = 'output_full_analysis_lehigh_doug_1.html'
	
	# 2nd run inputs.
	microgrid_2 = {
		'loads': ['675a_hospital','675b_residential1','675c_residential1'],
		'switch': '671692',
		'gen_bus': '675',
		'gen_obs_existing': [],
		'max_potential': '900'
	}
	
	# 2nd run output paths
	FULL_NAME_2 = 'lehigh_full_doug_2.dss'
	REOPT_FOLDER_BASE_2 = 'lehigh_reopt_base_doug_2'
	REOPT_FOLDER_FINAL_2 = 'lehigh_reopt_final_doug_2'
	BIG_OUT_NAME_2 = 'output_full_analysis_lehigh_doug_2.html'

	playground_microgrids = {
		'm1':microgrid_1,
		'm2':microgrid_2
	}

	main(BASE_NAME, LOAD_NAME, REOPT_INPUTS, microgrid_1, playground_microgrids, GEN_NAME, FULL_NAME_1, OMD_NAME, ONELINE_NAME, MAP_NAME, REOPT_FOLDER_BASE_1, REOPT_FOLDER_FINAL_1, BIG_OUT_NAME_1, QSTS_STEPS, DIESEL_SAFETY_FACTOR)
	main(FULL_NAME_1, LOAD_NAME, REOPT_INPUTS, microgrid_2, playground_microgrids, GEN_NAME, FULL_NAME_2, OMD_NAME, ONELINE_NAME, MAP_NAME, REOPT_FOLDER_BASE_2, REOPT_FOLDER_FINAL_2, BIG_OUT_NAME_2, QSTS_STEPS, DIESEL_SAFETY_FACTOR)