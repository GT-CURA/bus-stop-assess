import googlemaps.client
import pandas as pd
import googlemaps
import requests
import os
from cv2 import imread, imwrite
from numpy import hstack

class streetview:
    # Parameters for all pics 
    pic_size = "500x500"
    num_pics = 8
    pic_base = 'https://maps.googleapis.com/maps/api/streetview?'

    def __init__(self, lat_col: str, lon_col: str, id_col: str):
        """
        Args:
            lat_col (string): Name of the column containing latitude coordinates
            lon_col (string): Name of the column containing longtitude coordinates
            id_col (string): Name of the column containing bus stop IDs """
        # Read API key 
        self.api_key = open("api_key.txt", "r").read()
        gmaps = googlemaps.Client(key=self.api_key)

        # Set up params
        self.lat_col = lat_col
        self.lon_col = lon_col
        self.id_col = id_col

    def pull_image(self, stops: pd.DataFrame, folder_name: str):
        """
        Given a dataframe of coordinates, pulls a panorama of each coordinate from Google Streetview. 
        Pulls num_pics many images and stitches them together into a panorama. 

        Args:
            stops (dataframe): All coordinates to pull images of. 
            folder_name (string): Name of the output folder
        """

        # Iterate through each row in dataframe
        for index,row in stops.iterrows():

            # Set location to match current bus stop
            location = f"{row[self.lat_col]},{row[self.lon_col]}"
            image_paths = []

            # Capture 'num_pics' many photos
            for degree in range(0, 360, int(360/self.num_pics)):
                pic_params = {'key': self.api_key,
                        'location': location,
                        'size': self.pic_size,
                        'fov': 360/self.num_pics,
                        'heading': degree,
                        'return_error_code': True}
                
                # Try to fetch pic from API 
                try: 
                    response = requests.get(self.pic_base, params=pic_params)
                except requests.exceptions.RequestException as e: 
                    print(f"Failed to pull {row[self.id_col]}: {e}")
                    continue 
                
                # Make temp folder to store panorama segments
                if not os.path.exists("temp"):
                    os.makedirs("temp")
                
                # Write this image segment into the temp folder
                image_path = "temp" + "/" + f"{row[self.id_col]}" + "_" + f"{degree}" + ".jpg"
                with open(image_path, "wb") as file:
                    file.write(response.content)
                
                # Add file to list of paths for this bus stop
                image_paths.append(image_path)

                # Close response
                response.close()
            
            # Stitch all the images of this bus stop together
            self.stitch_images(image_paths, folder_name)

    def stitch_images(self, image_paths, folder_name):
        # Load images, create stitcher 
        images = [imread(image_path) for image_path in image_paths]

        # Stitch images 
        stitched_image = hstack(images)

        # Remove path and degree from name lol
        name = image_paths[0].replace('_0', '_stitched')
        name = name.replace('temp/', '')
        
        # Write into correct folder
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
        path = os.getcwd() + "/" + folder_name + "/" + name
        imwrite(path, stitched_image)