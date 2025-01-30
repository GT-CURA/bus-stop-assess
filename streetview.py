import math
import pandas as pd
from PIL import Image
from io import BytesIO
from dataclasses import dataclass, asdict
from os import makedirs, path

@dataclass
class Coord:
    """
    Represents a coordinate pair. 
    Attributes: 
        lat: Latitude coordinate as a float.
        lon: Longitude coordinate as a float.
    """
    lat: float
    lon: float

    def __repr__(self):
        return f"{self.lat},{self.lon}"

@dataclass
class Pic:
    """ Represents pictues, of which there can be multiple for a given POI. You 
    Probably don't need to interact with these. """
    pic_number: int = 0
    heading: float = None
    stitch_clock: int = 0
    stitch_counter: int = 0
    coords: Coord = None
    pano_id: str = None

    def to_dict(self):
        # Modifies the dictionary returned by asdict() to break coords into lon/lat
        dict = asdict(self)
        dict['pic_lat'] = self.coords.lat
        dict['pic_lon'] = self.coords.lon
        dict.pop('coords', None)
        return dict

class POI:
    """ A Point of Interest to capture pictures of.
    Attributes: 
        lat: Latitude of the POI 
        lon: Longitude of the POI 
        id: Some value to use as an identifier for the POI. Used for the image's name 
        keyword: The search criteria used when improving coordinates through the Maps API. 
        coord_pair: Strips the longitude and latitude from a coordinate pair
    """
    def __init__(self, lat:float, lon:float, id, keyword="bus stop"):
        # Create coord object to contain coords
        self.coords = Coord(lat, lon)

        # All other attributes
        self.id = id
        self.keyword = keyword
        self.fov: float = None
        self.errors = []
        self.pics = []
        self.original_coords = None

class Session:
    from tools import Requests, Log

    def __init__(self, folder_path: str, key_path="key.txt", pic_dims=(640, 640), 
                 debug=False, logging=True):
        # Store folder path and create it if it doesn't exist
        self.folder_path = folder_path
        if not path.exists(self.folder_path):
            makedirs(self.folder_path)

        # Set up requests session
        self.requests = self.Requests(key = open(key_path, "r").read(),
                                      debug=debug, 
                                      pic_dims=pic_dims)
        # Set up log session
        if logging: 
            self.log = self.Log(folder_path)

        # Variables
        self.debug = debug
        self.pic_dims = pic_dims
    
    def capture_POI(self, poi:POI, fov = 85, heading:float=None, stitch = (0,0)):
        """
        Capture image(s) of a POI. 
        Pass the POI into the multipoint class first if you're trying to capture multiple vantage points of the POI! 
        Args:
            poi: The POI to pull pictures of 
            fov: The field of view for all images 
            heading: The angle that the picture will be taken at, in degrees. Leave as None to automatically estimate. 
            stitch: The number of images that will be stitched to the primary one. A tuple of (num imgs to add clockwise, counterclockwise) 
        """
        # Check and update FOV 
        if 120 < fov < 10: 
            print("FOV must be between 10 and 120 degrees") 
            return
        poi.fov = fov

        # Handle multipoint capturing if the POI already has Pics
        if poi.pics:
            # Warn if heading is provided when multipointing
            if heading: 
                print("[WARNING] Inputted heading is overriden by the multipoint function!")
            
            # Capture each pic
            for pic in poi.pics: 
                self._capture_pic(pic)

        # Otherwise, build a new pic object and capture it 
        else: 
            # Build pic 
            pic = Pic(heading=heading, stitch_clock=stitch[0], stitch_counter=stitch[1], coords=poi.coords)
            
            # Estimate heading if none is provided 
            if heading == None:
                self.requests.pull_pano_info(pic)
                self._estimate_heading(pic, poi)
            
            # Pull pic 
            self._capture_pic(poi, pic)
        
        # Write this POI's entry/entries into the log 
        self.log.commit_entry(poi)

    def _capture_pic(self, poi: POI, pic: Pic):
        # Handle image stitching 
        if pic.stitch_clock or pic.stitch_counter:
            # Object to store the images in (as arrays) before stitching 
            imgs = []
            start_heading = pic.heading - (pic.stitch_counter * poi.fov)

            for i in range(pic.stitch_counter + pic.stitch_clock + 1):
                # Calculate heading for this image
                pic.heading = start_heading + i * poi.fov

                # Pull this image, check if an error occured, add to list 
                img = self.requests.pull_image(pic, poi)
                imgs.append(img)
            
            # Stitch images
            final_img = self._stitch_images(imgs)

        # Handle single image case
        else:
            # Pull image, check for errors
            img = self.requests.pull_image(pic, poi)

            # Open as PIL image
            final_img = Image.open(BytesIO(img))
        
        # Base pic name on POI ID and its number 
        image_path = f"{self.folder_path}/{poi.id}_{pic.pic_number}.jpg"

        # Save the image, add the Pic object to the POI
        final_img.save(image_path)
        poi.pics.append(pic)

    def _estimate_heading(self, pic: Pic, poi: POI):
        """
        Use pano's coords to determine the necessary camera heading.
        """
        # Convert latitude to radians, get distance between pic & POI lons in radians.  
        diff_lon = math.radians(poi.coords.lon - pic.coords.lon)
        old_lat = math.radians(pic.coords.lat)
        new_lat = math.radians(poi.coords.lat)

        # Determine degree
        x = math.sin(diff_lon) * math.cos(new_lat)
        y = math.cos(old_lat) * math.sin(new_lat) - math.sin(old_lat) * math.cos(new_lat) * math.cos(diff_lon)
        heading = math.atan2(x, y)
        
        # Convert radians to degrees, normalize
        heading = math.degrees(heading)
        heading = (heading + 360) % 360
        pic.heading = heading

    def _stitch_images(self, imgs):
        # Convert to PIL images
        pil_imgs = [Image.open(BytesIO(img_bytes)) for img_bytes in imgs]

        # Create a blank image
        stitched = Image.new('RGB', (self.pic_dims[0]*len(imgs), self.pic_dims[1]))

        # Paste each of the images onto the blank one
        x_offset = 0
        for img in pil_imgs:
            stitched.paste(img, (x_offset, 0))
            x_offset += img.width
        return stitched
    
    def improve_coords(self, poi: POI):
        """
        Pull Google's coordinates for a POI in the event that the provided coordinates suck. 
        Will use the 'nearby search' tool in the Google Maps API to find the nearest 'keyword'
        to the POI's location and update the POI's coords acoordingly (haha).  
        Args:
            poi: The point of interest that needs to have its coords improved. 
        """
        # Find nearest google maps 'business' of type keyword 
        nearest = self.requests.pull_closest(poi) 
        
        # Get the location from the results
        location = nearest['geometry']['location']

        # Update the POI 
        poi.original_coords = poi.coords
        updated_coord = Coord(location['lat'], location['lng'])
        poi.coords = updated_coord

        # Return the new coords 
        return updated_coord

    def write_log(self, name="log", delete_db=True):
        """
        Exports the SQLite log to a CSV file. Call once a session has finished, IE when done pulling images.
        Args:
            name: What the log file will be titled
            delete_db: Whether or not to delete the SQLite3 database file bc I couldn't decide if that was a good idea or not
        """
        self.log.write_log(self.folder_path, name, delete_db)
        
        # Let 'em know 
        if self.debug: print(f"Log written to {self.folder_path}/{name}")