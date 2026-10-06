# SPX Locker Finder


### Introduction:
This project leverages on shopee's SPX API and OneMap.gov's routing, distance measurement, and walk time features to calculate the nearest
Shopee SPX locker based on your regular commute.

### Problem Statement:
SPX Parcel Locator is quite basic and requires manually searching lockers along intended route to find the best one

### Solution:
Find the closest locker by walking distance based on intended regular commute. It might even unlock new lockers unknown to you in your area!

### Set up:
1. Clone this repo
2. Download dependencies using uv sync, uv pip install
3. Setup a secrets folder ./streamlit/secrets.toml file with:
   - your ONEMAP_API key
   - your CARTO_API_KEY
  
   Both of which are free, you just need to sign up through https://carto.com/basemaps/apikey/ and https://www.onemap.gov.sg/apidocs/

4. Hit streamlit run app.py and enjoy

