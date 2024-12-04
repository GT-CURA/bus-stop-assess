import os 
from dataclasses import dataclass
from cv2 import imread, imwrite
import numpy as np

@dataclass 
class Box:
    # Image dimensions 
    img_w: int 
    img_h: int 

    # Class of box 
    label: int 

    # Yolo boundaries
    center_x: float
    center_y: float
    box_w: float
    box_h: float

    def to_pixels(self):
        # Convert from YOLO format to pixels
        center_x = self.center_x * self.img_w
        center_y = self.center_y * self.img_h
        box_width = self.box_w * self.img_w
        box_height = self.box_h * self.img_h
        
        # Calculate the top-left and bottom-right corners of the bounding box
        self.x1 = int(center_x - box_width / 2)
        self.y1 = int(center_y - box_height / 2)
        self.x2 = int(center_x + box_width / 2)
        self.y2 = int(center_y + box_height / 2)

    def fight(self, lightweight, heavyweight):
        # idk man
        return min(lightweight, self.x1), max(heavyweight, self.x2)
    
    def adjust_bounds(self, left_bound, right_bound):
        # New width of cropped image
        new_w = right_bound - left_bound

        # Adjust x coordinates relative to the cropped region
        new_x1 = self.x1 - left_bound
        new_x2 = self.x2 - left_bound

        # Convert to YOLO format 
        self.new_box_x = ((new_x1 + new_x2) / 2) / new_w
        self.new_box_y = ((self.y1 + self.y2) / 2) / self.img_h 
        self.new_width = (new_x2 - new_x1) / new_w
        self.new_box_h = self.box_h 

    
    def paste(self):
        return f"{self.label} {self.new_box_x} {self.new_box_y} {self.new_width} {self.box_h}"

def make_folder(folder_path, name):
    da_path = f"{folder_path}/{name}"
    if not os.path.exists(da_path):
        os.makedirs(da_path)
    return da_path

def run(path:str, optimal_width=640, max_width=800, min_padding=50):
    # Make cropped folder
    cropped_path = make_folder(os.path.dirname(path), f"{os.path.basename(path)}_cropped")

    # Go through folder, reading each file 
    for file_name in os.listdir(f"{path}/labels"):
        # Open image 
        image_name = file_name.replace("txt", "jpg")
        img = imread(f"{path}/images/{image_name}")
        img_h, img_w = img.shape[:2]

        boxes = []
        min_x = img_w
        max_x = 0
        # Open labels file, step through each line to read boxes
        with open(f"{path}/labels/{file_name}", 'r') as file: 
            for line in file.readlines(): 
                # Create box 
                coords = line.strip().split()
                box = Box(img_w, img_h, coords[0], 
                          float(coords[1]), float(coords[2]), float(coords[3]), float(coords[4]))

                # Convert from YOLO standard to pixel coords 
                box.to_pixels()

                # See if this box has min or max 
                min_x, max_x = box.fight(min_x, max_x)
                boxes.append(box)
        
        # See if image needs to be split
        window = max_x-min_x
        if window > max_width:
            print("uhhhhhhhhh")
        else:
            # The number of pixels to be added to accomodate padding 
            desired_space = window + min_padding*2

            # If the space needed exceeds optimal width, make sure it's less than max 
            if desired_space > optimal_width:
                margin = max(desired_space, max_width)
            # Otherwise find space needed to fill optimal width 
            else: 
                margin = optimal_width - window

            # Find new image bounds 
            left_bound = int(min_x - margin/2) 
            right_bound = int(max_x + margin/2)

            # Check if the area surpasses the width of the image, redistribute if so
            if left_bound < 0:
                right_bound += 0-left_bound
                left_bound = 0

            # Check if if the area is less than the width of the image, redistribute if so
            if right_bound > img_w:
                left_bound -= right_bound-img_w
                right_bound = img_w

            # Slice image to new bounds
            img = img[:, left_bound:right_bound]

            # Save image 
            img_path = make_folder(cropped_path, "images")
            imwrite(f"{img_path}/{image_name}", img)

            # Writes new bounds into a txt file
            label_path = make_folder(cropped_path, "labels")
            with open(f"{label_path}/{file_name}", 'w', encoding='utf-8') as file:
                for box in boxes:
                    box.adjust_bounds(left_bound, right_bound)
                    file.write(box.paste() + '\n')

run("/home/dev/src/bus-stop-assess/datasets/crop")