from streetview import POI, Session
import multipoint
import geojson
import ultralytics

"""
The pipeline for automatically assessing bus stop completeness  
"""

def pull_imgs():
    # Create a new session of streetview 
    sesh = Session(folder_path="pics/atl_study_area/15", debug=True)

    # Load JSON of all stops within the study area 
    with open("data/atl/All_Stops_In_Bounds.json") as f:
        stops = geojson.load(f)['features']
    
    # Iterate through stops
    for stop in stops:
        # Build POI
        coords = stop["geometry"]["coordinates"]
        stop_id = stop["properties"]["MARTA_Inventory_Within.Stop_ID"]
        poi = POI(id=stop_id, lat=coords[1], lon=coords[0])
        
        # Update coords, use multipoint 
        # sesh.improve_coords(poi)
        points = multipoint.get_points(poi, 1, 1, interval=6)
        
        # Pull image
        # sesh.capture_multipoint(poi, points, 45)

    sesh.write_log()

pull_imgs()
# Go through the folder and 
def assess():
    pass