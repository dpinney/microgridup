import os, json
from omf.solvers import opendss
import networkx as nx
from pprint import pprint as pp
from collections import defaultdict, deque

# Auto gen some microgrid descriptions.
# See experiments with networkx here: https://colab.research.google.com/drive/1RZyD6pRIdRAT-V2sBB0nPKVIvZP_RGHw
# New colab with updated experiments: https://colab.research.google.com/drive/1j_u30UdnhaRovtG6Odhe_ivDKwBlc5qY?usp=sharing

# Test inputs
# CIRC_FILE = 'lehigh_base_3mg.dss'
# CRITICAL_LOADS = ['645_hangar','684_command_center', '611_runway','675a_hospital','634a_data_center', '634b_radar', '634c_atc_tower']
# ALGO = 'lukes' #'branch'

# Networkx helper functions
def nx_get_branches(G):
	'All branchy boys'
	return [(n,G.out_degree(n)) for n in G.nodes() if G.out_degree(n) > 1]

# A function to get all trees in a forest
def get_all_trees(F):
	list_of_trees = list(nx.weakly_connected_components(F))
	return [F.subgraph(tree) for tree in list_of_trees]

# Helper function to remove cycles and loops from a graph using hacky topological sort because nx_topological_sort breaks on cycles.
def remove_loops(G):
	# Delete edges to all parents except the first in topological order.
	H = G.copy()
	order = []
	for k,v in nx.dfs_successors(H).items():
		if k not in order:
			order.append(k)
		for v_ in v:
			if v_ not in order:
				order.append(v_)
	for node in order: 
		parents = list(H.predecessors(node))
		if len(parents) > 1:
			ordered_parents = [x for x in order if x in parents]
			for idx in range(1,len(ordered_parents)):
				H.remove_edge(ordered_parents[idx],node)
		# Origin shouldn't have any parents. TO DO: Figure out why this sometimes breaks circuits with cycles to the source.
		# elif node == order[0] and len(parents) == 1:
			# G.remove_edge(parents[0],node)
	return H

# Used by both bottom up and critical load algorithms.
def only_child(G, mgs):
	for key in list(mgs.keys()):
		parent = list(G.predecessors(key))
		if not parent:
			continue
		if len(parent) > 1:
			continue 
		grandparent = list(G.predecessors(parent[-1]))
		if not grandparent:
			continue # Do not want to include root node in microgrid (no viable switch).
		siblings = list(G.successors(parent[0]))
		while parent and len(siblings) == 1:
			mgs[parent[0]].append(siblings[0])
			mgs[parent[0]].extend(mgs[siblings[0]])
			del mgs[siblings[0]]
			parent = list(G.predecessors(parent[0]))
			grandparent = list(G.predecessors(parent[-1]))
			if not parent or len(parent) > 1 or not grandparent:
				break
			siblings = list(G.successors(parent[0]))
	return mgs

# Used by both bottom up and critical load algorithms.
def loop_avoider(G, mgs):
	bustworthy_nodes = set()
	
	def helper(node, isKey):
		bustworthy_nodes.add(node)
		# We have a loop on our hands. 
		lca = nx.lowest_common_ancestor(G, parents[0], parents[1]) # Assumption: only need to find LCA of two parents. TO DO: verify this assumption.
		lca_succs = list(nx.nodes(nx.dfs_tree(G, lca)))
		mgs[parents[0]].append(node)
		mgs[parents[0]].extend(mgs[node])
		mgs[parents[1]].extend([])
		if isKey:
			del mgs[node]
		new_keys = [x for x in topological_sort(G) if x in list(mgs.keys())] 
		for k in new_keys:
			if k in lca_succs:
				vals = mgs[k]
				pointer = k
				while pointer != lca: 
					vals.append(pointer)
					new_parents = list(G.predecessors(pointer))
					if len(new_parents) > 1:
						break 
					pointer = new_parents[0]
				mgs[lca].extend(vals)
				del mgs[k]

	# If a node has multiple parents, must find lowest common ancestor and make this node new key in mgs.
	keys = [x for x in topological_sort(G) if x in list(mgs.keys())]
	for key in keys:
		parents = list(G.predecessors(key))
		if len(parents) > 1:
			helper(key, True)
	# Did we miss any loops in the new values?
	for value in list(mgs.values()):
		for node in value:
			parents = list(G.predecessors(node))
			if len(parents) > 1 and node not in bustworthy_nodes:
				helper(node, False)
	return mgs

# Used by the bottom up algorithm.
def relatable_siblings(G, mgs):
	items = [x for x in topological_sort(G) if x in list(mgs.keys())]
	for key in items:
		if key not in mgs:
			continue
		parent = list(G.predecessors(key))
		if len(parent) > 1:
			continue
		siblings = list(G.successors(parent[0]))
		if all(sibling in mgs for sibling in siblings):
			# Merge microgrids 
			for sibling in siblings:
				mgs[parent[0]].append(sibling)
				mgs[parent[0]].extend(mgs[sibling]) 
				del mgs[sibling]
	return mgs

# Used by the critical load algorithm.
def merge_mgs(G, mgs):
	'''
	Check to see if parent is a key in a microgrid.
	Check to see if parent is a value in a microgrid.
	Check to see if parent is parent of other most ancestral node.
	Check to see if parent has no successors in any other mg.
	'''
	items = [x for x in topological_sort(G) if x in list(mgs.keys())]
	for k in items:
		if k not in mgs.keys():
			continue
		parent = list(G.predecessors(k))
		if not parent:
			continue
		parent = parent[0]
		inValues = [key for key, value in mgs.items() if parent in value]
		otherParent = [key for key, value in mgs.items() if list(G.predecessors(key)) == [parent] and key != k]
		otherKeys = [key for key, value in mgs.items() if key in list(nx.nodes(nx.dfs_tree(G, parent))) and key != k]
		otherValues = [key for key, value in mgs.items() if (set(value) & set(list(nx.nodes(nx.dfs_tree(G, parent))))) and key != k]
		otherMgs = otherKeys + otherValues
		if parent in mgs.keys() or inValues:
			# If the parent is already in a microgrid, merge with existing microgrid.
			if inValues: 
				mgs[inValues[0]].append(k)
				mgs[inValues[0]].extend(mgs[k])
				del mgs[k]
			else:
				mgs[parent].append(k)
				mgs[parent].extend(mgs[k]) 
				del mgs[k]
		elif otherParent:
			# Else if parent is also the parent of a different microgrid’s most ancestral node, annex parent and merge microgrids.
			mgs[parent].append(k)
			mgs[parent].append(otherParent[0])
			mgs[parent].extend(mgs[k])
			mgs[parent].extend(mgs[otherParent[0]])
			del mgs[k]
			del mgs[otherParent[0]]
		elif not otherMgs:
			# Else if parent has no successors in any other microgrid, annex parent.
			mgs[parent].append(k)
			mgs[parent].extend(mgs[k])
			del mgs[k]
	return mgs

def nx_group_branch(G, i_branch=0):
	'Create graph subgroups at branch point i_branch (topological order).'
	if not nx.is_tree(G):
		G = remove_loops(G)
	tree_root = list(topological_sort(G))[0]
	edges_in_order = nx.DiGraph(nx.algorithms.traversal.breadth_first_search.bfs_edges(G, tree_root))
	bbl = nx_get_branches(edges_in_order)
	first_branch = bbl[i_branch][0]
	succs = list(G.successors(first_branch))
	parts = [list(nx.algorithms.traversal.depth_first_search.dfs_tree(G, x).nodes()) for x in succs]
	return parts

def nx_group_lukes(G, size, node_weight=None, edge_weight=None):
	'Partition the graph using Lukes algorithm into pieces of [size] nodes.'
	if not nx.is_tree(G):
		G = remove_loops(G)
	tree_root = list(topological_sort(G))[0]
	G_topo_order = nx.DiGraph(nx.algorithms.traversal.breadth_first_search.bfs_edges(G, tree_root))
	return nx.algorithms.community.lukes.lukes_partitioning(G_topo_order, size, node_weight=node_weight, edge_weight=edge_weight)

def get_object_type_from_omd(node_name, omd):
	'''Get object type from omd given name.'''
	for key in omd:
		if omd[key].get('name') == node_name:
			return omd[key].get('object')
	return None 

def get_end_nodes(G, omd, cannot_be_mg):
	'''Find nodes with parents but no children. Omit leaves if they cannot be a microgrid on their own.'''
	end_nodes = []
	for node in G.nodes():
		if G.out_degree(node) == 0 and G.in_degree(node)!=0:
			object_type = get_object_type_from_omd(node, omd)
			if object_type not in cannot_be_mg:
				end_nodes.append([node])
	return end_nodes

def nx_bottom_up_branch(G, num_mgs=3, large_or_small='large', omd={}, cannot_be_mg=[]):
	'Form all microgrid combinations starting with leaves and working up to source maintaining single points of connection for each.'
	try:
		list(topological_sort(G))
	except ValueError:
		G = remove_loops(G)
	# Find leaves.
	end_nodes = get_end_nodes(G, omd, cannot_be_mg)
	mgs = defaultdict(list)
	for node in end_nodes:
		mgs[node[-1]] = []
	mgs = only_child(G, mgs)
	parts = defaultdict(list)
	for key in mgs:
		parts[0].append([key])
		parts[0][-1].extend(mgs[key])
	counter = 1
	while len(mgs) > 1:
		mgs = loop_avoider(G, mgs)
		mgs = relatable_siblings(G, mgs)
		mgs = only_child(G, mgs)
		if len(mgs) < num_mgs:
			break
		for key in mgs: 
			parts[counter].append([key])
			parts[counter][-1].extend(mgs[key])
		counter += 1
		if len(mgs) == num_mgs and large_or_small == 'small':
			break
	return parts[len(parts)-1]

def nx_critical_load_branch(G, criticalLoads, num_mgs=3, large_or_small='large'):
	'Form all microgrid combinations prioritizing only critical loads and single points of connection.'
	# Find all critical loads. They get a microgrid each. Output.
	critical_nodes = [[x] for x in G.nodes() if x in criticalLoads]
	try:
		top_down = list(topological_sort(G))
	except ValueError:
		G = remove_loops(G)
		top_down = list(topological_sort(G))
	mgs = defaultdict(list)
	for node in critical_nodes:
		mgs[node[-1]] = []
	# Include as many parents and parents of parents etc. in microgrid such that these parents have no other children.
	mgs = only_child(G, mgs)
	parts = defaultdict(list)
	for key in mgs:
		parts[0].append([key])
		parts[0][-1].extend(mgs[key])
	counter = 1
	while len(mgs) > 1:
		mgs = loop_avoider(G, mgs)
		mgs = merge_mgs(G, mgs)
		mgs = only_child(G, mgs)
		if len(mgs) < num_mgs:
			break
		for key in mgs:
			parts[counter].append([key])
			parts[counter][-1].extend(mgs[key])
		counter += 1
		if len(mgs) == num_mgs and large_or_small == 'small':
			break
	return parts[len(parts)-1]

def check_if_loads_in_tree(G, pairs):
	nodes_list = list(G.nodes())
	loads_in_tree = []
	nodes_not_in_tree = []
	for node in pairs:
		if node in nodes_list:
			loads_in_tree.append(node)
		else:
			nodes_not_in_tree.append(node)
	return loads_in_tree, nodes_not_in_tree

def load_grouping(G, pairings):
	'''Accepts loads paired to each microgrid and uses networkx to infer other existing objects in that subtree of the circuit.
	Graph G cannot contain loops.'''
	# Create reference dict of lcas for each pair of two nodes.
	tree_root = list(topological_sort(G))[0]
	lcas = nx.tree_all_pairs_lowest_common_ancestor(G, root=tree_root)
	lcas = dict(lcas)
	# Iterate through each MG's loads, comparing LCAs each time to find new overall LCA.
	mgs = {}
	pairings.pop('None', None)
	for mg in pairings:
		pairs = pairings[mg]
		loads_in_tree, nodes_not_in_tree = check_if_loads_in_tree(G, pairs)
		if not loads_in_tree:
			print(f'None of the pairs are in the current tree. Skipping.')
			continue
		if nodes_not_in_tree:
			print(f'Error: the following nodes are not in current tree: {nodes_not_in_tree}.')
		if len(pairs) > 1:
			cur_lca = lcas.get((pairs[0],pairs[1]),lcas.get((pairs[1],pairs[0])))
		elif len(pairs) == 1: # If there is only one load in a mg, use its parent as LCA. TO DO: Verify this assumption.
			cur_lca = list(G.predecessors(pairs[0]))[0]
		else:
			print('Error: Amount of loads in each microgrid must be greater than 0.')
		for idx in range(2,len(pairs)):
			cur_lca = lcas.get((cur_lca,pairs[idx]),lcas.get((pairs[idx],cur_lca)))
		mgs[mg] = list(nx.nodes(nx.dfs_tree(G, cur_lca)))
	# Only return the contents of each MG but do so in order specified by the user.
	parts = []
	counter = 0
	while mgs:
		key = f'Mg{counter}'
		if mgs.get(key):
			parts.append(mgs[key])
			del mgs[key]
		counter += 1
	return parts

def manual(pairings, gen_obs_existing):
	'''Partitioning without networkx. 
	Accepts dict of loads paired by mg and dict of gen_obs_existing paired by mg from user input.'''
	pairings.pop('None', None)
	parts = []
	for mg in pairings:
		loads = pairings[mg]
		mg_gen_obs_existing = gen_obs_existing[mg].split(',')
		parts.append(loads + mg_gen_obs_existing)
	return parts

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
	out_edges.sort()
	return out_edges

def get_edge_name(fr, to, omd_list):
	'Get an edge name using (fr,to) in the omd_list'
	edges = [ob.get('name') for ob in omd_list if ob.get('from') == fr and ob.get('to') == to]
	return None if len(edges) == 0 else edges[0]

def topological_sort(G):
	'Standardizes topological sort across networkx versions.'
	in_degree = {v: 0 for v in G}
	for u in G:
		for v in G[u]:
			in_degree[v] += 1
	queue = deque([u for u in in_degree if in_degree[u] == 0])
	result = []
	while queue:
		u = queue.popleft()
		result.append(u)
		for v in G[u]:
			in_degree[v] -= 1
			if in_degree[v] == 0:
				queue.append(v)
	if len(result) != len(G):
		raise ValueError("Graph contains a cycle")
	return result

def form_mg_mines(G, MG_GROUPS, CRITICAL_LOADS, omd, switch=None, gen_bus=None):
	'''Generate microgrid data structure from a networkx graph, group of mgs, and omd. 
	Optional parameters switch and gen_bus may be supplied when loadGrouping or manual partitioning is used.'''
	omd_list = list(omd.values())
	all_mgs = [
		(M_ID, MG_GROUP, MG_GROUP[0], nx_out_edges(G, MG_GROUP))
		for (M_ID, MG_GROUP) in enumerate([list(x) for x in MG_GROUPS])
	]
	MG_MINES = {}
	for idx in range(len(all_mgs)):
		M_ID, MG_GROUP, TREE_ROOT, BORDERS = all_mgs[idx]
		this_switch = switch[f'Mg{M_ID}'] if switch and switch[f'Mg{M_ID}'] != [''] else [get_edge_name(swedge[0], swedge[1], omd_list) for swedge in BORDERS]
		if this_switch and type(this_switch) == list:
			this_switch = this_switch[-1] if this_switch[-1] else this_switch[0] # TODO: Why is this_switch a list? Which value do we use? 
		this_gen_bus = gen_bus[f'Mg{M_ID}'] if gen_bus and gen_bus[f'Mg{M_ID}'] != '' else TREE_ROOT
		MG_MINES[f'mg{M_ID}'] = {
			'loads': [ob.get('name') for ob in omd_list if ob.get('name') in MG_GROUP and ob.get('object') == 'load'],
			'switch': this_switch, 
			'gen_bus': this_gen_bus,
			'gen_obs_existing': [ob.get('name') for ob in omd_list if ob.get('name') in MG_GROUP and ob.get('object') in ('generator','storage')],
			'critical_load_kws': [0.0 if ob.get('name') not in CRITICAL_LOADS else float(ob.get('kw','0')) for ob in omd_list if ob.get('name') in MG_GROUP and ob.get('object') == 'load'],
			'max_potential': '700', #TODO: this and other vars, how to set? Ask Matt.
			'max_potential_diesel': '1000000',
			'battery_capacity': '10000'
		}
	return MG_MINES

def form_mg_groups(G, CRITICAL_LOADS, algo, algo_params={}):
	'''Generate a group of mgs from networkx graph and crit_loads
	algo must be one of ["lukes", "branch", "bottomUp", "criticalLoads", "loadGrouping", "manual"]
	lukes algo params is 'size':int giving size of each mg.
	branch algo params is 'i_branch': giving which branch in the tree to split on.
	'''
	# Generate microgrids
	all_trees = get_all_trees(G)
	all_trees_pruned = [tree for tree in all_trees if len(tree.nodes()) > 1]
	num_trees_pruned = len(all_trees_pruned)
	MG_GROUPS = []
	for tree in all_trees_pruned:
		if algo == 'lukes':
			default_size = int(len(tree.nodes())/3)
			MG_GROUPS.extend(nx_group_lukes(tree, algo_params.get('size',default_size)))
		elif algo == 'branch':
			MG_GROUPS.extend(nx_group_branch(tree, i_branch=algo_params.get('i_branch',0)))
		elif algo == 'bottomUp':
			MG_GROUPS.extend(nx_bottom_up_branch(tree, num_mgs=algo_params.get('num_mgs',3)/num_trees_pruned, large_or_small='large', omd=algo_params.get('omd',{}), cannot_be_mg=algo_params.get('cannot_be_mg',[])))
		elif algo == 'criticalLoads':
			MG_GROUPS.extend(nx_critical_load_branch(tree, CRITICAL_LOADS, num_mgs=algo_params.get('num_mgs',3)/num_trees_pruned, large_or_small='large'))
		elif algo == 'loadGrouping':
			MG_GROUPS.extend(load_grouping(tree, algo_params['pairings']))
		elif algo == 'manual':
			MG_GROUPS.extend(manual(algo_params['pairings'], algo_params['gen_obs_existing']))
		else:
			print('Invalid algorithm. algo must be "branch", "lukes", "bottomUp", or "criticalLoads". No mgs generated.')
			return {}
	return MG_GROUPS

def _tests():
	_myDir = os.path.abspath(os.path.dirname(__file__))
	# - This is needed because these files are in the root of the Docker container and paths like "//" are invalid
	if _myDir == '/':
		_myDir = ''
	with open('testfiles/test_params.json') as file:
		test_params = json.load(file)
	MG_MINES = test_params['MG_MINES']
	algo_params = test_params['algo_params']
	crit_loads = test_params['crit_loads']
	lehigh_dss_path = f'{_myDir}/testfiles/lehigh_base_3mg.dss'
	wizard_dss_path = f'{_myDir}/testfiles/wizard_base_3mg.dss'
	# Testing microgridup_gen_mgs.mg_group().
	for _dir in MG_MINES:
		partitioning_method = MG_MINES[_dir][1]
		# HACK: loadGrouping accepts pairings but not gen_obs_existing. manual accepts both. Other algos accept neither. 
		if partitioning_method == 'loadGrouping': 
			params = algo_params.copy()
			del params['gen_obs_existing']
		elif partitioning_method == 'manual':
			params = algo_params
		else:
			params = {}
		try:
			_dir.index('wizard')
			G = opendss.dssConvert.dss_to_networkx(wizard_dss_path)
			omd = opendss.dssConvert.dssToOmd(wizard_dss_path, '', RADIUS=0.0004, write_out=False)
			MG_GROUPS_TEST = form_mg_groups(G, crit_loads, partitioning_method, params)
			MINES_TEST = form_mg_mines(G, MG_GROUPS_TEST, crit_loads, omd) if partitioning_method != 'manual' else form_mg_mines(G, MG_GROUPS_TEST, crit_loads, omd, params.get('switch'), params.get('gen_bus')) # No valid gen_bus in MG_GROUPS_TEST. When using manual partitioning, the user should specify gen_bus and switch.
		except ValueError:
			G = opendss.dssConvert.dss_to_networkx(lehigh_dss_path)
			omd = opendss.dssConvert.dssToOmd(lehigh_dss_path, '', RADIUS=0.0004, write_out=False)
			MG_GROUPS_TEST = form_mg_groups(G, crit_loads, partitioning_method, params)
			MINES_TEST = form_mg_mines(G, MG_GROUPS_TEST, crit_loads, omd, params.get('switch'), params.get('gen_bus'))
		# Lukes algorithm outputs different configuration each time. Not repeatable. Also errors out later in the MgUP run.
		if partitioning_method != 'lukes':
			assert MINES_TEST == MG_MINES[_dir][0], f'MGU_MINES_{_dir} did not match expected output.\nExpected output: {MG_MINES[_dir][0]}.\nReceived output: {MINES_TEST}.'
	return print('Ran all tests for microgridup_gen_mgs.py.')

if __name__ == '__main__':
	_tests()