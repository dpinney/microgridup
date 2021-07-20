from microgridup import *

'''Test to confirm diesel backup and existing wind with FOSSIL_BACKUP_PERCENT = 1'''

if __name__ == '__main__':
	# Input data.
	MODEL_DIR = '4mgs'
	BASE_DSS = 'lehigh_base_phased.dss'
	LOAD_CSV = 'lehigh_load.csv'
	FAULTED_LINE = '670671'
	QSTS_STEPS = 24*20
	FOSSIL_BACKUP_PERCENT = .5
	# DIESEL_SAFETY_FACTOR = 0 # DIESEL_SAFETY_FACTOR is not currenty in use; Revisit once we have a strategy for load growth
	REOPT_INPUTS = {
		"solar" : "on",
		"wind" : "off",
		"battery" : "on",
		"year" : '2017',
		"analysisYears": "25",
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
		'mg0': {
			'loads': ['634a_data_center','634b_radar','634c_atc_tower'],
			'switch': '632633',
			'gen_bus': '634',
			'gen_obs_existing': ['solar_634_existing','battery_634_existing'],
			'critical_load_kws': [70,90,10],
			'max_potential_battery': '700', # total kW rating on 634 bus is 500 kW
			'max_potential_diesel': '1000000',
			'battery_capacity': '10000'
		},
		'mg1': {
			'loads': ['675a_hospital','675b_residential1','675c_residential1'],
			'switch': '671692',
			'gen_bus': '675',
			'gen_obs_existing': ['solar_675_existing'],
			'critical_load_kws': [150,200,200],
			'max_potential_battery': '900', # total kW rating on 675 bus is 843 kW
			'max_potential_diesel': '300',
			'battery_capacity': '20000'
		},
		'mg2': {
			'loads': ['684_command_center','652_residential'],
			'switch': '671684',
			'gen_bus': '684',
			'gen_obs_existing': ['diesel_684_existing','battery_684_existing'],
			'critical_load_kws': [400,20],
			'max_potential': '1300', # total kW rating on 684 and 652 is 1283 kW
			'max_potential_diesel': '1000000',
			'battery_capacity': '10000'
		},
		'mg3': {
			'loads': ['645_hangar','646_office'],
			'switch': '632645',
			'gen_bus': '646',
			'gen_obs_existing': [],
			'critical_load_kws': [30,70],
			'max_potential_battery': '800', # total kW rating on 645 and 646 is 400 kW
			'max_potential_diesel': '1000000',
			'battery_capacity': '10000'
		}
	}
	# Run model.
	full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, FOSSIL_BACKUP_PERCENT, REOPT_INPUTS, MICROGRIDS, FAULTED_LINE)