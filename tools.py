"""
For sending requests 
"""
import requests
from streetview import Pic, POI, Coord
from dataclasses import dataclass

class Requests:
    def __init__(self, key: str, pic_dims, debug = False):
        self.key = key
        self.debug = debug
        if pic_dims:
            self.pic_len = pic_dims[0]
            self.pic_height = pic_dims[1]

    def pull_image(self, pic: Pic, poi: POI):
        # Parameters for API request
        pic_params = {
            'key': self.key,
            'return_error_code': True,
            'fov': poi.fov,
            'heading': pic.heading,
            'outdoor': True,
            'size': f"{self.pic_len}x{self.pic_height}"}
        
        # Add location or coordinates
        if pic.pano_id:
            pic_params['pano'] = pic.pano_id
        else:
            pic_params['location'] = repr(pic.coords)

        # Pull response 
        response = self._pull_response(
            params = pic_params,
            context = "Pulling image",
            coords = repr(pic.coords),
            base = 'https://maps.googleapis.com/maps/api/streetview?')
        
        # Handle errors
        if type(response) == Error:
            poi.errors.append(response)
            return
        
        # Close response, return content 
        content = response.content
        response.close()
        return content
    
    def pull_closest(self, poi: POI):
        # Build params
        params = {
            'key': self.key,
            'return_error_code': True,
            'location': repr(poi.coords),
            'keyword':poi.keyword,
            'rankby':'distance',
            'maxResultCount': 1
        }
        
        # Pull a response 
        response = self._pull_response(
            params = params,
            base = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json',
            context = "Pulling nearby search results",
            coords=poi.coords)
        
        # Handle errors
        if type(response) == Error:
            poi.errors.append(response)
            return
        
        # Get results from the response
        results = response.json().get('results', [])
        response.close()

        # Take the nearest result and use its coordinates to update the POI 
        if results:
            return results[0]

        # Handle no results 
        else: 
            poi.errors.append(Error("pulling nearby search results", f"no nearby {poi.keyword} found"))
            if self.debug: print(f"[ERROR] No nearby {poi.keyword} found for {poi.coords}")

    def pull_pano_info(self, pic: Pic, poi: POI):
        """
        Extract coordiantes from a pano's metadata, used to determine heading
        """
        # Params for request
        params = {
            'key': self.key,
            'return_error_code': True,
            'location': repr(pic.coords),
        }

        # Send a request
        response = self._pull_response(
            params=params,
            coords=repr(pic.coords),
            context="Pulling metadata",
            base='https://maps.googleapis.com/maps/api/streetview/metadata?')
        
        # Handle errors
        if type(response) == Error: 
            poi.errors.append(response)
            return 
        
        # Fetch the coordinates from the json response and store them in the POI
        pano_location = response.json().get("location")
        pic.coords = Coord(pano_location["lat"], pano_location["lng"])
        pic.pano_id = response.json().get("pano_id")
        response.close()

    def _pull_response(self, params, context, base, coords):
        # Print a sumamry of the request if debugging 
        if self.debug: print(f"[REQUEST] {context} for {coords}")

        # Issue request
        try:
            response = requests.get(base, params=params, timeout=10)
        
        # Catch any exceptions that are raised, return Error
        except requests.exceptions.RequestException as e:
            if self.debug: print(f"[ERROR] Got {e} when {context}!")
            return Error(context, repr(e))

        # Check the request's status code 
        if response.status_code == 200:
            return response

        # Check for empty response 
        if not response.content:
            return Error(context, "empty response")
        
        # Return error if the request was not successful
        else:
            response.close()
            return Error(context, f"({response.status_code}): {response.text}")

@dataclass
class Error:
    # I have OCD 
    context: str
    msg: str

    def __repr__(self):
        return f"{self.msg} while {self.context}."

class Log: 
    import sqlite3
    import json
    from csv import writer
    from os import remove

    def __init__(self, folder_path:str):
        # Create or connect database 
        self.db_path = f"{folder_path}/log.db"
        self.db_connect = self.sqlite3.connect(self.db_path)

        # Set up the point of interest table
        self.db_cursor = self.db_connect.cursor()
        self.db_cursor.execute("""
            CREATE TABLE IF NOT EXISTS pois (
                poi_id TEXT PRIMARY KEY,
                poi_lat REAL,
                poi_lon REAL,
                poi_og_lat REAL,
                poi_og_lon REAL,
                fov REAL,
                errors TEXT
            )
            """)

        # Set up the pic table
        self.db_cursor.execute("""
            CREATE TABLE IF NOT EXISTS pictures (
                pic_id INTEGER PRIMARY KEY AUTOINCREMENT,
                poi_id TEXT,
                pic_number INTEGER,
                pic_lat REAL,
                pic_lon REAL,
                heading REAL,
                FOREIGN KEY (poi_id) REFERENCES pois (poi_id)
            )
            """)

        self.db_connect.commit()

    def commit_entry(self, poi: POI):
        """
        Stores POI and picture data in separate relational tables.
        """
        # Insert or ignore POI data (to prevent duplicate inserts)
        self.db_cursor.execute("""
            INSERT INTO pois (poi_id, poi_lat, poi_lon, poi_og_lat, poi_og_lon, fov, errors)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(poi_id) DO UPDATE SET
            fov=excluded.fov, errors=excluded.errors
        """, (
            poi.id,
            poi.coords.lat,
            poi.coords.lon,
            poi.original_coords.lat if poi.original_coords else None,
            poi.original_coords.lon if poi.original_coords else None,
            poi.fov,
            ",".join([repr(error) for error in poi.errors]) if poi.errors else None
        ))

        # Insert entries for each of the POI's pics 
        for pic in poi.pics:
            self.db_cursor.execute("""
                INSERT INTO pictures (poi_id, pic_number, pic_lat, pic_lon, heading)
                VALUES (?, ?, ?, ?, ?)
            """, (
                poi.id,
                pic.pic_number,
                pic.coords.lat,
                pic.coords.lon,
                pic.heading
            ))

        self.db_connect.commit()

    def write_log(self, folder_path, name="log", delete_db=True):
        # Derive log 
        log_path = f"{folder_path}/{name}.json"

        # Query to fetch all POIs with their pictures
        self.db_cursor.execute("""
            SELECT pois.*, pictures.pic_number, pictures.pic_lat, pictures.pic_lon, pictures.heading
            FROM pois
            LEFT JOIN pictures ON pois.poi_id = pictures.poi_id
        """)

        rows = self.db_cursor.fetchall()
        column_names = [desc[0] for desc in self.db_cursor.description]

        # Organize data into hierarchical JSON format
        poi_dict = {}
        for row in rows:
            entry = dict(zip(column_names, row))
            poi_id = entry.pop("poi_id")

            # Ensure no redundancy, add
            if poi_id not in poi_dict:
                poi_dict[poi_id] = {
                    "poi_lat": entry.pop("poi_lat"),
                    "poi_lon": entry.pop("poi_lon"),
                    "poi_og_lat": entry.pop("poi_og_lat"),
                    "poi_og_lon": entry.pop("poi_og_lon"),
                    "fov": entry.pop("fov"),
                    "errors": entry.pop("errors").split(",") if entry.get("errors") else [],
                    "pictures": []
                }

            # If there's an associated picture, add it
            if entry["pic_number"] is not None:
                pic_entry = {
                    "pic_number": entry.pop("pic_number"),
                    "pic_lat": entry.pop("pic_lat"),
                    "pic_lon": entry.pop("pic_lon"),
                    "heading": entry.pop("heading")
                }
                poi_dict[poi_id]["pictures"].append(pic_entry)

        # Write log to JSON
        with open(log_path, "w", encoding="utf-8") as jsonfile:
            self.json.dump(poi_dict, jsonfile, indent=4)

        # Delete DB File or just close connection
        self.db_connect.close()
        if delete_db:
            self.remove(self.db_path)