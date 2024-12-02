from streetview import POI, Session
import pandas as pd
import multipoint

# Create new instances of streetview tools
sesh = Session("pics/benches_338-537", debug=True, key_path="key.txt")

# Read MARTA's inventory of bus stops 
bus_stops_atl = pd.read_csv("data/atl/MARTA_cleaned.csv")

# Select signs
benches_atl = bus_stops_atl[bus_stops_atl["Bus Stop Type"] == "Bench"]
sampled = benches_atl[338:]

def pull_row(row):
    # Build POI, improve its coordinates
    bus_stop = POI(row["Lat"], row["Lon"], row["Stop ID"])
    sesh.improve_coords(bus_stop)

    # Run multipoint tool, capture POI
    points = multipoint.get_points(bus_stop, 0, 1, 10)
    sesh.capture_POI(bus_stop, points, 35, None, (1,0))

# Pull each row in sample
sampled.apply(pull_row, axis=1)

# Write log 
sesh.write_log()
print("done")