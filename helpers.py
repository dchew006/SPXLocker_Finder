import requests
from datetime import datetime
import math

def find_lockers(lat, long, radius=500000):
    
    url = "https://spx.sg/api/service-point/point/around/list"


    params = {
        "radius": str(radius),
        "latitude": str(lat),
        "longitude": str(long),
        "selected_radius": "4000",
        "service_type_facility": "2",
        "distance_latitude": str(lat),
        "distance_longitude": str(long),
        "support_self_collection": "1",
    }

    headers = {
        'accept': "application/json, text/plain, */*",
        'cookie': "fms_language=sg",
        'user-agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/27.0 Safari/605.1.15",
        'referer': "https://spx.sg/service-point/around",
    }

    response = requests.get(url, params=params, headers=headers)
    if response.status_code == 200:
        print(response.json())
    else:
        print(f"Error fetching lockers ({response.status_code}): {response.text}")
        return None
    

def search_location_coordinates(search, onemap_api):
    # url = f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={search}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
    url = "https://www.onemap.gov.sg/api/common/elastic/search"
    params = {
        "searchVal": search,
        "returnGeom": "Y",
        "getAddrDetails": "Y",
        "pageNum": 1
    }
    headers = {"Authorization": onemap_api}
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    results = response.json().get("results", [])

    if not results:
        raise ValueError(f"No results found for search query: {search}")
    
    first_result = results[0]
    return float(first_result.get("LATITUDE")), float(first_result.get("LONGITUDE"))


def get_routing_itinerary(start_coordinates, end_coordinates, date_str=None, time_str=None):

    now = datetime.now()
    url = "https://www.onemap.gov.sg/api/public/routingsvc/route"
    params = {
        "start": f"{start_coordinates[0]},{start_coordinates[1]}",
        "end": f"{end_coordinates[0]},{end_coordinates[1]}",
        "routeType": "pt",
        "mode": "TRANSIT",
        "maxWalkDistance": "1000",
        "numItineraries": "1",
        "date": date_str or now.strftime("%m-%d-%Y"),
        "time": time_str or now.strftime("%H:%M:%S"),
    }
    headers = {"Authorization": onemap_api}
    if not headers["Authorization"]:
        raise ValueError("Onemap API key is required")
    
    response = requests.request("GET", url, headers=headers, params=params)
    response.raise_for_status()

    itineraries = response.json().get("plan", {}).get("itineraries", [])
    if not itineraries:
        raise ValueError("No itineraries found for the given route")
    return itineraries[0]


def get_walk_route_info(
    start_coordinates,
    end_coordinates,
    onemap_api):
    
    url = "https://www.onemap.gov.sg/api/public/routingsvc/route"
    params = {
        "start": f"{start_coordinates[0]},{start_coordinates[1]}",
        "end": f"{end_coordinates[0]},{end_coordinates[1]}",
        "routeType": "walk",
    }
    headers = {"Authorization": onemap_api}
    

    try:
            response = requests.get(url, params=params, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()

            if "route_summary" in data:
                return {
                    "distance_m": data["route_summary"]["total_distance"],
                    "duration_s": data["route_summary"]["total_time"],
                }
            elif "plan" in data and data["plan"].get("itineraries"):
                itinerary = data["plan"]["itineraries"][0]
                return {
                    "distance_m": itinerary.get("walkDistance", 0),
                    "duration_s": itinerary.get("duration", 0),
                }
    except requests.RequestException as exc:
        print(f"OneMap Walk API warning: {exc}")

    return None



def haversine_distance(lat1, lon1, lat2, lon2):
    """straightline distance in meters between two geographic coordinates"""
    earth_radius_m = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * \
        math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * earth_radius_m * math.atan2(math.sqrt(a), math.sqrt(1 - a))



def extract_transition_points(itinerary: dict) -> list:
    waypoints = []
    seen_coords = set()
    
    def add_waypoint(name, lat, lon, wpt_type):
        key = (round(float(lat), 6), round(float(lon), 6))
        if key not in seen_coords:
            seen_coords.add(key)
            waypoints.append({
                "name": name,
                "lat": float(lat),
                "lon": float(lon),
                "type": wpt_type
            })
            
    legs = itinerary.get("legs", [])
    if not legs:
        return waypoints
    
    # 1. Origin
    origin_node = legs[0].get("from", {})
    add_waypoint(origin_node.get("name", "Origin"),
                 origin_node["lat"], origin_node["lon"], "ORIGIN")
    
    
    # 2. intermediate leg transitions
    for leg in legs:
        mode = leg.get("mode")
        from_node = leg.get("from", {})
        to_node = leg.get("to", {})
        
        if mode == "WALK":
            for step in leg.get("steps", []):
                if step.get("lat") and step.get("lon"):
                    add_waypoint(
                        f"Walk Path ({step.get('streetName', 'path')})",
                        step["lat"],
                        step["lon"],
                        "WALK_WAYPOINT"
                    )
            add_waypoint(to_node.get("name", "Walk Stop"),
                         to_node["lat"],
                         to_node["lon"],
                         "WALK_TRANSITION")
            
        elif mode in {"BUS", "SUBWAY", "TRANSIT", "RAIL"}:
            add_waypoint(from_node.get("name", "Boarding"),
                         from_node["lat"],
                         from_node["lon"],
                         "TRANSIT_BOARDING")
            add_waypoint(to_node.get("name", "Alighting"),
                         to_node["lat"],
                         to_node["lon"],
                         "TRANSIT_ALIGHTING")
            
    # 3. Destination
    dest_node = legs[-1].get("to", {})
    add_waypoint(dest_node.get("name", "Destination"),
                 dest_node["lat"],
                 dest_node["lon"],
                 "DESTINATION")

    return waypoints

def fetch_spx_lockers(lat, lon, radius_meters=1000):
    '''fetch all nearby SPX lockers '''
    
    url = "https://spx.sg/api/service-point/point/around/list"
    params = {
        "radius": str(radius_meters),
        "latitude": str(lat),
        "longitude": str(lon),
        "selected_radius": str(radius_meters),
        "service_type_facility": "2",
        "support_self_collection": "1",
    }
    headers = {
        'accept': 'application/json, text/plain, */*',
        'cookie': 'fms_language=sg',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15',
        'referer': 'https://spx.sg/service-point/around',
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        
        if data.get("retcode") == 0:
            return data.get("data", {}).get("list", [])
    
    except requests.RequestException as e:
        print(f"SPX API Request Error: {e} at ({lat}, {lon})")
    
    return []

def collect_unique_locker_candidates(waypoints: list, max_radius_m: int):
    ''' finds unique locker candidates within max radius'''
    candidates = {}
    
    for wpt in waypoints:
        raw_lockers = fetch_spx_lockers(
            wpt["lat"],
            wpt["lon"],
            radius_meters=max_radius_m
        )
        
        for locker in raw_lockers:
            p_lat = float(locker.get("latitude") or locker.get("lat") or 0)
            p_lon = float(locker.get("longitude") or locker.get("lng") or 0)

            if not p_lat or not p_lon:
                continue
        
            locker_id = (
                locker.get("id")
                or locker.get("service_point_id")
                or locker.get("sp_id")
                or locker.get("code")
                or f"{locker.get('name')}_{p_lat}_{p_lon}"
            )
            
            h_dist = haversine_distance(wpt["lat"], wpt["lon"], p_lat, p_lon)
            if h_dist > max_radius_m:
                continue
            
            if locker_id not in candidates or h_dist < candidates[locker_id]["h_dist"]:

                candidates[locker_id] = {
                    "id": locker_id,
                    "name": locker.get("name", "SPX Locker"),
                    "address": locker.get("address", ""),
                    "lat": p_lat,
                    "lon": p_lon,
                    "h_dist": h_dist,
                    "closest_wpt_name": wpt["name"],
                    "closest_wpt_coords": (wpt["lat"], wpt["lon"]),
                    "wpt_type": wpt["type"],
                    "operating_hours": locker.get("operation_time", "N/A")
                }

    return candidates

def rank_lockers_by_actual_walk(waypoints,
                                api_token,
                                haversine_max_m = 500):
    
    '''find unique lockers along route waypoints, rank them by walking distance'''
    
    candidates = collect_unique_locker_candidates(waypoints, haversine_max_m)
    ranked_list = []
    
    for item in candidates.values():
        wpt_coords = item["closest_wpt_coords"]
        locker_coords = (item["lat"], item["lon"])
        
        walk_info = get_walk_route_info(wpt_coords, locker_coords, api_token)
        
        if walk_info:
            walk_dist_m = walk_info["distance_m"]
            walk_dur_s = walk_info["duration_s"]
            
        else:
            walk_dist_m = round(item['h_dist'],1)
            walk_dur_s = int(item["h_dist"] / 1.2) # assuming average walking speed of 1.2 m/s
            
        item['actual_walk_dist_m'] = walk_dist_m
        item['actual_walk_dur_s'] = walk_dur_s
        item['acutal_walk_mins'] = round(walk_dur_s / 60, 1)
        
        ranked_list.append(item)
        
    ranked_list.sort(key=lambda x: x['actual_walk_dist_m'])
    return ranked_list
    
    
def main():
    
    # define start and end locations
    start_location = "Ghim Moh Market"
    end_location = "Junction 8"
    
    
    # fetch start, end coordinates
    start_coordinates = search_location_coordinates(start_location, onemap_api)
    end_coordinates = search_location_coordinates(end_location, onemap_api)
    
    # get transit itinerary and waypoints
    route_itinerary = get_routing_itinerary(
        start_coordinates,
        end_coordinates
    )
    waypoints = extract_transition_points(route_itinerary)
    print(f"Extracted waypoints: {waypoints}")

    # find and rank lockers
    ranked_lockers = rank_lockers_by_actual_walk(
        waypoints,
        api_token = onemap_api,
        haversine_max_m = 500
    )
    print(
        f"Found {len(ranked_lockers)} unique lockers near your route waypoints.")
    for idx, locker in enumerate(ranked_lockers[:10], 1):
        print(
            f"{idx}. {locker['name']} — "
            f"{locker['actual_walk_dist_m']}m ({locker['acutal_walk_mins']} mins walk) "
            f"from '{locker['closest_wpt_name']}'"
            f"locker_coords: ({locker['lat']}, {locker['lon']})"
        )
    
if __name__ == "__main__":
    main()