#Import all libraries
import time 
import asyncio
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
import async_create_wildfire_map as wildfire
from flask_cors import CORS, cross_origin # Import CORS from flask_cors
from dotenv import load_dotenv
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
from branca.element import Element
from flask import Flask, send_from_directory, render_template, request, jsonify, make_response, Response

start_time = time.time()  # Record the start time


app = Flask(__name__,  static_folder='static_generated_firemap')  # Set static folder for Quart
CORS(app) # enable CORS


# ------------------------------ LOAD ENV VARIABLES AND SET DIRECTORY PATH ------------------------------
# Get directory path and set working directory 
calfire_geospatial_path = os.path.dirname(os.path.abspath(__file__)) 

# Load environmental variables
#load_dotenv(dotenv_path='/home/ajsbla/API_keys/.env')                   # Use for public deployment (directory where .env and GEE_API_key.json exist on pythonanywhere account)                                                           
load_dotenv(os.path.join(calfire_geospatial_path, '.env'))              # Use this for local development  



# ------------------------------ GOOGLE EARTH AUTHENTICATION KEYS ------------------------------

#API_key_json = os.getenv('GOOGLE_EARTH_API_KEY')  #Use for public deployment
API_key_json = os.path.join(calfire_geospatial_path, 'Data', 'API_keys', 'google_earth_engine_authentication_key.json') # for local
service_account = os.getenv('SERVICE_ACCOUNT')


# -------------------------------- BUILD FLASK APP -----------------------------------------
# Configure Flask-Caching, no caching for now using quart
#cache = Cache(Cache.MEMORY)  # Simple in-memory cache
#cache.init_app(app)


# ------------------------------- FETCH LANDCOVER DATA FROM GEE --------------------------------------------
# Route for API requests to google earth engine for the Landcover on-click events
@app.route('/fetch_landcover')
#@cross_origin()  # Enable CORS for this route if needed
#@cached(ttl=300)
def fetch_landcover():
    lat = float(request.args.get('lat'))
    lon = float(request.args.get('lon'))
    radius = float(request.args.get('radius'))
    
   
    # Make the request to Google Earth Engine API and return the data as a json
    try:
        landcover_data = wildfire.get_landcover(lat, lon, radius)

        # Print the JSON data for inspection
        print("Landcover Data:", landcover_data)
        
        return jsonify(landcover_data)
    except Exception as e:
        return jsonify({'error': str(e)})
         

# ----------------------------- FETCH WEATHER DATA FROM NOAA ------------------------------------------
@app.route('/fetch_weather')
def fetch_weather():
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
        noaa_data = wildfire.get_current_weather_conditions(lat, lon)
        return jsonify(noaa_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500




#------------------------------------- BUILD HTML TEMPLATE ----------------------------------
#Route for the homepage
# Running on port 8000 (localhost:8000)
@app.route('/')
def main():
    start_time = time.time()
    return send_from_directory('static_generated_firemap', 'firemap.html')

   
if __name__ == '__main__':
    # Authorize + Initialize Google Earth Engine
    wildfire.auth_and_initialize_earth_engine(API_key_json, service_account)
    elapsed_time = time.time() - start_time
    print(f"Total runtime: {elapsed_time:.2f} seconds")
    app.run(debug=True, port = 8000) # pythonanywhere recommends to add app.run() only within __main__


#app   





