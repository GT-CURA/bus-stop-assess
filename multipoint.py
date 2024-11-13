import geopandas as gpd
import pandas as pd
import osmnx as ox
import numpy as np
from shapely.geometry import Point
from shapely.ops import linemerge, unary_union
from streetview import POI
from math import pi

def _generate_points(road, interval):
    """ Generates points along a line."""
    # Project line for meter-based calculations 
    road = road.to_crs("EPSG:3857")

    # Merge into one road 
    if len(road) > 1: 
        road = linemerge(unary_union(road.geometry))

    # Calculate how many points need to be generated
    num_points = int(road.length // interval) + 1 

    # Interpolate num_points many points along the line 
    interpolated_points = [road.interpolate(i*interval) for i in range(num_points)]

    # Create a GeoDataFrame to store the interpolated points, convert to coords
    gdf = gpd.GeoDataFrame(geometry=interpolated_points, crs="EPSG:3857").to_crs("EPSG:4326")
    return gdf

def calc_headings(points, original_pt):
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

    # Covnert to geoseries 
    nearest_rd = gpd.GeoSeries([nearest_rd.geometry], crs="EPSG:4326")

    # Get all of the segments of this road within the bounding box, not just one. 
    nearest_rd_all = road_lines[road_lines["name"] == nearest_rd_name]

    # Define interval and generate points along the nearest road
    points = _generate_points(nearest_rd_all, interval)

    # Find the index of the point closest to the original point
    original_pt = original_pt.to_crs("EPSG:3857")
    points = points.to_crs("EPSG:3857")
    distances = points.distance(original_pt.geometry.iloc[0], False)
    closest_index = distances.idxmin()
    points = points.to_crs("EPSG:4326")
    original_pt = original_pt.to_crs("EPSG:4326")

    # Select the closest point and the specified number of points before and after it
    start_index = max(0, closest_index - points_before)
    end_index = min(len(points), closest_index + points_after + 1)
    selected_pts = points[start_index:end_index]

    # Transform original point to coordinates and calculate headings
    headings = calc_headings(selected_pts, original_pt)

    # Convert to a dataframe
    df = pd.DataFrame(data={'heading': headings,
                            'lat': selected_pts["geometry"].y, 
                            'lon': selected_pts["geometry"].x})
    return df