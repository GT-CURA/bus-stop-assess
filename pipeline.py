from streetview import POI, Session
import pandas as pd
import multipoint

# Create new instances of streetview tools
sesh = Session("pics/7m", debug=True, key_path="key.txt")

# Read MARTA's inventory of bus stops 
bus_stops_atl = pd.read_csv("data/atl/MARTA_cleaned.csv")

# Read NYC's bus shelter inventory
bus_shelters_nyc = pd.read_csv("data/nyc.csv")

# Select signs
stops = bus_stops_atl[bus_stops_atl["Bus Stop Type"] == "Shelter"]
sampled = bus_shelters_nyc[502:525]

def pull_row(row):
    # Build POI, improve its coordinates
    bus_stop = POI(row["Latitude"], row["Longitude"], row["Shelter_ID"])
    sesh.improve_coords(bus_stop)

    # Run multipoint tool, capture POI
    points = multipoint.get_points(bus_stop, 0, 1, 7)
    sesh.capture_POI(bus_stop, points, 35, None, (1,0))

# Pull each row in sample
sampled.apply(pull_row, axis=1)

# Write log 
sesh.write_log()
print("done")