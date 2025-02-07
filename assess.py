from streetview import POI, Session, Pic
from services import Error
import multipoint
import geojson
from models import BusStopAssess
import json
import numpy as np
from collections import defaultdict

"""
The pipeline for automatically assessing bus stop completeness  
"""

def pull_imgs():
    # Create new sessions of the tools we're using 
    sesh = Session(folder_path="pics/atl_study_area/test", debug=True)
    spacer = multipoint.Autoincrement("key.txt")

    with open("data/atl/All_Stops_In_Bounds.json") as f:
        stops = geojson.load(f)['features']

    # Iterate through stops
    for i in range(1, 3):
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

def assess(input_folder:str, output_folder:str = None, min_conf=.4):
    # Set up YOLO model and get its classes 
    model = BusStopAssess(input_folder, output_folder)

    # Open folder with log
    with open(f"{input_folder}/log.json") as f:
            stops = json.load(f)

    # Run the model on the entire folder
    output = model.infer_log(stops, False, min_conf)

    # Iterate through each POI, scoring likelihood of category being present
    scores = {}
    for id in output:
         
         # Each POI has a dict of labels
         poi_output = output[id]
         poi_scores = defaultdict()

         # Go through each class 
         for label in poi_output:
              
              # See if this label was detected 
              if label in poi_output:
                   # See how many pics this label was found in. Finding it in multiple pics gives big % boost 
                   num_pics = len(poi_output[label])

                   # Find the highest conf for each pic, sum them 
                   label_sum = np.sum([np.max(confs) for confs in poi_output[label]])

                   # Total score is the sum of predictions over number of pics, times log function of # pic occurences
                   total_score = (1 - np.exp(-num_pics)) * (label_sum / num_pics)

                   # Add to this label in the dict
                   poi_scores[label] = total_score

         # Add POI's results to dict
         scores[id] = poi_scores

    # Save in output if requested 
    save_path = f"{input_folder}/scores.json"
    if output_folder:
        save_path = f"{output_folder}/scores.json"

    with open(save_path, "w") as outfile: 
        json.dump(scores, outfile)
    return scores

def get_coords():
    sesh = Session(folder_path="pics/atl_study_area/test", debug=True)

    with open("data/atl/All_Stops_In_Bounds.json") as f:
        stops = geojson.load(f)['features']

    for i in range(347,501):
        # Build POI, get new coords
        stop = stops.__getitem__(i)
        coords = stop["geometry"]["coordinates"]
        stop_id = stop["properties"]["MARTA_Inventory_Within.Stop_ID"]
        poi = POI(id=stop_id, lat=coords[1], lon=coords[0])
        poi.errors.append(Error("while pulling images", "log didn't save."))
        sesh.improve_coords(poi)

        # Add PICs
        for i in range(3):
            pic = Pic(i+1)
            poi.pics.append(pic)

        # Write fucking entry
        sesh.log.commit_entry(poi)

    sesh.write_log()

# Run stuff
# pull_imgs()
scores = assess("pics/atl_study_area/200_to_500")
print("test")
