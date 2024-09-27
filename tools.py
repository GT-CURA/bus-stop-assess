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
