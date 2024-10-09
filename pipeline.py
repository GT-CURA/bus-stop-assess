from streetview import POI, coord, Session
from yolo import yolo
from cv2 import imwrite
import pandas as pd 

# Read MARTA's inventory of bus stops 
bus_stops = pd.read_csv("data/atl/MARTA_cleaned.csv")

# Read NYC's bus shelter inventory
bus_shelters_nyc = pd.read_csv("data/nyc/Bus_Stop_Shelter.csv")

# Select signs
shelters = bus_stops[bus_stops["Bus Stop Type"] == "Bench"]
sampled = bus_shelters_nyc[9:100]

# Create new instances of streetview tools and log
instance = Session("test/nyc", debug=True)
log_entries = []

def pull_row(row):
    # Build POI, improve its coordinates
    bus_stop = POI(row["Shelter_ID"], row["Latitude"], row["Longitude"], "bus stop")
    instance.improve_coordinates(bus_stop)

    # Get pano ID, plug it into heading function
    instance.set_heading(bus_stop)

    # Pull picture using pano ID found earlier
    instance.pull_image(bus_stop, 80)
    
    # Get log entry for this POI 
    log_entries.append(bus_stop.get_log())

# Pull each row in sample
sampled.apply(pull_row, axis=1)

# Write log 
instance.write_log()

# Gather all standalone bus stops
print("done")
