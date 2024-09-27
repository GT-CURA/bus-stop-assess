import onnxruntime as ort
import cv2
import numpy as np
import onnx 
import tools

if __name__ == "__main__":
    yolo = tools.yolo()
    final = yolo.run("pics/10th.png")
    cv2.imwrite("output.png", final)
    print("done")
