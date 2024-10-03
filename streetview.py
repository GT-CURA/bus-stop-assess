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

class POI:
    pano_id: str
    pano_coords: coord
    heading: float
    fov: float

    def __init__(self, id, lat: float, lon: float, key_word: str):
        self.ID = id
        self.coords = coord(lat, lon)
        self.original_coords = self.coords
        self.key_word = key_word

    def get_log(self):
        # Create dictionary with inputs, put into entries
        entry = {'id': self.ID, 'pano_id': self.pano_id, 'pano_coords': self.pano_coords.to_string, 
                 'original_coords': self.original_coords.to_string, 'updated_coords':self.coords, 
                 'heading': self.heading, 'fov':self.fov}
        return entry

class Session:
    # Parameters for all pics 
    pic_size = "500x500"

    def __init__(self, folder_path: str):
        # Read API key 
        self.api_key = open("api_key.txt", "r").read()

        # Store folder path and create it if it doesn't exist
        self.folder_path = folder_path
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)
        
        # Create log for this session, start clock
        self.log = []
    
    def improve_coordinates(self, poi: POI):
        """
        Pull Google's coordinates for a bus stop in the event that the provided coordinates suck
        """
        params = {
            'location': poi.coords.to_string(),
            'keyword':poi.key_word,
            'key': self.api_key,
            'rankby':'distance',
            'maxResultCount': 1
        }
        response = self.pull_response(params, 'https://maps.googleapis.com/maps/api/place/nearbysearch/json')

        results = response.json().get('results', [])
        if results:
            nearest = results[0]
            location = nearest['geometry']['location']
            updated_coord = coord(location['lat'], location['lng'])
            poi.coords = updated_coord

        else: 
            raise f"No nearby {poi.key_word} found for {poi.coords.to_string()}"
    
    def pull_pano_info(self, poi: POI):
        """
        Extract coordiantes from a pano's metadata, used to determine heading
        """
        # Params for request
        params = {
            'location': poi.coords.to_string(),
            'key': self.api_key
        }

        # Send a request, except faulty responses
        response = self.pull_response(params, 'https://maps.googleapis.com/maps/api/streetview/metadata?')
        
        # Fetch the coordinates from the json response and store in a coords class instance
        pano_location = response.json().get("location")
        poi.pano_coords = coord(pano_location["lat"], pano_location["lng"])
        poi.pano_id = response.json().get("pano_id")
    
    def set_heading(self, poi: POI):
        """
        Use pano's coords to determine the necessary camera FOV.
        """
        # Get the coordinates of the pano Google pics for this POI
        self.pull_pano_info(poi)

        # Convert to radians 
        diff_lon = math.radians(poi.coords.lon - poi.pano_coords.lon)
        lat1 = math.radians(poi.pano_coords.lat)
        lat2 = math.radians(poi.coords.lat)

        # Determine degree
        x = math.sin(diff_lon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(diff_lon)
    
        initial_bearing = math.atan2(x, y)
        
        # Convert radians to degrees and normalize to 0-360 degrees
        initial_bearing = math.degrees(initial_bearing)
        compass_bearing = (initial_bearing + 360) % 360
        poi.heading = compass_bearing

    def pull_image(self, poi: POI, fov: int):
        """
        Pull an image from google streetview 
        """
        # Set POI's FOV 
        poi.fov = fov

        # Parameters for API request
        pic_params = {'key': self.api_key,
                        'size': self.pic_size,
                        'fov': poi.fov,
                        'heading': poi.heading,
                        'return_error_code': True}
        
        # Add either coordinate location or pano ID depending on what's in the POI
        if poi.pano_id:
            pic_params['pano'] = poi.pano_id
            image_path = self.folder_path + "/" + f"{poi.pano_id}"+".jpg"
        else: 
            pic_params['location'] = poi.coords.to_string()
            image_path = self.folder_path + "/" + f"{poi.coords.to_string()}"+".jpg"

        # Try to fetch pic from API 
        response = self.pull_response(pic_params, 'https://maps.googleapis.com/maps/api/streetview?')
        
        # Write this image segment into the temp folder
        with open(image_path, "wb") as file:
            file.write(response.content)

        # Write this POI's log into the entries 
        self.log.append(poi.get_log())

        # Close response, return new image's path
        response.close()
        return image_path

    def pull_pano(self, poi: POI, num_pics=8):
        """
        Given a dataframe of coordinates, pulls a panorama of each coordinate from Google Streetview. 
        Pulls num_pics many images and stitches them together into a panorama. 

        Args:
            stops (dataframe): All coordinates to pull images of. 
            folder_name (string): Name of the output folder
        """
        image_paths = []
        poi.fov = 360/num_pics

        # Capture 'num_pics' many photos
        for degree in range(0, 360, int(360/num_pics)):
            # Save image into temp folder, get its path
            poi.heading = degree
            image_paths.append(self.pull_image(poi, "temp"))
        
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
    
    def write_log(self):
        log_df = pd.DataFrame(self.log)
        log_path = self.folder_path + "/log.csv"
        log_df.to_csv(log_path)
        
    def pull_response(self, params, base):
        # Issue request 
        response = requests.get(base, params=params)

         # Check if the request was successful
        if response.status_code == 200:
            return response
        else:
            raise f"Error ({response.status_code}): {response.text}"

