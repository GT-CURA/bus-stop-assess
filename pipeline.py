from tools import streetview, coord
import pandas as pd 

# Read MARTA's inventory of bus stops 
bus_stops = pd.read_csv("data/atl/MARTA_cleaned.csv")

# Before I forget: 
# pull coord from csv -> use nearby API to find precise coordinates of bus stop (if needed) -> 
# pull pano coord from metadata (Free!!) -> pull image from google streetview API -> stitch (if needed)

# Create test coordinates
northside = coord(33.781825, -84.407667)
#JOSEPH E LOWERY BLVD @ SELLS AVE SW
#joe = coord(33.745587, -84.417784)

# Create new instance of streetview tools
instance = streetview("test")

# Get coordiantes from google maps' nearby feature 
improved_coords = instance.improve_coordinates(northside)

# Calculate heading for this bus stop
heading = instance.get_heading(improved_coords)

# Pull image of bus stop 
instance.pull_image(improved_coords, "test", heading=heading)

# Gather all standalone bus stops
print("done")
