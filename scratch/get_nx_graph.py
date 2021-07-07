from omf.solvers import opendss
import networkx as nx

CIRC_FILE = '../lehigh_base_phased.dss'

G = opendss.dssConvert.dss_to_networkx(CIRC_FILE)

print(list(G.edges()))