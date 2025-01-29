from streetview import POI, Session
import pandas as pd
import multipoint

# Create new instances of streetview tools
sesh = Session("pics/sf", debug=True, key_path="key.txt")

# Read MARTA's inventory of bus stops 
stops_atl = pd.read_csv("data/atl/MARTA_cleaned.csv")

# Read SF's inventory of bus stops 
stops_sf = pd.read_csv("data/sf.csv")

# Select stops to pull
sampled = stops_sf[stops_sf["SHELTER"] == 1].sample(150)

def pull_row(row):
    # Build POI, improve its coordinates
    # stop = POI(row["Latitude"], row["Longitude"], row["Shelter_ID"])
    # sesh.improve_coords(stop)
    stop = POI(lat=row["LATITUDE"], lon=row["LONGITUDE"], id=row["OBJECTID"])
    # Run multipoint tool, capture POI
    points = multipoint.get_points(stop, 1, 1, 10)
    sesh.capture_POI(stop, points, 35, None, (0,1))

# Pull each row in sample
sampled.apply(pull_row, axis=1)

# Write log 
sesh.write_log()
print("done")