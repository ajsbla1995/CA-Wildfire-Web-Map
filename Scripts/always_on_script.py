import os
import requests
import time 

# Makes requests to the pythonanywhere.com server to make sure the web map stays on 
url = 'https://ajsbla.pythonanywhere.com'


while True:
    try:
        response = requests.get(url)

        if response == 200:
            print(f"The CA wildfire tracker is up and running, status code: {response.status_code}")
        else:
            print(f"The server returned status code: {response.status_code}")
    except Exception as e:
        print(f"An error occurred: {e}")

    time.sleep(900) # wait 15 minutes until the next ping