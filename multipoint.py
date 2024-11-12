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

def _calculate_headings(points):
    """ Calculates headings between consecutive coordinates."""
    headings = []
    for i in range(len(points) - 1):
        # Calculate difference between this coordinate and its neighbor
        delta_x = points[i + 1].x - points[i].x
        delta_y = points[i + 1].y - points[i].y

        # Calculate arctan2 of differences, then normalize
        azi = np.degrees(np.arctan2(delta_x, delta_y)) * (180 / pi)
        headings.append((azi + 360) % 360) 
    return headings

def _calculate_heading_between_points(x1, y1, x2, y2):
    """Calculate headings to original point from each selected point."""
    azi = np.degrees(np.arctan2(x1 - x2, y1 - y2))
    return (azi + 360) % 360 

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

    # Calculate headings if there are multiple points, remove last point 
    if len(points) > 1:
        headings = _calculate_headings(points.geometry)
        points = points.iloc[:-1]
        points['Heading'] = headings

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
    selected_points = points.iloc[start_index:end_index]

    # Transform original point to coordinates and calculate headings
    point_coords = original_pt.geometry.iloc[0].coords[0]
    headings = [_calculate_heading_between_points(point_coords[0], point_coords[1], p.x, p.y) for p in selected_points["geometry"]]

    # Convert to a dataframe
    df = pd.DataFrame(data={'heading': headings,
                            'lat': selected_points["geometry"].y, 
                            'lon': selected_points["geometry"].x})
    return df