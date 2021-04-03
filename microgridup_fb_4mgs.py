from microgridup_fb import *

if __name__ == '__main__':
	# Input data.
	BASE_NAME = 'lehigh_base_phased_fb.dss'
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
		#"outage_start_hour": "200",
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
		'gen_obs_existing': ['solar_634_existing'],
		'max_potential': '700' # total kW rating on 634 bus is 500 kW
	}

	# Output paths.
	GEN_NAME = 'lehigh_gen_fb.csv'
	FULL_NAME_1 = 'lehigh_full_fb_1.dss'
	OMD_NAME = 'lehigh_fb.dss.omd'
	ONELINE_NAME = 'lehigh_fb.oneline.html'
	MAP_NAME = 'lehigh_map_fb'
	REOPT_FOLDER_BASE_1 = 'lehigh_reopt_fb_base_1'
	REOPT_FOLDER_FINAL_1 = 'lehigh_reopt_fb_final_1'
	BIG_OUT_NAME_1 = 'output_full_analysis_lehigh_fb_1.html'
	
	# 2nd run inputs.
	microgrid_2 = {
		'loads': ['675a_hospital','675b_residential1','675c_residential1'],
		'switch': '671692',
		'gen_bus': '675',
		'gen_obs_existing': [],
		'max_potential': '900' # total kW rating on 675 bus is 843 kW
	}
	
	# 2nd run output paths
	FULL_NAME_2 = 'lehigh_full_fb_2.dss'
	REOPT_FOLDER_BASE_2 = 'lehigh_reopt_fb_base_2'
	REOPT_FOLDER_FINAL_2 = 'lehigh_reopt_fb_final_2'
	BIG_OUT_NAME_2 = 'output_full_analysis_lehigh_fb_2.html'

	# 3rd run inputs
	microgrid_3 = {
		'loads': ['684_command_center','652_residential'],
		'switch': '671684',
		'gen_bus': '684',
		'gen_obs_existing': ['diesel_684_existing'],
		'max_potential': '1300' # total kW rating on 684 and 652 is 1283 kW
	}

	# 3rd run output paths
	FULL_NAME_3 = 'lehigh_full_fb_3.dss'
	REOPT_FOLDER_BASE_3 = 'lehigh_reopt_fb_base_3'
	REOPT_FOLDER_FINAL_3 = 'lehigh_reopt_fb_final_3'
	BIG_OUT_NAME_3 = 'output_full_analysis_lehigh_fb_3.html'

	# 4rth run inputs
	microgrid_4 = {
		'loads': ['645_hangar','646_office'],
		'switch': '632645',
		'gen_bus': '646',
		'gen_obs_existing': [],
		'max_potential': '800' # total kW rating on 645 and 646 is 400 kW
	}

	playground_microgrids = {}
	playground_microgrids['m1'] = microgrid_1
	playground_microgrids['m2'] = microgrid_2
	playground_microgrids['m3'] = microgrid_3
	playground_microgrids['m4'] = microgrid_4

	# 4rth run output paths
	FULL_NAME_4 = 'lehigh_full_fb_4.dss'
	REOPT_FOLDER_BASE_4 = 'lehigh_reopt_fb_base_4'
	REOPT_FOLDER_FINAL_4 = 'lehigh_reopt_fb_final_4'
	BIG_OUT_NAME_4 = 'output_full_analysis_lehigh_fb_4.html'

	# # 5th (full) run inputs
	# microgrid_5 = {
	# 	'loads': [],
	# 	'switch': '650632',
	# 	'gen_bus': '670',
	# 	'gen_obs_existing': []
	# }

	# # 5th (full) run output paths
	# FULL_NAME_5 = 'lehigh_full_5.dss'
	# REOPT_FOLDER_5 = 'lehigh_reopt_5'
	# BIG_OUT_NAME_5 = 'output_full_analysis_lehigh_5.html'

	# Full microgrid
	# microgrid_full = {
	# 	'loads': ['634a_data_center','634b_radar','634c_atc_tower','675a_hospital','675b_residential1','675c_residential1','671_command_center','652_residential','645_hangar','646_office'],
	# 	'switch': '650632',
	# 	'gen_bus': '670',
	# 	'gen_obs_existing': ['solar_634_existing', 'diesel_684_existing']
	# }

	main(BASE_NAME, LOAD_NAME, REOPT_INPUTS, microgrid_1, playground_microgrids, GEN_NAME, FULL_NAME_1, OMD_NAME, ONELINE_NAME, MAP_NAME, REOPT_FOLDER_BASE_1, REOPT_FOLDER_FINAL_1, BIG_OUT_NAME_1, QSTS_STEPS, DIESEL_SAFETY_FACTOR)
	main(FULL_NAME_1, LOAD_NAME, REOPT_INPUTS, microgrid_2, playground_microgrids, GEN_NAME, FULL_NAME_2, OMD_NAME, ONELINE_NAME, MAP_NAME, REOPT_FOLDER_BASE_2, REOPT_FOLDER_FINAL_2, BIG_OUT_NAME_2, QSTS_STEPS, DIESEL_SAFETY_FACTOR)
	main(FULL_NAME_2, LOAD_NAME, REOPT_INPUTS, microgrid_3, playground_microgrids, GEN_NAME, FULL_NAME_3, OMD_NAME, ONELINE_NAME, MAP_NAME, REOPT_FOLDER_BASE_3, REOPT_FOLDER_FINAL_3, BIG_OUT_NAME_3, QSTS_STEPS, DIESEL_SAFETY_FACTOR)
	main(FULL_NAME_3, LOAD_NAME, REOPT_INPUTS, microgrid_4, playground_microgrids, GEN_NAME, FULL_NAME_4, OMD_NAME, ONELINE_NAME, MAP_NAME, REOPT_FOLDER_BASE_4, REOPT_FOLDER_FINAL_4, BIG_OUT_NAME_4, QSTS_STEPS, DIESEL_SAFETY_FACTOR)
	# main(FULL_NAME_4, LOAD_NAME, REOPT_INPUTS, microgrid_5, playground_microgrids, GEN_NAME, FULL_NAME_5, OMD_NAME, ONELINE_NAME, MAP_NAME, REOPT_FOLDER_5, BIG_OUT_NAME_5)