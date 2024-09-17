import googlemaps.client
import pandas as pd
import googlemaps
import requests

def pull_image(stops, folder_name):
    pic_base = 'https://maps.googleapis.com/maps/api/streetview?'

    # Iterate through entries
    for index,row in stops.iterrows():
        # Parameters to be passed into request
        location = f"{row['Stop_Lat']},{row['Stop_Lon']}"
        pic_params = {'key': api_key,
                'location': location,
                'size': "1000x500",
                'fov': 120,
                'return_error_code': 'true'}
        
        # Try to fetch pic from API 
        try: 
            response = requests.get(pic_base, params=pic_params)
        except requests.exceptions.RequestException as e: 
            print(f"Failed to pull {row['Record_ID']}: {e}")
            continue 
        
        # Write image
        file_name = f"{row['Record_ID']}"
        with open(folder_name + "/" + file_name + ".jpg", "wb") as file:
            file.write(response.content)
        
        # Close response
        response.close()
    

if __name__ == "__main__":
    # Read API key 
    api_key = open("api_key.txt", "r").read()
    gmaps = googlemaps.Client(key=api_key)

    # Read CSV into memory
    bus_stops = pd.read_csv('MARTA.csv')

    # Pull test images
    entry = bus_stops[(bus_stops["Record_ID"] == 573) | (bus_stops["Record_ID"] == 1205) ]
    pull_image(entry, "Test")