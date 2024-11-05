import geopandas as gpd
import pandas as pd
import osmnx as ox
import numpy as np
from shapely.geometry import Point, LineString
from shapely.ops import nearest_points
from streetview import POI, coord

# Function to generate points at intervals along a line
def generate_points(road: LineString, interval):
    # Project line for meter-based calculations 
    road = road.to_crs("EPSG:3857")

    # Calculate how many points need to be generated
    num_points = int(road.length // interval) + 1 

    # Generate points along the line
    points = []
    for i in range(num_points):
        point = road.interpolate(interval * i )
        points.append((point.x, point.y))

    # Convert to GeoDataFrame, then project. "God I wish there was an easier way to do this"
    gdf = gpd.GeoDataFrame(points, columns=['x', 'y'])
    gdf['geometry'] = gdf.apply(lambda row: Point(row['x'], row['y']), axis=1)
    gdf = gdf.set_geometry('geometry', crs="EPSG:3857")
    gdf = gdf.to_crs("EPSG:4326")
    gdf = gpd.GeoDataFrame(geometry=points, crs="EPSG:3857")
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
    point_sf = gpd.GeoDataFrame(geometry=[Point(poi.coords.lon, poi.coords.lat)], crs="EPSG:4326")
    
    # Make a bounding box around the point 
    point_buffer = point_sf.to_crs(epsg=26916).buffer(200).to_crs("EPSG:4326")
    bbox = point_buffer.total_bounds  # [minx, miny, maxx, maxy]

    # Retrieve road data within the bounding box from OSM
    tags = {"highway": ["motorway", "trunk", "primary", "secondary", "tertiary", "residential"]}
    osm_roads = ox.features_from_bbox(bbox[3], bbox[1], bbox[2], bbox[0], tags=tags)
    road_lines = osm_roads[osm_roads.geom_type == 'LineString'].to_crs("EPSG:4326")

    # Find the nearest road to the point of interest
    nearest_road = road_lines.iloc[road_lines.sindex.nearest(point_sf.iloc[0])[1]].iloc[0]
    nearest_road = gpd.GeoSeries([nearest_road.geometry], crs="EPSG:4326")
    # Define interval and generate points along the nearest road, convert to GeoSeries
    points = generate_points(nearest_road, interval)
    # Calculate headings if there are multiple points, remove last point 
    if len(points) > 1:
        headings = calculate_headings(points.geometry)
        points = points.iloc[:-1]
        points['Heading'] = headings

    # Find the index of the point closest to the original point_sf
    distances = points.distance(point_sf.geometry.iloc[0])
    closest_index = distances.idxmin()

    # Select points 10 meters before and after the closest point
    indices = [closest_index - 1, closest_index, closest_index + 1]
    indices = [idx for idx in indices if idx >= 0 and idx < len(points)]
    selected_points = points.iloc[indices]

    # Transform point_sf to coordinates and calculate headings
    point_coords = point_sf.geometry.iloc[0].coords[0]
    selected_points['Heading_to_point_sf'] = selected_points.geometry.apply(
        lambda p: calculate_heading_between_points(point_coords[0], point_coords[1], p.x, p.y)
    )

    return selected_points