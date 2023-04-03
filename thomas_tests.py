'''
Tests for all functions written by Thomas. 
11 logic pathways:
    1. wizard_loadGrouping
    2. wizard_lukes
    3. wizard_branch
    4. wizard_bottomUp
    5. wizard_criticalLoads
    6. lehigh_manual
    7. lehigh_loadGrouping
    8. lehigh_lukes
    9. lehigh_branch
    10. lehigh_bottomUp
    11. lehigh_criticalLoads
'''

import os
import microgridup_gen_mgs
import thomas_wip_frontend
import microgridup

_myDir = os.path.abspath(os.path.dirname(__file__))
lat = 39.7817
lon = -89.6501
crit_loads = ['634a_data_center', '634b_radar', '634c_atc_tower', '675a_hospital', '675b_residential1', '675c_residential1', '645_hangar', '646_office']
pairings = {'None': ['684_command_center', '692_warehouse2', '611_runway', '652_residential', '670a_residential2', '670b_residential2', '670c_residential2'], 'Mg1': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'Mg2': ['675a_hospital', '675b_residential1', '675c_residential1'], 'Mg3': ['645_hangar', '646_office']}
elements = [{'class': 'substation', 'text': 'sub'}, {'class': 'feeder', 'text': 'regNone'}, {'class': 'load', 'text': '684_command_center'}, {'class': 'load', 'text': '692_warehouse2'}, {'class': 'load', 'text': '611_runway'}, {'class': 'load', 'text': '652_residential'}, {'class': 'load', 'text': '670a_residential2'}, {'class': 'load', 'text': '670b_residential2'}, {'class': 'load', 'text': '670c_residential2'}, {'class': 'feeder', 'text': 'reg0'}, {'class': 'load', 'text': '634a_data_center'}, {'class': 'load', 'text': '634b_radar'}, {'class': 'load', 'text': '634c_atc_tower'}, {'class': 'solar', 'text': 'solar_634_existing'}, {'class': 'battery', 'text': 'battery_634_existing'}, {'class': 'feeder', 'text': 'reg1'}, {'class': 'load', 'text': '675a_hospital'}, {'class': 'load', 'text': '675b_residential1'}, {'class': 'load', 'text': '675c_residential1'}, {'class': 'diesel', 'text': 'fossil_675_existing'}, {'class': 'feeder', 'text': 'reg2'}, {'class': 'load', 'text': '645_hangar'}, {'class': 'load', 'text': '646_office'}]
REOPT_INPUTS = {'energyCost': '0.12', 'wholesaleCost': '0.034', 'demandCost': '20', 'solarCanCurtail': True, 'solarCanExport': True, 'criticalLoadFactor': '1', 'year': '2017', 'outageDuration': '48', 'value_of_lost_load': '1', 'solar': 'on', 'battery': 'on', 'wind': 'off', 'solarCost': '1600', 'solarExisting': '0', 'solarMax': '100000', 'solarMin': '0', 'batteryCapacityCost': '420', 'batteryCapacityMax': '1000000', 'batteryCapacityMin': '0', 'batteryKwhExisting': '0', 'batteryPowerCost': '840', 'batteryPowerMax': '1000000', 'batteryPowerMin': '0', 'batteryKwExisting': '0', 'dieselGenCost': '500', 'dieselMax': '1000000', 'fuelAvailable': '50000', 'genExisting': '0', 'minGenLoading': '0.3', 'windCost': '4989', 'windExisting': '0', 'windMax': '100000', 'windMin': '0'}

model_dir_wizard_loadGrouping = '3mgs_wizard_loadGrouping'
model_dir_wizard_lukes = '3mgs_wizard_lukes'
model_dir_wizard_branch = '3mgs_wizard_branch'
model_dir_wizard_bottomUp = '3mgs_wizard_bottomUp'
model_dir_wizard_criticalLoads = '3mgs_wizard_criticalLoads'
model_dir_lehigh_manual = '3mgs_lehigh_loadGrouping'
model_dir_lehigh_loadGrouping = '3mgs_lehigh_loadGrouping'
model_dir_lehigh_lukes = '3mgs_lehigh_lukes'
model_dir_lehigh_branch = '3mgs_lehigh_branch'
model_dir_lehigh_bottomUp = '3mgs_lehigh_bottomUp'
model_dir_lehigh_criticalLoads = '3mgs_lehigh_criticalLoads'

MG_MINES_3mgs_wizard_loadGrouping = {'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': ['reg0'], 'gen_bus': 'reg0_end', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1'], 'switch': ['reg1'], 'gen_bus': 'reg1_end', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['645_hangar', '646_office'], 'switch': ['reg2'], 'gen_bus': 'reg2_end', 'gen_obs_existing': [], 'critical_load_kws': [1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}
MG_MINES_3mgs_wizard_lukes = {'mg0': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1', '645_hangar', '646_office'], 'switch': ['regnone', 'reg0'], 'gen_bus': 'sub_bus', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [1155.0, 1155.0, 1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': ['reg0'], 'gen_bus': 'reg0_end', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['684_command_center', '692_warehouse2', '611_runway', '652_residential', '670a_residential2', '670b_residential2', '670c_residential2'], 'switch': ['regnone'], 'gen_bus': 'regnone', 'gen_obs_existing': [], 'critical_load_kws': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}
MG_MINES_3mgs_wizard_branch = {'mg0': {'loads': ['684_command_center', '692_warehouse2', '611_runway', '652_residential', '670a_residential2', '670b_residential2', '670c_residential2'], 'switch': ['regnone'], 'gen_bus': 'regnone_end', 'gen_obs_existing': [], 'critical_load_kws': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': ['reg0'], 'gen_bus': 'reg0_end', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1'], 'switch': ['reg1'], 'gen_bus': 'reg1_end', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg3': {'loads': ['645_hangar', '646_office'], 'switch': ['reg2'], 'gen_bus': 'reg2_end', 'gen_obs_existing': [], 'critical_load_kws': [1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}
MG_MINES_3mgs_wizard_bottomUp = {'mg0': {'loads': ['684_command_center', '692_warehouse2', '611_runway', '652_residential', '670a_residential2', '670b_residential2', '670c_residential2'], 'switch': ['regnone'], 'gen_bus': 'regnone_end', 'gen_obs_existing': [], 'critical_load_kws': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': ['reg0'], 'gen_bus': 'reg0_end', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1'], 'switch': ['reg1'], 'gen_bus': 'reg1_end', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg3': {'loads': ['645_hangar', '646_office'], 'switch': ['reg2'], 'gen_bus': 'reg2_end', 'gen_obs_existing': [], 'critical_load_kws': [1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}
MG_MINES_3mgs_wizard_criticalLoads = {'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': [None, None, None, 'reg0'], 'gen_bus': 'reg0_end', 'gen_obs_existing': [], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1'], 'switch': [None, None, 'reg1'], 'gen_bus': 'reg1_end', 'gen_obs_existing': [], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['645_hangar', '646_office'], 'switch': [None, 'reg2'], 'gen_bus': 'reg2_end', 'gen_obs_existing': [], 'critical_load_kws': [1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}
MG_MINES_3mgs_lehigh_manual = {'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': '632633', 'gen_bus': '634', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [160.0, 120.0, 120.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1'], 'switch': '671692', 'gen_bus': '675', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [485.0, 68.0, 290.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['645_hangar', '646_office'], 'switch': '632645', 'gen_bus': '646', 'gen_obs_existing': [], 'critical_load_kws': [170.0, 230.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}
MG_MINES_3mgs_lehigh_loadGrouping = {'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': ['xfm1'], 'gen_bus': '634', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [160.0, 120.0, 120.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1'], 'switch': ['692675'], 'gen_bus': '675', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [485.0, 68.0, 290.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['645_hangar', '646_office'], 'switch': ['632645'], 'gen_bus': '645', 'gen_obs_existing': [], 'critical_load_kws': [170.0, 230.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}
MG_MINES_3mgs_lehigh_lukes = {'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower', '645_hangar', '646_office', '670a_residential2', '670b_residential2', '670c_residential2'], 'switch': ['670671'], 'gen_bus': '634b_radar', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [160.0, 120.0, 120.0, 170.0, 230.0, 0.0, 0.0, 0.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['684_command_center', '692_warehouse2', '675a_hospital', '675b_residential1', '675c_residential1', '611_runway', '652_residential'], 'switch': ['670671'], 'gen_bus': '680', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [0.0, 0.0, 485.0, 68.0, 290.0, 0.0, 0.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}
MG_MINES_3mgs_lehigh_branch = {'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': ['632633'], 'gen_bus': '633', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [160.0, 120.0, 120.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['645_hangar', '646_office'], 'switch': ['632645'], 'gen_bus': '645', 'gen_obs_existing': [], 'critical_load_kws': [170.0, 230.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['684_command_center', '692_warehouse2', '675a_hospital', '675b_residential1', '675c_residential1', '611_runway', '652_residential', '670a_residential2', '670b_residential2', '670c_residential2'], 'switch': ['632670'], 'gen_bus': '670', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [0.0, 0.0, 485.0, 68.0, 290.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}
MG_MINES_3mgs_lehigh_bottomUp = {'mg0': {'loads': ['645_hangar', '646_office'], 'switch': ['632645'], 'gen_bus': '645', 'gen_obs_existing': [], 'critical_load_kws': [170.0, 230.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': ['632633'], 'gen_bus': '633', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [160.0, 120.0, 120.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['684_command_center', '692_warehouse2', '675a_hospital', '675b_residential1', '675c_residential1', '611_runway', '652_residential', '670a_residential2', '670b_residential2', '670c_residential2'], 'switch': ['632670'], 'gen_bus': '670', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [0.0, 0.0, 485.0, 68.0, 290.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}
MG_MINES_3mgs_lehigh_criticalLoads = {'mg0': {'loads': ['645_hangar', '646_office'], 'switch': ['632645'], 'gen_bus': '645', 'gen_obs_existing': [], 'critical_load_kws': [170.0, 230.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1'], 'switch': [None, None, '692675'], 'gen_bus': '675', 'gen_obs_existing': [], 'critical_load_kws': [485.0, 68.0, 290.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': ['632633', None, None], 'gen_bus': '633', 'gen_obs_existing': [], 'critical_load_kws': [160.0, 120.0, 120.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}

all_dir = [model_dir_wizard_loadGrouping, model_dir_wizard_lukes, model_dir_wizard_branch, model_dir_wizard_bottomUp, model_dir_wizard_criticalLoads, model_dir_lehigh_manual, model_dir_lehigh_loadGrouping, model_dir_lehigh_lukes, model_dir_lehigh_branch, model_dir_lehigh_bottomUp, model_dir_lehigh_criticalLoads]

wizard_dir = [model_dir_wizard_loadGrouping, model_dir_wizard_lukes, model_dir_wizard_branch, model_dir_wizard_bottomUp, model_dir_wizard_criticalLoads]

MG_MINES = {
    model_dir_wizard_loadGrouping: [MG_MINES_3mgs_wizard_loadGrouping, 'loadGrouping'],
    model_dir_wizard_lukes: [MG_MINES_3mgs_wizard_lukes, 'lukes'],
    model_dir_wizard_branch: [MG_MINES_3mgs_wizard_branch, 'branch'],
    model_dir_wizard_bottomUp: [MG_MINES_3mgs_wizard_bottomUp, 'bottomUp'],
    model_dir_wizard_criticalLoads: [MG_MINES_3mgs_wizard_criticalLoads, 'criticalLoads'], 
    model_dir_lehigh_manual: [MG_MINES_3mgs_lehigh_manual, 'manual'], 
    model_dir_lehigh_loadGrouping: [MG_MINES_3mgs_lehigh_loadGrouping, 'loadGrouping'], 
    model_dir_lehigh_lukes: [MG_MINES_3mgs_lehigh_lukes, 'lukes'], 
    model_dir_lehigh_branch: [MG_MINES_3mgs_lehigh_branch, 'branch'], 
    model_dir_lehigh_bottomUp: [MG_MINES_3mgs_lehigh_bottomUp, 'bottomUp'], 
    model_dir_lehigh_criticalLoads: [MG_MINES_3mgs_lehigh_criticalLoads, 'criticalLoads']
}


'''         IT'S TESTING TIME           '''
# Testing thomas_wip_frontend.jsonToDss/building circuits for microgridup.full() tests.
for dir in wizard_dir:
    thomas_wip_frontend.jsonToDss(dir, lat, lon, elements, True)    

# Testing microgridup_gen_mgs.mg_group().
for dir in MG_MINES:
    if MG_MINES[dir][0] == microgridup_gen_mgs.mg_group(f'{_myDir}/uploads/BASE_DSS_{dir}', crit_loads, MG_MINES[dir][1], pairings):
        print(f'MG_MINES_{dir} matches expected output.')
    else:
        print(f'MG_MINES_{dir} does not match expected output.')

# Testing compatibility of thomas_wip_frontend.py output with microgridup.full().
for dir in all_dir:
    mgu_args = [dir, f'{_myDir}/uploads/BASE_DSS_{dir}', f'{_myDir}/uploads/LOAD_CSV_{dir}', 480.0, 0.5, REOPT_INPUTS, MG_MINES[dir][0], '670671']
    print(f'Beginning full test of {dir}.')
    microgridup.full(*mgu_args)