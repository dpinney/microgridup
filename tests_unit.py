'''
Writes testing parameters to json and calls _tests() functions in microgridup_gui.py, microgridup_gen_mgs.py, microgridup_control.py, and microgridup.py.
11 logic pathways for end to end tests:
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
import json
from collections import OrderedDict
import microgridup_gen_mgs, microgridup_gui, microgridup_control, microgridup

crit_loads = ['634a_data_center', '634b_radar', '634c_atc_tower', '675a_hospital', '675b_residential1', '675c_residential1', '645_hangar', '646_office']
old_algo_params = {'pairings': {'None': ['684_command_center', '692_warehouse2', '611_runway', '652_residential', '670a_residential2', '670b_residential2', '670c_residential2'], 'Mg1': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'Mg3': ['645_hangar', '646_office'], 'Mg2': ['675a_hospital', '675b_residential1', '675c_residential1']}, 'gen_bus': {'Mg1': '634', 'Mg2': '675', 'Mg3': '646'}, 'switch': {'Mg1': '632633', 'Mg2': '671692', 'Mg3': '632645'}}
algo_params = {'pairings': {'None': ['684_command_center', '692_warehouse2', '611_runway', '652_residential', '670a_residential2', '670b_residential2', '670c_residential2'], 'Mg1': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'Mg3': ['645_hangar', '646_office'], 'Mg2': ['675a_hospital', '675b_residential1', '675c_residential1']}, 'gen_bus': {'Mg1': '634', 'Mg2': '675', 'Mg3': '646'}, 'switch': {'Mg1': ['632633'], 'Mg2': ['671692'], 'Mg3': ['632645']}} # Note: 'switch' must be ['string in list'] to match this_switch behavior in MG_MINES.
pairings = algo_params['pairings']
elements = [{'class': 'substation', 'text': 'sub'}, {'class': 'feeder', 'text': 'regNone'}, {'class': 'load', 'text': '684_command_center'}, {'class': 'load', 'text': '692_warehouse2'}, {'class': 'load', 'text': '611_runway'}, {'class': 'load', 'text': '652_residential'}, {'class': 'load', 'text': '670a_residential2'}, {'class': 'load', 'text': '670b_residential2'}, {'class': 'load', 'text': '670c_residential2'}, {'class': 'feeder', 'text': 'reg0'}, {'class': 'load', 'text': '634a_data_center'}, {'class': 'load', 'text': '634b_radar'}, {'class': 'load', 'text': '634c_atc_tower'}, {'class': 'solar', 'text': 'solar_634_existing'}, {'class': 'battery', 'text': 'battery_634_existing'}, {'class': 'feeder', 'text': 'reg1'}, {'class': 'load', 'text': '675a_hospital'}, {'class': 'load', 'text': '675b_residential1'}, {'class': 'load', 'text': '675c_residential1'}, {'class': 'fossil', 'text': 'fossil_675_existing'}, {'class': 'feeder', 'text': 'reg2'}, {'class': 'load', 'text': '645_hangar'}, {'class': 'load', 'text': '646_office'}]
REOPT_INPUTS = {'energyCost': '0.12', 'wholesaleCost': '0.034', 'demandCost': '20', 'solarCanCurtail': True, 'solarCanExport': True, 'criticalLoadFactor': '1', 'year': '2017', 'outageDuration': '48', 'value_of_lost_load': '1', 'solar': 'on', 'battery': 'on', 'fossil': 'on', 'wind': 'off', 'solarCost': '1600', 'solarExisting': '0', 'solarMax': '100000', 'solarMin': '0', 'batteryCapacityCost': '420', 'batteryCapacityMax': '1000000', 'batteryCapacityMin': '0', 'batteryKwhExisting': '0', 'batteryPowerCost': '840', 'batteryPowerMax': '1000000', 'batteryPowerMin': '0', 'batteryKwExisting': '0', 'dieselGenCost': '500', 'dieselMax': '1000000', 'fuelAvailable': '50000', 'genExisting': '0', 'minGenLoading': '0.3', 'windCost': '4989', 'windExisting': '0', 'windMax': '100000', 'windMin': '0'}
templateDssTree = [OrderedDict([('!CMD', 'clear')]), OrderedDict([('!CMD', 'set'), ('defaultbasefrequency', '60')]), OrderedDict([('!CMD', 'new'), ('object', 'REPLACE_ME')]), OrderedDict([('!CMD', 'new'), ('object', 'vsource.sub'), ('basekv', '115'), ('bus1', 'sub_bus.1.2.3'), ('pu', '1.00'), ('r1', '0'), ('x1', '0.0001'), ('r0', '0'), ('x0', '0.0001')]), OrderedDict([('!CMD', 'new'), ('object', 'line.regnone'), ('phases', '3'), ('bus1', 'sub_bus.1.2.3'), ('bus2', 'regnone_end.1.2.3'), ('length', '1333'), ('units', 'ft')]), OrderedDict([('!CMD', 'new'), ('object', 'load.684_command_center'), ('bus1', 'regnone_end.1'), ('phases', '1'), ('conn', 'wye'), ('model', '1'), ('kv', '2.4'), ('kw', '1155'), ('kvar', '660')]), OrderedDict([('!CMD', 'new'), ('object', 'load.692_warehouse2'), ('bus1', 'regnone_end.1'), ('phases', '1'), ('conn', 'wye'), ('model', '1'), ('kv', '2.4'), ('kw', '1155'), ('kvar', '660')]), OrderedDict([('!CMD', 'new'), ('object', 'load.611_runway'), ('bus1', 'regnone_end.1'), ('phases', '1'), ('conn', 'wye'), ('model', '1'), ('kv', '2.4'), ('kw', '1155'), ('kvar', '660')]), OrderedDict([('!CMD', 'new'), ('object', 'load.652_residential'), ('bus1', 'regnone_end.1'), ('phases', '1'), ('conn', 'wye'), ('model', '1'), ('kv', '2.4'), ('kw', '1155'), ('kvar', '660')]), OrderedDict([('!CMD', 'new'), ('object', 'load.670a_residential2'), ('bus1', 'regnone_end.1'), ('phases', '1'), ('conn', 'wye'), ('model', '1'), ('kv', '2.4'), ('kw', '1155'), ('kvar', '660')]), OrderedDict([('!CMD', 'new'), ('object', 'load.670b_residential2'), ('bus1', 'regnone_end.1'), ('phases', '1'), ('conn', 'wye'), ('model', '1'), ('kv', '2.4'), ('kw', '1155'), ('kvar', '660')]), OrderedDict([('!CMD', 'new'), ('object', 'load.670c_residential2'), ('bus1', 'regnone_end.1'), ('phases', '1'), ('conn', 'wye'), ('model', '1'), ('kv', '2.4'), ('kw', '1155'), ('kvar', '660')]), OrderedDict([('!CMD', 'new'), ('object', 'line.reg0'), ('phases', '3'), ('bus1', 'sub_bus.1.2.3'), ('bus2', 'reg0_end.1.2.3'), ('length', '1333'), ('units', 'ft')]), OrderedDict([('!CMD', 'new'), ('object', 'load.634a_data_center'), ('bus1', 'reg0_end.1'), ('phases', '1'), ('conn', 'wye'), ('model', '1'), ('kv', '2.4'), ('kw', '1155'), ('kvar', '660')]), OrderedDict([('!CMD', 'new'), ('object', 'load.634b_radar'), ('bus1', 'reg0_end.1'), ('phases', '1'), ('conn', 'wye'), ('model', '1'), ('kv', '2.4'), ('kw', '1155'), ('kvar', '660')]), OrderedDict([('!CMD', 'new'), ('object', 'load.634c_atc_tower'), ('bus1', 'reg0_end.1'), ('phases', '1'), ('conn', 'wye'), ('model', '1'), ('kv', '2.4'), ('kw', '1155'), ('kvar', '660')]), OrderedDict([('!CMD', 'new'), ('object', 'generator.solar_634_existing'), ('bus1', 'reg0_end.1'), ('phases', '1'), ('kv', '0.277'), ('kw', '440'), ('pf', '1')]), OrderedDict([('!CMD', 'new'), ('object', 'storage.battery_634_existing'), ('bus1', 'reg0_end.1'), ('phases', '1'), ('kv', '0.277'), ('kwrated', '79'), ('kwhstored', '307'), ('kwhrated', '307'), ('dispmode', 'follow'), ('%charge', '100'), ('%discharge', '100'), ('%effcharge', '96'), ('%effdischarge', '96')]), OrderedDict([('!CMD', 'new'), ('object', 'line.reg1'), ('phases', '3'), ('bus1', 'sub_bus.1.2.3'), ('bus2', 'reg1_end.1.2.3'), ('length', '1333'), ('units', 'ft')]), OrderedDict([('!CMD', 'new'), ('object', 'load.675a_hospital'), ('bus1', 'reg1_end.1'), ('phases', '1'), ('conn', 'wye'), ('model', '1'), ('kv', '2.4'), ('kw', '1155'), ('kvar', '660')]), OrderedDict([('!CMD', 'new'), ('object', 'load.675b_residential1'), ('bus1', 'reg1_end.1'), ('phases', '1'), ('conn', 'wye'), ('model', '1'), ('kv', '2.4'), ('kw', '1155'), ('kvar', '660')]), OrderedDict([('!CMD', 'new'), ('object', 'load.675c_residential1'), ('bus1', 'reg1_end.1'), ('phases', '1'), ('conn', 'wye'), ('model', '1'), ('kv', '2.4'), ('kw', '1155'), ('kvar', '660')]), OrderedDict([('!CMD', 'new'), ('object', 'generator.fossil_675_existing'), ('bus1', 'reg1_end.1.2.3'), ('phases', '3'), ('kw', '265'), ('pf', '1'), ('kv', '2.4'), ('xdp', '0.27'), ('xdpp', '0.2'), ('h', '2')]), OrderedDict([('!CMD', 'new'), ('object', 'line.reg2'), ('phases', '3'), ('bus1', 'sub_bus.1.2.3'), ('bus2', 'reg2_end.1.2.3'), ('length', '1333'), ('units', 'ft')]), OrderedDict([('!CMD', 'new'), ('object', 'load.645_hangar'), ('bus1', 'reg2_end.1'), ('phases', '1'), ('conn', 'wye'), ('model', '1'), ('kv', '2.4'), ('kw', '1155'), ('kvar', '660')]), OrderedDict([('!CMD', 'new'), ('object', 'load.646_office'), ('bus1', 'reg2_end.1'), ('phases', '1'), ('conn', 'wye'), ('model', '1'), ('kv', '2.4'), ('kw', '1155'), ('kvar', '660')]), OrderedDict([('!CMD', 'makebuslist')]), OrderedDict([('!CMD', 'setbusxy'), ('bus', 'sub_bus'), ('y', '39.780499999999996'), ('x', '-89.6528749')]), OrderedDict([('!CMD', 'setbusxy'), ('bus', 'regnone_end'), ('y', '39.783882999999996'), ('x', '-89.6516439')]), OrderedDict([('!CMD', 'setbusxy'), ('bus', 'reg0_end'), ('y', '39.779875'), ('x', '-89.6564204')])]
MG_MINES = {
    '3mgs_wizard_loadgrouping': [{'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': 'reg0', 'gen_bus': 'reg0_end', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1'], 'switch': 'reg1', 'gen_bus': 'reg1_end', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['645_hangar', '646_office'], 'switch': 'reg2', 'gen_bus': 'reg2_end', 'gen_obs_existing': [], 'critical_load_kws': [1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}, 'loadGrouping'],
    '3mgs_wizard_lukes': [{'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower', '645_hangar', '646_office'], 'switch': 'reg1', 'gen_bus': 'battery_634_existing', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [1155.0, 1155.0, 1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1'], 'switch': 'reg1', 'gen_bus': 'reg1_end', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['684_command_center', '692_warehouse2', '611_runway', '652_residential', '670a_residential2', '670b_residential2', '670c_residential2'], 'switch': 'regnone', 'gen_bus': '670a_residential2', 'gen_obs_existing': [], 'critical_load_kws': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}, 'lukes'],
    '3mgs_wizard_branch': [{'mg0': {'loads': ['684_command_center', '692_warehouse2', '611_runway', '652_residential', '670a_residential2', '670b_residential2', '670c_residential2'], 'switch': 'regnone', 'gen_bus': 'regnone_end', 'gen_obs_existing': [], 'critical_load_kws': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': 'reg0', 'gen_bus': 'reg0_end', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1'], 'switch': 'reg1', 'gen_bus': 'reg1_end', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg3': {'loads': ['645_hangar', '646_office'], 'switch': 'reg2', 'gen_bus': 'reg2_end', 'gen_obs_existing': [], 'critical_load_kws': [1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}, 'branch'],
    '3mgs_wizard_bottomup': [{'mg0': {'loads': ['684_command_center', '692_warehouse2', '611_runway', '652_residential', '670a_residential2', '670b_residential2', '670c_residential2'], 'switch': 'regnone', 'gen_bus': 'regnone_end', 'gen_obs_existing': [], 'critical_load_kws': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': 'reg0', 'gen_bus': 'reg0_end', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1'], 'switch': 'reg1', 'gen_bus': 'reg1_end', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg3': {'loads': ['645_hangar', '646_office'], 'switch': 'reg2', 'gen_bus': 'reg2_end', 'gen_obs_existing': [], 'critical_load_kws': [1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}, 'bottomUp'],
    '3mgs_wizard_criticalloads': [{'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': 'reg0', 'gen_bus': 'reg0_end', 'gen_obs_existing': [], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1'], 'switch': 'reg1', 'gen_bus': 'reg1_end', 'gen_obs_existing': [], 'critical_load_kws': [1155.0, 1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['645_hangar', '646_office'], 'switch': 'reg2', 'gen_bus': 'reg2_end', 'gen_obs_existing': [], 'critical_load_kws': [1155.0, 1155.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}, 'criticalLoads'],
    '3mgs_lehigh_manual': [{'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': '632633', 'gen_bus': '634', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [160.0, 120.0, 120.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1'], 'switch': '671692', 'gen_bus': '675', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [485.0, 68.0, 290.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['645_hangar', '646_office'], 'switch': '632645', 'gen_bus': '646', 'gen_obs_existing': [], 'critical_load_kws': [170.0, 230.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}, 'manual'],
    '3mgs_lehigh_loadgrouping': [{'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': 'xfm1', 'gen_bus': '634', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [160.0, 120.0, 120.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1'], 'switch': '692675', 'gen_bus': '675', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [485.0, 68.0, 290.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['645_hangar', '646_office'], 'switch': '632645', 'gen_bus': '645', 'gen_obs_existing': [], 'critical_load_kws': [170.0, 230.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}, 'loadGrouping'], 
    '3mgs_lehigh_lukes': [{'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower', '645_hangar', '646_office', '670a_residential2', '670b_residential2', '670c_residential2'], 'switch': '670671', 'gen_bus': '650', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [160.0, 120.0, 120.0, 170.0, 230.0, 0.0, 0.0, 0.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['684_command_center', '692_warehouse2', '675a_hospital', '675b_residential1', '675c_residential1', '611_runway', '652_residential'], 'switch': '670671', 'gen_bus': '680', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [0.0, 0.0, 485.0, 68.0, 290.0, 0.0, 0.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}, 'lukes'], 
    '3mgs_lehigh_branch': [{'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': '632633', 'gen_bus': '633', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [160.0, 120.0, 120.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['645_hangar', '646_office'], 'switch': '632645', 'gen_bus': '645', 'gen_obs_existing': [], 'critical_load_kws': [170.0, 230.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['684_command_center', '692_warehouse2', '675a_hospital', '675b_residential1', '675c_residential1', '611_runway', '652_residential', '670a_residential2', '670b_residential2', '670c_residential2'], 'switch': '632670', 'gen_bus': '670', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [0.0, 0.0, 485.0, 68.0, 290.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}, 'branch'], 
    '3mgs_lehigh_bottomup': [{'mg0': {'loads': ['645_hangar', '646_office'], 'switch': '632645', 'gen_bus': '645', 'gen_obs_existing': [], 'critical_load_kws': [170.0, 230.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': '632633', 'gen_bus': '633', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [160.0, 120.0, 120.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['684_command_center', '692_warehouse2', '675a_hospital', '675b_residential1', '675c_residential1', '611_runway', '652_residential', '670a_residential2', '670b_residential2', '670c_residential2'], 'switch': '632670', 'gen_bus': '670', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [0.0, 0.0, 485.0, 68.0, 290.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}, 'bottomUp'],
    '3mgs_lehigh_criticalloads': [{'mg0': {'loads': ['645_hangar', '646_office'], 'switch': '632645', 'gen_bus': '645', 'gen_obs_existing': [], 'critical_load_kws': [170.0, 230.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1'], 'switch': '692675', 'gen_bus': '675', 'gen_obs_existing': [], 'critical_load_kws': [485.0, 68.0, 290.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': '632633', 'gen_bus': '633', 'gen_obs_existing': [], 'critical_load_kws': [160.0, 120.0, 120.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}, 'criticalLoads']
}
control_test_args = {
    'lehigh1mg':{'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower', '675a_hospital', '675b_residential1', '675c_residential1', '692_warehouse2', '684_command_center', '652_residential', '611_runway', '645_hangar', '646_office'], 'switch': '650632', 'gen_bus': '670', 'gen_obs_existing': ['solar_634_existing', 'solar_675_existing', 'fossil_684_existing', 'fossil_646_existing', 'battery_634_existing', 'battery_684_existing'], 'critical_load_kws': [70, 90, 10, 150, 200, 200, 400, 20, 30, 70, 0, 0]}},
    'lehigh2mgs':{'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': '632633', 'gen_bus': '634', 'gen_obs_existing': ['wind_634_existing'], 'critical_load_kws': [70, 90, 10]}, 'mg1': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1', '692_warehouse2'], 'switch': '671692', 'gen_bus': '675', 'gen_obs_existing': ['battery_675_existing', 'battery_675_2_existing'], 'critical_load_kws': [150, 200, 200]}},
    'lehigh3mgs':{'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': '632633', 'gen_bus': '634', 'gen_obs_existing': ['solar_634_existing', 'battery_634_existing'], 'critical_load_kws': [70, 90, 10]}, 'mg1': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1', '692_warehouse2'], 'switch': '671692', 'gen_bus': '675', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [150, 200, 200]}, 'mg2': {'loads': ['645_hangar', '646_office'], 'switch': '632645', 'gen_bus': '646', 'gen_obs_existing': [], 'critical_load_kws': [30, 70]}},
    'lehigh4mgs':{'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': '632633', 'gen_bus': '634', 'gen_obs_existing': ['solar_634_existing', 'battery_634_existing'], 'critical_load_kws': [70, 90, 10]}, 'mg1': {'loads': ['675a_hospital', '675b_residential1', '675c_residential1', '692_warehouse2'], 'switch': '671692', 'gen_bus': '675', 'gen_obs_existing': ['solar_675_existing'], 'critical_load_kws': [150, 200, 200, 0]}, 'mg2': {'loads': ['684_command_center', '652_residential', '611_runway'], 'switch': '671684', 'gen_bus': '684', 'gen_obs_existing': ['fossil_684_existing', 'battery_684_existing'], 'critical_load_kws': [400, 20, 0]}, 'mg3': {'loads': ['645_hangar', '646_office'], 'switch': '632645', 'gen_bus': '646', 'gen_obs_existing': ['battery_646_existing'], 'critical_load_kws': [30, 70]}},
    'lehighauto_3mg':{'mg0': {'loads': ['634a_data_center', '634b_radar', '634c_atc_tower'], 'switch': '632633', 'gen_bus': '633', 'gen_obs_existing': ['solar_634_existing'], 'critical_load_kws': [160.0, 120.0, 120.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg1': {'loads': ['645_hangar', '646_office'], 'switch': '632645', 'gen_bus': '645', 'gen_obs_existing': [], 'critical_load_kws': [170.0, 0.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}, 'mg2': {'loads': ['684_command_center', '692_warehouse2', '675a_hospital', '675b_residential1', '675c_residential1', '611_runway', '652_residential', '670a_residential2', '670b_residential2', '670c_residential2'], 'switch': '632670', 'gen_bus': '670', 'gen_obs_existing': ['fossil_675_existing'], 'critical_load_kws': [1155.0, 0.0, 485.0, 0.0, 0.0, 170.0, 0.0, 0.0, 0.0, 0.0], 'max_potential': '700', 'max_potential_diesel': '1000000', 'battery_capacity': '10000'}}
}
max_crit_loads = {
    'lehigh1mg':{'mg0':1240},
    'lehigh2mgs':{'mg0':170,
                 'mg1':550},
    'lehigh3mgs':{'mg0':170,
                  'mg1':550,
                  'mg2':100},
    'lehigh4mgs':{'mg0':170,
                  'mg1':550,
                  'mg2':420,
                  'mg3':100},
    'lehighauto_3mg':{'mg0':400,
                      'mg1':170,
                      'mg2':1810}
}


'''         IT'S TESTING TIME           '''
def write_test_params():
    test_params = {
        'crit_loads':crit_loads,
        'algo_params':algo_params,
        'elements':elements,
        'REOPT_INPUTS':REOPT_INPUTS,
        'templateDssTree':templateDssTree,
        'MG_MINES':MG_MINES,
        'control_test_args':control_test_args,
        'max_crit_loads':max_crit_loads
    }
    with open(f'{microgridup.MGU_FOLDER}/testfiles/test_params.json', 'w') as file:
        json.dump(test_params, file, sort_keys=False, indent=4)
    return print('Wrote test_params to test_params.json.')

def run_all_tests():
    microgridup_gui._tests()
    microgridup_gen_mgs._tests()
    microgridup_control._tests()
    microgridup._tests()
    return print('Ran all tests.')
                
if __name__ == '__main__':
    write_test_params()
    run_all_tests()