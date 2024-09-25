import onnxruntime as ort
import cv2
import numpy as np
import onnx 

# Preprocess the image
def preprocess_image(img):
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)  # Convert to RGB
    img = cv2.resize(img, (640, 640))  # Resize to model's expected size
    img = img.astype(np.float32) / 255.0  # Normalize the image
    img = np.transpose(img, (2, 0, 1))  # Change data order from HWC to CHW
    img = np.expand_dims(img, axis=0)  # Add batch dimension
    return img

# Perform inference
def classify_image(processed_image):

    # Inputs 
    inputs = {
        "images": processed_image,
    }

    # Run inference
    output = session.run(None, inputs)
    
    # Postprocess and return the output (classification results)
    return output

def scale_boxes(boxes, original_shape):
    # Assuming original_shape is (height, width)
    height, width = original_shape
    boxes[0, :] *= width  # x center
    boxes[1, :] *= height  # y center
    boxes[2, :] *= width  # box width
    boxes[3, :] *= height  # box height
    return boxes

def draw_boxes(image, boxes, confidences, predicted_classes, class_names):
    for i in range(boxes.shape[1]):
        x_center, y_center, box_width, box_height = boxes[:, i]
        
        # Convert to corner format (x1, y1, x2, y2)
        x1 = int(x_center - box_width / 2)
        y1 = int(y_center - box_height / 2)
        x2 = int(x_center + box_width / 2)
        y2 = int(y_center + box_height / 2)
        
        # Draw rectangle around detected object
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Display confidence and class
        label = f"{class_names[predicted_classes[i]]}: {confidences[i]:.2f}"
        cv2.putText(image, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)


def process_output(array, original_image):
    # Convert to NP array and squeeze dimensions 
    array = np.squeeze(np.array(array))

    # Extract components
    boxes = array[:4, :]  # First 4 entries are bbox coordinates
    confidences = array[4, :]  # The 5th entry is object confidence
    class_scores = array[5:, :]  # The remaining are class scores (3 classes in this case)
    confidence_threshold = 0.5  # Set your confidence threshold
    indices = np.where(confidences > confidence_threshold)[0]  # Get indices of high-confidence detections

    # Filter boxes and class scores
    filtered_boxes = boxes[:, indices]
    filtered_confidences = confidences[indices]
    filtered_class_scores = class_scores[:, indices]

    # Get the class with the highest probability for each detection
    predicted_classes = np.argmax(filtered_class_scores, axis=0)
    original_shape = (640, 640)
    scaled_boxes = scale_boxes(filtered_boxes, original_shape)
    
    # Draw boxes
    class_names = ["Shelter", "Seating", "Trash Can", "Signage"] 
    draw_boxes(original_image, scaled_boxes, filtered_confidences, predicted_classes, class_names)
    return original_image

# Run 
if __name__ == "__main__":
    # Load ONNX model
    model = onnx.load("models/june-30.onnx")
    onnx.checker.check_model(model)
    
    # Start session
    session = ort.InferenceSession("models/june-30.onnx")

    # Pipeline
    image_path = "10th.png"
    original_image = cv2.imread(image_path)

    processed_image = preprocess_image(original_image)
    output = classify_image(processed_image)
    final = process_output(output, original_image)
    cv2.imwrite("output.png", final)