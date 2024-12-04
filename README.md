# Bus Stop Assess 
A program for automatically determining what accomodations are present at bus stops (seating, shelter, etc.). Includes tools used to create the dataset, such as pulling images from Google Streetview, automatically annotating images using previous iterations of the model, and cropping images based on annotations.
Fall 2024 GRA project for the Center for Spatial Analtyics and Visualization at Georgia Tech.
Part of a broader research project on creating an index for street "completeness."  

## Contents 
### Google Streetview Tools 
 - streetview.py: contains tools for pulling images from Google Streetivew. 
 - multipoint.py: used to determine multiple coordinates for pulling images of a POI in Streetivew. Automatically determines headings.
 - pipeline.py: example usage of tools.

### Other Tools 
 - autocrop.py: Crops annotated (YOLOv8 format) images based on position of bounding boxes. 
 - models.py: Runs the University of Washington Makeability Lab's BusStopCV model. Also a wrapper for Ultralytic's YOLO package. I stopped updating this.  
 - CVAT/: A containerized Nuclio task that runs my model, used for automatic annotation in CVAT.  

### Bus Stop Datasets 
 - Locations of bus stops from ATL, NYC, SF, St. Louis. Refer to data_sources.md for more information. 

### Misc. 
 - plot.ipynb: Used for visualizing and troubleshooting the multipoint features.
 - runs/: Previous versions of the model and their stats. 
 