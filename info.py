import csv

reader = csv.DictReader(open("naaca-solar.csv", newline=""))
lots = 0
vacant = 0
solar = 0
lat = 35.174581
long = -106.533469
for row in reader:
    if float(row["CENTER_LONG"]) > long and float(row["CENTER_LAT"]) > lat:
        #print(row)
        lots = lots + 1
        if row["PROP_TYPE"] == "V":
            vacant = vacant + 1
        if row["SOLAR"] == "Y":
            solar = solar + 1
print(f"lots {lots} vacant {vacant} solar {solar}")
