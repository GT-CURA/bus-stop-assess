from tools import streetview, coord, yolo
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

# Create new instance of streetview tools
instance = streetview("test")

def pull_row(row):
    # Get--then improve--cordiantes 
    coordiante = coord(row["Lat"], row["Lon"])
    improved_coords = instance.improve_coordinates(coordiante, radius=100)

    # Get pano ID, plug it into heading function
    pano_coords, pano_ID = instance.pull_pano_info(improved_coords)
    heading = instance.get_heading(improved_coords, pano_coords)

    # Pull picture using pano ID found earlier
    instance.pull_image(pano_ID=pano_ID, path="test", fov=80, heading=heading, coords=None)

# Pull each row in sample
sampled.apply(pull_row, axis=1)

# Gather all standalone bus stops
print("done")
