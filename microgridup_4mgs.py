from microgridup import *

if __name__ == '__main__':
	# Input data.
	BASE_NAME = 'lehigh_base_phased.dss'
	LOAD_NAME = 'lehigh_load.csv'
	REOPT_INPUTS = {
		"solar" : "on",
		"wind" : "off",
		"battery" : "on",
		"year" : '2017',
		"energyCost" : "0.12",
		"demandCost" : '20',
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
		'gen_obs_existing': ['solar_634_existing'],
		'max_potential': '700' # total kW rating on 634 bus is 500 kW
	}

	# Output paths.
	GEN_NAME = 'lehigh_gen.csv'
	FULL_NAME_1 = 'lehigh_full_1.dss'
	OMD_NAME = 'lehigh.dss.omd'
	ONELINE_NAME = 'lehigh.oneline.html'
	MAP_NAME = 'lehigh_map'
	REOPT_FOLDER_1 = 'lehigh_reopt_1'
	BIG_OUT_NAME_1 = 'output_full_analysis_lehigh_1.html'
	
	# 2nd run inputs.
	microgrid_2 = {
		'loads': ['675a_hospital','675b_residential1','675c_residential1'],
		'switch': '671692',
		'gen_bus': '675',
		'gen_obs_existing': [],
		'max_potential': '900' # total kW rating on 675 bus is 843 kW
	}
	
	# 2nd run output paths
	FULL_NAME_2 = 'lehigh_full_2.dss'
	REOPT_FOLDER_2 = 'lehigh_reopt_2'
	BIG_OUT_NAME_2 = 'output_full_analysis_lehigh_2.html'

	# 3rd run inputs
	microgrid_3 = {
		'loads': ['671_command_center','652_residential'],
		'switch': '671684',
		'gen_bus': '684',
		'gen_obs_existing': ['diesel_684_existing'],
		'max_potential': '650' # total kW rating on 671 and 652 is 1283 kW
	}

	# 3rd run output paths
	FULL_NAME_3 = 'lehigh_full_3.dss'
	REOPT_FOLDER_3 = 'lehigh_reopt_3'
	BIG_OUT_NAME_3 = 'output_full_analysis_lehigh_3.html'

	# 4rth run inputs
	microgrid_4 = {
		'loads': ['645_hangar','646_office'],
		'switch': '632645',
		'gen_bus': '646',
		'gen_obs_existing': [],
		'max_potential': '800' 
	}

	playground_microgrids = {}
	playground_microgrids['m1'] = microgrid_1
	playground_microgrids['m2'] = microgrid_2
	playground_microgrids['m3'] = microgrid_3
	playground_microgrids['m4'] = microgrid_4

	# 4rth run output paths
	FULL_NAME_4 = 'lehigh_full_4.dss'
	REOPT_FOLDER_4 = 'lehigh_reopt_4'
	BIG_OUT_NAME_4 = 'output_full_analysis_lehigh_4.html'

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

	main(BASE_NAME, LOAD_NAME, REOPT_INPUTS, microgrid_1, playground_microgrids, GEN_NAME, FULL_NAME_1, OMD_NAME, ONELINE_NAME, MAP_NAME, REOPT_FOLDER_1, BIG_OUT_NAME_1)
	main(FULL_NAME_1, LOAD_NAME, REOPT_INPUTS, microgrid_2, playground_microgrids, GEN_NAME, FULL_NAME_2, OMD_NAME, ONELINE_NAME, MAP_NAME, REOPT_FOLDER_2, BIG_OUT_NAME_2)
	main(FULL_NAME_2, LOAD_NAME, REOPT_INPUTS, microgrid_3, playground_microgrids, GEN_NAME, FULL_NAME_3, OMD_NAME, ONELINE_NAME, MAP_NAME, REOPT_FOLDER_3, BIG_OUT_NAME_3)
	main(FULL_NAME_3, LOAD_NAME, REOPT_INPUTS, microgrid_4, playground_microgrids, GEN_NAME, FULL_NAME_4, OMD_NAME, ONELINE_NAME, MAP_NAME, REOPT_FOLDER_4, BIG_OUT_NAME_4)
	# main(FULL_NAME_4, LOAD_NAME, REOPT_INPUTS, microgrid_5, playground_microgrids, GEN_NAME, FULL_NAME_5, OMD_NAME, ONELINE_NAME, MAP_NAME, REOPT_FOLDER_5, BIG_OUT_NAME_5)