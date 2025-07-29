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
import asyncio
import os
import time
from async_create_wildfire_map import *

# Your paths
calfire_geospatial_path = os.path.dirname(os.path.abspath(__file__))
API_key_json = os.path.join(calfire_geospatial_path, 'Data', 'API_keys', 'google_earth_engine_authentication_key.json')
service_account = os.getenv('SERVICE_ACCOUNT')

async def generate_static_firemap():
    start_time = time.time()

    # Load base data
    CA_counties, CA_state, stations, nws_zones, fire_weather_zones = await asyncio.gather(
        asyncio.to_thread(load_county_border_shapefile, calfire_geospatial_path),
        asyncio.to_thread(load_state_border_shapefile, calfire_geospatial_path),
        asyncio.to_thread(load_geocoded_firestations_df, calfire_geospatial_path),
        asyncio.to_thread(load_CA_forecast_zones, calfire_geospatial_path),
        asyncio.to_thread(load_fire_weather_zones, calfire_geospatial_path)
    )

    # Create base map
    m = create_folium_map(CA_counties, CA_state)

    # Use this map name variable for the on-click javascript events
    map_name = m.get_name()
    print(map_name)
    add_title_to_map(m)

    # Authenticate Earth Engine
    auth_and_initialize_earth_engine(API_key_json, service_account)

    # Fire data
    calfire_geojson = await fetch_calfire_geojson()
    perimeters_geojson = await fetch_wildfire_perims_nifc()
    calfire_df = process_geojson_to_df(calfire_geojson)
    perimeters_gdf = process_perimeters_geojson_to_gdf(perimeters_geojson)
    calfire_nifc_gdf_left_joined = left_join_nifc_calfire_gdfs(perimeters_gdf, calfire_df)

    # Fire layers
    add_fires_from_calfire_and_perimeters_from_nifc_to_map(calfire_nifc_gdf_left_joined, m)

    # Metrics
    total_acres = compute_total_acres_for_current_yr(calfire_df)
    total_active_fires = compute_number_of_fires(calfire_df)
    total_cost = compute_total_damage(calfire_nifc_gdf_left_joined)

    acres_burned_image_path = os.path.join(calfire_geospatial_path, 'Data', 'Images', 'forest_fire_emblem Background Removed.png')
    total_cost_image_path = os.path.join(calfire_geospatial_path, 'Data', 'Images', 'house_on_fire Background Removed.png')
    total_active_fires_image_path = os.path.join(calfire_geospatial_path, 'Data', 'Images', 'red_fire Background Removed.png')

    add_metrics_panel(m, total_active_fires, total_acres, total_cost,
                      image_to_base64(acres_burned_image_path),
                      image_to_base64(total_cost_image_path),
                      image_to_base64(total_active_fires_image_path))

    await asyncio.gather(
        add_red_flag_warning('CA', fire_weather_zones, m),
        add_excessive_heat_warning('CA', nws_zones, m)
    )

    add_all_fds_to_map(stations, m)
    get_closest_fds(stations, calfire_df, m)


    # Landcover
    landcover_image = get_landcover()
    landcover_viz = wildfire.landcover_viz()
    add_ee_layer(landcover_image, landcover_viz, 'National Land Cover (2019)', True, m)

    # Sentinel
    sentinel_image, sentinel_image_ndvi = get_sentinel_data()
    add_ee_layer(sentinel_image, band_combinations(['B4', 'B3', 'B2']), 'Sentinel-2 RGB Composite', False, m)
    add_ee_layer(sentinel_image, band_combinations(['B8', 'B4', 'B3']), 'Sentinel-2 False Color Composite', False, m)
    add_ee_layer(sentinel_image, band_combinations(['B12', 'B11', 'B4']), 'Sentinel-2 False Burn Composite', False, m)
    add_ee_layer(sentinel_image_ndvi, ndvi_viz(), 'NDVI', False, m)

    # Controls
    add_Layer_Control(m)
    map_info_button = add_map_information_button(m) # Adds map info button
   #map_info_button_interactive = enable_info_button_interactivity(map_name = m)
    map_info_button_interaction_html = add_map_info_button_with_interactivity(m, map_name)

    landcover_legend = add_landcover_legend(m)
    legend_html = render_html(landcover_legend)
    landcover_control = enable_landcover_legend_interactivity()
    map_html = render_html(m)


    # On-click interactivity for NOAA weather data 
    weather_js = f"""
            <script>
            document.addEventListener('DOMContentLoaded', function () {{
                const mapInterval = setInterval(() => {{
                    if (window.{map_name} && window.{map_name}.on) {{
                        clearInterval(mapInterval);
                        const leafletMap = window.{map_name};

                        leafletMap.on('click', async function (e) {{
                            const lat = e.latlng.lat.toFixed(4);
                            const lon = e.latlng.lng.toFixed(4);

                            L.popup()
                            .setLatLng(e.latlng)
                            .setContent('Fetching weather...')
                            .openOn(leafletMap);

                            try {{
                                const res = await fetch(`/fetch_weather?lat=${{lat}}&lon=${{lon}}`);
                                const data = await res.json();
                                const content = data.error || JSON.stringify(data, null, 2);
                                L.popup()
                                .setLatLng(e.latlng)
                                .setContent(`<pre>${{content}}</pre>`)
                                .openOn(leafletMap);
                            }} catch (err) {{
                                L.popup()
                                .setLatLng(e.latlng)
                                .setContent('Failed to fetch weather.')
                                .openOn(leafletMap);
                            }}
                        }});
                    }}
                }}, 100);
            }});
            </script>
        """
  
    
    

    #final_html = map_html.replace('<body>', '<body>' + landcover_control + legend_html + map_info_button_interactive + weather_js)
    interactivity_html = landcover_control + legend_html 
    final_html = map_html.replace('<body>', '<body>' + interactivity_html)
    #final_html = final_html.replace('</body>', weather_js + '</body>')
    final_html = map_html.replace('</body>', f'{interactivity_html}{weather_js}{map_info_button_interaction_html}</body>') # injects the interactivity HTML into the body of the map html

    # ------------------ Make HTML file and save in appropraite directory ------------------
    # Ensure that there is a static directory for saving the HTML file
    os.makedirs(os.path.join(calfire_geospatial_path, 'static_generated_firemap'), exist_ok=True)
    # Save HTML
    with open(os.path.join(calfire_geospatial_path, 'static_generated_firemap', 'firemap.html'), 'w') as f:
        f.write(final_html)

    elapsed_time = time.time() - start_time
    print(f"Static firemap generated in {elapsed_time:.2f} seconds")

if __name__ == '__main__':
    asyncio.run(generate_static_firemap())