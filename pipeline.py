from tools import streetview, coord, yolo
from cv2 import imwrite
import pandas as pd 
"""
# Read MARTA's inventory of bus stops 
bus_stops = pd.read_csv("data/atl/MARTA_cleaned.csv")

# Before I forget: 
# pull coord from csv -> use nearby API to find precise coordinates of bus stop (if needed) -> 
# pull pano coord from metadata (Free!!) -> pull image from google streetview API -> stitch (if needed)
yolo_instance = yolo()
output = yolo_instance.run("manual_pics/sign.png")
imwrite("output/sign.png",output)
"""

# NORTHSIDE DR @ 10th 
tenth = coord(33.781825, -84.407667)

# NORTHSIDE DR @ 14th
fourteenth = coord(33.785674, -84.407509) 

#JOSEPH E LOWERY BLVD @ SELLS AVE SW
joe = coord(33.745587, -84.417784)

# ROSWELL RD NE@SPALDING DR NE
roswell = coord(33.945827, -84.370956)

# Create new instance of streetview tools
instance = streetview("test")

# Get coordiantes from google maps' nearby feature 
improved_coords = instance.improve_coordinates(roswell, radius=500)

# Calculate heading for this bus stop
heading = instance.get_heading(improved_coords)

# Pull image of bus stop 
instance.pull_image(improved_coords, "test", 60, heading=heading)

# Gather all standalone bus stops
print("done")
