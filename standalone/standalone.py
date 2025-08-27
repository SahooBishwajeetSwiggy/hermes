from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Union, Annotated

import os
import json
from datetime import time

VEHICLE_TYPES = {
  "TATA_ACE_4W": {
    "capacity": 900,
    "fixed_cost": 1950,
    "cost_per_delivery": 0,
    "allowed_sizes": [0, 1, 2]
  },
  "EV_3W": {
    "capacity": 450,
    "fixed_cost": 1650,
    "cost_per_delivery": 0,
    "allowed_sizes": [0, 1]
  },
  "BIKE_2W": {
    "capacity": 20,
    "fixed_cost": 400,
    "cost_per_delivery": 60,
    "allowed_sizes": [0]
  }
}

# =========================================================
# ========================= MODEL =========================
# =========================================================


class FieldMapping(BaseModel):
    id: str = Field("Order ID", description="Order ID")
    loc: str = Field("Location ID", description="Location ID")
    st: str = Field("Customer Slot Start", description="Customer Slot Start")
    et: str = Field("Customer Slot End", description="Customer Slot End")
    lat: str = Field("Customer Location Latitude", description="Customer Location Latitude")
    lng: str = Field("Customer Location Longitude", description="Customer Location Longitude")
    amt: str = Field("Amount", description="Amount")
    wt: str = Field("Weight", description="Weight")
    wu: str = Field("Weight Unit", description="Weight Unit")
    pd: str = Field("Customer Promised Date", description="Customer Promised Date")
    sz: str = Field("Size", description="Size")


class DeliveryBase(BaseModel):
    id: str = Field(..., description="Order ID")
    loc: str = Field(..., description="Location ID")
    st: str = Field(..., description="Customer Slot Start (DD/MM/YY HH:MM)")
    et: str = Field(..., description="Customer Slot End (DD/MM/YY HH:MM)")
    lat: Annotated[float, Field(strict=True, ge=-90, le=90)] = Field(..., description="Latitude")
    lng: Annotated[float, Field(strict=True, ge=-180, le=180)] = Field(..., description="Longitude")
    amt: str = Field(..., description="Order amount as string")
    wt: float = Field(..., description="Weight")
    wu: str = Field(..., description="Weight Unit (e.g., KG)")
    pd: str = Field(..., description="Promised Delivery Date and Time (DD/MM/YY HH:MM)")
    sz: Annotated[int, Field(strict=True, ge=0)] = Field(..., description="Size indicator")


class DeliveryInput(DeliveryBase):
    pass


class DeliveryOutput(DeliveryBase):
    vehicle_id: int = Field(..., description="Assigned vehicle ID")
    vehicle_type: str = Field(..., description="Assigned vehicle type")
    planned_time: Annotated[str, Field(pattern=r"^\d{1,2}:\d{2}$")] = Field(..., description="Planned delivery time")


class TimelineEntry(BaseModel):
    node_id: str = Field(..., description="Delivery ID or 'Depot'")
    arrival: str = Field(..., description="Arrival time in format 'HH:MM (X mins)'")
    latest: str = Field(..., description="Latest possible arrival in format 'HH:MM (X mins)'")
    service_time: int = Field(..., description="Service time at this location in minutes")
    travel_time_to_next: int = Field(..., description="Travel time to next location in minutes")


class VehicleRoute(BaseModel):
    sequence: List[str] = Field(..., description="Sequence of location IDs")
    start_time: Annotated[str, Field(pattern=r"^\d{1,2}:\d{2}$")] = Field(..., description="Route start time")
    end_time: Annotated[str, Field(pattern=r"^\d{1,2}:\d{2}$")] = Field(..., description="Route end time")
    latest_end_time: Annotated[str, Field(pattern=r"^\d{1,2}:\d{2}$")] = Field(..., description="Latest possible end time")
    timeline: List[TimelineEntry] = Field(..., description="Detailed timeline of the route")


class VehicleOutput(BaseModel):
    vehicle_id: int = Field(..., description="Vehicle identifier")
    vehicle_type: str = Field(..., description="Type of vehicle")
    total_load: float = Field(..., description="Total weight loaded")
    total_distance: float = Field(..., description="Total distance covered")
    delivery_ids: List[str] = Field(..., description="List of delivery IDs assigned to this vehicle")
    route: VehicleRoute = Field(..., description="Detailed route information")


class Parameters(BaseModel):
    current_time: Annotated[str, Field(pattern=r"^\d{1,2}:\d{2}$")] = Field(..., description="Current time (HH:MM)")
    use_haversine: bool = Field(False, description="Use haversine distance calculation instead of maps")
    enforce_all_deliveries: bool = Field(False, description="Do not allow dropping any deliveries")
    enable_time_windows: bool = Field(False, description="Enable time windows for deliveries")
    optimizing_time_limit: int = Field(20, description="Time limit for optimization in seconds (optimal between 5 and 30)")

    @field_validator('optimizing_time_limit')
    def validate_optimizing_time_limit(cls, v):
        if v <= 15:
            raise ValueError("Optimizing time limit is too low, please set it to more than 15 seconds.")
        elif v > 40:
            raise ValueError("Optimizing time limit is too high, please set it to 40 seconds or less.")
        return v

class TimeWindow(BaseModel):
    start: Annotated[str, Field(pattern=r"^\d{1,2}:\d{2}$")] = Field(..., description="Start time of operations (HH:MM)")
    end: Annotated[str, Field(pattern=r"^\d{1,2}:\d{2}$")] = Field(..., description="End time of operations (HH:MM)")


class WarehouseConfig(BaseModel):
    average_speed: int = Field(10, description="Average vehicle speed in km/h", gt=0)
    service_time: int = Field(5, description="Service time in minutes", gt=0)

    @field_validator('average_speed')
    def validate_speed(cls, v):
        if v <= 0:
            raise ValueError("Average speed must be greater than 0")
        return v

    @field_validator('service_time')
    def validate_times(cls, v):
        if v <= 0:
            raise ValueError("Time values must be greater than 0")
        return v


class WarehouseBase(BaseModel):
    name: str = Field(..., description="Name of the warehouse", example="Main Depot")
    city: str = Field(..., description="City where the warehouse is located", example="Bangalore")
    latitude: float = Field(..., description="Latitude coordinate of the warehouse", example=12.9716)
    longitude: float = Field(..., description="Longitude coordinate of the warehouse", example=77.5946)
    operating_hours: TimeWindow = Field(
        default=TimeWindow(start="09:00", end="18:00"),
        description="Operating hours of the warehouse"
    )
    config: Optional[WarehouseConfig] = Field(
        default=WarehouseConfig(),
        description="Warehouse-specific configuration"
    )


class VehicleBase(BaseModel):
    vehicle_type: str = Field(..., description="Type of vehicle (EV_3W, TATA_ACE_4W, BIKE_2W)", example="EV_3W")
    registration_number: str = Field(..., description="Vehicle registration number", example="KA01AB1234")
    max_distance: int = Field(0, description="Total distance covered today in meters", example=100000)
    capacity: int = Field(0, description="Vehicle capacity in kg", example=1000)

    @field_validator('vehicle_type')
    def validate_vehicle_type(cls, v):
        if v not in VEHICLE_TYPES.keys():
            raise ValueError(f"Invalid vehicle type. Must be one of: {VEHICLE_TYPES.keys()}")
        return v


class RoutingAPIInput(BaseModel):
    warehouse: WarehouseBase
    vehicles: List[VehicleBase]
    fields: FieldMapping = Field(default_factory=FieldMapping)
    deliveries: List[DeliveryInput]
    solver_params: Optional[Parameters] = Field(None, description="Optional solver parameters")


class RoutingAPIOutput(BaseModel):
    vehicles: List[VehicleOutput]
    fields: FieldMapping = Field(default_factory=FieldMapping)
    deliveries: List[DeliveryOutput]
    dropped_deliveries: List[DeliveryInput]
    report: str



# =========================================================
# ========================= ROUTE =========================
# =========================================================

router = APIRouter()

@router.post("/solve", response_model=RoutingAPIOutput)
async def solve_routing(
    routing_input: RoutingAPIInput
):
    warehouse, vehicles, fields, deliveries, solver_params = routing_input.model_dump().values()

    def _calculate_minutes(time_str: str) -> int:
        """Calculate minutes from time string (HH:MM or HH:MM:SS)"""
        parts = time_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        return hours * 60 + minutes

    start = solver_params["current_time"]
    end = warehouse["operating_hours"]["end"]
    working_minutes = (_calculate_minutes(end) - _calculate_minutes(start))

    def _group_vehicles(vehicles):
        """Group vehicles by type and max_distance"""
        grouped = {}
        
        for vehicle in vehicles:
            v_type = vehicle["vehicle_type"]
            max_dist = vehicle["max_distance"]
            capacity = vehicle["capacity"]

            key = (v_type, max_dist, capacity)
            if key not in grouped:
                grouped[key] = 1
            else:
                grouped[key] += 1
        
        return grouped
    
    def _generate_vehicle_config(vehicles, VEHICLE_TYPES):
        """Generate vehicle configuration by combining static and dynamic configs"""
        vehicle_config = {}
        
        grouped_vehicles = _group_vehicles(vehicles)

        for (v_type, max_dist, capacity), count in grouped_vehicles.items():
            static_config = VEHICLE_TYPES[v_type]

            config_key = f"{v_type}_{max_dist}_{capacity}"

            vehicle_config[config_key] = {
                "capacity": capacity,
                "max_distance": max_dist,
                "fixed_cost": static_config["fixed_cost"],
                "cost_per_delivery": static_config["cost_per_delivery"],
                "allowed_sizes": static_config["allowed_sizes"],
                "count": count
            }
        
        return vehicle_config
    
    config = {
        "average_speed": warehouse['config']['average_speed'],
        "depot_index": 0,
        "enable_time_windows": solver_params["enable_time_windows"],
        "service_time": warehouse['config']['service_time'],
        "time_config": {
            "day_start": start,
            "day_end": end,
            "depot_window": [0, working_minutes]
        },
        "vehicle_types": _generate_vehicle_config(vehicles, VEHICLE_TYPES),
        "working_hours": working_minutes,
        "latitude": warehouse["latitude"],
        "longitude": warehouse["longitude"],
        "city": warehouse["city"]
    }

    try:
        CITY_NAME = warehouse["city"]
        BASE_DIR = os.path.dirname(__file__)

        if solver_params['use_haversine']:
            OSM_PATH = None
            GRAPHML_PATH = None
        else:
            OSM_PATH = os.path.join(
                BASE_DIR, "maps", f"{CITY_NAME.lower()}.osm"
            )
            GRAPHML_PATH = os.path.join(
                BASE_DIR, "maps", f"{CITY_NAME.lower()}.graphml"
            )

        solver_input = generate_solver_input(deliveries, config, solver_params["current_time"], OSM_PATH, GRAPHML_PATH, use_haversine=solver_params['use_haversine'])

        # Create and solve routing model
        routing, manager, solution, solution_report, dropped_nodes = create_routing_model(
            solver_input["distance_matrix"],
            solver_input["demands"],
            solver_input["time_matrix"],
            solver_input["time_windows"],
            solver_input["amounts"],
            solver_input["sizes"],
            solver_input["promised_time_deltas"],
            solver_input["delivery_ids"],
            config,
            enforce_all=solver_params["enforce_all_deliveries"],
            optimizing_time_limit=solver_params["optimizing_time_limit"]
        )

        if not solution:
            raise HTTPException(status_code=400, detail="No solution found")

        dropped = expand_deliveries(dropped_nodes, deliveries)

        formatted_solution = format_solution_output(routing, manager, solution, solver_input, routing_input.model_dump(), config)

        formatted_solution["report"] = solution_report
        formatted_solution["dropped_deliveries"] = dropped

        return formatted_solution

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# ========================= UTILS =========================
# =========================================================


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


def expand_deliveries(delivery_ids, deliveries):
    """Expand delivery IDs to include all relevant information."""
    expanded = []
    for delivery in deliveries:
        if delivery["id"] in delivery_ids:
            expanded.append(delivery)

    return expanded


def format_solution_output(routing, manager, solution, solver_input, data, config):
    """Format solution in required JSON format with vehicle and time info."""
    time_dimension = routing.GetDimensionOrDie("Time")
    vehicle_type_list = expand_vehicle_types(config)[2]
    
    deliveries = []
    vehicles = []

    for vehicle_id in range(routing.vehicles()):
        vehicle_type = vehicle_type_list[vehicle_id]
        index = routing.Start(vehicle_id)
        
        # Skip empty routes
        if solution.Value(routing.NextVar(index)) == routing.End(vehicle_id):
            continue

        stats = {
            "vehicle_id": vehicle_id,
            "vehicle_type": vehicle_type,
            "total_load": 0,
            "total_distance": 0,
            "delivery_ids": [],
            "route": {
                "sequence": [],
                "start_time": None,
                "end_time": None,
                "latest_end_time": None,
                "timeline": []
            }
        }

        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            next_index = solution.Value(routing.NextVar(index))
            next_node = manager.IndexToNode(next_index)

            time_var = time_dimension.CumulVar(index)
            min_time = solution.Min(time_var)
            max_time = solution.Max(time_var)
            
            service_time = config["service_time"] if node_index != config["depot_index"] else 0
            travel_time = solver_input["time_matrix"][node_index][next_node] if not routing.IsEnd(next_index) else 0
            
            node_info = {
                "node_id": solver_input["delivery_ids"][node_index],
                "arrival": f"{minutes_to_time_str(min_time, config)} ({min_time} mins)",
                "latest": f"{minutes_to_time_str(max_time, config)} ({max_time} mins)",
                "service_time": service_time,
                "travel_time_to_next": travel_time
            }
            stats["route"]["timeline"].append(node_info)

            if not routing.IsEnd(next_index):
                location_id = solver_input["locations"][next_node]  # Changed from node_index to next_node
                delivery = next(d for d in data["deliveries"] if d["id"] == solver_input["delivery_ids"][next_node])

                planned_time = minutes_to_time_str(min_time + service_time, config)
                delivery_output = {
                    **delivery,
                    "vehicle_id": vehicle_id,
                    "vehicle_type": vehicle_type,
                    "planned_time": planned_time
                }
                deliveries.append(delivery_output)
                
                stats["total_load"] += solver_input["demands"][next_node]
                stats["delivery_ids"].append(solver_input["delivery_ids"][next_node])
                stats["route"]["sequence"].append(location_id)
                
            stats["total_distance"] += solver_input["distance_matrix"][node_index][next_node]
            index = next_index

        if stats["delivery_ids"]:
            end_time_var = time_dimension.CumulVar(index)
            end_min = solution.Min(end_time_var)
            end_max = solution.Max(end_time_var)
            
            final_node_info = {
                "node_id": "Depot",
                "arrival": f"{minutes_to_time_str(end_min, config)} ({end_min} mins)",
                "latest": f"{minutes_to_time_str(end_max, config)} ({end_max} mins)",
                "service_time": 0,
                "travel_time_to_next": 0
            }
            stats["route"]["timeline"].append(final_node_info)
            
            start_var = time_dimension.CumulVar(routing.Start(vehicle_id))
            stats["route"]["start_time"] = minutes_to_time_str(
                solution.Min(start_var), config
            )
            stats["route"]["end_time"] = minutes_to_time_str(
                end_min, config
            )
            stats["route"]["latest_end_time"] = minutes_to_time_str(
                end_max, config
            )
            vehicles.append(stats)

    return {
        "fields": data.get("fields", {}),
        "deliveries": deliveries,
        "vehicles": vehicles
    }

# =========================================================
# ==================== INPUT GENERATION ===================
# =========================================================

import math

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


def calculate_distance_matrix_haversine(locations):
    """Calculate distance matrix using haversine formula"""
    num_locations = len(locations)
    distance_matrix = [[0] * num_locations for _ in range(num_locations)]
    
    for i in range(num_locations):
        for j in range(i + 1, num_locations):
            dist_km = haversine(locations[i], locations[j])
            dist_mm = int(round(dist_km, 3) * 1000)
            distance_matrix[i][j] = dist_mm
            distance_matrix[j][i] = dist_mm
    
    return distance_matrix


def calculate_promised_time_deltas(locations, current_time, promised_times, config):
    """Calculate time deltas between current time and promised delivery time for each location."""
    num_locations = len(locations)
    promised_time_deltas = [0] * num_locations
    
    curr_time_mins = convert_time_to_minutes(current_time)
    if curr_time_mins is None:
        return promised_time_deltas
        
    for j in range(1, num_locations):
        if j >= len(promised_times):
            continue
            
        promised_time = promised_times[j]
        if promised_time:
            try:
                promised_time = promised_time.split(" ")[1]  # Get HH:MM part
                promised_mins = convert_time_to_minutes(promised_time)
                if promised_mins is not None:
                    delta = promised_mins - curr_time_mins
                    promised_time_deltas[j] = delta
            except (IndexError, ValueError):
                continue
    
    return promised_time_deltas


def generate_solver_input(deliveries, config, current_time, OSM_PATH, GRAPHML_PATH, use_haversine = False):
    day_start = config["time_config"]["day_start"]
    depot_lat = config["latitude"]
    depot_lon = config["longitude"]

    locations = [(depot_lat, depot_lon)]
    location_labels = ["Depot"]
    delivery_ids = ["Depot"]
    demands = [0]
    amounts = [0]
    sizes = [None]
    time_windows = [config["time_config"]["depot_window"]]
    promised_times = [""]

    for delivery in deliveries:
        locations.append((float(delivery["lat"]), float(delivery["lng"])))
        location_labels.append(delivery["loc"])
        delivery_ids.append(delivery["id"])
        demands.append(int(delivery["wt"]))
        amounts.append(float(delivery["amt"].replace(",", "")))
        sizes.append(int(delivery["sz"]))
        promised_times.append(delivery["pd"])

        start_offset = calculate_time_offset(delivery["st"], day_start)
        end_offset = calculate_time_offset(delivery["et"], day_start)
        if start_offset is not None and end_offset is not None:
            time_windows.append((start_offset, end_offset))
        else:
            time_windows.append(config["time_config"]["depot_window"])

    num_locations = len(locations)
    
    if use_haversine:
        distance_matrix = calculate_distance_matrix_haversine(locations)
    else:
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

    speed_mpm = (config["average_speed"] * 1000) / 60
    time_matrix = [
        [int(distance_matrix[i][j] / speed_mpm) for j in range(num_locations)]
        for i in range(num_locations)
    ]

    promised_time_deltas = calculate_promised_time_deltas(locations, current_time, promised_times, config)

    return {
        "distance_matrix": distance_matrix,
        "demands": demands,
        "time_matrix": time_matrix,
        "time_windows": time_windows,
        "amounts": amounts,
        "sizes": sizes,
        "promised_time_deltas": promised_time_deltas,
        "locations": location_labels,
        "delivery_ids": delivery_ids
    }


# ==========================================================
# ========================= SOLVER =========================
# ==========================================================

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

# Distance constants
DISTANCE_CONST = 0.002 # ₹2 per km

# Penalty constants
PROFIT_MARGIN_PERCENT = 10
BUFFER_MULTIPLIER = 1.5  # Buffer multiplier for travel time
TIME_INTERVAL_MINUTES = 15  # Every X minutes
PENALTY_PER_INTERVAL = 30  # Base penalty increase per interval


def create_routing_model(distance_matrix, demands, time_matrix, time_windows, amounts, sizes, promised_time_deltas, delivery_ids,config, enforce_all=False, optimizing_time_limit=20):
    vehicle_capacities, vehicle_distances, vehicle_type_list, vehicle_fixed_costs, vehicle_per_delivery_costs, vehicle_allowed_sizes = expand_vehicle_types(config)
    num_vehicles = len(vehicle_capacities)
    
    if promised_time_deltas is None:
        promised_time_deltas = [0] * len(distance_matrix)
    
    # Create routing model
    manager = pywrapcp.RoutingIndexManager(len(distance_matrix), num_vehicles, config["depot_index"])
    routing = pywrapcp.RoutingModel(manager)

    # 0. Enforce size contraint based on vehicle type
    for node in range(1, len(distance_matrix)):  # skip d5epot
        pkg_size = sizes[node]
        if pkg_size is None:
            continue
        for vehicle_id, allowed in enumerate(vehicle_allowed_sizes):
            if pkg_size not in allowed:
                # Prevent this node from being assigned to this vehicle
                routing.VehicleVar(manager.NodeToIndex(node)).RemoveValue(vehicle_id)

    # 1. Cost Optimization - Primary Objective
    def cost_callback(from_index, to_index):
        try:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            vehicle_idx = routing.VehicleIndex(from_index)
            
            if vehicle_idx < 0 or vehicle_idx >= len(vehicle_per_delivery_costs):
                return 0

            # Combine distance cost (weighted lower) with delivery and fixed costs
            distance = int(distance_matrix[from_node][to_node])
            distance_cost = int(distance * DISTANCE_CONST)
            delivery_cost = vehicle_per_delivery_costs[vehicle_idx] if to_node != config["depot_index"] else 0
            fixed_cost = vehicle_fixed_costs[vehicle_idx] if from_node == config["depot_index"] else 0

            return distance_cost + delivery_cost + fixed_cost
        except Exception:
            return 0

    cost_callback_index = routing.RegisterTransitCallback(cost_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(cost_callback_index)

    # 2. Distance Constraint
    def distance_callback(from_index, to_index):
        try:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return int(distance_matrix[from_node][to_node])
        except Exception:
            return 0

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.AddDimension(
        transit_callback_index,
        0,
        max(vehicle_distances),
        True,
        "Distance"
    )
    distance_dimension = routing.GetDimensionOrDie("Distance")
    for vehicle_id, max_dist in enumerate(vehicle_distances):
        distance_dimension.CumulVar(routing.End(vehicle_id)).SetMax(max_dist)

    # 3. Capacity Constraint
    def demand_callback(from_index):
        try:
            return int(demands[manager.IndexToNode(from_index)])
        except Exception:
            return 0

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,
        vehicle_capacities,
        True,
        "Capacity"
    )

    # 4. Time Constraint (including service time and time windows)
    def time_callback(from_index, to_index):
        try:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            travel_time = time_matrix[from_node][to_node]
            return travel_time
        except Exception:
            return 0

    time_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.AddDimension(
        time_callback_index,
        config["service_time"],
        config["working_hours"],  # maximum time per vehicle
        True,
        "Time"
    )

    time_dimension = routing.GetDimensionOrDie("Time")
    
    # Add time window constraints
    if config["enable_time_windows"] and time_windows:
        # Add time window constraints for each location except depot
        for location_idx, time_window in enumerate(time_windows):
            if location_idx == config["depot_index"]:
                continue
            index = manager.NodeToIndex(location_idx)
            time_dimension.CumulVar(index).SetRange(time_window[0], time_window[1])
        
        # Add time window constraints for each vehicle start node (depot)
        depot_time_window = time_windows[config["depot_index"]]
        for vehicle_id in range(num_vehicles):
            index = routing.Start(vehicle_id)
            time_dimension.CumulVar(index).SetRange(
                depot_time_window[0],
                depot_time_window[1]
            )
            
        # Minimize the time span of each vehicle's route
        for vehicle_id in range(num_vehicles):
            routing.AddVariableMinimizedByFinalizer(
                time_dimension.CumulVar(routing.Start(vehicle_id))
            )
            routing.AddVariableMinimizedByFinalizer(
                time_dimension.CumulVar(routing.End(vehicle_id))
            )

    # 5. Optional Deliveries (with penalty for dropping orders)
    # Calculate penalty based on order amount and promised time
    penalties = {}

    # If enforce_all_deliveries is True, set extremely high penalties
    if enforce_all:
        for node in range(1, len(distance_matrix)):
            penalty = 1000000000    # Very high penalty to effectively force inclusion
            penalties[node] = penalty
            routing.AddDisjunction([manager.NodeToIndex(node)], penalty)

    else:
        for node in range(1, len(distance_matrix)):
            order_amount = amounts[node]
            base_penalty = min(250, int(order_amount * PROFIT_MARGIN_PERCENT / 100))
            
            travel_time = time_matrix[config['depot_index']][node]
            buffered_travel_time = int(travel_time * BUFFER_MULTIPLIER)
            promised_time_delta = promised_time_deltas[node]
            
            if promised_time_delta <= buffered_travel_time:
                time_difference = buffered_travel_time - promised_time_delta
                num_intervals = time_difference // TIME_INTERVAL_MINUTES + 1
                
                urgency_penalty = PENALTY_PER_INTERVAL * (2 ** num_intervals)
                penalty = base_penalty + urgency_penalty

            else:
                penalty = base_penalty

            penalties[node] = penalty

            routing.AddDisjunction([manager.NodeToIndex(node)], penalty)

    # Solver settings
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_parameters.time_limit.seconds = optimizing_time_limit


    solution = routing.SolveWithParameters(search_parameters)
    
    solution_report = ""
    if solution:
        time_dimension = routing.GetDimensionOrDie("Time")
        solution_report += ("\n=== SOLUTION ANALYSIS ===\n")

        # Track dropped nodes
        dropped_nodes = []
        served_nodes = []
        
        for node in range(1, len(distance_matrix)):
            index = manager.NodeToIndex(node)
            if routing.IsStart(index) or routing.IsEnd(index):
                continue
            
            if solution.Value(routing.NextVar(index)) == index:
                depot_index = config["depot_index"]
                delivery_id = delivery_ids[node]
                dropped_nodes.append(delivery_id)
                solution_report += (f"\nOrder {delivery_id} was DROPPED:\n")
                solution_report += (f"  Order Details:\n")
                solution_report += (f"    Amount: ₹{amounts[node]}\n")
                solution_report += (f"    Weight: {demands[node]} kg\n")
                if time_windows and config["enable_time_windows"]:
                    solution_report += (f"    Time Window: {time_windows[node]}\n")
                    solution_report += (f"    Travel Time from Depot: {time_matrix[depot_index][node]} minutes\n")
                
                # Calculate distance metrics
                depot_to_node = distance_matrix[depot_index][node]
                node_to_depot = distance_matrix[node][depot_index]
                total_distance = depot_to_node + node_to_depot
                
                solution_report += (f"\n  Constraints Analysis:\n")
                
                # 1. Check Size Constraints
                size = sizes[node]
                suitable_vehicles = []
                for v_id, allowed_sizes in enumerate(vehicle_allowed_sizes):
                    if size in allowed_sizes:
                        suitable_vehicles.append(vehicle_type_list[v_id])
                
                if not suitable_vehicles:
                    solution_report += (f"    ✘ Size Constraint: Package size {size} not supported by any vehicle\n")
                else:
                    solution_report += (f"    ✔ Size Constraint: Package size {size} supported by {', '.join(suitable_vehicles)}\n")
                
                # 2. Check Weight Constraints
                weight_suitable = []
                for v_id, cap in enumerate(vehicle_capacities):
                    if demands[node] <= cap:
                        weight_suitable.append(f"{vehicle_type_list[v_id]} ({cap}kg)")
                
                if not weight_suitable:
                    solution_report += (f"    ✘ Weight Constraint: Order weight {demands[node]}kg exceeds all vehicle capacities\n")
                else:
                    solution_report += (f"    ✔ Weight Constraint: Order weight suitable for {', '.join(weight_suitable)}\n")
                
                # 3. Check Distance Constraints
                distance_suitable = []
                for v_id, max_dist in enumerate(vehicle_distances):
                    if total_distance <= max_dist:
                        distance_suitable.append(f"{vehicle_type_list[v_id]} ({max_dist/1000:.1f}km)")
                
                if not distance_suitable:
                    solution_report += (f"    ✘ Distance Constraint: Round trip distance {total_distance/1000:.1f}km exceeds all vehicle limits\n")
                else:
                    solution_report += (f"    ✔ Distance Constraint: Distance {total_distance/1000:.1f}km suitable for {', '.join(distance_suitable)}\n")
                
                # 4. Check Time Window Constraints if enabled
                if time_windows and config["enable_time_windows"]:
                    start_time, end_time = time_windows[node]
                    service_duration = config["service_time"]
                    travel_time = time_matrix[depot_index][node]
                    
                    if end_time - start_time < service_duration:
                        solution_report += (f"    ✘ Time Window Constraint: Service time ({service_duration}min) exceeds available window ({end_time - start_time}min)\n")
                    elif travel_time > end_time:
                        solution_report += (f"    ✘ Time Window Constraint: Minimum travel time ({travel_time}min) exceeds latest allowed arrival ({end_time}min)\n")
                    else:
                        solution_report += (f"    ✔ Time Window Constraint: Delivery possible within time window\n")
                
                # 5. Cost Analysis
                solution_report += (f"\n  Cost Analysis:\n")
                min_direct_distance_cost = int((total_distance) * DISTANCE_CONST)
                solution_report += (f"    Base Distance Cost: ₹{min_direct_distance_cost}\n")
                
                vehicle_costs = []
                feasible_vehicles = []
                
                for v_id, (v_cap, v_dist) in enumerate(zip(vehicle_capacities, vehicle_distances)):
                    if demands[node] <= v_cap and total_distance <= v_dist and size in vehicle_allowed_sizes[v_id]:
                        total_cost = (min_direct_distance_cost + 
                                   vehicle_fixed_costs[v_id] + 
                                   vehicle_per_delivery_costs[v_id])
                        vehicle_costs.append((v_id, total_cost))
                        feasible_vehicles.append(
                            f"{vehicle_type_list[v_id]} (Fixed: ₹{vehicle_fixed_costs[v_id]}, "
                            f"Per Delivery: ₹{vehicle_per_delivery_costs[v_id]}, "
                            f"Total: ₹{total_cost})"
                        )
                
                if feasible_vehicles:
                    solution_report += ("    Feasible Vehicle Options:\n")
                    for desc in feasible_vehicles:
                        solution_report += (f"      • {desc}\n")
                    best_vehicle, best_cost = min(vehicle_costs, key=lambda x: x[1])
                    solution_report += (f"\n    Best Option: {vehicle_type_list[best_vehicle]} at ₹{best_cost}\n")
                else:
                    solution_report += ("    ✘ No feasible vehicle options due to combined constraints!\n")
                
                # 6. Final Drop Reason
                solution_report += ("\n  Primary Drop Reason(s):\n")
                if not feasible_vehicles:
                    reasons = []
                    if not suitable_vehicles:
                        reasons.append("No vehicles support the package size")
                    if not weight_suitable:
                        reasons.append("Package weight too high")
                    if not distance_suitable:
                        reasons.append("Delivery distance too far")
                    solution_report += (f"    • {' and '.join(reasons)}\n")
                else:
                    solution_report += (f"    • Order was dropped to optimize overall solution cost\n")
                    solution_report += (f"    • Penalty for dropping (₹{penalties[node]}) was less than cost of service (₹{best_cost})\n")
            else:
                served_nodes.append(node)
        
        solution_report += (f"\nSummary:\n")
        solution_report += (f"Total Orders: {len(distance_matrix) - 1}\n")  # minus depot
        solution_report += (f"Served Orders: {len(served_nodes)}\n")
        solution_report += (f"Dropped Orders: {len(dropped_nodes)}\n")
        if dropped_nodes:
            solution_report += (f"Dropped Order IDs: {dropped_nodes}\n")
        
        # Print route costs
        for vehicle_id in range(num_vehicles):
            index = routing.Start(vehicle_id)
            route_load = 0
            route_distance = 0

            if solution.Value(routing.NextVar(index)) != routing.End(vehicle_id):
                solution_report += (f"\nVehicle {vehicle_id} ({vehicle_type_list[vehicle_id]}):\n")
                route_ids = []

                while not routing.IsEnd(index):
                    node_index = manager.IndexToNode(index)
                    next_index = solution.Value(routing.NextVar(index))
                    next_node = manager.IndexToNode(next_index)
                    if not routing.IsEnd(next_index):
                        route_load += demands[next_node]
                        route_ids.append(delivery_ids[next_node])
                        
                    route_distance += distance_matrix[node_index][next_node]
                    index = next_index

                time_var = time_dimension.CumulVar(routing.End(vehicle_id))
                route_time = solution.Min(time_var)

                solution_report += (f"  Route: {' > '.join(route_ids)}\n")
                solution_report += (f"  Route Load: {route_load}/{vehicle_capacities[vehicle_id]}\n")
                solution_report += (f"  Route Distance: {route_distance}/{vehicle_distances[vehicle_id]}\n")
                solution_report += (f"  Route Time: {route_time}/{config['working_hours']}\n")

    if dropped_nodes:
        solution_report += f"If some orders were dropped but you wanted to include them or you have chosen to enforce all deliveries, please verify the capacity of all the vehicles and allocate more resources accordingly.\n"

    return routing, manager, solution, solution_report, dropped_nodes
