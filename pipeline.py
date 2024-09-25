from tools import streetview
import pandas as pd 

# Read CV file 
bus_stops = pd.read_csv('MARTA_bus_stop_data.csv')

bus_stops["BUS_STOP_TYPE"].unique()

# All signs
tet = bus_stops["BUS_STOP_TYPE"].value_counts()
signs = bus_stops[(bus_stops["BUS STOP TYPE"] == "Sign Strapped to Pole") | (bus_stops["BUS STOP TYPE"] == "Sign on Post")]
# All Shelter 



"""
# Create instance
instance = streetview("Stop_Lat", "Stop_Lon", "Stop_ID")

# Test of streetview tools 
test_stops = bus_stops[bus_stops["Main_Street_or_Station"] == "ALABAMA ST"]
instance.pull_image(stops=test_stops, folder_name="Alabama")

# Gather all standalone bus stops
standalone = bus_stops[(bus_stops["Shelter"] == "No") & (bus_stops["Seating"] != "No, there is no seating")]
"""