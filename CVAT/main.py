"""
Runs the yolov11 model I trained (best.pt) as a serverless nuclio task in CVAT. 
Used to automatically generate annotations. 
In this repo bc I don't want to fork CVAT :( 
"""

import base64
import io
import json
import yaml
from PIL import Image
import ultralytics as ua

def init_context(context):
    context.logger.info("Init context...  0%")

    # Read labels
    with open("/opt/nuclio/function.yaml", 'rb') as function_file:
        functionconfig = yaml.safe_load(function_file)
    labels_spec = functionconfig['metadata']['annotations']['spec']

    # Save labels to dict, store in context
    context.user_data.labels = {item['id']: item['name'] for item in json.loads(labels_spec)}

    # Read the model
    context.user_data.model = ua.YOLO("best.pt")
    context.logger.info("Init context...100%")


def handler(context, event):
    context.logger.info("Run YoloV11 model")

    # Load image from event, converting to PIL image
    data = event.body
    buf = io.BytesIO(base64.b64decode(data["image"]))
    image = Image.open(buf)

    # Run model
    output = context.user_data.model(image)[0].boxes

    # Iterate through each result, adding to a dictionary
    results = []
    for i in range(0, len(output.cls)):
        result = {
            "confidence": str(output.conf[i].item()),
            "label": context.user_data.labels[int(output.cls[i].item())],
            "points": output.xyxy[i, :].cpu().numpy().tolist(),
            "type": "rectangle",
        }
        results.append(result)
        context.logger.info(f"{result['label']}")

    # Send results as json in response
    return context.Response(body=json.dumps(results), headers={},
        content_type='application/json', status_code=200)
