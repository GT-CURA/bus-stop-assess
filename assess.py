from streetview import POI, Session
import multipoint
import geojson
from models import BusStopAssess

"""
The pipeline for automatically assessing bus stop completeness  
"""

def pull_imgs():
    # Create new sessions of the tools we're using 
    sesh = Session(folder_path="pics/atl_study_area/27_150", debug=True)
    spacer = multipoint.Autoincrement("key.txt")

    with open("data/atl/All_Stops_In_Bounds.json") as f:
        stops = geojson.load(f)['features']

    # Iterate through stops
    for i in range(26, 150):
        # Fetch stop at this index
        stop = stops.__getitem__(i)
        # Build POI
        coords = stop["geometry"]["coordinates"]
        stop_id = stop["properties"]["MARTA_Inventory_Within.Stop_ID"]
        poi = POI(id=stop_id, lat=coords[1], lon=coords[0])

        # Update coords, check if it's been used
        if sesh.improve_coords(poi, True):
            # Multipoint
            spacer.determine_points(poi, (1,1), 6, 1)
            # Pull image
            sesh.capture_POI(poi, 45)

        sesh.write_log()

# Go through the folder and 
def assess():
    model = BusStopAssess()
    results = model.infer_log("pics/atl_study_area/first_26", output_folder="pics/atl_study_area/first_output")

    
    print("pause")
assess()