import requests
import os
import cv2
import numpy as np
import onnxruntime as ort
import math
import googlemaps
import googlemaps.places as places

class coord:
    def __init__(self, lat: float, lon: float):
        self.lat = lat
        self.lon = lon
    
    def to_string(self):
        return f"{self.lat},{self.lon}"
    
class streetview:
    # Parameters for all pics 
    pic_size = "500x500"

    def __init__(self, folder_path: str):
        # Read API key 
        self.api_key = open("api_key.txt", "r").read()
        self.maps_cli = googlemaps.Client(key=self.api_key)
        
        # Set up params
        self.folder_path = folder_path

    def improve_coordinates(self, coords: coord, radius=100):
        """
        Pull Google's coordinates for a bus stop in the event that the provided coordinates suck
        """
        # Send request
        params = {
            'location': coords.to_string(),
            'radius': radius,
            'type': 'transit_station',
            'key': self.api_key,
            'maxResultCount': 1
        }
        response = self.get_response(params, 'https://maps.googleapis.com/maps/api/place/nearbysearch/json')

        results = response.json().get('results', [])
        if results:
            nearest = results[0]
            location = nearest['geometry']['location']
            return coord(location['lat'], location['lon'])
        else: 
            raise f"No nearby bus stop found for {coords.to_string()}"
    
    def get_pano_coords(self, coords: coord):
        """
        Extract coordiantes from a pano's metadata, used to determine heading
        """
        # Params for request
        params = {
            'location': coords.to_string(),
            'key': self.api_key
        }

        # Send a request, except faulty responses
        response = self.get_response(params, 'https://maps.googleapis.com/maps/api/streetview/metadata?')
        
        # Fetch the coordinates from the json response and store in a coords class instance
        pano_location = response.json().get("location")
        pano_coords = coord(pano_location["lat"], pano_location["lng"])
        return pano_coords
    
    def get_heading(self, coords: coord):
        """
        Use pano's coords to determine the necessary camera FOV.
        """
        # Determine the panorama's coords 
        pano_coords = self.get_pano_coords(coords)
        
        d_lng = math.radians(coords.lon - pano_coords.lon)
        lat1 = math.radians(pano_coords.lat)
        lat2 = math.radians(coords.lat)

        x = math.sin(d_lng) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(d_lng)
        
        initial_bearing = math.atan2(x, y)
        
        # Convert radians to degrees and normalize to 0-360 degrees
        initial_bearing = math.degrees(initial_bearing)
        compass_bearing = (initial_bearing + 360) % 360
        return compass_bearing

    def pull_image(self, coords: coord, path: str, fov=120, heading=0):
        """
        Pull an image from google streetview 
        """
        pic_params = {'key': self.api_key,
                    'location': coords.to_string(),
                    'size': self.pic_size,
                    'fov': fov,
                    'heading': heading,
                    'return_error_code': True}
            
        # Try to fetch pic from API 
        response = self.get_response(pic_params, 'https://maps.googleapis.com/maps/api/streetview?')
        
        # Make folder if it doesn't exist
        if not os.path.exists(path):
            os.makedirs(path)
        
        # Write this image segment into the temp folder
        image_path = path + "/" + f"{coords.to_string()}"+".jpg"
        with open(image_path, "wb") as file:
            file.write(response.content)

        # Close response, return new image's path
        response.close()
        return image_path

    def pull_pano(self, coords: coord, num_pics=8):
        """
        Given a dataframe of coordinates, pulls a panorama of each coordinate from Google Streetview. 
        Pulls num_pics many images and stitches them together into a panorama. 

        Args:
            stops (dataframe): All coordinates to pull images of. 
            folder_name (string): Name of the output folder
        """
        image_paths = []

        # Capture 'num_pics' many photos
        for degree in range(0, 360, int(360/num_pics)):
            # Save image into temp folder, get its path
            image_paths.append(self.pull_image(coords.lat, coords.lon, "temp", 360/num_pics, degree))
        
        # Stitch all the images of this bus stop together
        self.stitch_images(image_paths)

    def stitch_images(self, image_paths: str):
        # Load images, create stitcher 
        images = [cv2.imread(image_path) for image_path in image_paths]

        # Stitch images 
        stitched_image = np.hstack(images)

        # Remove path and degree from name lol
        name = image_paths[0].replace('_0', '_stitched')
        name = name.replace('temp/', '')
        
        # Write into correct folder
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)
        path = os.getcwd() + "/" + self.folder_path + "/" + name
        cv2.imwrite(path, stitched_image)
    
    def get_response(self, params, base):
        # Issue request 
        response = requests.get(base, params=params)

         # Check if the request was successful
        if response.status_code == 200:
            return response
        else:
            raise f"Error ({response.status_code}): {response.text}"
        
class yolo:
    # Constants
    input_shape = [1, 3, 640, 640]
    topk = 100
    iouThreshold = 0.45
    scoreThreshold = 0.2
    class_names = ["Seating", "Shelter", "Signage", "Trash Can"] 

    def run(self, image_path: str):
        # Start model sessions
        session = ort.InferenceSession("models/attempt-2.onnx")
        nms = ort.InferenceSession("models/nms-yolov8.onnx")
        
        # Read image, store dimensions
        image = cv2.imread(image_path)  
        self.original_height, self.original_width = image.shape[:2]

        # Pre-process image
        processed_image = self.preprocess_image(image)

        # Run models
        config = np.array([self.topk, self.iouThreshold, self.scoreThreshold])
        output = session.run(None, {"images": processed_image})
        selected = nms.run(None, {"detection": output[0], "config": config.astype(np.float32)})

        # Get and draw boxes on the original image size
        boxes = self.get_boxes(selected[0])
        return self.draw_boxes(boxes, image)
    
    def preprocess_image(self, image):
        height, width = image.shape[:2]

        # Calculate scaling factors to preserve the aspect ratio
        if width > height:
            scale = 640 / width
            new_width = 640
            new_height = int(height * scale)
        else:
            scale = 640 / height
            new_height = 640
            new_width = int(width * scale)

        # Resize the image while preserving the aspect ratio
        resized_image = cv2.resize(image, (new_width, new_height))

        # Calculate padding to make the image 640x640
        self.x_pad = (640 - new_width) // 2
        self.y_pad = (640 - new_height) // 2

        # Add padding
        padded_image = cv2.copyMakeBorder(
            src = resized_image, 
            top = self.y_pad, 
            bottom = 640 - new_height - self.y_pad, 
            left = self.x_pad, 
            right = 640 - new_width - self.x_pad, 
            borderType = cv2.BORDER_CONSTANT, 
            value = (114, 114, 114))

        # Normalize and prepare for model input
        padded_image = padded_image.astype(np.float32) / 255.0    # Normalize image
        padded_image = np.expand_dims(padded_image, axis=0)       # Add batch dimension
        padded_image = np.transpose(padded_image, (0, 3, 1, 2))  # Rearrange to (1, 3, 640, 640)

        # Return the preprocessed image and scaling factors for post-processing
        self.scale_x = width / new_width
        self.scale_y = height / new_height

        return padded_image
    
    def get_boxes(self, selected):
        boxes = []
        for i in range(selected.shape[1]):
            # Get rows
            data = selected[0, i, :]
            x, y, w, h = data[:4]

            # Maximum probability score and corresponding label
            scores = data[4:]
            score = np.max(scores)
            label = np.argmax(scores)

            # Convert the box coordinates from 640x640 space to the padded image space
            x1, y1 = x - w / 2, y - h / 2
            x2, y2 = x + w / 2, y + h / 2

            # Remove the padding and scale the box coordinates back to the original image size
            x1 = int((x1 - self.x_pad) * self.scale_x)
            y1 = int((y1 - self.y_pad) * self.scale_y)
            x2 = int((x2 - self.x_pad) * self.scale_x)
            y2 = int((y2 - self.y_pad) * self.scale_y)

            # Add to boxes
            boxes.append({
                "label": label, 
                "prob": score, 
                "bounds": (x1, y1, x2, y2)
            })
        
        return boxes
    
    def draw_boxes(self, boxes, image):
        final = image
        for box in boxes:
            bounds = box["bounds"]
            cv2.rectangle(final, (bounds[0], bounds[1]), (bounds[2], bounds[3]), (0, 255, 0), 2)
        
             # Display confidence and class label
            label = f"{self.class_names[box['label']]}: {box['prob']:.2f}"
            cv2.putText(final, label, (bounds[0], bounds[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        return final