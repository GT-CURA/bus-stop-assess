from streetview import POI, Session
import multipoint
import geojson
from models import BusStopAssess
import json
import numpy as np
from collections import defaultdict
import os 

"""
The pipeline for automatically assessing bus stop completeness  
"""

def pull_imgs(folder_path: str, geojson_path: str):
    """
    Pull an image of every bus stop from a geojson file. 
    """
    # Create new sessions of the tools we're using 
    sesh = Session(folder_path=folder_path, debug=True)
    spacer = multipoint.Autoincrement("key.txt")

    # Open geojson record of stops 
    with open(geojson_path) as f:
        stops = geojson.load(f)['features']

    # Iterate through stops
    for stop in stops:
        # Build POI
        coords = stop["geometry"]["coordinates"]
        stop_id = stop["properties"]["Stop_ID"]
        poi = POI(id=stop_id, lat=coords[1], lon=coords[0])

        # Update coords, check if it's been used
        if sesh.improve_coords(poi, True):
            # Multipoint
            spacer.determine_points(poi, (1,1), 6, 1)
            # Pull image
            sesh.capture_POI(poi, 45)

    # Once complete, write log
    sesh.write_log()

def _assess(stops, model, min_conf=.4):
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

         # Add some of the POI's info from the log 
         poi_dict = {
              'latitude': stops[id]["lat"],
              'longitude': stops[id]["lon"],
              'latitude_og': stops[id]["og_lat"],
              'longitude_og': stops[id]["og_lon"],
              'gmaps_place_name': stops[id]["place_name"],
              'amenity_scores': poi_scores 
         }

         # Add POI's results to dict
         scores[id] = poi_dict

    return scores

def make_chunks(stops, chunk_size):
    items = list(stops.items())
    for i in range(0, len(items), chunk_size):
        yield dict(items[i:i + chunk_size])

def assess(input_folder:str, output_folder:str = None, min_conf=.4, chunk_size=0):
    """
    Runs each of the images pulled from the prior step through the model, 
    generating a json file containing the likelihood 'score' of each amenity for each stop.
    Uses the log generated from the streetview pulling process to find images. 
    """
    # Open the log 
    log_path = os.path.join(input_folder, "log.json")
    with open(log_path) as f:
            stops = json.load(f)

    # Set up YOLO model 
    model = BusStopAssess(input_folder, output_folder)
    
    # Set save path to output folder if provided 
    save_path = input_folder
    if output_folder:
        save_path = output_folder

    # Only run the model on a finite number of stops bc WSL keeps crashing :(
    if not chunk_size: 
         chunk_size = len(stops)
    chunks = make_chunks(stops, chunk_size)

    # Run model on each chunk
    temp_files = []
    for i, chunk in enumerate(chunks): 
         
         # Plug this chunk into the model
         chunk_scores = _assess(chunk, model, min_conf)
         
         # Save results to a temp JSON file
         chunk_path = os.path.join(save_path, f"temp_{i}.json")
         temp_files.append(chunk_path)
         with open(chunk_path, "w") as f: 
              json.dump(chunk_scores, f, indent=2)

    # Merge all temp JSON files into one final JSON
    final_scores = {}
    for file in temp_files:
        with open(file, "r") as f:
            chunk_data = json.load(f)
            final_scores.update(chunk_data)

    # Save the final combined results
    final_path = os.path.join(save_path, "scores.json")
    with open(final_path, "w") as f:
        json.dump(final_scores, f, indent=2)

    # Delete temp JSON files
    for file in temp_files:
        os.remove(file)