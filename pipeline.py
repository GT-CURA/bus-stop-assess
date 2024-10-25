from streetview import POI, coord, Session
import pandas as pd
from models import BusStopCV, yolo
import os

pics = ["sign2.png","manual.png"]
model = yolo()
model.infer(image_paths=pics)

# Read MARTA's inventory of bus stops 
bus_stops_atl = pd.read_csv("data/atl/MARTA_cleaned.csv")

# Read NYC's bus shelter inventory
bus_shelters_nyc = pd.read_csv("data/nyc.csv")

# Select signs
stops = bus_stops_atl[bus_stops_atl["Bus Stop Type"] == "Shelter"]
sampled = stops[351:400]

# Create new instances of streetview tools
instance = Session("pics/atl/shelters", debug=True)

def pull_row(row):
    # Build POI, improve its coordinates
    bus_stop = POI(row["Stop ID"], row["Lat"], row["Lon"], "bus stop")
    instance.improve_coordinates(bus_stop)

    # Get pano ID, plug it into heading function
    instance.set_heading(bus_stop)

    # Pull picture using pano ID found earlier
    instance.pull_image(bus_stop, 45)

# Pull each row in sample
sampled.apply(pull_row, axis=1)

# Write log 
instance.write_log()
print("done")