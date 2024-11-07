from streetview import POI, Session
import pandas as pd
import multipoint

# Define a temp POI 
test = POI(id="15", lat=33.781501, lon=-84.407777)

points = multipoint.get_points(test)

# Create new instances of streetview tools
instance = Session("pics/test", debug=True)

# Read MARTA's inventory of bus stops 
bus_stops_atl = pd.read_csv("data/atl/MARTA_cleaned.csv")

# Read NYC's bus shelter inventory
bus_shelters_nyc = pd.read_csv("data/nyc.csv")

# Select signs
stops = bus_stops_atl[bus_stops_atl["Bus Stop Type"] == "Shelter"]
sampled = stops[500:502]

def pull_row(row):
    # Build POI, improve its coordinates
    bus_stop = POI(row["Stop ID"], row["Lat"], row["Lon"])
    instance.improve_coordinates(bus_stop)

    # Get pano ID, plug it into heading function
    instance.estimate_heading(bus_stop)

    # Pull picture using pano ID found earlier
    instance.pull_image(bus_stop, 45)

def pull_multipic(row):
    lat = row["lat"]
    lon = row["lon"]
    bus_stop = POI(None, lat=lat, lon=lon)
    bus_stop.heading = row["heading"]
    instance.pull_image(bus_stop)

points.apply(pull_multipic, axis=1)

# Pull each row in sample
sampled.apply(pull_row, axis=1)

# Write log 
instance.write_log()
print("done")