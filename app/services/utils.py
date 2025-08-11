import json
import math
import os
import time
import osmnx as ox
import networkx as nx
from functools import lru_cache

EARTH_RADIUS_KM = 6371.0

def build_and_save_graph(OSM_PATH, GRAPHML_PATH):
    print("Building driving network from OSM...")
    G = ox.graph_from_xml(OSM_PATH, simplify=True, retain_all=False)
    ox.save_graphml(G, GRAPHML_PATH)
    return G

def load_graph(OSM_PATH, GRAPHML_PATH):
    if os.path.exists(GRAPHML_PATH):
        print("Loading prebuilt graph...")
        return ox.load_graphml(GRAPHML_PATH)
    else:
        return build_and_save_graph(OSM_PATH, GRAPHML_PATH)

# Cache the road network to avoid loading it multiple times
@lru_cache(maxsize=1)
def get_road_network(OSM_PATH, GRAPHML_PATH):
    """Load the road network from local OSM file."""
    G = load_graph(OSM_PATH, GRAPHML_PATH)
    return G

def haversine(coord1, coord2):
    """Calculate the great circle distance between two points on Earth."""
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

def minutes_to_time_str(minutes, config):
    day_start = config["time_config"]["day_start"]
    start_hour, start_min = map(int, day_start.split(':'))
    
    total_minutes = minutes + (start_hour * 60 + start_min)
    hours = total_minutes // 60
    mins = total_minutes % 60
    return f"{hours:02d}:{mins:02d}"

def format_time_window(location_id, time_window, config):
    start_time = minutes_to_time_str(time_window[0], config)
    end_time = minutes_to_time_str(time_window[1], config)
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


@lru_cache(maxsize=None)
def coord_to_node(coord, OSM_PATH, GRAPHML_PATH):
    """Map (lat, lon) to nearest graph node."""
    return ox.distance.nearest_nodes(get_road_network(OSM_PATH, GRAPHML_PATH), coord[1], coord[0])

def get_all_distances_from(coord, OSM_PATH, GRAPHML_PATH):
    """Compute shortest path distances from one coordinate to all others."""
    G = get_road_network(OSM_PATH, GRAPHML_PATH)
    source_node = coord_to_node(coord, OSM_PATH, GRAPHML_PATH)
    lengths = nx.single_source_dijkstra_path_length(G, source_node, weight="length")
    return lengths

def generate_solver_input(input_data, config, OSM_PATH, GRAPHML_PATH):
    day_start = config["time_config"]["day_start"]
    depot_lat = config.get("latitude", 12.880460) 
    depot_lon = config.get("longitude", 77.646980) 

    # Build location list
    locations = [(depot_lat, depot_lon)]
    location_labels = ["Depot"]
    demands = [0]
    amounts = [0]
    sizes = [None]
    time_windows = [config["time_config"]["depot_window"]]

    for delivery in input_data["deliveries"]:
        locations.append((float(delivery["lat"]), float(delivery["lng"])))
        location_labels.append(delivery["loc"])
        demands.append(int(delivery["wt"]))
        amounts.append(float(delivery["amt"].replace(",", "")))
        sizes.append(int(delivery["sz"]))

        start_offset = calculate_time_offset(delivery["st"], day_start)
        end_offset = calculate_time_offset(delivery["et"], day_start)
        if start_offset is not None and end_offset is not None:
            time_windows.append((start_offset, end_offset))
        else:
            time_windows.append((0, config["working_hours"]))

    num_locations = len(locations)

    # Build distance matrix efficiently
    distance_matrix = [[0] * num_locations for _ in range(num_locations)]
    for i in range(num_locations):
        dist_dict = get_all_distances_from(locations[i], OSM_PATH, GRAPHML_PATH)
        for j in range(i + 1, num_locations):
            node_j = coord_to_node(locations[j], OSM_PATH, GRAPHML_PATH)
            if node_j in dist_dict:
                dist_m = dist_dict[node_j]
            else:
                dist_m = ox.distance.great_circle_vec(
                    locations[i][0], locations[i][1],
                    locations[j][0], locations[j][1]
                )
            dist_km = dist_m / 1000
            dist_mm = int(round(dist_km, 3) * 1000)
            distance_matrix[i][j] = dist_mm
            distance_matrix[j][i] = dist_mm  # symmetry

    # Time matrix from distances
    speed_mpm = (config["average_speed"] * 1000) / 60
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