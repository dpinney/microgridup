import os, json
from omf.solvers import opendss
import networkx as nx
from pprint import pprint as pp
from collections import defaultdict, deque

# Auto gen some microgrid descriptions.
# See experiments with networkx here: https://colab.research.google.com/drive/1RZyD6pRIdRAT-V2sBB0nPKVIvZP_RGHw
# New colab with updated experiments: https://colab.research.google.com/drive/1j_u30UdnhaRovtG6Odhe_ivDKwBlc5qY?usp=sharing

# Test inputs
CIRC_FILE = 'lehigh_base_3mg.dss'
CRITICAL_LOADS = ['645_hangar','684_command_center', '611_runway','675a_hospital','634a_data_center', '634b_radar', '634c_atc_tower']
ALGO = 'lukes' #'branch'
_myDir = os.path.abspath(os.path.dirname(__file__))

# Networkx helper functions
def nx_get_branches(G):
	'All branchy boys'
	return [(n,G.out_degree(n)) for n in G.nodes() if G.out_degree(n) > 1]

# Helper function to remove cycles and loops from a graph using hacky topological sort because nx_topological_sort breaks on cycles.
def remove_loops(G):
	# Delete edges to all parents except the first in topological order.
	order = []
	for k,v in nx.dfs_successors(G).items():
		if k not in order:
			order.append(k)
		for v_ in v:
			if v_ not in order:
				order.append(v_)
	for node in order: 
		parents = list(G.predecessors(node))
		if len(parents) > 1:
			ordered_parents = [x for x in order if x in parents]
			for idx in range(1,len(ordered_parents)):
				G.remove_edge(ordered_parents[idx],node)
		# Origin shouldn't have any parents. TO DO: Figure out why this sometimes breaks circuits with cycles to the source.
		# elif node == order[0] and len(parents) == 1:
			# G.remove_edge(parents[0],node)
	return G

# Used by both bottom up and critical load algorithms.
def only_child(G, mgs):
	for key in list(mgs.keys()):
		parent = list(G.predecessors(key))
		if not parent:
			continue
		if len(parent) > 1:
			continue 
		siblings = list(G.successors(parent[0]))
		while parent and len(siblings) == 1:
			mgs[parent[0]].append(siblings[0])
			mgs[parent[0]].extend(mgs[siblings[0]])
			del mgs[siblings[0]]
			parent = list(G.predecessors(parent[0]))
			if not parent or len(parent) > 1:
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

def nx_bottom_up_branch(G, num_mgs=3, large_or_small='large'):
	'Form all microgrid combinations starting with leaves and working up to source maintaining single points of connection for each.'
	try:
		list(topological_sort(G))
	except ValueError:
		G = remove_loops(G)
	# Find leaves.
	end_nodes = [[x] for x in G.nodes() if G.out_degree(x)==0 and G.in_degree(x)!=0]
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

def manual_groups(G, pairings):
	# Create reference dict of lcas for each pair of two nodes.
	tree_root = list(topological_sort(G))[0]
	lcas = nx.tree_all_pairs_lowest_common_ancestor(G, root=tree_root)
	lcas = dict(lcas)
	# Iterate through each MG's loads, comparing LCAs each time to find new overall LCA.
	mgs = {}
	pairings.pop('None', None)
	for mg in pairings:
		pairs = pairings[mg]
		cur_lca = lcas.get((pairs[0],pairs[1]),lcas.get((pairs[1],pairs[0])))
		for idx in range(2,len(pairs)):
			cur_lca = lcas.get((cur_lca,pairs[idx]),lcas.get((pairs[idx],cur_lca)))
		mgs[mg] = list(nx.nodes(nx.dfs_tree(G, cur_lca)))
	# Only return the contents of each MG but do so in order specified by the user.
	parts = []
	for idx in range(len(mgs)):
		parts.append(mgs[f'Mg{idx+1}'])
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

def mg_group(circ_path, CRITICAL_LOADS, algo, algo_params={}):
	def helper(MG_GROUPS, switch, gen_bus):
		all_mgs = [
			(M_ID, MG_GROUP, MG_GROUP[0], nx_out_edges(G, MG_GROUP))
			for (M_ID, MG_GROUP) in enumerate([list(x) for x in MG_GROUPS])
		]
		MG_MINES = {}
		for idx in range(len(all_mgs)):
			M_ID, MG_GROUP, TREE_ROOT, BORDERS = all_mgs[idx]
			this_switch = switch[f'Mg{M_ID+1}'] if switch else [get_edge_name(swedge[0], swedge[1], omd_list) for swedge in BORDERS]
			if this_switch and type(this_switch) == list:
				this_switch = this_switch[-1] if this_switch[-1] else this_switch[0] # TODO: Why is this_switch a list? Which value do we use? 
			this_gen_bus = gen_bus[f'Mg{M_ID+1}'] if gen_bus else TREE_ROOT
			MG_MINES[f'mg{M_ID}'] = {
				'loads': [ob.get('name') for ob in omd_list if ob.get('name') in MG_GROUP and ob.get('object') == 'load'],
				'switch': this_switch, 
				'gen_bus': this_gen_bus,
				'gen_obs_existing': [ob.get('name') for ob in omd_list if ob.get('name') in MG_GROUP and ob.get('object') in ('generator','pvsystem')],
				'critical_load_kws': [0.0 if ob.get('name') not in CRITICAL_LOADS else float(ob.get('kw','0')) for ob in omd_list if ob.get('name') in MG_GROUP and ob.get('object') == 'load'],
				'max_potential': '700', #TODO: this and other vars, how to set? Ask Matt.
				'max_potential_diesel': '1000000',
				'battery_capacity': '10000'
			}
		return MG_MINES
	'''Generate a group of mgs from circ_path with crit_loads
	algo must be one of ["lukes", "branch", "bottomUp", "criticalLoads"]
	lukes algo params is 'size':int giving size of each mg.
	branch algo params is 'i_branch': giving which branch in the tree to split on.'''
	# Load data
	G = opendss.dssConvert.dss_to_networkx(circ_path)
	omd = opendss.dssConvert.dssToOmd(circ_path, None, write_out=False)
	omd_list = list(omd.values())
	# Generate microgrids
	switch, gen_bus = None, None
	if algo == 'lukes':
		default_size = int(len(G.nodes())/3)
		MG_GROUPS = nx_group_lukes(G, algo_params.get('size',default_size))
	elif algo == 'branch':
		MG_GROUPS = nx_group_branch(G, i_branch=algo_params.get('i_branch',0))
	elif algo == 'bottomUp':
		MG_GROUPS = nx_bottom_up_branch(G, num_mgs=algo_params.get('num_mgs',3), large_or_small='large')
	elif algo == 'criticalLoads':
		MG_GROUPS = nx_critical_load_branch(G, CRITICAL_LOADS, num_mgs=algo_params.get('num_mgs',3), large_or_small='large')
	elif algo == 'loadGrouping':
		MG_GROUPS = manual_groups(G, algo_params)
	elif algo == 'manual':
		MG_GROUPS = manual_groups(G, algo_params['pairings'])
		switch = algo_params['switch']
		gen_bus = algo_params['gen_bus']
	else:
		print('Invalid algorithm. algo must be "branch", "lukes", "bottomUp", or "criticalLoads". No mgs generated.')
		return {}
	MG_MINES = helper(MG_GROUPS, switch, gen_bus)
	return MG_MINES

def colorby_mgs(mg_group_dictionary):
	''' generate a colorby CSV/JSON that works with omf.geo map interface.
	To use, set omd['attachments'] = function JSON output'''
	attachments_keys = {
		"coloringFiles": {
			"microgridColoring.csv": {
				"csv": "<content>",
				"colorOnLoadColumnIndex": "1" 
			}
		}
	}
	mg_keys = mg_group_dictionary.keys()
	color_step = float(1/len(mg_keys))
	output_csv = 'bus,color\n'
	for i, mg_key in enumerate(mg_group_dictionary):
		my_color = i * color_step
		mg_ob = mg_group_dictionary[mg_key]
		all_items = mg_ob['loads'] + mg_ob['gen_obs_existing'] + [mg_ob['gen_bus']]
		# TODO: find all buses in the interior of the microgrid and add them to the list.
		# TODO: also find new generation objects
		# TODO: also  make all other objects gray or something.
		for item in all_items:
			output_csv += item + ',' + str(my_color) + '\n'
	attachments_keys['coloringFiles']['microgridColoring.csv']['csv'] = output_csv
	return attachments_keys

def _tests():
	with open('testfiles/test_params.json') as file:
		test_params = json.load(file)
	MG_MINES = test_params['MG_MINES']
	algo_params = test_params['algo_params']
	crit_loads = test_params['crit_loads']
	# Testing microgridup_gen_mgs.mg_group().
	for _dir in MG_MINES:
		if MG_MINES[_dir][1] == 'manual':
			params = algo_params
		else:
			params = algo_params['pairings']
		MINES_TEST = mg_group(f'{_myDir}/uploads/BASE_DSS_{_dir}', crit_loads, MG_MINES[_dir][1], params)
		# Lukes algorithm outputs different configuration each time. Not repeatable. Also errors out later in the MgUP run.
		if MG_MINES[_dir][1] != 'lukes':
			assert MINES_TEST == MG_MINES[_dir][0], f'MGU_MINES_{_dir} did not match expected output.\nExpected output: {MG_MINES[_dir][0]}.\nReceived output: {MINES_TEST}.'
	return print('Ran all tests for microgridup_gen_mgs.py.')

if __name__ == '__main__':
	_tests()