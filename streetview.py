import requests
import math
import pandas as pd
from PIL import Image
from io import BytesIO
from dataclasses import dataclass, asdict
from os import makedirs, path, remove
import sqlite3
from csv import writer

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
class _Pic:
    """ Represents pictues, of which there can be multiple for a given POI. """
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

    def get_entry(self):
        # Represents the row corresponding to this POI in the log.
        entry = {'poi_id': self.id, 
                 'poi_lat': self.coords.lat,
                 'poi_lon': self.coords.lon,
                 'fov': self.fov, 
                 'errors': [repr(error) for error in self.errors] if self.errors else None}
        
        # Only add original coords if improve_coords was called
        if self.original_coords: 
            entry.update({
                'poi_og_lat': self.original_coords.lat, 
                'poi_og_lon': self.original_coords.lon,
            })
        
        # Accomodate multiple Pics 
        entries = []
        for pic in self.pics:
            # Copy this entry, update it with Pic details
            pic_entry = entry.copy()
            pic_entry.update(pic.to_dict())
            entries.append(pic_entry)
        
        # Return all entries
        return entries

@dataclass
class _Error:
    # I have OCD 
    context: str
    msg: str

    def __repr__(self):
        return f"{self.msg} while {self.context}. "

class Session:
    # Parameters for all pics
    pic_height = 640
    pic_len = 640

    def __init__(self, folder_path: str, debug=False, key_path="key.txt"):
        # Read API key 
        self.api_key = open(key_path, "r").read()

        # Set debug mode
        self.debug = debug

        # Store folder path and create it if it doesn't exist
        self.folder_path = folder_path
        if not path.exists(self.folder_path):
            makedirs(self.folder_path)
        
        # Set up SQLite database and create log 
        self.db_path = f"{self.folder_path}/log.db"
        self.db_connect = sqlite3.connect(self.db_path)
        self.db_cursor = self.db_connect.cursor()
        self.db_cursor.execute("""
            CREATE TABLE IF NOT EXISTS stops (
                poi_id TEXT,
                poi_lat REAL,
                poi_lon REAL,
                poi_og_lat REAL,
                poi_og_lon REAL,
                fov REAL,
                errors TEXT,
                pic_number INTEGER,
                pic_lat REAL,
                pic_lon REAL,
                heading REAL
            )
        """)
        self.db_connect.commit()
    
    def capture_POI(self, poi:POI, fov = 85, heading:float=None, stitch = (0,0)):
        """
        Main method for capturing a single image of a POI. 
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

        # Build pic 
        pic = _Pic(heading=heading, stitch_clock=stitch[0], stitch_counter=stitch[1], coords=poi.coords)

        # Estimate heading if none is provided 
        if heading == None:
            self._estimate_heading(pic, poi)
        
        # Pull pic 
        self._capture_pic(poi, pic)
        
        # Write this POI's entry/entries into the log 
        self._commit_entry(poi)
    
    def capture_multipoint(self, poi:POI, points:pd.DataFrame, estimate_heading=False,
                    fov = 85, stitch = (0,0)):
        """
        Method for capturing multiple points of a POI. Use multipoint class to get the requisite dataframe of points.
        Args:
            poi: The POI to pull pictures of
            points: A dataframe of points generated by the multipoint tool 
            estimate_heading: Automatically determines more precise headings using Streetview metadata calls. Slower than using the ones provided by multipoint.
            stitch: The number of images that will be stitched to the primary one. A tuple of (num imgs to add clockwise, counterclockwise) 
        """
        # Check and update FOV 
        if 120 < fov < 10: 
            print("FOV must be between 10 and 120 degrees") 
            return
        poi.fov = fov

        # Build and capture Pic for each row of the dataframe 
        for index, row in points.iterrows():
            # Use metadata to improve heading 
            if estimate_heading:

            pic = _Pic(index, row["heading"], stitch[0], stitch[1], Coord(row["lat"], row["lon"]))
            self._capture_pic(poi, pic)
        
        # Write this POI's entry/entries into the log 
        self._commit_entry(poi)

    def _capture_pic(self, poi: POI, pic: _Pic):
        # Handle image stitching 
        if pic.stitch_clock or pic.stitch_counter:
            # Object to store the images in (as arrays) before stitching 
            imgs = []
            start_heading = pic.heading - (pic.stitch_counter * poi.fov)

            for i in range(pic.stitch_counter + pic.stitch_clock + 1):
                # Calculate heading for this image
                heading = start_heading + i * poi.fov

                # Pull this image, check if an error occured, add to list 
                img = self._pull_image(pic, poi.fov, heading)
                if type(img) == _Error:
                    poi.errors.append(img)
                    return 
                imgs.append(img)
            
            # Stitch images
            final_img = self._stitch_images(imgs)

        # Handle single image case
        else:
            # Pull image, check for errors
            img = self._pull_image(pic, poi.fov, pic.heading)
            if type(img) == _Error:
                poi.errors.append(img)
                return 

            # Open as PIL image
            final_img = Image.open(BytesIO(img))
        
        # Base pic name on POI ID and its number 
        image_path = f"{self.folder_path}/{poi.id}_{pic.pic_number}.jpg"

        # Save the image, add the Pic object to the POI
        final_img.save(image_path)
        poi.pics.append(pic)

    def _pull_image(self, pic: _Pic, fov, heading):
        # Parameters for API request
        pic_params = {'key': self.api_key,
                        'size': f"{self.pic_len}x{self.pic_height}",
                        'fov': fov,
                        'heading': heading,
                        'return_error_code': True,
                        'outdoor': True}
        
        # Add location or coordinates
        if pic.pano_id:
            pic_params['pano'] = pic.pano_id
        else:
            pic_params['location'] = repr(pic.coords)

        # Pull response 
        response = self._pull_response(
            params = pic_params,
            context = "pulling image",
            coords = repr(pic.coords),
            base = 'https://maps.googleapis.com/maps/api/streetview?')
        
        # Check for errors 
        if type(response) == _Error: 
            return response

        # Check for empty image 
        if not response.content:
            return _Error("pulling image", "no image found")
        
        # Close response, return content 
        content = response.content
        response.close()
        return content

    def improve_coords(self, poi: POI):
        """
        Pull Google's coordinates for a POI in the event that the provided coordinates suck. 
        Will use the 'nearby search' tool in the Google Maps API to find the nearest 'keyword'
        to the POI's location and update the POI's coords acoordingly (haha).  
        Args:
            poi: The point of interest that needs to have its coords improved. 
        """
        # Build params
        params = {
            'location': repr(poi.coords),
            'keyword':poi.keyword,
            'key': self.api_key,
            'rankby':'distance',
            'maxResultCount': 1
        }
        
        # Pull a response 
        response = self._pull_response(
            params = params,
            base = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json',
            context = "pulling nearby search results",
            coords=poi.coords)
        
        # Check if request errored
        if type(response) == _Error: return
        
        # Get results from the response
        results = response.json().get('results', [])

        # Take the nearest result and use its coordinates to update the POI 
        if results:
            nearest = results[0]
            location = nearest['geometry']['location']
            poi.original_coords = poi.coords
            updated_coord = Coord(location['lat'], location['lng'])
            poi.coords = updated_coord
            return updated_coord

        # Handle no results 
        else: 
            poi.errors.append(_Error("pulling nearby search results", f"no nearby {poi.keyword} found"))
            if self.debug: print(f"No nearby {poi.keyword} found for {poi.coords}")

    def _estimate_heading(self, pic: _Pic, poi: POI):
        """
        Use pano's coords to determine the necessary camera FOV.
        """
        # Get the coordinates of the pano Google picks for this POI
        self._pull_pano_info(pic)

        # Convert latitude to radians, get distance between new & old lons in radians.  
        diff_lon = math.radians(poi.coords.lon - pic.coords.lon)
        old_lat = math.radians(pic.coords.lat)
        new_lat = math.radians(poi.coords.lat)

        # Determine degree
        x = math.sin(diff_lon) * math.cos(new_lat)
        y = math.cos(old_lat) * math.sin(new_lat) - math.sin(old_lat) * math.cos(new_lat) * math.cos(diff_lon)
    
        bearing = math.atan2(x, y)
        
        # Convert radians to degrees, normalize
        bearing = math.degrees(bearing)
        compass_bearing = (bearing + 360) % 360
        pic.heading = compass_bearing

    def _pull_pano_info(self, pic: _Pic):
        """
        Extract coordiantes from a pano's metadata, used to determine heading
        """
        # Params for request
        params = {
            'location': repr(pic.coords),
            'key': self.api_key
        }

        # Send a request
        response = self._pull_response(
            params=params,
            coords=repr(pic.coords),
            context="pulling metadata",
            base='https://maps.googleapis.com/maps/api/streetview/metadata?')
        
        # Check for errors 
        if type(response) == _Error: return 
        
        # Fetch the coordinates from the json response and store them in the POI
        pano_location = response.json().get("location")
        pic.coords = Coord(pano_location["lat"], pano_location["lng"])
        pic.pano_id = response.json().get("pano_id")
        response.close()

    def _stitch_images(self, imgs):
        # Convert to PIL images
        pil_imgs = [Image.open(BytesIO(img_bytes)) for img_bytes in imgs]

        # Create a blank image
        stitched = Image.new('RGB', (self.pic_len*len(imgs), self.pic_height))

        # Paste each of the images onto the blank one
        x_offset = 0
        for img in pil_imgs:
            stitched.paste(img, (x_offset, 0))
            x_offset += img.width
        return stitched
    
    def _commit_entry(self, poi: POI):
        """
            Uses the POI's get_entry() method to get an entry once pulled, then stores it in the database.
        """
        # POI will return multiple entries if multiple Pics were pulled
        for entry in poi.get_entry():

            # Add entry into database
            self.db_cursor.execute("""
                INSERT INTO stops (poi_id, poi_lat, poi_lon, poi_og_lat, poi_og_lon, fov, errors,
                                   pic_number, pic_lat, pic_lon, heading)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.get('poi_id'),
                entry.get('poi_lat'),
                entry.get('poi_lon'),
                entry.get('poi_og_lat'),
                entry.get('poi_og_lon'),
                entry.get('fov'),
                ",".join(entry['errors']) if entry.get('errors') else None,
                entry.get('pic_number'),
                entry.get('pic_lat'),
                entry.get('pic_lon'),
                entry.get('heading')
            ))
        self.db_connect.commit()

    def write_log(self, name="log", delete_db= True):
        """
        Exports the SQLite log to a CSV file. Call once a session has finished, IE when done pulling images.
        Args:
            name: What the log file will be titled
            delete_db: Whether or not to delete the SQLite3 database file bc I couldn't decide if that was a good idea or not
        """
        log_path = f"{self.folder_path}/{name}.csv"
        with open(log_path, "w", newline="") as csvfile:
            csv_writer = writer(csvfile)

            # Write header
            csv_writer.writerow(["poi_id", "poi_lat", "poi_lon", "poi_og_lat", "poi_og_lon",
                             "fov", "errors", "pic_number", "pic_lat", "pic_lon", "heading"])
            
            # Write data
            for row in self.db_cursor.execute("SELECT * FROM stops"):
                csv_writer.writerow(row)

        # Send msg if debugging is enabled 
        if self.debug: print(f"Log written to {log_path}")

        # Delete DB File or just close connection
        if delete_db:
            self.db_connect.close()
            remove(self.db_path)
        else: 
            self.db_connect.close()
        
    def _pull_response(self, params, context, base, coords):
        # Print a sumamry of the request if debugging 
        if self.debug: print(f"{context} for {coords}")

        # Issue request
        try:
            response = requests.get(base, params=params, timeout=10)
        
        # Catch any exceptions that are raised, return Error
        except requests.exceptions.RequestException as e:
            if self.debug: print(f"Error when {context}: {e}")
            return _Error(context, repr(e))

        # Check the request's status code 
        if response.status_code == 200:
            return response

        # Return error if the request was not successful
        else:
            response.close()
            return _Error(context, f"({response.status_code}): {response.text}")

