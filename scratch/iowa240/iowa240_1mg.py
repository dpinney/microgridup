from microgridup import *

'''Build a microgrid of the whole iowa240 circuit as a test'''

if __name__ == '__main__':
	# Input data.
	MODEL_DIR = 'iowa240_1mg'
	BASE_DSS = 'iowa240.clean_updated_coords.dss'
	LOAD_CSV = 'iowa240_load.csv'
	FAULTED_LINE = 'cb_1'
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
			'loads': ['load_1003','load_1004','load_1005','load_1006','load_1007','load_1008','load_1009','load_1010','load_1011','load_1012','load_1013','load_1014','load_1015','load_1016','load_1017','load_2002','load_2003','load_2005','load_2008','load_2009','load_2010','load_2011','load_2014','load_2015','load_2016','load_2017','load_2018','load_2020','load_2022','load_2023','load_2024','load_2025','load_2028','load_2029','load_2030','load_2031','load_2032','load_2034','load_2035','load_2037','load_2040','load_2041','load_2042','load_2043','load_2045','load_2046','load_2047','load_2048','load_2049','load_2050','load_2051','load_2052','load_2053','load_2054','load_2055','load_2056','load_2058','load_2059','load_2060','load_3002','load_3004','load_3006','load_3007','load_3009','load_3010','load_3011','load_3012','load_3013','load_3014','load_3016','load_3017','load_3018','load_3019','load_3020','load_3021','load_3023','load_3024','load_3025','load_3026','load_3027','load_3028','load_3029','load_3031','load_3032','load_3033','load_3034','load_3035','load_3036','load_3037','load_3038','load_3039','load_3041','load_3042','load_3043','load_3044','load_3045','load_3047','load_3048','load_3049','load_3050','load_3051','load_3052','load_3054','load_3056','load_3057','load_3058','load_3059','load_3060','load_3061','load_3062','load_3063','load_3064','load_3065','load_3066','load_3067','load_3070','load_3071','load_3072','load_3073','load_3074','load_3077','load_3078','load_3081','load_3083','load_3084','load_3085','load_3086','load_3087','load_3088','load_3089','load_3090','load_3091','load_3093','load_3094','load_3095','load_3096','load_3097','load_3098','load_3099','load_3101','load_3102','load_3103','load_3104','load_3105','load_3106','load_3108','load_3109','load_3110','load_3111','load_3112','load_3114','load_3115','load_3116','load_3117','load_3120','load_3121','load_3122','load_3123','load_3124','load_3125','load_3126','load_3127','load_3128','load_3129','load_3130','load_3131','load_3132','load_3134','load_3135','load_3136','load_3137','load_3138','load_3139','load_3141','load_3142','load_3143','load_3144','load_3145','load_3146','load_3147','load_3148','load_3149','load_3150','load_3151','load_3152','load_3153','load_3154','load_3155','load_3157','load_3158','load_3159','load_3160','load_3161','load_3162'],
			'switch': 'cb_1',
			'gen_bus': 'bus_fault',
			'gen_obs_existing': [],
			'critical_load_kws': [1000]
		} # ,
		# 'mg1': {
		# 	'loads': ['675a_hospital','675b_residential1','675c_residential1','692_warehouse2'],
		# 	'switch': '671692',
		# 	'gen_bus': '675',
		# 	'gen_obs_existing': ['solar_675_existing'],
		# 	'critical_load_kws': [150,200,200,0]
		# },
		# 'mg2': {
		# 	'loads': ['684_command_center','652_residential','611_runway'],
		# 	'switch': '671684',
		# 	'gen_bus': '684',
		# 	'gen_obs_existing': ['fossil_684_existing','battery_684_existing'],
		# 	'critical_load_kws': [400,20,0]
		# },
		# 'mg3': {
		# 	'loads': ['645_hangar','646_office'],
		# 	'switch': '632645',
		# 	'gen_bus': '646',
		# 	'gen_obs_existing': ['battery_646_existing'],
		# 	'critical_load_kws': [30,70]
		# }
	}
	# Run model.
	full(MODEL_DIR, BASE_DSS, LOAD_CSV, QSTS_STEPS, FOSSIL_BACKUP_PERCENT, REOPT_INPUTS, MICROGRIDS, FAULTED_LINE, open_results=True)