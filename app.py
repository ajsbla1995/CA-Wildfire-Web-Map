# Import all libraries
import geopandas as gpd
import pandas as pd
import folium
from folium import Element
import ee      # Google Earth Engine API
import geemap
import json
import pycrs
from geopy.geocoders import Nominatim
import requests
import re
import googlemaps
from math import radians, sin, cos, sqrt, atan2       # Haversine Formula, closest points
import networkx as nx
import time
from IPython.display import HTML
from jinja2 import Template
from folium import plugins
from folium.plugins import GroupedLayerControl
from datetime import datetime
from branca.element import Template, MacroElement  # for Legend on map
from IPython.display import HTML
import requests
from bs4 import BeautifulSoup
import create_wildfire_map as wildfire
from flask import Flask, render_template, request, jsonify, make_response
from flask_cors import CORS, cross_origin # Import CORS from flask_cors
from dotenv import load_dotenv
from flask_caching import Cache
import os
from shapely import wkt
from shapely.geometry import Polygon
from shapely.geometry import box
from shapely.geometry import shape
import matplotlib.pyplot as plt
import numpy as np
import glob
import geojson
import osmnx as ox
import logging


app = Flask(__name__)
CORS(app) # enable CORS


# Get directory path and set working directory 
calfire_geospatial_path = os.path.dirname(os.path.abspath(__file__)) 

# Load environmental variables
#load_dotenv(dotenv_path='/home/ajsbla/API_keys/.env') # Use for public deployment (directory where .env and GEE_API_key.json exist on pythonanywhere account)
#load_dotenv()                                              # Use this for local development

# Load Google Earth Engine API key and service account credentials
API_key_json = os.getenv('GOOGLE_EARTH_API_KEY') 
service_account = os.getenv('SERVICE_ACCOUNT')


# Configure Flask-Caching
cache = Cache(config={'CACHE_TYPE': 'simple'})
cache.init_app(app)


# ------------------------------- FETCH LANDCOVER DATA FROM GEE --------------------------------------------
# Route for API requests to google earth engine for the Landcover on-click events
@app.route('/fetch_landcover')
#@cross_origin()  # Enable CORS for this route if needed
@cache.cached(timeout=300, query_string=True)
def fetch_landcover():
    lat = float(request.args.get('lat'))
    lon = float(request.args.get('lon'))
    radius = float(request.args.get('radius'))
    
   
    # Make the request to Google Earth Engine API and return the data as a json
    try:
        landcover_data = wildfire.on_click_landcover(lat, lon, radius)

        # Print the JSON data for inspection
        print("Landcover Data:", landcover_data)
        
        return jsonify(landcover_data)
    except Exception as e:
        return jsonify({'error': str(e)})
         

# ----------------------------- FETCH WEATHER DATA FROM NOAA ------------------------------------------
@app.route('/fetch_weather') # route to fetch weather from NOAA API 
@cache.cached(timeout=300, query_string=True)
def fetch_weather():
    lat = float(request.args.get('lat'))
    lon = float(request.args.get('lon'))
    
    
   
    # Make the request to Google Earth Engine API and return the data as a json
    try:
        noaa_data = wildfire.get_current_weather_conditions(lat, lon)
        return jsonify(noaa_data)
    
    except Exception as e:
        return jsonify({'error': str(e)})
    
#------------------------------------- BUILD HTML TEMPLATE ----------------------------------
#Route for the homepage
# Running on port 8000 (localhost:8000)
@app.route('/')
#@cross_origin()
def index():

    # Load CA shapefile data, historic perimeters, and firestations data
    CA_counties = wildfire.load_county_border_shapefile(calfire_geospatial_path)
    CA_state = wildfire.load_state_border_shapefile(calfire_geospatial_path)
    #historic_perimeters = wildfire.load_historic_fire_perimeters(calfire_geospatial_path)
    stations = wildfire.load_geocoded_firestations_df(calfire_geospatial_path)
    nws_zones = wildfire.load_CA_forecast_zones(calfire_geospatial_path)

    # Initialize the firemap 
    m = wildfire.create_folium_map(CA_counties, CA_state)
   
    # Add Title
    wildfire.add_title_to_map(m)


    # Authorize + Initialize Google Earth Engine
    wildfire.auth_and_initialize_earth_engine(API_key_json, service_account)


    # Make API call to CALfire for currently active fire locations, and add to map
    fire_df = wildfire.scrape_calfire_geojson_to_df()
    wildfire.add_fires_to_map(fire_df, m)


    # Add NOAA weather data

    wildfire.add_red_flag_warning('CA', nws_zones, m)
    wildfire.add_excessive_heat_warning('CA', nws_zones, m )


    # Add all fire departments to map
    wildfire.add_all_fds_to_map(stations, m)
    wildfire.get_closest_fds(stations, fire_df, m)

 
    # Load Landcover Dataset
    landcover_image = wildfire.get_landcover()
    landcover_viz = wildfire.landcover_viz()
    # Add Landcover Layer
    wildfire.add_ee_layer(landcover_image, landcover_viz, 'National Land Cover (2019)', True, m)
    
    
    
    # Add Sentinel Images, [0] for normal image, [1] for NDVI 
    sentinel_image = wildfire.get_sentinel_data()[0]
    rgb = wildfire.band_combinations(['B4','B3', 'B2'])
    false_color = wildfire.band_combinations(['B8','B4', 'B3'])
    false_burn = wildfire.band_combinations(['B12','B11', 'B4'])
    sentinel_image_ndvi = wildfire.get_sentinel_data()[1]
    ndvi = wildfire.ndvi_viz()
    wildfire.add_ee_layer(sentinel_image, rgb, 'Sentinel-2 RGB Composite', False, m)
    wildfire.add_ee_layer(sentinel_image, false_color, 'Sentinel-2 False Color Composite', False, m)
    wildfire.add_ee_layer(sentinel_image, false_burn, 'Sentinel-2 False Burn Composite', False, m)
    wildfire.add_ee_layer(sentinel_image_ndvi, ndvi, 'NDVI', False, m)

    
   
    # Add Layer Control (last)
    wildfire.add_Layer_Control(m)


    # Add on click functionality to retrieve weather and landcover data for selected area
    firemap_html = wildfire.render_html(m)                 # renders map html, MAKE THIS A FUNCTION
    firemap_id = wildfire.find_map_variable(firemap_html)   # returns unique map_id of the html map object, anytime map elements change, so does the map object id
    on_click_event = wildfire.add_click_event_retrieve_landcover_weather(firemap_id)         # custom code now points to map_variable

    
    # Add Map Information button
    map_info_button = wildfire.add_map_information_button(m)
    map_info_button_interactive = wildfire.enable_info_button_interactivity()
    
    # Add landcover legend elements 
    landcover_legend = wildfire.add_landcover_legend(m)
    landcover_legend = wildfire.render_html(landcover_legend)    # returns legend element as html
    landcover_control = wildfire.enable_landcover_legend_interactivity()     # returns show/hide functionality as html 
    landcover_legend_interactive = landcover_control + landcover_legend # legend and control code is highly dependent on each other, so we must combine 




    # Inject the on-click, map info button, and landcover legend functionalities into the final html 
    firemap_html_interactive = firemap_html.replace('<body>' , '<body>' + landcover_legend_interactive + on_click_event + map_info_button_interactive)


    # return firemap_html_interactive
    #return render_template('index.html', map_html=firemap_html_interactive, map_js='')
    return make_response(firemap_html_interactive)

        
    


if __name__ == '__main__':
    # Authorize + Initialize Google Earth Engine
    wildfire.auth_and_initialize_earth_engine(API_key_json, service_account)

    app.run(debug=False, port = 8000) # pythonanywhere recommends to add app.run() only within __main__


#app   




