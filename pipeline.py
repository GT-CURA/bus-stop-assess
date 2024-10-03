from streetview import tools, coord, POI
import yolo
from cv2 import imwrite
import pandas as pd 

# Read MARTA's inventory of bus stops 
bus_stops = pd.read_csv("data/atl/MARTA_cleaned.csv")

"""
# Before I forget: 
# pull coord from csv -> use nearby API to find precise coordinates of bus stop (if needed) -> 
# pull pano coord from metadata (Free!!) -> pull image from google streetview API -> stitch (if needed)
yolo_instance = yolo()
output = yolo_instance.run("manual_pics/sign.png")
imwrite("output/sign.png",output)
"""

# Temporary test coordinates
tenth = coord(33.781825, -84.407667) # NORTHSIDE DR @ 10th 
fourteenth = coord(33.785674, -84.407509) # NORTHSIDE DR @ 14th
joe = coord(33.745587, -84.417784) #JOSEPH E LOWERY BLVD @ SELLS AVE SW
roswell = coord(33.945827, -84.370956) # ROSWELL RD NE@SPALDING DR NE

# Select shelters
shelters = bus_stops[bus_stops["Bus Stop Type"] == "Shelter"]
sampled = shelters.sample(7)

# Create new instances of streetview tools and log
instance = tools("test")

def pull_row(row):
    # Build POI, improve its coordinates
    bus_stop = POI(row["Stop ID"], row["Lat"], row["Lon"], "bus stop")
    instance.improve_coordinates(bus_stop)

    # Get pano ID, plug it into heading function
    instance.set_heading(bus_stop)

    # Pull picture using pano ID found earlier
    instance.pull_image(bus_stop, "test/nyc")
    
# Pull each row in sample
sampled.apply(pull_row, axis=1)

# Gather all standalone bus stops
print("done")
