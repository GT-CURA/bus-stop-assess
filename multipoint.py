import geopandas as gpd
import osmnx as ox
import numpy as np
from shapely.geometry import Point
from shapely.ops import linemerge, unary_union, transform
from pyproj import Transformer
from streetview import POI, Pic, Coord
import math
from tools import Error

def _get_road(poi: POI, original_pt):
    """ Finds the road that the POI most likely sits on. Has to stitch multiple segments together. """
    # Make a bounding box around the point 
    point_buffer = original_pt.to_crs(epsg=26916).buffer(200).to_crs("EPSG:4326")
    bbox = point_buffer.total_bounds

    # Retrieve road data within the bounding box from OSM
    tags = {"highway": ["motorway", "trunk", "primary", "secondary", "tertiary", "residential"]}
    osm_roads = ox.features_from_bbox(bbox, tags)
    road_lines = osm_roads[osm_roads.geom_type == 'LineString'].to_crs("EPSG:4326")

    # Find the nearest road to the point of interest
    nearest_rd = road_lines.iloc[road_lines.sindex.nearest(original_pt.iloc[0])[1]].iloc[0]
    nearest_rd_name = nearest_rd.get("name")

    # Get all of the segments of this road within the bounding box, not just one. 
    if type(nearest_rd_name) == str:
        nearest_rd_all = road_lines[road_lines["name"] == nearest_rd_name]
    # Sometimes roads lack a name. Try the tiger base name 
    elif type(nearest_rd.get("tiger:name_base")) == str: 
        nearest_rd_all = road_lines[road_lines["tiger:name_base"] == nearest_rd.get("tiger:name_base")]
    else:
        poi.errors.append(Error("attempting to run multipoint", "couldnt find adjacent road"))
        return None

    # Project line for meter-based calculations 
    nearest_rd_all = nearest_rd_all.to_crs("EPSG:3857")

    # Merge into one road
    if len(nearest_rd_all) > 1: 
        road = linemerge(unary_union(nearest_rd_all.geometry))
    else: 
        # Convert the one road segment to Linestring to prevent annoying errors 
        road = nearest_rd_all.geometry.iloc[0]

    return road 
    
def _generate_points(road, interval, main_pt, num_pts):
    """ Generates points along a linestring (road). """
    # Project point for meter-based calculations 
    main_pt = main_pt.to_crs("EPSG:3857")

    # Project the point onto the road, then get distance to this point
    main_pt_projected = road.interpolate(road.project(main_pt.geometry.iloc[0]))
    start_distance = road.project(main_pt_projected)

    # Iterate through the specified number of points, calculating distance and then interpolating onto road
    points = []
    for i in range(-num_pts[0], num_pts[1] + 1):
        # Calculate distance that this point should be from the main one. 
        distance = start_distance + i * interval 
        # Round to zero or max road length so that the resulting point doesn't surpass the road
        distance = max(0, min(distance, road.length))
        # Interpolate point onto road 
        points.append(road.interpolate(distance))

    # Create a GeoDataFrame to store the interpolated points
    gdf = gpd.GeoDataFrame(geometry=points, crs="EPSG:3857")
    return gdf

def _calc_headings(points, original_pt):
    """ Calculates headings ST every point's heading is directed at POI. """
    # Get coords from original point
    original_x, original_y = original_pt.geometry.iloc[0].coords[0]

    # Find distance between points 
    x_diff = np.array(points["geometry"].x) - original_x
    y_diff = np.array(points["geometry"].y) - original_y

    # Find arctan2 of distance
    headings = np.arctan2(y_diff, x_diff) * (180 / math.pi)

    # Normalize 
    normed_headings = (headings + 180) % 360
    return normed_headings

def get_points(poi: POI, num_points=(0,0), interval=15):
    """ Gets a DataFrame of nearest points along the closest road to the POI along with headings facing towards the POI.
        Includes the 'main point', IE the one directly in front of the POI, plus the number specified before and after.
        Args: 
            poi: The point of interest around which points will be located 
            num_points: The number of points before and after the main point in the format of (before, after)
            interval: The distance between each point in meters.
    """
    # Make POI's coords into a geodataframe 
    original_pt = gpd.GeoDataFrame(geometry=[Point(poi.coords.lon, poi.coords.lat)], crs="EPSG:4326")

    # Find the road that this POI sits on
    nearest_road = _get_road(poi, original_pt)

    # Define interval and generate points along the nearest road
    points = _generate_points(nearest_road, interval, original_pt, num_points)
    
    # Convert back to coordinate form to calculate headings
    points = points.to_crs("EPSG:4326")
    original_pt = original_pt.to_crs("EPSG:4326")

    # Calculate headings
    headings = _calc_headings(points, original_pt)

    # Convert to a dataframe
    df = pd.DataFrame(data={'heading': headings,
                            'lat': points["geometry"].y, 
                            'lon': points["geometry"].x})
    return df

class Autospacer:
    from tools import Requests

    def __init__(self, key_path:str, debug=True):
        self.requests = self.Requests(key=open(key_path, "r").read(),
                                      pic_dims=None,
                                      debug=debug)

    def _estimate_heading(self, pic: Pic, poi: POI):
        """
        Use pano's coords to determine the necessary camera heading.
        """
        # Convert latitude to radians, get distance between pic & POI lons in radians.  
        diff_lon = math.radians(poi.coords.lon - pic.coords.lon)
        old_lat = math.radians(pic.coords.lat)
        new_lat = math.radians(poi.coords.lat)

        # Determine degree bearing
        x = math.sin(diff_lon) * math.cos(new_lat)
        y = math.cos(old_lat) * math.sin(new_lat) - math.sin(old_lat) * math.cos(new_lat) * math.cos(diff_lon)
        heading = math.atan2(x, y)
        
        # Convert from radians to degrees, normalize
        heading = math.degrees(heading)
        heading = (heading + 360) % 360
        pic.heading = heading

    def _check_redundancy(self, min_dist, add_dist, panos, rd, poi:POI):
            # Calculate distance that this point should be from the main one. 
            distance = min_dist + add_dist

            # If the new distance is outside of the road adjust it and don't try again
            distance = max(0, min(distance, rd.length))
            stop_trying = False
            if distance == rd.length or distance == 0:
                stop_trying = True

            # Interpolate the point onto the road and transform it
            transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
            new_pt = rd.interpolate(distance)
            lon, lat = transformer.transform(new_pt.x, new_pt.y)

            # Create Pic object
            pic = Pic(len(panos) + 1, coords=Coord(lat, lon))

            # Pull the panorama used for these coords, check to see if pano has been used
            self.requests.pull_pano_info(pic, poi)
            if pic.pano_id not in panos:
                # Add to panos so that it won't be used again
                panos.append(pic.pano_id)
                # Calculate the heading bc why not 
                self._estimate_heading(pic, poi)
                # Add the pic to the POI, return True to break the loop
                poi.pics.append(pic)
                return True
            elif stop_trying:
                # If the pano wasn't far enough but we hit the end of the road, stop trying
                error = Error("incrementing a multipoint", "Hit end of road")
                poi.errors.append(error)
                if self.debug: print(error)
                return True
            else:
                # Keep increasing distance
                return False

    def determine_points(self, poi: POI, num_points=(0,0), min_interval=5, add_interval=1):
        """ Gets a DataFrame of nearest points along the closest road to the POI along with headings facing towards the POI.
            Includes the 'main point', IE the one directly in front of the POI, plus the number specified before and after.
            Args: 
                poi: The point of interest around which points will be located 
                num_points: The number of points before and after the main point in the format of (before, after)
                min_interval: The distance between each point in meters.
        """
        # Make POI's coords into a geodataframe 
        main_pt = gpd.GeoDataFrame(geometry=[Point(poi.coords.lon, poi.coords.lat)], crs="EPSG:4326")

        # Find the road that this POI sits on
        nearest_rd = _get_road(poi, main_pt)
        
        # Project main point onto the road
        main_pt = main_pt.to_crs("EPSG:3857")
        main_pt_projected =  nearest_rd.interpolate(nearest_rd.project(main_pt.geometry.iloc[0]))
        start_distance = nearest_rd.project(main_pt_projected)

        # Add main point to the list of panos so that future points don't override it 
        pano_ids = []
        self._check_redundancy(start_distance, 0, pano_ids, nearest_rd, poi)

        # Iterate through the points we need to add
        for i in range(-num_points[0], num_points[1] + 1):
            # Skip the main point since we already added it 
            if i==0: 
                continue

            # Add the distance necessary to reach the next point
            min_dist = start_distance + i * min_interval

            # Keep incrementing distance by inputted interval until we get a new pano
            add_dist = 0
            while self._check_redundancy(min_dist, add_dist, pano_ids, nearest_rd, poi) == False:
                add_dist += add_interval
        
        # Return the POI now that it has its pics 
        return poi