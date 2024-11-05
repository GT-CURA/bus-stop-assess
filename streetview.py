import requests
import os
import math
import pandas as pd
from PIL import Image
import io 

class coord:
    """
    Represents a coordinate pair. 
    Attributes: 
        lat: Latitude coordinate as a float.
        lon: Longitude coordinate as a float.
    """
    def __init__(self, lat: float, lon: float):
        self.lat = lat
        self.lon = lon
    
    def to_string(self):
        """Outputs coordinate pair as an f-string"""
        return f"{self.lat},{self.lon}"

class POI:
    pano_id: str
    pano_coords: coord
    heading: float
    fov: float
    error: str
    num_imgs = 1

    def __init__(self, id, lat: float, lon: float, key_word = "bus stop"):
        self.ID = id
        self.coords = coord(lat, lon)
        self.original_coords = self.coords
        self.key_word = key_word

    def get_entry(self):
        # Represents the row corresponding to this image in the log.
        entry = {'id': self.ID, 'num_imgs':self.num_imgs, 'pano_id': self.pano_id, 
                 'pano_lat': self.pano_coords.lat, 'pano_lon':self.pano_coords.lon, 
                 'original_lat': self.original_coords.lat, 'original_lon':self.original_coords.lon,
                 'updated_lat':self.coords.lat,'updated_lon':self.coords.lon, 
                 'heading': self.heading, 'fov':self.fov}
        return entry

class Session:
    # Parameters for all pics
    pic_height = 640
    pic_len = 640

    def __init__(self, folder_path: str, debug=False, key_path="keys/streetview.txt"):
        # Read API key 
        self.api_key = open(key_path, "r").read()

        # Set debug mode
        self.debug = debug

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
        
        # Attempt to get a response from Google Maps API 
        if self.debug: print(f"Pulling nearby search results for {poi.coords.to_string()}")
        response = self.pull_response(params, 'https://maps.googleapis.com/maps/api/place/nearbysearch/json')
        results = response.json().get('results', [])

        # Take the nearest result and use its coordinates
        if results:
            nearest = results[0]
            location = nearest['geometry']['location']
            updated_coord = coord(location['lat'], location['lng'])
            poi.coords = updated_coord

        # Handle errors
        else: 
            poi.error="Failed to update coords."
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
        if self.debug: print(f"Pulling metadata for {poi.coords.to_string()}")
        response = self.pull_response(params, 'https://maps.googleapis.com/maps/api/streetview/metadata?')
        
        # Fetch the coordinates from the json response and store them in the POI
        pano_location = response.json().get("location")
        poi.pano_coords = coord(pano_location["lat"], pano_location["lng"])
        poi.pano_id = response.json().get("pano_id")
    
    def set_heading(self, poi: POI):
        """
        Use pano's coords to determine the necessary camera FOV.
        """
        # Get the coordinates of the pano Google pics for this POI
        self.pull_pano_info(poi)

        # Convert latitude to radians, get distance between lon in radians.  
        diff_lon = math.radians(poi.coords.lon - poi.pano_coords.lon)
        lat1 = math.radians(poi.pano_coords.lat)
        lat2 = math.radians(poi.coords.lat)

        # Determine degree
        x = math.sin(diff_lon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(diff_lon)
    
        bearing = math.atan2(x, y)
        
        # Convert radians to degrees and then compass bearing
        bearing = math.degrees(bearing)
        compass_bearing = (bearing + 360) % 360
        poi.heading = compass_bearing

    def pull_image(self, poi: POI, fov=85, num_imgs=1):
        """
        Pull an image of a POI from google streetview 
        Args:
            poi: The point of interest object that you're trying to capture
            fov: The field of view for the streetview image (Google only allows up to 120 degrees)
            num_imgs: Pulls this many pictures of the POI and stitches them together. Currently must be odd bc I'm lazy. 
        """
        # Set POI's FOV
        if fov <= 120: 
            poi.fov = fov
        else:
            print("FOV Must be <= 120")
            return
        
        # Pull each images
        if num_imgs > 1:
            # Update POI 
            poi.num_imgs = num_imgs

            # Object to store the images in (as arrays) before stitching 
            imgs = []
            start_heading = poi.heading - ((num_imgs-1)/2 * fov)

            # Iterate through each value of heading, pulling images
            for i in range(num_imgs):
                heading = start_heading + i * poi.fov
                img = self.__pull_image(poi, heading)
                imgs.append(img)
            
            # Stitch images
            final_img = self.stitch_images(imgs)
        else:
            final_img = self.__pull_image(poi, poi.heading)
        
        # Add either coordinate location or pano ID depending on what's in the POI
        if poi.pano_id:
            image_path = self.folder_path + "/" + f"{poi.pano_id}"+".jpg"
        else: 
            image_path = self.folder_path + "/" + f"{poi.coords.to_string()}"+".jpg"

        # Write this image segment into the temp folder
        final_img.save(image_path)

        # Write this POI's entry into the log 
        self.log.append(poi.get_entry())

    def __pull_image(self, poi: POI, heading):
        # Parameters for API request
        pic_params = {'key': self.api_key,
                        'size': f"{self.pic_len}x{self.pic_height}",
                        'fov': poi.fov,
                        'heading': heading,
                        'return_error_code': True,
                        'outdoor': True,
                        'size':"640x640"}
        
        # Add location or coordinates
        if poi.pano_id:
            pic_params['pano'] = poi.pano_id
        else:
            pic_params['location'] = poi.coords
            
        # Try to fetch pic from API
        if self.debug: print(f"Pulling image for {poi.coords.to_string()}")
        response = self.pull_response(pic_params, 'https://maps.googleapis.com/maps/api/streetview?')

        # Close response, return content 
        content = response.content
        response.close()
        return content

    def pull_pano(self, poi: POI, num_pics=8):
        """
        Pulls num_pics many images of a POI and stitches them together into a panorama. 

        Args:
            poi: the POI that will be captured. 
            num_pics: how many pics will be captured and stitched into the pano.
        """
        poi.fov = 360/num_pics
        imgs = []

        # Capture 'num_pics' many photos
        for degree in range(0, 360, int(360/num_pics)):
            # Save image into temp folder, get its path
            poi.heading = degree
            imgs.append(self.__pull_image(poi))
        
        # Stitch all the images of this bus stop together
        pano = self.stitch_images(imgs)

        # Add either coordinate location or pano ID depending on what's in the POI
        if poi.pano_id:
            image_path = self.folder_path + "/" + f"{poi.pano_id}"+".jpg"
        else: 
            image_path = self.folder_path + "/" + f"{poi.coords.to_string()}"+".jpg"

        # Write this image segment into the temp folder
        pano.save(image_path)

    def stitch_images(self, imgs):
        # Convert to PIL images
        pil_imgs = [Image.open(io.BytesIO(img_bytes)) for img_bytes in imgs]

        # Create a blank image
        stitched = Image.new('RGB', (self.pic_len*len(imgs), self.pic_height))

        # Paste each of the images onto the blank one
        x_offset = 0
        for img in pil_imgs:
            stitched.paste(img, (x_offset, 0))
            x_offset += img.width
        return stitched
    
    def write_log(self):
        """
            Writes a CSV file with the coordinates, FOV, etc. of each POI.
            Use at the END of a session, IE when you're finished pulling images.
        """
        log_df = pd.DataFrame(self.log)
        log_path = self.folder_path + "/log.csv"
        log_df.to_csv(log_path)
        
    def pull_response(self, params, base):
        # Issue request, except timeout
        try:
            response = requests.get(base, params=params, timeout=10)
        except requests.exceptions.Timeout: 
            print(f"Request timed out!")

        # Check if the request was successful
        if response.status_code == 200:
            return response
        else:
            raise f"Error ({response.status_code}): {response.text}"

