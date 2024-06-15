#!/usr/bin/env python
# coding: utf-8

import geopandas as gpd
import pandas as pd
import folium
from folium import Element
import ee      # Google Earth Engine API
import geemap
import json
import pycrs
from geopy.geocoders import Nominatim
from osgeo import ogr
import requests
import re
import googlemaps
import time
from math import radians, sin, cos, sqrt, atan2       # Haversine Formula, closest points
import networkx as nx
import time
from IPython.display import HTML
from jinja2 import Template
from folium import plugins
from folium.plugins import GroupedLayerControl
import ee
from datetime import datetime
from branca.element import Template, MacroElement  # for Legend on map
from IPython.display import HTML
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request
from dotenv import load_dotenv
import os
from shapely import wkt
from shapely.geometry import Polygon
from shapely.geometry import box
from shapely.geometry import shape
import matplotlib.pyplot as plt
import contextily as ctx
import numpy as np
import glob
import geojson
import osmnx as ox




# Load environmental variables (API_keys, credentials, pathnames)
load_dotenv()

# Change directory
def get_path_to_project_directory():
    return os.getenv('CALFIRE_GEOSPATIAL_PATH')

def set_working_directory(path):
    os.chdir(path)

# Load border shapefiles and fire data
def load_county_border_shapefile(calfire_geospatial_path):
    #CA_jurisdictions_path = os.path.join(calfire_geospatial_path, 'California Fire Stations', 'CA_firestations.geojson')
    CA_counties_path = os.path.join(calfire_geospatial_path, 'Data', 'County_and_Weather_Zones.shp', 'CA_Counties', 'CA_Counties_TIGER2016.shp')
    CA_counties = gpd.read_file(CA_counties_path).to_crs(epsg = 4269)
    return CA_counties

def load_state_border_shapefile(calfire_geospatial_path):
    return ox.geocode_to_gdf('California')

def load_geocoded_firestations_df(calfire_geospatial_path):
    geocoded_firestations_csv = os.path.join(calfire_geospatial_path,'Data', 'Firestations', 'geocoded_CA_firestations_lonLat_final.csv')
    stations =  pd.read_csv(geocoded_firestations_csv)
    return stations

#def load_historic_fire_perimeters(calfire_geospatial_path):
 #   CA_perimeters_path = os.path.join(calfire_geospatial_path, 'CA_Wildfire_Perimeters', 'California_Fire_Perimeters_(all).shp')
  #  CA_perimeters = gpd.read_file(CA_perimeters_path)
   # return CA_perimeters

def load_CA_forecast_zones(calfire_geospatial_path):
    nws_forecast_path = os.path.join(calfire_geospatial_path, 'Data', 'County_and_Weather_Zones.shp', 'nws_zones', 'z_19se23.shp')
    CA_forecast_zones = (gpd.read_file(nws_forecast_path)
                        .query("STATE == 'CA'")
                        .assign(S_zone = lambda x: x['STATE_ZONE'].apply(lambda zone: zone.replace('A', 'AZ')))
                )
    return CA_forecast_zones

def load_fire_weather_zones(calfire_geospatial_path):
    fire_weather_zones_path = os.path.join(calfire_geospatial_path, 'Data', 'fire_weather_zones.shp', 'fz05mr24.shp')
    fire_weather_zones = (gpd.read_file(fire_weather_zones_path)
                        .query("STATE == 'CA'")
                        .assign(S_zone = lambda x: x['STATE_ZONE'].apply(lambda zone: zone.replace('A', 'AZ')))
                )
    return fire_weather_zones

def load_GEE_API_key():
    return os.getenv('GOOGLE_EARTH_API_KEY')

def load_GEE_service_account_credentials():
    return os.getenv('SERVICE_ACCOUNT')



# ----------------------------------- CREATE FOLIUM MAP ------------------------------
  
def create_folium_map(counties_shapefile, state_shapefile):

    # Create initial map
    map = folium.Map(location = [36.7783, -119.4179], zoom_start=10, tiles = None)
    folium.TileLayer('esriworldstreetmap', control = False).add_to(map)

    # Fit map bounds to California
    california_bounds = [[32.5341, -124.4096], [42.0095, -114.1308]]
    map.fit_bounds(california_bounds)


    # Counties Boundary Layer
    def style_function_county(feature):
        return {
            'fillColor': 'white',  # Fill color of the county
            'color': '#737373',       # Outline color of the county
            'weight': .5,           # Outline weight
            'fillOpacity': .05     # Fill opacity
        }
    folium.GeoJson(counties_shapefile, name = 'County Boundaries', style_function=style_function_county, control = False).add_to(map)

    # State Boundary Layer
    def style_function_state(feature):
        return {
            'fillColor': 'white',  # Fill color of the county
            'color': '#000000',       # Outline color of the county
            'weight': 1.2,           # Outline weight
            'fillOpacity': .05     # Fill opacity
        }
    folium.GeoJson(state_shapefile, name = 'CA State Boundary', style_function=style_function_state, control = False).add_to(map)


    return map

def add_title_to_map(m):
    # Add Title
    title_html = '''
    <div style="position: absolute; top: 10px; left: 50%; transform: translateX(-50%); z-index: 1000; 
                background-color: white; padding: 5px 10px; border-radius: 5px; box-shadow: 0 0 10px rgba(0,0,0,0.5);">
        <h3 style="margin: 0; font-size: 20px;"><b>2024 CA Wildfire Tracker within State Responsibility Area</b></h3>
    </div>
    '''
    title_element = Element(title_html)
    m.get_root().html.add_child(title_element)




# -------------------------------------- API CALL TO CALFIRE TO GET FIRE LOCATIONS -------------------------------

def scrape_calfire_geojson_to_df():

    url = 'https://incidents.fire.ca.gov/umbraco/api/IncidentApi/GeoJsonList?inactive=true'
    
    headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'   
    }

    r = requests.get(url, headers = headers)
    
    soup = BeautifulSoup(r.content)
    
    if r.status_code == 200:
        # Parse the JSON response into a GeoJSON object
        geojson_data = geojson.loads(r.text)
    
        # Initialize an empty list to store the flattened feature properties
        data = []
        
        # Loop through each feature in the GeoJSON data
        for feature in geojson_data['features']:
            # Flatten the properties of the feature
            properties = feature['properties']
        
            # Add the flattened properties to the list
            data.append(properties)
        
        # Create a DataFrame from the list of dictionaries
        df = (pd
              .DataFrame(data)
              .drop(columns = ['AdminUnitUrl', 'AgencyNames', 'UniqueId', 'Updated', 'StartedDateOnly','Final', 'Updated', 'ControlStatement', 'ExtinguishedDate' , 'Url', 'NotificationDesired'])
              .assign(Coordinates_Fire = (lambda x : '('+ x['Latitude'].astype(str)+ ','+ x['Longitude'].astype(str) + ')'))
             )
          
    
    else:
        print("Failed to fetch GeoJSON data. Status code:")

    return df



# -------------------------- ADD CALFIRE FIRES TO MAP --------------------------


def add_fires_to_map(fire_df, map):
   
    # CSS added to control tooltip sizing
    tooltip_width_css = """
    <style>
        .fire-tooltip {
            max-width: 300px; /* Set the maximum width of the tooltip */
            min-width: 200px; 
            white-space: normal; /* Ensure the text wraps within the tooltip */
        }
    </style>
    """
     # Add the custom CSS to the map
    map.get_root().html.add_child(folium.Element(tooltip_width_css))


    active_layer = folium.FeatureGroup(name='All Active Fires', control= True, show = True)
    small_fires_active = folium.FeatureGroup(name='Active Small Fires (<100 acres)', control= True, show = False)
    medium_fires_active = folium.FeatureGroup(name='Active Medium Fires (100 - 1,000 acres)', control= True, show = False)
    large_fires_active = folium.FeatureGroup(name = 'Active Large Fires (1,000 - 10,000 acres)', control = True, show = False)
    mega_fires_active = folium.FeatureGroup(name='Active Mega Fires (10,000+ acres)', control= True, show = False)
    inactive_layer = folium.FeatureGroup(name='All Contained Fires', control = True, show = False)
    large_fires_inactive = folium.FeatureGroup(name = ' Contained Large Fires (1000+ acres)', control = True, show = False)
                                  
    for index, fire in fire_df.iterrows():
        lat = fire['Latitude']
        lon = fire['Longitude']
        fire_name = fire['Name']
        start_date_month_day = (datetime
                      .strptime(fire['Started'], '%Y-%m-%dT%H:%M:%SZ')
                      .strftime('%B %d')
                     )
        start_date_hour = (datetime
                      .strptime(fire['Started'], '%Y-%m-%dT%H:%M:%SZ')
                      .strftime('%H:%M')
                     )
        
        admin_unit = fire['AdminUnit']
        county = fire['County']
        acres = fire['AcresBurned']
        # Check if acres is NaN
        if pd.isna(acres):
            acres_burned = 'Not Yet Updated'
        else:
            acres_burned = round(acres, 2)

        percent_contained = fire['PercentContained']
        # Check if percent_contained is NaN
        if pd.isna(percent_contained):
            containment_status = 'Not Yet Updated'
        else:
            containment_status = f"{percent_contained}% contained"
    

        # Adds markers for each active fire, if acres > 300, adds markers to 'large_fires_active' Feature Group
        if (fire['IsActive'] == True):
            color = 'red'
            containment = 'still active'
            folium.Marker([lat, lon], 
                      #popup=fire_name, 
                      tooltip = f"""
                          <div class="fire-tooltip">
                              <strong>{fire_name.upper()}</strong> <br>
                              Discovered on {start_date_month_day} at {start_date_hour} <br>
                              <strong>County</strong>: {county} <br>
                              <strong>Acres</strong>: {acres_burned} <br>
                              <strong>Status</strong>: {containment_status} <br>
                              <strong>Administrative Unit</strong>: {admin_unit}
                          </div>
                          """,
                      icon = folium.Icon(icon = 'fire', 
                                       color =color, 
                                       icon_color= 'white')).add_to(active_layer)
            if fire['AcresBurned'] < 100:
                color = 'red'
                containment = 'still active'
                folium.Marker([lat, lon], 
                          #popup=fire_name, 
                          tooltip = f"""
                          <div class="fire-tooltip">
                              <strong>{fire_name.upper()}</strong> <br>
                              Discovered on {start_date_month_day} at {start_date_hour} <br>
                              <strong>County</strong>: {county} <br>
                              <strong>Acres</strong>: {acres_burned} <br>
                              <strong>Status</strong>: {containment_status} <br>
                              <strong>Administrative Unit</strong>: {admin_unit}
                          </div>
                          """,
                          icon = folium.Icon(icon = 'fire',
                                        color =color, 
                                        icon_color= 'white')).add_to(small_fires_active)
            elif (fire['AcresBurned'] > 100 and fire['AcresBurned']<1000):
                color = 'red'
                containment = 'still active'
                folium.Marker([lat, lon], 
                          #popup=fire_name, 
                          tooltip = f"""
                          <div class="fire-tooltip">
                              <strong>{fire_name.upper()}</strong> <br>
                              Discovered on {start_date_month_day} at {start_date_hour} <br>
                              <strong>County</strong>: {county} <br>
                              <strong>Acres</strong>: {acres_burned} <br>
                              <strong>Status</strong>: {containment_status} <br>
                              <strong>Administrative Unit</strong>: {admin_unit}
                          </div>
                          """,
                          icon = folium.Icon(icon = 'fire',
                                        color =color, 
                                        icon_color= 'white')).add_to(medium_fires_active)
            elif (fire['AcresBurned'] > 1000 and fire['AcresBurned']<10000):
                color = 'red'
                containment = 'still active'
                folium.Marker([lat, lon], 
                        #popup=fire_name, 
                        tooltip = f"""
                        <div class="fire-tooltip">
                            <strong>{fire_name.upper()}</strong> <br>
                            Discovered on {start_date_month_day} at {start_date_hour} <br>
                            <strong>County</strong>: {county} <br>
                            <strong>Acres</strong>: {acres_burned} <br>
                            <strong>Status</strong>: {containment_status} <br>
                            <strong>Administrative Unit</strong>: {admin_unit}
                        </div>
                        """,
                        icon = folium.Icon(icon = 'fire',
                                        color =color, 
                                        icon_color= 'white')).add_to(large_fires_active)
            elif fire['AcresBurned'] > 10000:
                color = 'red'
                containment = 'still active'
                folium.Marker([lat, lon], 
                          #popup=fire_name, 
                          tooltip = f"""
                          <div class="fire-tooltip">
                              <strong>{fire_name.upper()}</strong> <br>
                              Discovered on {start_date_month_day} at {start_date_hour} <br>
                              <strong>County</strong>: {county} <br>
                              <strong>Acres</strong>: {acres_burned} <br>
                              <strong>Status</strong>: {containment_status} <br>
                              <strong>Administrative Unit</strong>: {admin_unit}
                          </div>
                          """,
                          icon = folium.Icon(icon = 'fire',
                                        color =color, 
                                        icon_color= 'white')).add_to(mega_fires_active)
        else:
                color = 'lightgray'
                containment = 'not active'
                folium.Marker([lat, lon], 
                          #popup=fire_name, 
                          tooltip = f"""
                          <div class="fire-tooltip">
                              <strong>{fire_name.upper()}</strong> <br>
                              Discovered on {start_date_month_day} at {start_date_hour} <br>
                              <strong>County</strong>: {county} <br>
                              <strong>Acres</strong>: {acres_burned} <br>
                              <strong>Status</strong>: {containment_status} <br>
                              <strong>Administrative Unit</strong>: {admin_unit}
                          </div>
                          """,
                          icon = folium.Icon(icon = 'fire', 
                                             color =color, 
                                             icon_color= 'white')).add_to(inactive_layer)  
                if  fire['AcresBurned'] > 1000: 
                    color = 'lightgray' 
                    containment = 'not active'
                    folium.Marker([lat, lon], 
                              #popup=fire_name, 
                              tooltip = f"""
                          <div class="fire-tooltip">
                              <strong>{fire_name.upper()}</strong> <br>
                              Discovered on {start_date_month_day} at {start_date_hour} <br>
                              <strong>County</strong>: {county} <br>
                              <strong>Acres</strong>: {acres_burned} <br>
                              <strong>Status</strong>: {containment_status} <br>
                              <strong>Administrative Unit</strong>: {admin_unit}
                          </div>
                          """,
                              icon = folium.Icon(icon = 'fire', 
                                                 color =color, 
                                                 icon_color= 'white')).add_to(large_fires_inactive) 
            
    active_layer.add_to(map)
    small_fires_active.add_to(map)
    medium_fires_active.add_to(map)
    large_fires_active.add_to(map)
    mega_fires_active.add_to(map)
    inactive_layer.add_to(map)
    large_fires_inactive.add_to(map)

    current_date = datetime.now().strftime('%m-%d-%Y')
    
    grouped_layer_control = GroupedLayerControl(
                                            groups={
                                                f'<b>CURRENTLY ACTIVE FIRES AS OF {current_date}</b>': [active_layer, small_fires_active, medium_fires_active, large_fires_active, mega_fires_active], 
                                                '<br>INACTIVE FIRES</br>': [inactive_layer, large_fires_inactive]
                                            },
                                            collapsed=False,
                                            exclusive_groups= False,
                                            position = 'bottomleft'
                                            ).add_to(map)
 
    
    return map
    
   


# --------------------------------- ADD FIRE DEPTs ---------------------------------- 


def add_all_fds_to_map(stations_df, map):

    '''
    Adds all firestations within the bounds of California. This is to account for erroneous geocoding, or areas out of the bounds. 
    If the Mapbox API geocoder returned (None, None), which indicates it could not locate the firestation, then these rows are filtered.
    Adds this to firemap as a Feature Group, which can then be toggled on/off by the user, default is set to not shown.
    '''
    
    fd_layer = folium.FeatureGroup(name='All California Fire Stations',
                                   control= True,
                                   show = False)
    
    # Define the bounding box of California
    california_bbox = [-124.55, 32.32, -114.13, 42.0]  # [min_lon, min_lat, max_lon, max_lat]
    

    # Filter out fire stations outside of California
    stations_ca = stations_df[
        (stations_df['Longitude'] >= california_bbox[0]) &
        (stations_df['Longitude'] <= california_bbox[2]) &
        (stations_df['Latitude'] >= california_bbox[1]) &
        (stations_df['Latitude'] <= california_bbox[3])
    ]

    for index, station in stations_ca.iterrows():
        try:
            lat, lon = station['Latitude'], station['Longitude']
            (folium
             .CircleMarker([lat, lon], 
                           tooltip = station['Fire dept name'], 
                           color = '#a50f15', 
                           radius = 1, 
                           popup='FD')
             .add_to(fd_layer)
            )
            
        except:
            lat, lon = None, None
            
    # Add the FeatureGroup to the map
    fd_layer.add_to(map)
    return map


def get_closest_fds(df_firestations, fire_df, map):
    
    '''
    Iterates through the fire_df and, for every firestation in the dataframe, calculates the distance to each fire location in California 
    using the Haversine Formula. A new dataframe is created that joins data from firestations and fire dataframes; the firestations are
    grouped by fire name, and then sorted based on distance to each fire. The top 5 stations are selected. 

    We check to see if the fire is active. If it is currently active then, then the top 5 closest stations are plotted onto firemap. 
    This ensures minimal data clutter and highlights only the local resources for active fires.


    '''
    
    R =  6371.0 # Earth's Radius in km

    distances_list = []

    fd_layer = folium.FeatureGroup(name='Closest Fire Stations to Currently Active Fires',
                               control= True,
                               show = False)

    for index, fire_coord in fire_df.iterrows():
   
        for index, station in df_firestations.iterrows():

            # Filters out all data without addresses or can't be geocoded
            if (station['Coordinates_Firestation'] != (None, None)) and (station['Coordinates_Firestation'] != (41.257081, -70.063891)):
                lat1 = radians(station['Latitude'])
                lon1 = radians(station['Longitude'])
            
                lat2 = radians(fire_coord['Latitude'])
                lon2 = radians(fire_coord['Longitude'])
    
                
                lat_dif = lat2 - lat1
                lon_dif = lon2 - lon1

                # Haversine Formula to calculate distance of each fire station to the fire. Assumes Earth is a perfect sphere!
                a = sin(lat_dif /2) **2 + cos(lat1) * cos(lat2) * sin(lon_dif / 2)**2
                c = 2 * atan2(sqrt(a), sqrt(1-a))
                distance = (R * c) * 0.621371  # Distance in miles each station is away from fire
        
                
                distance_dict = {'Station' : station['Fire dept name'],
                                 'County' : station['County'],
                                 'FD_Latitude' : station['Latitude'],
                                 'FD_Longitude' : station['Longitude'],
                                 'Fire_Name' : fire_coord['Name'],
                                 'IsActive' : fire_coord['IsActive'],
                                 'Coordinates_Fire': fire_coord['Coordinates_Fire'],
                                 'Fire_Latitude' : fire_coord['Latitude'],
                                 'Fire_Longitude' : fire_coord['Longitude'],
                                 'Distance (mi)' : distance,
                                
                                }
                distances_list.append(distance_dict)
            
         
    distances_df = (pd
                    .DataFrame(distances_list)
                    #.astype({'Coordinates_Fire': str})
                    .sort_values(['Fire_Name', 'Distance (mi)'], ascending = True)
                   
                    .groupby(['Fire_Name'])
                    .head(5)
                    .reset_index(drop = True)
                   )
 
    
    # Add markers to folium map
    for index, station in distances_df.iterrows():
        if station['IsActive'] == True:
            lat,lon = station['FD_Latitude'], station['FD_Longitude']
            (folium.CircleMarker([lat, lon], 
                                  tooltip = f"{station['Station']} - {round(station['Distance (mi)'], 2)} miles from {station['Fire_Name']}",
                                  color = '#a50f15', 
                                  radius = 1 
                                  )
                                
                     .add_to(fd_layer)
            )
        else:
            None

    fd_layer.add_to(map)
    return map


    
# ----------------------------------- ADD HISTORIC PERIMS --------------------------

def add_historic_perims(map, historic_perims):
    def style_function_perims(feature):
        return {
            'fillColor': '#525252',  # Fill color of the county
            'color': '#cb181d',       # Outline color of the county
            'weight': .5,           # Outline weight
            'fillOpacity': .05     # Fill opacity
        }
    folium.GeoJson(historic_perims, name = 'Historic Wildfire Perimeters', style_function = style_function_perims, control = True).add_to(map)
    
    return map




# ------------------------------------ AUTHORIZE AND INITIALIZE GOOGLE EARTH ENGINE ------------------------


# ----------------------------- INITIALIZE GOOGLE EARTH ENGINE -----------

def auth_and_initialize_earth_engine(API_key_json, service_account):
    '''
    Service account and geojson key associated with the Cloud Project in environmental variables (.env file in project directory)

    '''
    service_account = service_account
    credentials = ee.ServiceAccountCredentials(service_account, API_key_json)
    ee.Initialize(credentials)

 


# ----------------------------- GOOGLE EARTH ENGINE LAYERS ------------------------------------------

# Define a method for displaying Earth Engine image tiles on a folium map.
def add_ee_layer(ee_object, vis_params, name, show, firemap):
    try:
        # display ee.Image()
        if isinstance(ee_object, ee.image.Image):    
            map_id_dict = ee.Image(ee_object).getMapId(vis_params)
            folium.raster_layers.TileLayer(
                tiles=map_id_dict['tile_fetcher'].url_format,
                attr='Google Earth Engine',
                name=name,
                overlay=True,
                control=True,
                show=show
            ).add_to(firemap)

        # display ee.ImageCollection()
        elif isinstance(ee_object, ee.imagecollection.ImageCollection):    
            ee_object_new = ee_object.mosaic()
            map_id_dict = ee.Image(ee_object_new).getMapId(vis_params)
            folium.raster_layers.TileLayer(
                tiles=map_id_dict['tile_fetcher'].url_format,
                attr='Google Earth Engine',
                name=name,
                overlay=True,
                control=True,
                show=show
            ).add_to(firemap)

        # display ee.Geometry()
        elif isinstance(ee_object, ee.geometry.Geometry):    
            folium.GeoJson(
                data=ee_object.getInfo(),
                name=name,
                overlay=True,
                control=True,
                show=show
            ).add_to(firemap)

        # display ee.FeatureCollection()
        elif isinstance(ee_object, ee.featurecollection.FeatureCollection):  
            ee_object_new = ee.Image().paint(ee_object, 0, 2)
            map_id_dict = ee.Image(ee_object_new).getMapId(vis_params)
            folium.raster_layers.TileLayer(
                tiles=map_id_dict['tile_fetcher'].url_format,
                attr='Google Earth Engine',
                name=name,
                overlay=True,
                control=True,
                show=show
            ).add_to(firemap)

    except Exception as e:
        print(f"Could not display {name}. Error: {str(e)}")
    
    # Add EE drawing method to folium.
    folium.Map.add_ee_layer = add_ee_layer
    return firemap


# ------------- SENTINEL --------------------   
def band_combinations(bands):
    sentinel_viz= {
                    'min': 0,
                    'max': 1,
                    'bands': bands,  
    }
    return sentinel_viz

# NDVI visualization
def ndvi_viz():
    return {
        'min': -1,
        'max': 1,
        'palette': ['blue', 'yellow', 'green'],
        'bands': ['NDVI']
    }

def get_sentinel_data():

    # Get most recent Sentinel Image
    current_date = ee.Date(datetime.now().strftime('%Y-%m-%d'))
    # Temporal Resolution of Sentinel 2, seven days
    five_days_prior = current_date.advance(-5, 'day')

    
    
    # Get Filter Bounds from geodataframe 
    def get_ee_geometry_bounds(state_shapefile):
        '''
        Converts a state_shapefile (returned as a geodataframe) to a geojson. Selects the 'geometry' of this geojson, returns this
        geometry as a ee.Geometry object.

        Input
        ------
        state_shapefile : , converts to geojson and selects geometry features. 
        
        Return
        ------
        ee.Geometry object that can be used to determine the filter bounds of the Earth Engine image.
        '''
        geojson = state_shapefile.to_json()
        geo_dict = json.loads(geojson)
        geometry = geo_dict['features'][0]['geometry']
        geo_bounds = ee.Geometry(geometry)
        return geo_bounds

    def normalize_sentinel(image):
        return image.divide(5000)
    
    # NDVI
    def calculate_ndvi(image):
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        return image.addBands(ndvi)

    # NDVI
    def calculate_ndvi(image):
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        return image.addBands(ndvi)
    sentinel_dataset = (ee
                        .ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                        .filterDate(five_days_prior, current_date)
                        # Pre-filter to get less cloudy granules.
                        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 90))
                        # Constrain bounds to cover CA only
                        #.filterBounds(get_ee_geometry_bounds(state_shapefile))
                        .map(normalize_sentinel)
                        #.map(mask_s2_clouds)
                        #.map(calculate_ndvi)
                    )
    sentinel_dataset_ndvi = sentinel_dataset.map(calculate_ndvi)

    return sentinel_dataset, sentinel_dataset_ndvi



#--------------- LANDCOVER -------------------

def get_landcover():
    
    landcover = (ee
             .ImageCollection("USGS/NLCD_RELEASES/2019_REL/NLCD") 
             .select('landcover')
            )
    return landcover

def landcover_viz():
    return {
            'min': 0,
            'max': 95,
            'palette': [
                '#466b9f',  # No Data
                '#9ecae1',  # Open Water
                '#4575b4',  # Perennial Ice/Snow
                '#fee0d2',  # Developed, Open Space
                '#fc9272',  # Developed, Low Intensity
                '#ef3b2c',  # Developed, Medium Intensity
                '#a50f15',  # Developed, High Intensity
                '#f6e8c3',  # Barren Land (Rock/Sand/Clay)
                '#74c476',  # Deciduous Forest
                '#006d2c',  # Evergreen Forest
                '#d9f0a3',  # Mixed Forest
                '#dfc27d',  # Dwarf Scrub
                '#f6e8c3',  # Shrub/Scrub
                '#ffffbf',  # Grassland/Herbaceous
                '#b8e186',  # Sedge/Herbaceous
                '#a6d96a',  # Lichens
                '#35978f',  # Moss
                '#b35806',  # Pasture/Hay
                '#ffff33',  # Cultivated Crops
                '#d1e5f0',  # Woody Wetlands
                '#4393c3',  # Emergent Herbaceous Wetlands
                            ],
                'opacity': 0.5
                }




# ---------------- MODIS -------------------

def get_modis():
    # Temporal Resolution of MODIS is 2 days
    current_date =  ee.Date(datetime.now().strftime('%Y-%m-%d'))
    two_days_prior = current_date.advance(-8, 'day')
  

    #Fire Information for Resource Management System (FIRMS)
    modis_dataset = (ee.ImageCollection("FIRMS")#('MODIS/061/MYD14A1')#.select(['MaxFRP', 'FireMask'])
                     .select('T21')
                     .filterDate(two_days_prior, current_date)
                    )
    return modis_dataset
    
def modis_viz():
    firms_viz = {
        'min': 325.0,
        'max': 400.0,
        'palette': ['red', 'orange', 'yellow'],
    }
    return firms_viz


   
    



# ---------------------------------------- NATIONAL WEATHER SERVICE DATA ----------------------


def add_red_flag_warning(state, fire_weather_zones, m):

    '''
    GET request to National Weather Service API for Special NWS warnings 'Fire Weather Watch' and 'Red Flag Warning'.

    Inputs
    ------
    state (str) : For this project, state will be 'CA', this is used in the endpoint to query all warnings for CA
    nws_zones (df) : Shapefile of National Weather Zones (NWS), the geocoded areas used by NWS to alert users for fire weather
    m : the current folium map object

    Returns
    -------
    Map object with added Red Flag Warning layer. 
    
    
    '''
    tooltip_width_css = """
    <style>
        .leaflet-tooltip {
            max-width: 300px; /* Set the maximum width of the tooltip */
            min-width: 200px; 
            white-space: normal; /* Ensure the text wraps within the tooltip */
        }
    </style>
    """
     # Add the custom CSS to the map
    m.get_root().html.add_child(folium.Element(tooltip_width_css))


    # Endpoint that contains the alerts for the specified state
    endpoint = f'https://api.weather.gov/alerts/active?area={state}'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
    }
    
    events = ['Fire Weather Watch', 'Red Flag Warning']

    red_flag_layer = folium.FeatureGroup(name='Areas Under Fire Watch / Red Flag Warning', control=True)
    
    geocodes = [] # Special NWS warnings like red flag and heat warnings are organized by geocode zones, no geometry available
    
    for event in events:
        parameters = {
            'event': event,  # Adjust based on the specific event you're interested in
        }
        
        response = requests.get(endpoint, params=parameters, headers=headers)

        if response.status_code == 200:
            noaa_json_response = response.json()

            for feature in noaa_json_response['features']:
                properties = feature['properties']
                geocode_list = properties.get('geocode', {})  
                ugc_list = geocode_list.get('UGC', [])
           
                for ugc in ugc_list:
                    #if ugc.startswith('CA'):
                     geocodes.append(ugc)

        else:
            print(f"Failed to retrieve Red Flag Warning data. Status code: {response.status_code}")

    # if geocodes is empty, there are no red flag warnings
    if not geocodes:
        print("There are currently no Red Flag Warnings.")
        red_flag_layer.add_to(m) # returns layer with no geometries
        return m

    
    #red_flag_layer = folium.FeatureGroup(name='Areas Under Fire Watch / Red Flag Warning', control=True)
    
    # Filter forecast zones dataframe based on the geocodes
    zones_df = pd.concat([fire_weather_zones.query(f"S_zone == '{geocode}'") for geocode in geocodes])
    
        
    # Add the geometries to the map
    for _, row in zones_df.iterrows():
        geometry = row['geometry']
        folium.GeoJson(
            data=geometry.__geo_interface__,
            overlay = True,
            name=f"<b>Fire Watch / Red Flag Warning</b> - {row['NAME']}",
            tooltip=f"<b>Red Flag / Fire Watch Warning</b> - {row['NAME']}",
            style_function= lambda feature: {
                                            'fillColor': '#fe9929',#'#67000d',  # Fill color of the polygon
                                            'color': '#fe9929',#'#800026',      # Outline color of the polygon
                                            'weight': .01,          # Outline weight
                                            'fillOpacity': .75, 
                                        }                          
                                    ).add_to(red_flag_layer)
            
        
    red_flag_layer.add_to(m)


    return m


def add_excessive_heat_warning(state, nws_zones, m):
    # Endpoint that contains the alerts for the specified state
    endpoint = f'https://api.weather.gov/alerts/active?area={state}'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
    }
    
    events = ['Excessive Heat Warning', 'Excessive Heat Watch']
    
    excessive_heat_layer = folium.FeatureGroup(name='Areas Under Excessive Heat Warning / Heat Watch', control=True)
    
    geocodes = []
    for event in events:
        parameters = {
            'event': event,  # Adjust based on the specific event you're interested in
        }
        
        response = requests.get(endpoint, params=parameters, headers=headers)

        if response.status_code == 200:
            noaa_json_response = response.json()
            
            for feature in noaa_json_response['features']:
                properties = feature['properties']
                geocode_list = properties.get('geocode', {})
                ugc_list = geocode_list.get('UGC', [])
            
                for ugc in ugc_list:
                    if ugc.startswith('CA'):
                        geocodes.append(ugc)
        else:
            print(f"Failed to retrieve Excessive Heat Warning data. Status code: {response.status_code}")

     # if geocodes is empty, there are no heat warnings
    if not geocodes:
        print("There are currently no excessive heat warnings.")
        excessive_heat_layer.add_to(m) # returns layer with no geometries
        return m

    

    # Filter forecast zones based on the geocodes
    zones_df = pd.concat([nws_zones.query(f"S_zone == '{geocode}'") for geocode in geocodes])
    
    # Add the geometries to the map
    for _, row in zones_df.iterrows():
        geometry = row['geometry']
        folium.GeoJson(
            data=geometry.__geo_interface__,
            overlay=False,
            name=f"<b>Excessive Heat Warning</b> - {row['SHORTNAME']}",
            tooltip=f"<b>Excessive Heat Warning</b> - {row['SHORTNAME']}",
            style_function=lambda feature: {
                'fillColor': 'salmon',  # Fill color of the polygon
                'color': '#a50f15',     # Outline color of the polygon
                'weight': 0.2,          # Outline weight
                'fillOpacity': 0.45,    # Fill opacity
            }
        ).add_to(excessive_heat_layer)
    
    excessive_heat_layer.add_to(m)
    
    return m


def get_current_weather_conditions(lat, lon):

    '''
    Makes API call to NOAA for the current weather forecast. Data returned as JSON with structure data['properties']['periods'][0]...
    ['periods'][0] indicates the current day, ['periods'][0] is the forecast for night, etc. We are querying, temperature, relative humidity,
    wind speed, and wind direction. 
    '''
    
    
    # Step 1: Get the forecast URL from the points endpoint
    endpoint = f'https://api.weather.gov/points/{lat},{lon}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
    }

    response = requests.get(endpoint, headers=headers)
    if response.status_code == 200:
        data = response.json()
        forecast_url = data['properties']['forecast']
        #return forecast_url
    else:
        return f"Error: Unable to retrieve forecast URL. Status code {response.status_code}"

    # Step 2: Get the current weather observation from the forecast URL
    response = requests.get(forecast_url, headers=headers)
    if response.status_code == 200:
         data = response.json()
         temperature = data['properties']['periods'][0]['temperature']
         temperature_unit = data['properties']['periods'][0]['temperatureUnit']
         humidity = data['properties']['periods'][0]['relativeHumidity']['value']
         wind_speed = data['properties']['periods'][0]['windSpeed']
         wind_direction = data['properties']['periods'][0]['windDirection']
         forecast = data['properties']['periods'][0]['detailedForecast']
         day_of_week = data['properties']['periods'][0]['name']
         date = data['properties']['periods'][0]['startTime']
         date_converted = datetime.fromisoformat(date[:-6]).strftime('%m/%d/%y')
        
         return f"({date_converted}): {forecast} The humidity is {humidity}%"
         #return temperature, temperature_unit
    else:
        return f"Unable to retrieve current weather data for location ({response.status_code})"





# ------------------------------ CUSTOM JAVASCRIPT CODE TO INJECT ON CLICK EVENTS, MAP INFO BUTTON, LANDCOVER LEGEND -----------------------


# Search this new html for map variable
def find_map_variable(html):
  '''
  Function to parse the html and find the dynamic JS map object variable name. 
  Returns this variable so it can be used to add on click events and increase
  interactivity
  
  '''
  # pattern where the js map object is first instantiated and named
  # Example : in the html code -->  var map_69 = L.map(map_69). This js map variable will change each time we refresh the page. this is why we need to change our variable each time
  pattern = 'var map_'
  # searches html for the pattern. Adds 4 so that 'var ' is excluded and we are left with 'map_'
  starting_index = html.find(pattern) + 4

  # subsets the html code so that we start at the starting index (which is 'map_'). this still contains the rest of the html, so lets subset even further.
  # returns 'map_'
  html_temp = html[starting_index:]

  # using the new subsetted html, find ' =', everything after this '=' is used as the js map object variable 
  # returns 'map_69', from our example above
  ending_index = html_temp.find(' =') + starting_index

  #retun everything between 'map_69', this is your map variable
  return html[starting_index:ending_index]

def add_click_event_retrieve_landcover_weather(map_variable_name):
    """
    Returns javascript code to add on-click event to retrieve landcover and weather data within 5-mile radius.
    
    """
    
    return f"""
<style>
    .landcover-tooltip {{
    max-width: 300px; /* Set the maximum width of the tooltip */
    min-width: 200px; /* Set the minimum width of the tooltip */
    white-space: pre-wrap; /* Ensure the text wraps within the tooltip */
  }}
</style>
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        var currentCircle = null;
        var currentTooltip = null;

        const landCoverClassNames = {{
            '11': 'Open water',
            '12': 'Perennial ice/snow',
            '21': 'Developed, open space',
            '22': 'Developed, low intensity',
            '23': 'Developed, medium intensity',
            '24': 'Developed high intensity',
            '31': 'Barren land (rock/sand/clay)',
            '41': 'Deciduous forest',
            '42': 'Evergreen forest',
            '43': 'Mixed forest',
            '51': 'Dwarf scrub',
            '52': 'Shrub/scrub',
            '71': 'Grassland/herbaceous',
            '72': 'Sedge/herbaceous',
            '73': 'Lichens',
            '74': 'Moss',
            '81': 'Pasture/hay',
            '82': 'Cultivated crops',
            '90': 'Woody wetlands',
            '95': 'Emergent herbaceous wetlands',
        }};

        function onMapClick(e) {{
            var lat = e.latlng.lat;
            var lon = e.latlng.lng;
            var bufferRadius = 5 * 1609.34;

            if (currentCircle !== null) {{
                {map_variable_name}.removeLayer(currentCircle);
            }}

            currentCircle = L.circle([lat, lon], {{
                radius: bufferRadius,
                color: 'yellow',
                fillColor: '#30f',
                fillOpacity: 0.05,
                dashArray: 5
            }}).addTo({map_variable_name});

            console.log('Clicked location:', lat, lon);
            console.log('Buffer radius:', bufferRadius);

            Promise.all([
                fetch(`/fetch_landcover?lat=${{lat}}&lon=${{lon}}&radius=${{bufferRadius}}`).then(response => response.json()),
                fetch(`/fetch_weather?lat=${{lat}}&lon=${{lon}}`).then(response => response.json())
            ])
            .then(([landcoverData, weatherData]) => {{
                console.log('Land Cover Data:', landcoverData);
                console.log('Weather Data:', weatherData);

                var tooltipContent = "<b>LANDCOVER</b><br>";

                if (landcoverData.landcover) {{
                    var totalPixels = Object.values(landcoverData.landcover).reduce((a, b) => a + b, 0);

                    var landCoverData = Object.entries(landcoverData.landcover).map(([key, value]) => {{
                        var className = landCoverClassNames[key] || "Unknown";
                        var areaInAcres = value * 0.222395;  // Convert pixel count to acres
                        var percentage = (value / totalPixels) * 100;
                        return {{
                            key: key,
                            className: className,
                            areaInAcres: areaInAcres.toFixed(2),
                            percentage: percentage.toFixed(1)
                        }};
                    }});

                    // Sort the land cover data by value (percentage) in descending order
                    landCoverData.sort((a, b) => b.percentage - a.percentage);

                    // Extract the top 3 land cover values
                    var top3LandCoverData = landCoverData.slice(0, 3);

                    // Calculate the 'Other' category
                    var otherData = landCoverData.slice(3);
                    var otherAreaInAcres = otherData.reduce((sum, data) => sum + parseFloat(data.areaInAcres), 0).toFixed(2);
                    var otherPercentage = otherData.reduce((sum, data) => sum + parseFloat(data.percentage), 0).toFixed(2);

                    // Add the 'Other' category if there are remaining categories
                    if (otherData.length > 0) {{
                        top3LandCoverData.push({{
                            key: 'Other',
                            className: 'Other',
                            areaInAcres: otherAreaInAcres,
                            percentage: otherPercentage
                        }});
                    }}

                    top3LandCoverData.forEach(data => {{
                        tooltipContent += `<b>${{data.className}}:</b> ${{data.percentage}}%<br>`;
                    }});
                }} else {{
                    console.error('No landcover data found');
                }}

                if (weatherData) {{
                    tooltipContent += `<br><b>WEATHER</b><br> ${{weatherData}}<br>`;
                }} else {{
                    console.error('No weather data found or weatherData.weather is undefined');
                }}

                // Remove any existing tooltip
                if (currentTooltip !== null) {{
                    {map_variable_name}.removeLayer(currentTooltip);
                    currentTooltip = null;
                }}

                // Show tooltip immediately on click
                currentTooltip = L.tooltip({{
                    direction: 'bottom',
                    offset: L.point(0, 40),
                    className: 'landcover-tooltip'
                }})
                .setLatLng(e.latlng)
                .setContent(tooltipContent)
                .addTo({map_variable_name});

                // Remove tooltip when mouse leaves circle bounds
                currentCircle.on('mouseout', function(e) {{
                    {map_variable_name}.removeLayer(currentTooltip);
                    currentTooltip = null;
                }});

                // Show tooltip again when mouse enters circle bounds
                currentCircle.on('mouseover', function(e) {{
                    if (currentTooltip === null) {{
                        currentTooltip = L.tooltip({{
                            direction: 'bottom',
                            offset: L.point(0, 40),
                            className: 'landcover-tooltip'
                        }})
                        .setLatLng(e.latlng)
                        .setContent(tooltipContent)
                        .addTo({map_variable_name});
                    }}
                }});

            }})
            .catch(error => console.error('Error:', error));
        }}

        if (typeof {map_variable_name} !== 'undefined') {{
            {map_variable_name}.on('click', onMapClick);
        }} else {{
            console.error('Map variable {map_variable_name} is not defined.');
        }}
    }});
    </script>
    """


# Map Button
def add_map_information_button(map):
    
    """
    Returns html to add a map information button element

    """
    
    map_info_button =   """
    <style>
    .collapsible {
        background-color: #777;
        color: white;
        cursor: pointer;
        padding: 10px;
        width: 235px;
        border: none;
        text-align: left;
        outline: none;
        font-size: 15px;
        position: fixed; 
        bottom: 35.5%; 
        left: 1%;
        z-index:9999;
    }

    .active, .collapsible:hover {
        background-color: #555;
    }

    .content {
        padding: 0 18px;
        display: none;
        overflow: hidden;
        background-color: #f1f1f1;
        border: 2px solid grey;
        width: 300px;
        position: fixed; 
        bottom: 1.3%; 
        left: 19%;
        font-size: 10px;
        z-index:9999;
        max-height: 313px;
        overflow-y: auto;
    }
    </style>

    <button class="collapsible">Map Information & Data Sources</button>
    <div class="content">
        <h4>Map Information</h4>
        <p><b>ABOUT THIS MAP</b> <br>This map aims to provide the user more context for current wildfire potential, activity, and containment within areas in California where CAL Fire is the primary emergency response agency.</br></p>
        <p><b>ABOUT THE DATA</b> <br><b>Sentinel-2 :</b> Satelite imagery was queried from Google Earth Engine, each Sentinel-2 layer represents a composite image within the last 5 days. A cloud cover mask was applied for areas with >90 percent cloud cover.</br><br>The <i>RGB Composite</i> uses bands 2,3,4 and represents a true color image -- useful for visualizing changes in landcover before and after a fire.</br><br>The <i>False Color Composite</i> uses bands 8,4,3 to highlight healthy vegetation as red and helps to show the damage of wildfires on vegetation, and an area's vegetative recovery post-fire.</br><br>The <i>False Burn Composite</i> uses bands 12,11,4 to visualize active fire perimeters and burned areas through smoke. Useful for showing how a fire behaves over time.</br><br><i>NDVI</i> uses the normalized difference of bands 8 and 4. Useful for monitoring vegetation health; greener areas represent healthy vegetation while yellow areas represent barren areas or areas with poor vegetative health.</br>
        <br><b>National Weather Service :</b> Weather data is retrieved from the National Weather Service API, and is the most recent detailed forecast for the current date. </br><br><i> Excessive Heat Warnings</i>: Dangerously hot conditions that typically correspond to a maximum heat index of 105F+ for 2 or more days and nighttime temps will not fall below 75F.</br><br><i> Red Flag Warnings :</i> A condition of high temperatures, very low humidities, and strong winds that increase the risk of fire danger.</br> 
        </p>
        <p><b>HOW TO USE THE MAP</b><br>Click anywhere on the map to get information on landcover class type, along with the weather forecast for the current date, within a 5 mile radius. Weather data only represents the forecast for that latitude, longitude; not necessarily for the entire 5 mile radius.</br></p>
    
        <h4>Data Sources</h4>
        <ul>
            <li><a href="https://www.weather.gov/" target="_blank">NOAA Weather Service</a></li>
            <li><a href="https://earthengine.google.com/" target="_blank">Google Earth Engine</a></li>
            <li><a href="https://www.calfire.ca.gov/" target="_blank">CAL FIRE</a></li>
            <li><a href = "https://apps.usfa.fema.gov/registry/" target="_blank">US Fire Administration</a></li>
            <!-- Add more references as needed -->
        </ul>

    </div>
    """
    references_control = Element(map_info_button)
    map.get_root().html.add_child(references_control)
    return map

def enable_info_button_interactivity():
    """
    Returns javascript code to enable show/hide interactivity
    """

    return """
    <script>
    document.addEventListener("DOMContentLoaded", function() {
        var coll = document.getElementsByClassName("collapsible");
        for (var i = 0; i < coll.length; i++) {
            coll[i].addEventListener("click", function() {
                this.classList.toggle("active");
                var content = this.nextElementSibling;
                if (content.style.display === "block") {
                    content.style.display = "none";
                } else {
                    content.style.display = "block";
                }
            });
        }
    });
    </script>
    """



# Landcover 
def add_landcover_legend(map):
     # National Land Cover Legend
    template = """
    {% macro html(this, kwargs) %}
    
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>jQuery UI Draggable - Default functionality</title>
      <link rel="stylesheet" href="//code.jquery.com/ui/1.12.1/themes/base/jquery-ui.css">
    
      <script src="https://code.jquery.com/jquery-1.12.4.js"></script>
      <script src="https://code.jquery.com/ui/1.12.1/jquery-ui.js"></script>
      
      <script>
      $( function() {
        $( "#maplegend" ).draggable({
                        start: function (event, ui) {
                            $(this).css({
                                right: "auto",
                                top: "auto",
                                bottom: "auto"
                            });
                        }
                    });
    });
    
      </script>
    </head>
    <body>
    
     
    <div id='maplegend' class='maplegend' 
        style='position: absolute; z-index:9999; border:2px solid lightgrey; background-color:rgba(255, 255, 255, 0.8);
         border-radius:6px; padding: 10px; font-size:14px; right: 20px; bottom: 260px;'>
         
    <div class='legend-title'>National Land Cover Legend</div>
    <div class='legend-scale'>
      <ul class='legend-labels'>
        <li><span style='background:#4575b4;opacity:0.7;'></span>Open Water</li>
        <li><span style='background:#ffffff;opacity:0.7;'></span>Perennial Ice/Snow</li>
        <li><span style='background:#fee0d2;opacity:0.7;'></span>Developed, Open Space</li>
        <li><span style='background:#fc9272;opacity:0.7;'></span>Developed, Low Intensity</li>
        <li><span style='background:#ef3b2c;opacity:0.7;'></span>Developed, Medium Intensity</li>
        <li><span style='background:#a50f15;opacity:0.7;'></span>Developed, High Intensity</li>
        <li><span style='background:#f1b6da;opacity:0.7;'></span>Barren Land (Rock/Sand/Clay)</li>
        <li><span style='background:#74c476;opacity:0.7;'></span>Deciduous Forest</li>
        <li><span style='background:#006d2c;opacity:0.7;'></span>Evergreen Forest</li>
        <li><span style='background:#d9f0a3;opacity:0.7;'></span>Mixed Forest</li>
        <li><span style='background:#dfc27d;opacity:0.7;'></span>Dwarf Scrub</li>
        <li><span style='background:#fff7bc;opacity:0.7;'></span>Shrub/Scrub</li>
        <li><span style='background:#d9f0a3;opacity:.85;'></span>Grassland/Herbaceous</li>
        <li><span style='background:#b8e186;opacity:0.7;'></span>Sedge/Herbaceous</li>
        <li><span style='background:#a6d96a;opacity:0.7;'></span>Lichens</li>
        <li><span style='background:#35978f;opacity:0.7;'></span>Moss</li>
        <li><span style='background:#ffff33;opacity:0.7;'></span>Pasture/Hay</li>
        <li><span style='background:#b35806;opacity:0.7;'></span>Cultivated Crops</li>
        <li><span style='background:#d1e5f0;opacity:0.7;'></span>Woody Wetlands</li>
        <li><span style='background:#4393c3;opacity:0.7;'></span>Emergent Herbaceous Wetlands</li>
    
      </ul>
    </div>
    </div>
     
    </body>
    </html>
    
    <style type='text/css'>
      .maplegend .legend-title {
        text-align: left;
        margin-bottom: 5px;
        font-weight: bold;
        font-size: 90%;
        }
      .maplegend .legend-scale ul {
        margin: 0;
        margin-bottom: 5px;
        padding: 0;
        float: left;
        list-style: none;
        }
      .maplegend .legend-scale ul li {
        font-size: 80%;
        list-style: none;
        margin-left: 0;
        line-height: 18px;
        margin-bottom: 2px;
        }
      .maplegend ul.legend-labels li span {
        display: block;
        float: left;
        height: 16px;
        width: 30px;
        margin-right: 5px;
        margin-left: 0;
        border: 1px solid #999;
        }
      .maplegend .legend-source {
        font-size: 80%;
        color: #777;
        clear: both;
        }
      .maplegend a {
        color: #777;
        }
    </style>
    {% endmacro %}
    """
    
    macro = MacroElement()
    macro._template = Template(template)
    
    # Inject the legend HTML into the map's HTML

    map.get_root().add_child(macro)

    return map 

def enable_landcover_legend_interactivity():
    '''
    Javascript code that adds listener to the layer control only after html is fully loaded. Selects elements
    in the layer control class, and listens for when the 'Landcover' layer is selected or unselected. If the 
    layer is checked then makes legend visible, if else then hides legend.
    '''

    return """
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        // Find the checkbox for the landcover layer
        var layersControl = document.querySelectorAll('.leaflet-control-layers-selector');
        var landcoverLayerCheckbox;
        
        layersControl.forEach(function(layer) {
            var label = layer.nextElementSibling.innerHTML.trim();
            if (label === 'National Land Cover (2019)') {
                landcoverLayerCheckbox = layer;
            }
        });

        if (landcoverLayerCheckbox) {
            landcoverLayerCheckbox.addEventListener('change', function() {
                var legend = document.getElementById('maplegend');
                if (landcoverLayerCheckbox.checked) {
                    legend.style.display = 'block';
                } else {
                    legend.style.display = 'none';
                }
            });
        }
    });
    </script>
    """



# handle on_click landcover data request to the server
def on_click_landcover(lat, lon, radius):
        
        # Define the point and buffer region
        point = ee.Geometry.Point(lon, lat)
        buffer = point.buffer(radius)
        region = buffer.bounds()

        # Load the NLCD landcover dataset and select the 'landcover' band
        landcover = (ee.ImageCollection("USGS/NLCD_RELEASES/2019_REL/NLCD")
                    .first()
                    .select('landcover')
                    
        )

        # Reduce the region and get the landcover data
        landcover_data = landcover.reduceRegion(
                                                reducer=ee.Reducer.frequencyHistogram(),
                                                geometry=region,
                                                scale=30,
                                                maxPixels=1e8
                                            ).getInfo()
        print(landcover_data)

        return landcover_data




 # Render html     
def render_html(element_to_render):
    return element_to_render.get_root().render()


def add_Layer_Control(map):
    folium.LayerControl(position='topleft').add_to(map)
    return map



