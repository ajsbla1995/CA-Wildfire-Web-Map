# CA Wildfire Tracker

## Overview
- Welcome to my CA Wildfire Tracker web map! This wildfire tracker pulls up-to-date spatial data on active California wildfires from www.CALfire.com via the API for developers. Going beyond simply giving coordinates of active fires, I wanted to provide the user with more context such as: What are the current weather forecasts for the wildfire area of interest? What landcover types are present within the active region of the fire? Can satellite imagery be updated in near-real-time to show wildfire perimeters and the extent of potential damage? 

- The end goal of this project was to create an interactive web map in Python that allowed the user to be able to select any point on the map and retrieve weather and landcover data for that point. Weather data were collected from the National Weather Service's API Points endpoint, which gives a detailed forecast for latitude, longitude coordinate pair. Landcover data were queried from Google Earth Engine via the Python API. To include interactivity, my Python code has Javascript injected when necessary.

- Satellite Imagery was queried from Google Earth Engine, and specifically uses Sentinel-2 imagery. The temporal resolution of Sentinel-2 images is ~5 days (number of days to orbit the same location), which allows us to track large fires that span weeks. 

- Lastly, to handle all the API requests and data required in this web map, a Flask web framework was used. 

## Features

- **Real-time Wildfire Data**: Displays active wildfires in California. 
- **Active and Inactive Wildfire Perimeters**: Shows updated fire perimeters to show progression and recovery of burned acreage
- **Weather Information**: Fetches current weather conditions from NOAA.
- **Land Cover Data**: Shows land cover information based on user clicks.
- **Fire Stations**: Marks the locations of fire stations across California.
- **Interactive Map**: Users can click on the map to get specific data about the selected area.
- **Customizable Layers**: Includes multiple layers as Sentinel-2 images, NDVI, and land cover types to show how fires spread and the recovery of areas affected by fires.

## Installation

### Prerequisites

- Python 3.10 or higher
- Flask
- Geopandas
- Folium
- Google Earth Engine API
- Geemap
- Other Python libraries as listed in `requirements.txt`

### Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/ajsbla1995/CA-Wildfire-Web-Map.git
   cd CA-Wildfire-Web-Map

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set-up environmental variables**
    - Make Google Earth Engine account
    - Register a service account 
    - Create and download a JSON private key file (.private-key.json) for the service account.
    - Create new file, named .env, in the project root
    

    ```bash
    touch .env
    ```

    - Create service account and google earth api key environmental variables 

    ```python
    SERVICE_ACCOUNT = "your-service-account@your-project.iam.gserviceaccount.com"
    GOOGLE_EARTH_API_KEY = "path/to/your/google_earth_api.json"
    ```

4. **Run application**
   ```bash
   python app.py
   ```

    Open your web browser and navigate to http://localhost:8000. If this port=8000 is already in use, you can update code to port=5000 in app.py

5. **Usage** 
    - Interact with the map to view active and inactive fires as well as get information on landcover and near-real-time weather and satellite data.

### License

This project is licensed under the MIT License

    ```markdown
    MIT License

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
        



