''' A quick way to calculate max load needing to be covered by diesel in an outage.
	This method assumes only solar generation and no support from battery
	to model the worst case long term outage.'''

import json
import pandas as pd
import numpy as np
import csv
from os.path import join as pJoin

def diesel_min_size(REOPT_FOLDER):
	
	with open(pJoin(REOPT_FOLDER, 'results.json')) as jsonFile:
		results = json.load(jsonFile)
	resultsSubset = results['outputs']['Scenario']['Site']
	load_df = pd.DataFrame()
	load_df['total_load'] = pd.Series(resultsSubset['LoadProfile']['year_one_electric_load_series_kw'])
	load_df['solar_gen'] = pd.Series(resultsSubset['PV']['year_one_power_production_series_kw'])
	load_df['remaining_load'] = load_df['total_load']-load_df['solar_gen']
	# max load in loadshape
	max_load = max(load_df['total_load'])
	# diesel size recommended by REopt
	diesel_REopt = resultsSubset['Generator']['size_kw']
	# diesel size needed for uninterupted power throughout the year
	diesel_uninterrupted = max(load_df['remaining_load'])
	#print(load_df)
	print("Max total load for", REOPT_FOLDER, ":", max_load)
	print("Max load needed to be supported by diesel for", REOPT_FOLDER, ":", diesel_uninterrupted)
	print("% more kW diesel needed than recommended by REopt for", REOPT_FOLDER, ":", (diesel_uninterrupted - diesel_REopt)/diesel_REopt)
	return diesel_uninterrupted

if __name__ == '__main__':
	diesel_min_size('lehigh_reopt_1')
	diesel_min_size('lehigh_reopt_2')
	diesel_min_size('lehigh_reopt_3')
	diesel_min_size('lehigh_reopt_4')