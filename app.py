# app.py
import streamlit as st
import folium
from streamlit_folium import st_folium
import polyline
from folium.plugins import BeautifyIcon

from services import (
    search_location_coordinates,
    get_routing_itinerary,
    extract_transition_points,
    rank_lockers_by_actual_walk,
)
st.set_page_config(page_title="SPX Locker & Route Finder", layout="wide")

def get_secret(key_name: str) -> str:
    if key_name in st.secrets:
        return st.secrets[key_name]
    st.error(
        f"Secret `{key_name}` missing! Please add it to `.streamlit/secrets.toml`.")
    st.stop()
    
ONEMAP_API = get_secret("ONEMAP_API")
CARTO_API_KEY = get_secret("CARTO_API_KEY")

carto_positron_url = f"https://basemaps.cartocdn.com/rastertiles/light_all/{{z}}/{{x}}/{{y}}.png?key={CARTO_API_KEY}"

def get_distance_color(dist_m: float) -> str:
    """Returns hex color code based on walking distance in meters."""
    if dist_m <= 300:
        return "#28a745"
    elif dist_m <= 600:
        return "#e0a800"
    else:
        return "#dc3545"


def build_route_map(start_coords, end_coords, itinerary, lockers, tile_config=None):
    mid_lat = (start_coords[0] + end_coords[0]) / 2
    mid_lon = (start_coords[1] + end_coords[1]) / 2

    # Map Tile Setup
    if tile_config:
        m = folium.Map(location=[mid_lat, mid_lon], zoom_start=13,
                       tiles=tile_config["tiles"], attr=tile_config["attr"])
    else:
        # Default to CARTO Positron
        m = folium.Map(
            location=[mid_lat, mid_lon],
            zoom_start=13,
            tiles=carto_positron_url,
            attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
        )

    # 1. Draw Route Lines
    for leg in itinerary.get("legs", []):
        mode = leg.get("mode")
        color = "#38ef7d" if mode in {
            "BUS", "SUBWAY", "TRANSIT", "RAIL"} else "#a8a8a8"
        dash_array = "5, 5" if mode == "WALK" else None

        geom = leg.get("legGeometry", {}).get("points")
        if geom:
            coords = polyline.decode(geom)
            folium.PolyLine(coords, color=color, weight=5,
                            opacity=0.8, dash_array=dash_array).add_to(m)

    # 2. Start & Destination Pins
    folium.Marker(start_coords, tooltip="Start Location", icon=folium.Icon(
        color="green", icon="play", prefix="fa")).add_to(m)
    folium.Marker(end_coords, tooltip="Destination", icon=folium.Icon(
        color="red", icon="flag", prefix="fa")).add_to(m)

    # 3. Numbered & Color-Coded SPX Locker Pins
    for idx, loc in enumerate(lockers, 1):
        dist_m = loc.get("actual_walk_dist_m", loc.get("h_dist", 0))
        color_hex = get_distance_color(dist_m)

        # Custom Numbered Pin
        numbered_icon = BeautifyIcon(
            number=idx,
            border_color=color_hex,
            background_color=color_hex,
            text_color="#ffffff",
            icon_shape="marker",
            inner_icon_style="margin-top:0px; font-weight:bold;",
        )

        popup_html = f"""
        <div style="font-family: sans-serif; width: 210px;">
            <h4 style="margin: 0 0 6px 0; color: {color_hex};">#{idx}. {loc['name']}</h4>
            <p style="margin: 2px 0;"><b>Walk Distance:</b> {dist_m}m (~{loc['walk_mins']} mins)</p>
            <p style="margin: 2px 0;"><b>Near Stop:</b> {loc['closest_wpt_name']}</p>
            <p style="margin: 2px 0; font-size: 12px; color: #555;"><b>Address:</b> {loc['address']}</p>
        </div>
        """

        folium.Marker(
            location=[loc["lat"], loc["lon"]],
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"#{idx} {loc['name']} ({dist_m}m walk)",
            icon=numbered_icon
        ).add_to(m)

    return m


# Streamlit Layout
st.title("📦 SPX Locker & Route Finder")

with st.sidebar:
    st.header("Search Parameters")
    start_input = st.text_input("Start Location", "ang mo kio community centre")
    end_input = st.text_input("End Location", "1 Fusionopolis")
    search_radius = st.slider(
        "Locker Search Radius (meters)", 100, 1000, 500, step=50)
    search_btn = st.button("Find Route & Lockers", type="primary")

    st.markdown("---")
    st.markdown("### 📍 Locker Distance Legend")
    st.markdown("🟢 **100m – 300m**: closeby (~1–3 mins)")
    st.markdown("🟡 **400m – 600m**: moderate (~4–7 mins)")
    st.markdown("🔴 **> 600m**: far (> 7 mins)")

if search_btn or "app_data" not in st.session_state:
    with st.spinner("Calculating route and discovering lockers..."):
        try:
            start_coords = search_location_coordinates(start_input, ONEMAP_API)
            end_coords = search_location_coordinates(end_input, ONEMAP_API)
            itinerary = get_routing_itinerary(
                start_coords,
                end_coords,
                time_str="14:00:00")
            
            waypoints = extract_transition_points(itinerary)
            ranked_lockers = rank_lockers_by_actual_walk(waypoints,
                                                         haversine_max_m=search_radius,
                                                         api_token=ONEMAP_API)

            st.session_state["app_data"] = {
                "start_coords": start_coords,
                "end_coords": end_coords,
                "itinerary": itinerary,
                "waypoints": waypoints,
                "ranked_lockers": ranked_lockers
            }
        except Exception as err:
            st.error(f"Error: {err}")
            st.stop()

data = st.session_state.get("app_data")

if data:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Route Map")
        m = build_route_map(data["start_coords"], data["end_coords"],
                            data["itinerary"], data["ranked_lockers"])
        st_folium(m, width="100%", height=800)

    with col2:
        st.subheader(f"Lockers ({len(data['ranked_lockers'])})")
        for idx, item in enumerate(data["ranked_lockers"][:10], 1):
            with st.expander(f"#{idx} {item['name']} — {item['h_dist']}m"):
                st.write(f"**Walk:** ~{item['walk_mins']} mins")
                st.write(f"**Address:** {item['address']}")
