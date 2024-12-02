import geopandas as gpd
import pandas as pd
import osmnx as ox
import numpy as np
from shapely.geometry import Point, LineString
from shapely.ops import linemerge, unary_union
from streetview import POI
from math import pi, isnan

def _generate_points(road, interval, point, pts_before, pts_after):
    """ Generates points along a line."""
    # Project line for meter-based calculations 
    road = road.to_crs("EPSG:3857")
    point = point.to_crs("EPSG:3857")

    # Merge into one road
    if len(road) > 1: 
        road = linemerge(unary_union(road.geometry))
    
    # Convert to Linestring to prevent annoying errors 
    else: 
        road = road.geometry.iloc[0]

    # Project the point onto the road, then get distance to this point
    nearest_pt =  road.interpolate(road.project(point.geometry.iloc[0]))
    start_distance = road.project(nearest_pt)

    # Iterate through the specified number of points, calculating distance and then interpolating onto road
    points = []
    for i in range(-pts_before, pts_after + 1):
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
    # Get coords from original point
    original_x, original_y = original_pt.geometry.iloc[0].coords[0]

    # Find distance between points 
    x_diff = np.array(points["geometry"].x) - original_x
    y_diff = np.array(points["geometry"].y) - original_y

    # Find arctan2 of distance
    headings = np.arctan2(y_diff, x_diff) * (180 / pi)

    # Normalize 
    normed_headings = (headings + 180) % 360
    return normed_headings
    

def get_points(poi: POI, points_before = 0, points_after = 0, interval=15):
    """ Gets a DataFrame of nearest points along the closest road to the POI along with headings facing towards the POI. 
        Args: 
            poi: The point of interest around which points will be located 
            points_before: The number of points to be found before the closest one. 
            points_after: The number of points to be found after the closest one. 
            interval: The distance between each point in meters.
    """
    # Make point into a geodataframe 
    original_pt = gpd.GeoDataFrame(geometry=[Point(poi.coords.lon, poi.coords.lat)], crs="EPSG:4326")
    
    # Make a bounding box around the point 
    point_buffer = original_pt.to_crs(epsg=26916).buffer(200).to_crs("EPSG:4326")
    bbox = point_buffer.total_bounds

    # Retrieve road data within the bounding box from OSM
    tags = {"highway": ["motorway", "trunk", "primary", "secondary", "tertiary", "residential"]}
    osm_roads = ox.features_from_bbox(bbox[3], bbox[1], bbox[2], bbox[0], tags=tags)
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
        print(f"Multipoint errored for {poi.id}")
        return None

    # Define interval and generate points along the nearest road
    points = _generate_points(nearest_rd_all, interval, original_pt, points_before, points_after)
    
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
