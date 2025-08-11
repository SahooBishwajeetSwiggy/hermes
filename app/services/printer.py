from collections import defaultdict
from app.services.solver import expand_vehicle_types
from app.services.utils import format_time_window, minutes_to_time_str

def print_solution(data, routing, manager, solution, config):
    (
        _capacities,
        _distances,
        vehicle_type_list,
        vehicle_fixed_costs,
        vehicle_per_delivery_costs,
        vehicle_type_capacities
    ) = expand_vehicle_types(config)

    total_vehicles_used = 0
    total_distance = 0
    total_load = 0
    total_cost = 0
    delivery_count = 0
    dropped_nodes = []

    grouped_data = defaultdict(list)

    print("== Vehicle-wise Routes ==")
    for vehicle_id in range(len(vehicle_type_list)):
        index = routing.Start(vehicle_id)
        route = []
        load = 0
        route_distance = 0
        delivery_points = 0
        cost_per_delivery = 0

        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route.append(node_index)
            load += data["demands"][node_index]
            if node_index != config["depot_index"]:
                delivery_points += 1
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += routing.GetArcCostForVehicle(previous_index, index, vehicle_id)
        route.append(manager.IndexToNode(index))

        if delivery_points == 0:
            cost = 0
        else:
            total_vehicles_used += 1
            fixed = vehicle_fixed_costs[vehicle_id]
            per_delivery = vehicle_per_delivery_costs[vehicle_id]
            cost = fixed + per_delivery * delivery_points
            cost_per_delivery = cost / delivery_points

        # Format route with time windows
        if "time_windows" in data and config["enable_time_windows"]:
            time_dim = routing.GetDimensionOrDie("Time")
            route_with_times = []
            for node in route:
                time_window = data["time_windows"][node]
                # location_str = f"{data["locations"][node]} ({time_window[0]} - {time_window[1]})"
                location_str = format_time_window(data["locations"][node], time_window, config)
                route_with_times.append(location_str)
            readable_route = " -> ".join(route_with_times)
        else:
            readable_route = " -> ".join(data["locations"][node] for node in route)
        
        # Get time information for route start/end
        route_times = {}
        if "time_windows" in data and config["enable_time_windows"]:
            time_dim = routing.GetDimensionOrDie("Time")
            route_times = {
                "start": solution.Min(time_dim.CumulVar(routing.Start(vehicle_id))),
                "end": solution.Max(time_dim.CumulVar(index))
            }

        vehicle_type = vehicle_type_list[vehicle_id]
        grouped_data[vehicle_type].append({
            "vehicle_id": vehicle_id,
            "route": readable_route,
            "load": load,
            "distance": route_distance,
            "deliveries": delivery_points,
            "cost": cost,
            "cost_per_delivery": cost_per_delivery,
            "times": route_times
        })

        total_distance += route_distance
        total_load += load
        total_cost += cost
        delivery_count += delivery_points

    print("\n== Grouped Report ==")
    for vtype, entries in grouped_data.items():
        group_cost = sum(v["cost"] for v in entries)
        group_load = sum(v["load"] for v in entries)
        group_distance = sum(v["distance"] for v in entries)
        group_deliveries = sum(v["deliveries"] for v in entries)
        group_cost_per_delivery = group_cost / group_deliveries if group_deliveries else None

        print(f"\n-- {vtype} --")
        for v in entries:
            if v["deliveries"] == 0:
                continue
            route_info = f"\n  [Vehicle {v['vehicle_id']}] {v['route']}"
            route_info += f"\n  Load: {v['load']} | Distance: {v['distance']} | Deliveries: {v['deliveries']} | Cost: ₹{v['cost']} | Cost Per Delivery: ₹{v['cost_per_delivery']}"
            if v['times']:
                start_time = minutes_to_time_str(v['times']['start'], config)
                end_time = minutes_to_time_str(v['times']['end'], config)
                route_info += f"\n  Route Time: {start_time} - {end_time}"
            print(route_info)
        print(f"\n  Total Load: {group_load} | Total Distance: {group_distance} | Deliveries: {group_deliveries} | Total Cost: ₹{group_cost} | Cost Per Delivery: ₹{group_cost_per_delivery}")

    print("\n== Dropped Deliveries ==")
    for node in range(1, len(data["locations"])):
        index = manager.NodeToIndex(node)
        if solution.Value(routing.NextVar(index)) == index:
            dropped_nodes.append(node)
            print(f"{data['locations'][node]} | Demand: {data['demands'][node]}")
    if not dropped_nodes:
        print("None")

    print("\n== Overall Totals ==")
    print(f"Total Vehicles used: {total_vehicles_used}")
    print(f"Total Distance: {total_distance}")
    print(f"Total Load: {total_load}")
    print(f"Total Deliveries: {delivery_count}")
    print(f"Total Cost: ₹{total_cost}")
    if delivery_count > 0:
        print(f"Average Cost per Delivery: ₹{total_cost / delivery_count:.2f}")
    print()