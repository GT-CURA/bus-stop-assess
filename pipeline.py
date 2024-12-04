from streetview import POI, Session
import pandas as pd
import multipoint

# Create new instances of streetview tools
sesh = Session("pics/nyc_100-500", debug=True, key_path="key.txt")

# Read MARTA's inventory of bus stops 
stops_atl = pd.read_csv("data/atl/MARTA_cleaned.csv")

# Read NYC's inventory of bus stops
stops_nyc = pd.read_csv("data/nyc.csv")

# Select category
benches_atl = stops_atl[stops_atl["Bus Stop Type"] == "Bench"]
sampled = stops_nyc[491:500]

def pull_row(row):
    # Build POI, improve its coordinates
    #stop = POI(row["Lat"], row["Lon"], row["Stop ID"])
    stop = POI(row["Latitude"], row["Longitude"], row["Shelter_ID"])
    # sesh.improve_coords(stop)

    # Run multipoint tool, capture POI
    # points = multipoint.get_points(stop, 1, 1, 10)
    # sesh.capture_POI(stop, points, 35, None)
    sesh.capture_POI(stop, None, 25, stitch=(6, 6))
    print("")

# Pull each row in sample
sampled.apply(pull_row, axis=1)

# Write log 
sesh.write_log()
print("done")