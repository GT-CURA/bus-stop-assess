from tools import streetview
import pandas as pd 

# Read MARTA's inventory of bus stops 
bus_stops = pd.read_csv("data/MARTA_cleaned.csv")

# 
"""
# Create instance
instance = streetview("Stop_Lat", "Stop_Lon", "Stop_ID")

# Test of streetview tools 
test_stops = bus_stops[bus_stops["Main_Street_or_Station"] == "ALABAMA ST"]
instance.pull_image(stops=test_stops, folder_name="Alabama")

# Gather all standalone bus stops
standalone = bus_stops[(bus_stops["Shelter"] == "No") & (bus_stops["Seating"] != "No, there is no seating")]
"""