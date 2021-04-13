from microgridup import *


if __name__ == '__main__':
	# Input data.
	MODEL_DIR = '4mgs'
	BASE_DSS = 'lehigh_base_phased.dss'
	LOAD_CSV = 'lehigh_load.csv'
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
	MICROGRIDS = {
		'm1': {
			'loads': ['634a_data_center','634b_radar','634c_atc_tower'],
			'switch': '632633',
			'gen_bus': '634',
			'gen_obs_existing': ['solar_634_existing'],
			'max_potential': '700' # total kW rating on 634 bus is 500 kW
		},
		'm2': {
			'loads': ['675a_hospital','675b_residential1','675c_residential1'],
			'switch': '671692',
			'gen_bus': '675',
			'gen_obs_existing': [],
			'max_potential': '900' # total kW rating on 675 bus is 843 kW
		},
		'm3': {
			'loads': ['684_command_center','652_residential'],
			'switch': '671684',
			'gen_bus': '684',
			'gen_obs_existing': ['diesel_684_existing'],
			'max_potential': '1300' # total kW rating on 684 and 652 is 1283 kW
		},
		'm4': {
			'loads': ['645_hangar','646_office'],
			'switch': '632645',
			'gen_bus': '646',
			'gen_obs_existing': [],
			'max_potential': '800' # total kW rating on 645 and 646 is 400 kW
		}
	}
	# Run model.
	full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, DIESEL_SAFETY_FACTOR, REOPT_INPUTS, MICROGRIDS)