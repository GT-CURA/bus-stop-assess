import geopandas as gpd
import pandas as pd
import osmnx as ox
import numpy as np
from shapely.geometry import Point
from shapely.ops import linemerge, unary_union
from streetview import POI

# Function to generate points at intervals along a line
def generate_points(road, interval):
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

# Function to calculate headings (azimuths) between consecutive coordinates
def calculate_headings(coords):
    headings = []
    for i in range(len(coords) - 1):
        delta_x = coords[i + 1].x - coords[i].x
        delta_y = coords[i + 1].y - coords[i].y
        azi = np.degrees(np.arctan2(delta_x, delta_y))
        headings.append((azi + 360) % 360)  # Normalize heading within 0-360 degrees
    return headings

# Calculate headings to point_sf from each selected point
def calculate_heading_between_points(x1, y1, x2, y2):
    azi = np.degrees(np.arctan2(x1 - x2, y1 - y2))
    return (azi + 360) % 360  # Normalize heading to 0-360 degrees

def get_points(poi: POI, interval=10):
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
    points = generate_points(nearest_rd_all, interval)

    # Calculate headings if there are multiple points, remove last point 
    if len(points) > 1:
        headings = calculate_headings(points.geometry)
        points = points.iloc[:-1]
        points['Heading'] = headings

    # Find the index of the point closest to the original point
    original_pt = original_pt.to_crs("EPSG:3857")
    points = points.to_crs("EPSG:3857")
    distances = points.distance(original_pt.geometry.iloc[0], False)
    closest_index = distances.idxmin()
    points = points.to_crs("EPSG:4326")

    # Select points 10 meters before and after the closest point
    indices = [closest_index - 1, closest_index, closest_index + 1]
    indices = [idx for idx in indices if idx >= 0 and idx < len(points)]
    selected_points = points.iloc[indices]

    # Transform point_sf to coordinates and calculate headings
    point_coords = original_pt.geometry.iloc[0].coords[0]
    selected_points['Heading_to_point_sf'] = selected_points.geometry.apply(
        lambda p: calculate_heading_between_points(point_coords[0], point_coords[1], p.x, p.y)
    )

    # Convert to a dataframe
    df = pd.DataFrame(data={'heading': selected_points["Heading_to_point_sf"],
                            'lat': selected_points["geometry"].y, 
                            'lon': selected_points["geometry"].x})
    return df