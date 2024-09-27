import googlemaps.client
import pandas as pd
import googlemaps
import requests
import os
import cv2
import numpy as np
import onnxruntime as ort

class streetview:
    # Parameters for all pics 
    pic_size = "500x500"
    num_pics = 8
    pic_base = 'https://maps.googleapis.com/maps/api/streetview?'

    def __init__(self, lat_col: str, lon_col: str, id_col: str):
        """
        Args:
            lat_col (string): Name of the column containing latitude coordinates
            lon_col (string): Name of the column containing longtitude coordinates
            id_col (string): Name of the column containing bus stop IDs """
        # Read API key 
        self.api_key = open("api_key.txt", "r").read()
        gmaps = googlemaps.Client(key=self.api_key)

        # Set up params
        self.lat_col = lat_col
        self.lon_col = lon_col
        self.id_col = id_col

    def pull_image(self, stops: pd.DataFrame, folder_name: str):
        """
        Given a dataframe of coordinates, pulls a panorama of each coordinate from Google Streetview. 
        Pulls num_pics many images and stitches them together into a panorama. 

        Args:
            stops (dataframe): All coordinates to pull images of. 
            folder_name (string): Name of the output folder
        """

        # Iterate through each row in dataframe
        for index,row in stops.iterrows():

            # Set location to match current bus stop
            location = f"{row[self.lat_col]},{row[self.lon_col]}"
            image_paths = []

            # Capture 'num_pics' many photos
            for degree in range(0, 360, int(360/self.num_pics)):
                pic_params = {'key': self.api_key,
                        'location': location,
                        'size': self.pic_size,
                        'fov': 360/self.num_pics,
                        'heading': degree,
                        'return_error_code': True}
                
                # Try to fetch pic from API 
                try: 
                    response = requests.get(self.pic_base, params=pic_params)
                except requests.exceptions.RequestException as e: 
                    print(f"Failed to pull {row[self.id_col]}: {e}")
                    continue 
                
                # Make temp folder to store panorama segments
                if not os.path.exists("temp"):
                    os.makedirs("temp")
                
                # Write this image segment into the temp folder
                image_path = "temp" + "/" + f"{row[self.id_col]}" + "_" + f"{degree}" + ".jpg"
                with open(image_path, "wb") as file:
                    file.write(response.content)
                
                # Add file to list of paths for this bus stop
                image_paths.append(image_path)

                # Close response
                response.close()
            
            # Stitch all the images of this bus stop together
            self.stitch_images(image_paths, folder_name)

    def stitch_images(self, image_paths, folder_name):
        # Load images, create stitcher 
        images = [cv2.imread(image_path) for image_path in image_paths]

        # Stitch images 
        stitched_image = np.hstack(images)

        # Remove path and degree from name lol
        name = image_paths[0].replace('_0', '_stitched')
        name = name.replace('temp/', '')
        
        # Write into correct folder
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
        path = os.getcwd() + "/" + folder_name + "/" + name
        cv2.imwrite(path, stitched_image)
        
class yolo:
    # Constants
    input_shape = [1, 3, 640, 640]
    topk = 100
    iouThreshold = 0.45
    scoreThreshold = 0.2
    class_names = ["Seating", "Shelter", "Signage", "Trash Can"] 

    def run(self, image_path):
        # Start model 
        session = ort.InferenceSession("models/attempt-2.onnx")
        nms = ort.InferenceSession("models/nms-yolov8.onnx")
        
        image = cv2.imread(image_path) # Read into CV
        self.original_height = image.shape[0]
        self.original_width = image.shape[1]

        processed_image = self.preprocess_image(image) # Pre-process image

        # Run model 
        config = np.array([self.topk, self.iouThreshold, self.scoreThreshold])
        output = session.run(None, {"images": processed_image})
        selected = nms.run(None, {"detection": output[0], "config": config.astype(np.float32)})
        
        # Draw boxes
        boxes = self.get_boxes(selected[0])
        return self.draw_boxes(boxes, image)
    
    def preprocess_image(self, image):
        image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
        width, height = image.shape[0], image.shape[1]
        max_dim = max(height, width)
        
        # Determine padding for x and y 
        x_pad = max_dim - width
        self.x_ratio = max_dim / width
        y_pad = max_dim - height
        self.y_ratio = max_dim / height

        self.scale_x = width / 640
        self.scale_y = height / 640

        # image = cv2.copyMakeBorder(image, 0, y_pad, 0, x_pad, cv2.BORDER_CONSTANT) # Add padding
        image = image.astype(np.float32) / 255.0    # Normalize image
        image = cv2.resize(image, (640, 640))   # Resize image
        image = np.expand_dims(image, axis=0)   # Expand dimensions
        image = np.transpose(image, (0, 3, 1, 2))
        return image
    
    def get_boxes(self, selected):
        boxes = []
        for i in range(selected.shape[1]):
            # Get rows
            data = selected[0,i,:]
            x, y, w, h = data[:4]
            # Naximum probability score
            scores = data[4:]
            score = np.max(scores)
            label = np.argmax(scores)

            # Calculate box coordinates
            x1, y1 = x - w / 2, y - h / 2
            x2, y2 = x + w / 2, y + h / 2

            # Scale coordinates to match dimensions of original image
            x1 = int(x1 * self.scale_x)
            y1 = int(y1 * self.scale_y)
            x2 = int(x2 * self.scale_x)
            y2 = int(y2 * self.scale_y)

            # Add to boxes
            boxes.append({
                "label": label, 
                "prob": score, 
                "bounds": (int(x1), int(y1), int(x2), int(y2))
            })
        
        return boxes
    
    def draw_boxes(self, boxes, image):
        final = image
        for box in boxes:
            bounds = box["bounds"]
            cv2.rectangle(final, (bounds[0], bounds[1]), (bounds[2], bounds[3]), (0, 255, 0), 2)
        
             # Display confidence and class
            label = f"{self.class_names[box['label']]}: {box['prob']:.2f}"
            cv2.putText(final, label, (bounds[0], bounds[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        return final
        