from omf.solvers import opendss
import networkx as nx
from pprint import pprint as pp

CIRC_FILE = '../lehigh_base_phased.dss'
G = opendss.dssConvert.dss_to_networkx(CIRC_FILE)
print(list(G.edges()))

# Design inspiration
MICROGRIDS = {
	'm0': {
		'loads': ['634a_data_center','634b_radar','634c_atc_tower'],
		'switch': '632633',
		'gen_bus': '634',
		'gen_obs_existing': ['solar_634_existing', 'battery_634_existing'],
		'critical_load_kws': [], #[70,90,10],
		'max_potential': '700',
		'max_potential_diesel': '1000000',
		'battery_capacity': '10000'
	},
	'm1': {
		'loads': ['675a_hospital','675b_residential1','675c_residential1'],
		'switch': '671692',
		'gen_bus': '675',
		'gen_obs_existing': [],
		'critical_load_kws': [150,200,200],
		'max_potential': '900',
		'max_potential_diesel': '1000000',
		'battery_capacity': '10000'
	}
}

# Networkx helper functions
def nx_get_branches(G):
	'All branchy boys'
	return [(n,G.out_degree(n)) for n in G.nodes() if G.out_degree(n) > 1]

def nx_group_branch(G, i_branch=0):
	'Create graph subgroups at branch point i_branch (topological order).'
	tree_root = list(nx.topological_sort(G))[0]
	edges_in_order = nx.DiGraph(nx.algorithms.traversal.breadth_first_search.bfs_edges(G, tree_root))
	bbl = nx_get_branches(edges_in_order)
	first_branch = bbl[i_branch][0]
	succs = list(G.successors(first_branch))
	parts = [list(nx.algorithms.traversal.depth_first_search.dfs_tree(G, x).nodes()) for x in succs]
	return parts

def nx_group_lukes(G, size, node_weight=None, edge_weight=None):
    ''' Partition the graph using Lukes algorithm into pieces of [size] nodes.'''
    tree_root = list(nx.topological_sort(G))[0]
    G_topo_order = nx.DiGraph(nx.algorithms.traversal.breadth_first_search.bfs_edges(G, tree_root))
    return nx.algorithms.community.lukes.lukes_partitioning(G_topo_order, size, node_weight=node_weight, edge_weight=edge_weight)

# Auto gen some microgrid descriptions.
'''
def mg_group_lukes(omd, size) -> MICROGRIDS
def mg_group_branch(omd, b_index) - > MICROGRIDS
'''

omd = opendss.dssConvert.dssToOmd(CIRC_FILE, None, write_out=False)
omd_list = list(omd.values())
MG_GROUPS = nx_group_lukes(G, 12)

def get_parent(G, n):
	preds = G.predecessors(n)
	return list(preds)[0]

all_mgs = [(M_ID, MG_GROUP, MG_GROUP[0], get_parent(G, MG_GROUP[0])) for (M_ID, MG_GROUP) in enumerate([list(x) for x in MG_GROUPS])]
print(all_mgs)

CRITICAL_LOADS = ['645_hangar','684_command_center', '611_runway','675a_hospital','634a_data_center', '634b_radar', '634c_atc_tower']

MG_MINES = {
	f'm{M_ID}': {
		'loads': [ob.get('name') for ob in omd_list if ob.get('name') in MG_GROUP and ob.get('object') == 'load'],
		'switch': [ob.get('name') for ob in omd_list if ob.get('from') == UP_1_NODE and ob.get('to') == TREE_ROOT], #TODO: handle multiple switches.
		'gen_bus': TREE_ROOT,
		'gen_obs_existing': [ob.get('name') for ob in omd_list if ob.get('name') in MG_GROUP and ob.get('object') in ('generator','pvsystem')],
		'critical_load_kws': [0.0 if ob.get('name') not in CRITICAL_LOADS else float(ob.get('kw','0')) for ob in omd_list if ob.get('name') in MG_GROUP and ob.get('object') == 'load'],
		'max_potential': '700', #TODO: this and other vars, how to set? Ask Matt.
		'max_potential_diesel': '1000000',
		'battery_capacity': '10000'
	} for (M_ID, MG_GROUP, TREE_ROOT, UP_1_NODE) in all_mgs
}

pp(MG_MINES)