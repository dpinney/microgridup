from omf.solvers import opendss
import networkx as nx
from pprint import pprint as pp

# Auto gen some microgrid descriptions.
# See experiments with networkx here: https://colab.research.google.com/drive/1RZyD6pRIdRAT-V2sBB0nPKVIvZP_RGHw

# Test inputs
CIRC_FILE = '../lehigh_base_phased.dss'
CRITICAL_LOADS = ['645_hangar','684_command_center', '611_runway','675a_hospital','634a_data_center', '634b_radar', '634c_atc_tower']
ALGO = 'lukes' #'branch'

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
	'Partition the graph using Lukes algorithm into pieces of [size] nodes.'
	tree_root = list(nx.topological_sort(G))[0]
	G_topo_order = nx.DiGraph(nx.algorithms.traversal.breadth_first_search.bfs_edges(G, tree_root))
	return nx.algorithms.community.lukes.lukes_partitioning(G_topo_order, size, node_weight=node_weight, edge_weight=edge_weight)

def nx_get_parent(G, n):
	preds = G.predecessors(n)
	return list(preds)[0]

def nx_out_edges(G, sub_nodes):
	'Find edges connect sub_nodes to rest of graph.'
	mg1 = G.subgraph(sub_nodes)
	out_edges = []
	for n in mg1.nodes():
		out_preds = [(x,n) for x in G.predecessors(n) if x not in mg1]
		out_succ = [(n,x) for x in G.successors(n) if x not in mg1]
		out_edges.extend(out_succ)
		out_edges.extend(out_preds)
	return out_edges

def get_edge_name(fr, to, omd_list):
	'Get an edge name using (fr,to) in the omd_list'
	edges = [ob.get('name') for ob in omd_list if ob.get('from') == fr and ob.get('to') == to]
	return None if len(edges) == 0 else edges[0]

def mg_group(circ_path, crit_loads, algo, algo_params={}):
	'''Generate a group of mgs from circ_path with crit_loads
	algo must be one of ["lukes", "branch"]
	lukes algo params is 'size':int giving size of each mg.
	branch algo params is 'i_branch': giving which branch in the tree to split on.'''
	# Load data
	G = opendss.dssConvert.dss_to_networkx(CIRC_FILE)
	# print(list(G.edges()))
	omd = opendss.dssConvert.dssToOmd(CIRC_FILE, None, write_out=False)
	omd_list = list(omd.values())
	# Generate microgrids
	if algo == 'lukes':
		default_size = int(len(G.nodes())/3)
		MG_GROUPS = nx_group_lukes(G, algo_params.get('size',default_size))
	elif algo == 'branch':
		MG_GROUPS = nx_group_branch(G, i_branch=algo_params.get('i_branch',0))
	else:
		print('Invalid algorithm. algo must be "branch" or "lukes". No mgs generated.')
		return {}
	all_mgs = [
		(M_ID, MG_GROUP, MG_GROUP[0], nx_out_edges(G, MG_GROUP))
		for (M_ID, MG_GROUP) in enumerate([list(x) for x in MG_GROUPS])
	]
	# print(all_mgs)
	MG_MINES = {
		f'mg{M_ID}': {
			'loads': [ob.get('name') for ob in omd_list if ob.get('name') in MG_GROUP and ob.get('object') == 'load'],
			'switch': [get_edge_name(swedge[0], swedge[1], omd_list) for swedge in BORDERS], #TODO: get daniel's code to handle multiple switches.
			'gen_bus': TREE_ROOT,
			'gen_obs_existing': [ob.get('name') for ob in omd_list if ob.get('name') in MG_GROUP and ob.get('object') in ('generator','pvsystem')],
			'critical_load_kws': [0.0 if ob.get('name') not in CRITICAL_LOADS else float(ob.get('kw','0')) for ob in omd_list if ob.get('name') in MG_GROUP and ob.get('object') == 'load'],
			'max_potential': '700', #TODO: this and other vars, how to set? Ask Matt.
			'max_potential_diesel': '1000000',
			'battery_capacity': '10000'
		} for (M_ID, MG_GROUP, TREE_ROOT, BORDERS) in all_mgs
	}
	return MG_MINES

if __name__ == '__main__':
	mgs = mg_group(CIRC_FILE, CRITICAL_LOADS, 'lukes')
	pp(mgs)