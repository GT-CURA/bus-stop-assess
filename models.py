import cv2
import numpy as np
import onnxruntime as ort
import ultralytics as ua
from roboflow import Roboflow

class BusStopCV:
    """
    Runs the University of Washington Makeability Lab's BusStopCV model.
    https://makeabilitylab.cs.washington.edu/project/busstopcv/
    """
    # Constants
    input_shape = [1, 3, 640, 640]
    topk = 100
    iouThreshold = 0.45
    scoreThreshold = 0.2
    class_names = ["Seating", "Shelter", "Signage", "Trash Can"] 

    def __init__(self):
        # Set up models
        self.model = ort.InferenceSession("models/attempt-2.onnx")
        self.nms = ort.InferenceSession("models/nms-yolov8.onnx")

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

class yolo:
    """
    Wrapper for ultralytics' yolo module. 
    """
    def __init__(self, model_path = "models/best.pt"):
        # Set up model
        self.model = ua.YOLO(model_path)
    
    def infer(self, image_paths):
        # Run model
        results = self.model(image_paths)
        for result in results:
            # Extract the name from the result's path bc I can't think of a better way to do this
            name = result.path.rsplit('/')[-1]

            # Save output image
            result.save(filename=f"output/{name}")

    def train(self):
        # Check hardware & load pre-trained model from ultralytics
        #ua.checks()
        #model = ua.YOLO("models/yolo11n.pt")

        # Download dataset
        key = open("keys/roboflow.txt", "r").read()
        rf = Roboflow(api_key=key)
        project = rf.workspace("brycetjones").project("bus-stop-classification")
        version = project.version(2)
        dataset = version.download("yolov11", location="datasets")

        # Train model, use patience param to stop after 100 epochs if performance isn't increasing 
        #results = model.train(data="first/data.yaml", epochs=300, imgsz=640, patience=100)

        # Export model 
        #model.export(format="onnx")



    def to_onnx(self):
        self.model.export(format="onnx")
    
    def deploy_to_roboflow(self, model_path):
        # configure roboflow 
        key = open("keys/roboflow.txt", "r").read()
        rf = Roboflow(api_key=key)
        project = rf.workspace("brycetjones").project("bus-stop-classification")
        version = project.version(1)

        # Deploy model to roboflow
        version.deploy("yolov11", model_path, "best.pt")