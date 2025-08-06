import json
import math
from src.config_utils import load_config

DEPOT_LAT = 12.880460
DEPOT_LON = 77.646980
EARTH_RADIUS_KM = 6371.0

def haversine(coord1, coord2):
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def convert_time_to_minutes(time_str):
    try:
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes
    except:
        return None

def calculate_time_offset(time_str, day_start):
    time_str = time_str.split(" ")[1]
    time_minutes = convert_time_to_minutes(time_str)
    start_minutes = convert_time_to_minutes(day_start)
    if time_minutes is not None and start_minutes is not None:
        return max(0, time_minutes - start_minutes)
    return None

def generate_solver_input(input_data):
    config = load_config()
    day_start = config["time_config"]["day_start"]
    
    # Initialize with depot data
    locations = [(DEPOT_LAT, DEPOT_LON)]
    location_labels = ["Depot"]
    demands = [0]  # Depot has zero demand
    amounts = [0]  # Depot has zero amount
    sizes = [None]
    time_windows = [config["time_config"]["depot_window"]]  # Depot time window
    
    # Process each delivery
    for delivery in input_data["deliveries"]:
        locations.append((float(delivery["lat"]), float(delivery["lng"])))
        location_labels.append(delivery["loc"])
        demands.append(int(delivery["wt"]))
        amounts.append(float(delivery["amt"].replace(",", "")))
        sizes.append(int(delivery["sz"]))
        
        # Process time windows
        start_offset = calculate_time_offset(delivery["st"], day_start)
        end_offset = calculate_time_offset(delivery["et"], day_start)
        
        if start_offset is not None and end_offset is not None:
            time_windows.append((start_offset, end_offset))
        else:
            time_windows.append((0, config["working_hours"]))
    
    num_locations = len(locations)
    
    # Calculate distance matrix (in meters)
    distance_matrix = [
        [int(round(haversine(locations[i], locations[j]), 3) * 1000) for j in range(num_locations)]
        for i in range(num_locations)
    ]
    
    # Calculate time matrix (in minutes)
    speed_mpm = (config["average_speed"] * 1000) / 60  # meters per minute
    time_matrix = [
        [int(distance_matrix[i][j] / speed_mpm) for j in range(num_locations)]
        for i in range(num_locations)
    ]
    
    return {
        "distance_matrix": distance_matrix,
        "time_matrix": time_matrix,
        "time_windows": time_windows,
        "demands": demands,
        "amounts": amounts,
        "sizes": sizes,
        "locations": location_labels,
        "coords": locations
    }

def minutes_to_time_str(minutes):
    config = load_config()
    day_start = config["time_config"]["day_start"]
    start_hour, start_min = map(int, day_start.split(':'))
    
    total_minutes = minutes + (start_hour * 60 + start_min)
    hours = total_minutes // 60
    mins = total_minutes % 60
    return f"{hours:02d}:{mins:02d}"

def format_time_window(location_id, time_window):
    start_time = minutes_to_time_str(time_window[0])
    end_time = minutes_to_time_str(time_window[1])
    return f"{location_id}({start_time}-{end_time})"

def expand_vehicle_types(config):
    vehicle_capacities = []
    vehicle_distances = []
    vehicle_type_list = []
    vehicle_fixed_costs = []
    vehicle_per_delivery_costs = []
    vehicle_allowed_sizes = []

    for vehicle_type, props in config["vehicle_types"].items():
        for _ in range(props["count"]):
            vehicle_capacities.append(props["capacity"])
            vehicle_distances.append(props["max_distance"])
            vehicle_type_list.append(vehicle_type)
            vehicle_fixed_costs.append(props.get("fixed_cost", 0))
            vehicle_per_delivery_costs.append(props.get("cost_per_delivery", 0))
            vehicle_allowed_sizes.append(set(props.get("allowed_sizes", [])))

    return vehicle_capacities, vehicle_distances, vehicle_type_list, vehicle_fixed_costs, vehicle_per_delivery_costs, vehicle_allowed_sizes
