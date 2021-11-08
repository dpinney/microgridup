import microgridup_control

omds = ['test1.omd','test2.omd']
# dss_files = [convert_omd_dss(x) for x in omds]
# tielinesPath = [convert_omd_ties(x) for x in omds]
microgrids = [{},{},{},{}]
test_controlmgs = {
	'm1': {
		'loads': ['634a_supermarket','634b_supermarket','634c_supermarket'],
		'switch': '632633',
		'gen_bus': '633',
		'kw_rating_battery': '16',
		'kw_rating_diesel': '1000',
		'kwh_rating_battery': '100'
	},
	'm2': {
		'loads': ['675a_hospital','675b_residential1','675c_residential1'],
		'switch': '671692',
		'gen_bus': '675',
		'kw_rating_battery': '128',
		'kw_rating_diesel': '538.0170262240325',
		'kwh_rating_battery': '553'
	},
	'm3': {
		'loads': ['684_command_center','652_residential'],
		'switch': '671684',
		'gen_bus': '684',
		'gen_obs_existing': ['diesel_684_existing','battery_684_existing'],
		'critical_load_kws': [400,20],
		'kw_rating_battery': '20', # total kW rating on 684 and 652 is 1283 kW
		'kw_rating_diesel': '593.2050653749545',
		'kwh_rating_battery': '65.97158243892608'
		},
	'm4': {
		'loads': ['645_warehouse1','646_med_office'],
		'switch': '632645',
		'gen_bus': '646',
		'kw_rating_battery': '12',
		'kw_rating_diesel': '1000',
		'kwh_rating_battery': '100'
	}
}
test_4mgs = {
		'mg0': {
			'loads': ['634a_data_center','634b_radar','634c_atc_tower'],
			'switch': '632633',
			'gen_bus': '634',
			'gen_obs_existing': ['solar_634_existing','battery_634_existing'],
			'critical_load_kws': [70,90,10],
			'kw_rating_battery': '7', # total kW rating on 634 bus is 500 kW
			'kw_rating_diesel': '100',
			'kwh_rating_battery': '100'
		},
		'mg1': {
			'loads': ['675a_hospital','675b_residential1','675c_residential1','692_warehouse2'],
			'switch': '671692',
			'gen_bus': '675',
			'gen_obs_existing': ['solar_675_existing'],
			'critical_load_kws': [150,200,200],
			'kw_rating_battery': '128',
			'kw_rating_diesel': '538.0170262240325',
			'kwh_rating_battery': '553'
		},
		'mg2': {
			'loads': ['684_command_center','652_residential','611_runway'],
			'switch': '671684',
			'gen_bus': '684',
			'gen_obs_existing': ['fossil_684_existing','battery_684_existing'],
			'critical_load_kws': [400,20],
			'kw_rating_battery': '20', # total kW rating on 684 and 652 is 1283 kW
			'kw_rating_diesel': '593.2050653749545',
			'kwh_rating_battery': '65.97158243892608'
		},
		'mg3': {
			'loads': ['645_hangar','646_office'],
			'switch': '632645',
			'gen_bus': '646',
			'gen_obs_existing': [],
			'critical_load_kws': [30,70],
			'kw_rating_battery': '8', # total kW rating on 645 and 646 is 400 kW
			'kw_rating_diesel': '1000',
			'kwh_rating_battery': '100'
		}
	}
test_3mgs = {
		'mg0': {
			'loads': ['634a_data_center','634b_radar','634c_atc_tower'],
			'switch': '632633',
			'gen_bus': '634',
			'gen_obs_existing': ['solar_634_existing','battery_634_existing'],
			'critical_load_kws': [70,90,10],
			'kw_rating_battery': '700', # total kW rating on 634 bus is 500 kW
			'kw_rating_diesel': '1000000',
			'kwh_rating_battery': '10000'
		},
		'mg1': {
			'loads': ['675a_hospital','675b_residential1','675c_residential1','692_warehouse2'],
			'switch': '671692',
			'gen_bus': '675',
			'gen_obs_existing': ['solar_675_existing'],
			'critical_load_kws': [150,200,200],
			'kw_rating_battery': '100', # total kW rating on 675 bus is 843 kW
			'kw_rating_diesel': '900',
			'kwh_rating_battery': '2000'
		},
		'mg2': {
			'loads': ['645_hangar','646_office'],
			'switch': '632645',
			'gen_bus': '646',
			'gen_obs_existing': [],
			'critical_load_kws': [30,70],
			'kw_rating_battery': '800', # total kW rating on 645 and 646 is 400 kW
			'kw_rating_diesel': '1000000',
			'kwh_rating_battery': '10000'
		}
	}
test_2mgs = {
		'mg0': {
			'loads': ['634a_data_center','634b_radar','634c_atc_tower'],
			'switch': '632633',
			'gen_bus': '634',
			'gen_obs_existing': ['solar_634_existing', 'battery_634_existing'],
			'critical_load_kws': [], #[70,90,10],
			'kw_rating_battery': '700',
			'kw_rating_diesel': '1000000',
			'kwh_rating_battery': '10000'
		},
		'mg1': {
			'loads': ['675a_hospital','675b_residential1','675c_residential1','692_warehouse2'],
			'switch': '671692',
			'gen_bus': '675',
			'gen_obs_existing': [],
			'critical_load_kws': [150,200,200],
			'kw_rating_battery': '900',
			'kw_rating_diesel': '1000000',
			'kwh_rating_battery': '10000'
		}
	}
test_1mg = {
		'mg0': {
			'loads': ['634a_data_center','634b_radar','634c_atc_tower','675a_hospital','675b_residential1','675c_residential1','692_warehouse2','684_command_center','652_residential','611_runway','645_hangar','646_office'],
			'switch': '650632',
			'gen_bus': '670',
			'gen_obs_existing': ['solar_634_existing','battery_634_existing','solar_675_existing','fossil_684_existing','battery_684_existing'],
			'critical_load_kws': [70,90,10,150,200,200,400,20,30,70],
			'kw_rating_battery': '200',
			'kw_rating_diesel': '100',
			'kwh_rating_battery': '500'
		}
	}
faultedLine = ['1','3','5']
# outageStart = ['2018-09-01T12:45Z',...]
lengthOfOutage = [10,40,50]
switchingTime = [1,2,3]


# play(<a couple inputs 1>)
# play(<a couple inputs 2>)
# play(<a couple inputs 3>)
# play(<a couple inputs 4>)
# play(<a couple inputs 5>)


# play(pathToOmd, pathToDss, pathToTieLines, workDir, microgrids, faultedLine, radial, outageStart, lengthOfOutage, switchingTime)

# example from microgridup_control.py
# microgridup_control.play('./4mgs/circuit.dss.omd', './4mgs/circuit_plusmg_3.dss', None, None, test_controlmgs, '670671', False, 60, 120, 30)

# 4mgs 
# microgridup_control.play('./4mgs/circuit.dss.omd', './4mgs/circuit_plusmg_3.dss', None, None, test_4mgs, '670671', False, 60, 120, 30)

# 3mgs
# microgridup_control.play('./3mgs/circuit.dss.omd', './3mgs/circuit_plusmg_2.dss', None, None, test_3mgs, '670671', False, 60, 120, 30)

# 2mgs 
# microgridup_control.play('./2mgs/circuit.dss.omd', './2mgs/circuit_plusmg_1.dss', None, None, test_2mgs, '670671', False, 60, 120, 30)

# 1mg
# microgridup_control.play('./1mg/circuit.dss.omd', './1mg/circuit_plusmg_0.dss', None, None, test_1mg, '670671', False, 60, 120, 30)

# make chart 
# microgridup_control.make_chart('./4mgs/timezcontrol_gen.csv', 'Name', 'hour', ['P1(kW)','P2(kW)','P3(kW)'], 2019, test_4mgs, './4mgs/circuit.dss.omd',)
# microgridup_control.make_chart('./4mgs/timezcontrol_load.csv', 'Name', 'hour', ['V1(PU)','V2(PU)','V3(PU)'], 2019, test_4mgs, './4mgs/circuit.dss.omd', ansi_bands=True)




