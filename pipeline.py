from tools import streetview, coord
import pandas as pd 

# Read MARTA's inventory of bus stops 
bus_stops = pd.read_csv("data/atl/MARTA_cleaned.csv")

# Before I forget: 
# pull coord from csv -> use nearby API to find precise coordinates of bus stop (if needed) -> 
# pull pano coord from metadata (Free!!) -> pull image from google streetview API -> stitch (if needed)

# Create test coordinates
test_coords = coord(33.781825, -84.407667)

# Create new instance of streetview tools
instance = streetview("test")

# Calculate heading for this bus stop
heading = instance.get_heading(test_coords)

# Pull image of bus stop 
instance.pull_image(test_coords, "test", heading=heading)

# Gather all standalone bus stops
standalone = bus_stops[(bus_stops["Shelter"] == "No") & (bus_stops["Seating"] != "No, there is no seating")]
