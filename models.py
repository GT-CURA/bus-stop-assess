import cv2
import numpy as np
import ultralytics as ua
import os
from collections import defaultdict

class BusStopAssess:
    """
    Various tools for running the project model.
    """
    def __init__(self, model_path = "models/best.pt"):
        # Set up model
        self.model = ua.YOLO(model_path)
        self.classes = self.model.names
        self.num_classes = len(self.model.names)
    
    def infer(self, image_paths=None, input_folder=None, output_folder="output"):
        """Runs the model with inputted images. Specify a folder path to infer every image in the folder."""
        # Ensure that input is provided
        if image_paths == None and input_folder == None: 
            print("No input specified")
            return 
        
        # Gather the names of each file in the folder if a folder path is specified 
        if input_folder:
            file_names = [f"{input_folder}/{file}" for file in os.listdir(input_folder)]
            image_paths=file_names

        # Run model
        results = self.model(image_paths)
        for result in results:
            # Extract the name from the result's path bc I can't think of a better way to do this
            name = result.path.rsplit('/')[-1]

            # Make sure the folder exists bc I keep forgetting to 
            self.make_folder(output_folder)

            # Save output image
            result.save(filename=f"{output_folder}/{name}")
    
    def infer_img(self, pic_num:int, poi_id:int, input_folder:str, min_conf=.6, output_folder:str=None):
        # Build path
        img_path = f"{input_folder}/{poi_id}_{pic_num}.jpg"

        # Determine path of this image and plug it into model
        output = self.model(img_path, conf=min_conf)[0]

        # Save outputted image if requested
        if output_folder:
            self.make_folder(output_folder)
            output.save(filename=f"{output_folder}/{poi_id}_{pic_num}.jpg")
        
        # Return a list of predictions
        predictions = np.zeros(6)
        for box in output.boxes:
            predictions[int(box.cls)] += float(box.conf)
        return predictions

    def infer_log(self, stops, input_folder:str, output_folder:str=None, min_conf=.6,):
        """
        When supplied with the log from a streetview capture session, will return
        the classes with confidence scores for each bus stop. Images must be in same folder as log!
        Args:
            input_folder: Folder containing BOTH the log and images.
            min_conf: Minimum confidence score required to be part of results.
            output_folder: If you want the outputted images to be saved, specify a path here. 
        """
        # It's faster to input all images at once. Get paths in disgusting embedded loop
        img_paths = []
        for id in stops:
            stop = stops[id]
            for pic in stop['pictures']:
                img_paths.append(f"{input_folder}/{id}_{pic['pic_number']}.jpg")

        # Run model on paths 
        output = self.model(img_paths, conf=min_conf)

        preds = {}
        # Iterate through output, saving predictions
        for result in output:
            # Create list for each class
            img_preds = defaultdict(list)

            # Iterate through boxes, getting classes and confidence levels
            for box in result.boxes:
                img_preds[self.classes[int(box.cls)]].append(float(box.conf))

            # Conver to numpy arrays >:(
            for i in range(self.num_classes):
                cls = self.classes[i]
                if cls in img_preds:
                    img_preds[cls] = np.array(img_preds[cls])

                # For classes with no predictions, put in empty array
                else:
                    img_preds[cls] = np.empty((0))

            # Save image if requested 
            if output_folder:
                self.make_folder(output_folder)
                output.save(filename=result.path.replace(input_folder, output_folder))
            
            # Can't think of a less stupid way to get POI numbers
            poi = result.path.split("/")[-1].split("_")[0]
            
            # Save this image's results in dict with key = its POI 
            if poi not in preds:
                preds[poi] = [img_preds]
            else:
                preds[poi].append(img_preds)

        return preds

    
    def make_folder(self, path):
        if not os.path.exists(path): 
            os.makedirs(path)
            
class BusStopCV:
    """
    Runs the University of Washington Makeability Lab's BusStopCV model.
    Didn't generalize well (failed to detect MARTA bus stops)
    https://makeabilitylab.cs.washington.edu/project/busstopcv/
    """
    # import onnxruntime as ort

    # Constants
    input_shape = [1, 3, 640, 640]
    topk = 100
    iouThreshold = 0.45
    scoreThreshold = 0.2
    class_names = ["Seating", "Shelter", "Signage", "Trash Can"] 

    def __init__(self):
        # Set up models
        self.model = self.ort.InferenceSession("models/attempt-2.onnx")
        self.nms = self.ort.InferenceSession("models/nms-yolov8.onnx")

    def infer(self, image_path: str):
        # Read image, store dimensions
        image = cv2.imread(image_path)  
        self.original_height, self.original_width = image.shape[:2]

        # Pre-process image
        processed_image = self.preprocess_image(image)

        # Run models
        config = np.array([self.topk, self.iouThreshold, self.scoreThreshold])
        output = self.model.run(None, {"images": processed_image})
        selected = self.nms.run(None, {"detection": output[0], "config": config.astype(np.float32)})

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

        # Normalize, expand dimensions, transpose
        padded_image = padded_image.astype(np.float32) / 255.0    
        padded_image = np.expand_dims(padded_image, axis=0)       
        padded_image = np.transpose(padded_image, (0, 3, 1, 2))  

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

            # Get max score and corresponding label
            scores = data[4:]
            score = np.max(scores)
            label = np.argmax(scores)

            # Convert box coordinates 
            x1, y1 = x - w / 2, y - h / 2
            x2, y2 = x + w / 2, y + h / 2

            # Remove the padding and scale the box coordinates back to the original image size
            x1 = int((x1 - self.x_pad) * self.scale_x)
            y1 = int((y1 - self.y_pad) * self.scale_y)
            x2 = int((x2 - self.x_pad) * self.scale_x)
            y2 = int((y2 - self.y_pad) * self.scale_y)

            # Add to box list
            boxes.append({
                "label": label, 
                "prob": score, 
                "bounds": (x1, y1, x2, y2)
            })
        
        return boxes
    
    def draw_boxes(self, boxes, image):
        final = image

        # Iterate through box list 
        for box in boxes:
            # Extract bounds and draw onto inputted image
            bounds = box["bounds"]
            cv2.rectangle(final, (bounds[0], bounds[1]), (bounds[2], bounds[3]), (0, 255, 0), 2)
        
             # Display confidence and class label
            label = f"{self.class_names[box['label']]}: {box['prob']:.2f}"
            cv2.putText(final, label, (bounds[0], bounds[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        return final

