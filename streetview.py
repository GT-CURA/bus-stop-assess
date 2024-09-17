import googlemaps.client
import pandas as pd
import googlemaps
import requests
import cv2
import numpy as np
import os

# Parameters for all pics 
pic_size = "500x500"
num_pics = 8
pic_base = 'https://maps.googleapis.com/maps/api/streetview?'

def pull_image(stops, folder_name, lat_name, lon_name, id_name):
    for index,row in stops.iterrows():

        # Set location to match current bus stop
        location = f"{row[lat_name]},{row[lon_name]}"
        image_paths = []

        # Capture 'num_pics' many photos
        for degree in range(0, 360, int(360/num_pics)):
            pic_params = {'key': api_key,
                    'location': location,
                    'size': pic_size,
                    'fov': 360/num_pics,
                    'heading': degree,
                    'return_error_code': True}
            
            # Try to fetch pic from API 
            try: 
                response = requests.get(pic_base, params=pic_params)
            except requests.exceptions.RequestException as e: 
                print(f"Failed to pull {row[id_name]}: {e}")
                continue 
            
            # Make temp folder to store panorama segments
            if not os.path.exists("temp"):
                os.makedirs("temp")
            
            # Write this image segment into the temp folder
            image_path = "temp" + "/" + f"{row[id_name]}" + "_" + f"{degree}" + ".jpg"
            with open(image_path, "wb") as file:
                file.write(response.content)
            
            # Add file to list of paths for this bus stop
            image_paths.append(image_path)

            # Close response
            response.close()
        
        # Stitch all the images of this bus stop together
        stitch_images(image_paths, folder_name)

def stitch_images(image_paths, folder_name):
    # Load images, create stitcher 
    images = [cv2.imread(image_path) for image_path in image_paths]

    # Stitch images 
    stitched_image = np.hstack(images)

    # Remove path and degree from name lol
    name = image_paths[0].replace('_0', '_stitched')
    name = name.replace('temp/', '')
    
    # Write into correct folder
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    path = os.getcwd() + "/" + folder_name + "/" + name
    cv2.imwrite(path, stitched_image)

if __name__ == "__main__":
    # Read API key 
    api_key = open("api_key.txt", "r").read()
    gmaps = googlemaps.Client(key=api_key)
