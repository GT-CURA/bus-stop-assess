# Google Streetview Tools 
 - streetview.py: contains tools for pulling images from Google Streetivew. 
 - multipoint.py: used to determine multiple coordinates for pulling images of a POI in Streetivew. Automatically determines headings.

# Other Tools 
 - autocrop.py: Crops annotated (YOLOv8 format) images based on position of bounding boxes. 
 - models.py: Runs the University of Washington Makeability Lab's BusStopCV model. Also a wrapper for Ultralytic's YOLO package. I stopped updating this.  
 - /CVAT: A containerized Nuclio task that runs my model, used for automatic annotation in CVAT.  

# Bus Stop Datasets 
 - Locations of bus stops from ATL, NYC, SF, St. Louis. Refer to data_sources.md for more information. 

# Misc. 
 - plot.ipynb: Used for visualizing and troubleshooting the multipoint features. 
 