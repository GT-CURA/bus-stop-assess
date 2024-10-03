import requests
import os
import math
from cv2 import imwrite, imread
import numpy as np
import pandas as pd

class coord:
    def __init__(self, lat: float, lon: float):
        self.lat = lat
        self.lon = lon
    
    def to_string(self):
        return f"{self.lat},{self.lon}"

class tools:
    # Parameters for all pics 
    pic_size = "500x500"

    def __init__(self, folder_path: str):
        # Read API key 
        self.api_key = open("api_key.txt", "r").read()

        # Set up params
        self.folder_path = folder_path
    
    def improve_coordinates(self, coords: coord, radius=500):
        """
        Pull Google's coordinates for a bus stop in the event that the provided coordinates suck
        """
        params = {
            'location': coords.to_string(),
            'keyword':'bus stop',
            'key': self.api_key,
            'rankby':'distance',
            'maxResultCount': 1
        }
        response = self.get_response(params, 'https://maps.googleapis.com/maps/api/place/nearbysearch/json')

        results = response.json().get('results', [])
        if results:
            nearest = results[0]
            location = nearest['geometry']['location']
            return coord(location['lat'], location['lng'])
        else: 
            raise f"No nearby bus stop found for {coords.to_string()}"
    
    def pull_pano_info(self, coords: coord):
        """
        Extract coordiantes from a pano's metadata, used to determine heading
        """
        # Params for request
        params = {
            'location': coords.to_string(),
            'key': self.api_key
        }

        # Send a request, except faulty responses
        response = self.get_response(params, 'https://maps.googleapis.com/maps/api/streetview/metadata?')
        
        # Fetch the coordinates from the json response and store in a coords class instance
        pano_location = response.json().get("location")
        pano_coords = coord(pano_location["lat"], pano_location["lng"])
        pano_id = response.json().get("pano_id")
        return pano_coords, pano_id
    
    def get_heading(self, coords: coord = None, pano_coords: coord = None):
        """
        Use pano's coords to determine the necessary camera FOV.
        """
        # Convert to radians 
        diff_lon = math.radians(coords.lon - pano_coords.lon)
        lat1 = math.radians(pano_coords.lat)
        lat2 = math.radians(coords.lat)

        # Determine degree
        x = math.sin(diff_lon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(diff_lon)
    
        initial_bearing = math.atan2(x, y)
        
        # Convert radians to degrees and normalize to 0-360 degrees
        initial_bearing = math.degrees(initial_bearing)
        compass_bearing = (initial_bearing + 360) % 360
        return compass_bearing

    def pull_image(self, coords: coord, pano_ID: str, path: str, fov=120, heading=0):
        """
        Pull an image from google streetview 
        """
        # Parameters for API request
        pic_params = {'key': self.api_key,
                        'size': self.pic_size,
                        'fov': fov,
                        'heading': heading,
                        'return_error_code': True}
        
        # Add either coordinate location or pano ID depending on what's provided
        if coords:
            pic_params['location'] = coords.to_string()
            image_path = path + "/" + f"{coords.to_string()}"+".jpg"
        else: 
            pic_params['pano'] = pano_ID
            image_path = path + "/" + f"{pano_ID}"+".jpg"

        # Try to fetch pic from API 
        response = self.get_response(pic_params, 'https://maps.googleapis.com/maps/api/streetview?')
        
        # Make folder if it doesn't exist
        if not os.path.exists(path):
            os.makedirs(path)
        
        # Write this image segment into the temp folder
        with open(image_path, "wb") as file:
            file.write(response.content)

        # Close response, return new image's path
        response.close()
        return image_path

    def pull_pano(self, coords: coord, num_pics=8):
        """
        Given a dataframe of coordinates, pulls a panorama of each coordinate from Google Streetview. 
        Pulls num_pics many images and stitches them together into a panorama. 

        Args:
            stops (dataframe): All coordinates to pull images of. 
            folder_name (string): Name of the output folder
        """
        image_paths = []

        # Capture 'num_pics' many photos
        for degree in range(0, 360, int(360/num_pics)):
            # Save image into temp folder, get its path
            image_paths.append(self.pull_image(coords.lat, coords.lon, "temp", 360/num_pics, degree))
        
        # Stitch all the images of this bus stop together
        self.stitch_images(image_paths)

    def stitch_images(self, image_paths: str):
        # Load images, create stitcher 
        images = [imread(image_path) for image_path in image_paths]

        # Stitch images 
        stitched_image = np.hstack(images)

        # Remove path and degree from name lol
        name = image_paths[0].replace('_0', '_stitched')
        name = name.replace('temp/', '')
        
        # Write into correct folder
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)
        path = os.getcwd() + "/" + self.folder_path + "/" + name
        imwrite(path, stitched_image)
    
    def get_response(self, params, base):
        # Issue request 
        response = requests.get(base, params=params)

         # Check if the request was successful
        if response.status_code == 200:
            return response
        else:
            raise f"Error ({response.status_code}): {response.text}"

class log:
    entries: pd.DataFrame
    def add_entry(self, id: str, pano_id: str, pano_coords: coord,
                   original_coords: coord, updated_coords: coord, 
                   heading: int, fov:int,):
        
        # Create dictionary with inputs, put into entries
        entry = {'id': id, 'pano_id': pano_id, 'pano_coords': pano_coords, 
                 'original_coords': original_coords, 'updated_coords': updated_coords,
                 'heading': heading, 'fov':fov}
        self.entries.add(entry)
    
    def write_csv(self, path: str):
        self.entries.to_csv(path)