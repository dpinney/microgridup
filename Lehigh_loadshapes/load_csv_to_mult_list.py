
#!/usr/bin/env python3

import codecs
import csv
import os

#Convert an excel csv with a single column of 8760 hours to a loadshape made with BOM support

#to run from command line: python3 load_csv_to_mult_list.py > output.txt

def shape_csv_to_dss_txt(in_name, out_name):
	#def csv_column_to_list(csv_file):
	with codecs.open(in_name, encoding='utf-8-sig') as f:
		rows = [row for row in csv.reader(f)]
	#convert to flat_list
	flat_list =  [item for sublist in rows for item in sublist]
	#Take away string formatting:
	loadshape = [float(hour) for hour in flat_list]
	max_load = max(loadshape)
	#convert kWH to ratio of max_load
	mult_list = [round(hour/max_load,6) for hour in loadshape]
	# print(mult_list)
	with open(out_name,'w') as outfile:
		out_data = str(mult_list).replace(' ','')
		outfile.write(out_data)

# shape_csv_to_dss_txt('hospital.csv', 'hospital.txt')

all_csv_files  = [x for x in os.listdir('.') if x.endswith('.csv')]

# print(all_csv_files)

for csv_name in all_csv_files:
	print('Processed', csv_name)
	shape_csv_to_dss_txt(csv_name, csv_name[0:-4] + '.txt')

#copy and paste output of mult_list into Lehigh.dss

#if BOm is not appearing at the first entry of the CSV, you can use for the load in:
#with open('day_load_row.csv', newline='') as csvfile:
#	list_of_lists = list(csv.reader(csvfile))