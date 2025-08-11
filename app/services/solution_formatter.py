from app.services.utils import minutes_to_time_str, expand_vehicle_types, format_time_window

def get_dropped_deliveries(routing, manager, solution, solver_input, merged_data):
    """Get list of dropped deliveries in original format."""
    dropped = []
    
    for node in range(1, len(solver_input["locations"])):
        index = manager.NodeToIndex(node)
        if solution.Value(routing.NextVar(index)) == index:
            # Get the location ID of dropped delivery
            location_id = solver_input["locations"][node]
            # Find corresponding original delivery data
            for delivery in merged_data["deliveries"]:
                if delivery["loc"] == location_id:
                    dropped.append(delivery)
                    break
    
    return dropped

def format_solution_output(routing, manager, solution, solver_input, merged_data, config):
    """Format solution in required JSON format with added vehicle and time info."""
    time_dimension = routing.GetDimensionOrDie("Time")
    vehicle_type_list = expand_vehicle_types(config)[2]
    
    # Format deliveries with vehicle assignments
    deliveries = []
    vehicles_info = []

    # Track vehicle stats
    vehicle_stats = {}

    for vehicle_id in range(routing.vehicles()):
        route = []
        load = 0
        distance = 0
        vehicle_type = vehicle_type_list[vehicle_id]

        if vehicle_id not in vehicle_stats:
            vehicle_stats[vehicle_id] = {
                "vehicle_id": vehicle_id,
                "vehicle_type": vehicle_type,
                "total_load": 0,
                "total_distance": 0,
                "delivery_ids": [],
                "route": {
                    "sequence": [],
                    "start_time": None,
                    "end_time": None,
                    "stops": []
                }
            }

        index = routing.Start(vehicle_id)
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != config["depot_index"]:  # Skip depot
                location_id = solver_input["locations"][node]
                # Find original delivery data
                delivery = next(d for d in merged_data["deliveries"] if d["loc"] == location_id)
                
                # Get time window info
                time_var = time_dimension.CumulVar(index)
                time_min = solution.Min(time_var)
                time_max = solution.Max(time_var)
                planned_time = minutes_to_time_str(time_min, config)

                # Add vehicle and time info to delivery
                delivery_with_vehicle = delivery.copy()
                delivery_with_vehicle["vehicle_id"] = vehicle_id
                delivery_with_vehicle["vehicle_type"] = vehicle_type
                delivery_with_vehicle["planned_time"] = planned_time
                deliveries.append(delivery_with_vehicle)

                # Get stop time window
                time_var = time_dimension.CumulVar(index)
                stop_min = solution.Min(time_var)
                stop_max = solution.Max(time_var)
                
                # Update vehicle stats
                vehicle_stats[vehicle_id]["total_load"] += int(delivery["wt"])
                vehicle_stats[vehicle_id]["delivery_ids"].append(delivery["id"])
                vehicle_stats[vehicle_id]["route"]["sequence"].append(location_id)
                
                # Add stop with time window
                stop_window = format_time_window(location_id, (stop_min, stop_max), config)
                vehicle_stats[vehicle_id]["route"]["stops"].append(stop_window)

            # Update distance and times
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            distance = routing.GetArcCostForVehicle(previous_index, index, vehicle_id)
            vehicle_stats[vehicle_id]["total_distance"] += distance

        # Set route start and end times
        if vehicle_stats[vehicle_id]["delivery_ids"]:  # Only if vehicle is used
            time_var_start = time_dimension.CumulVar(routing.Start(vehicle_id))
            time_var_end = time_dimension.CumulVar(index)  # index is at route end here
            vehicle_stats[vehicle_id]["route"]["start_time"] = minutes_to_time_str(solution.Min(time_var_start), config)
            vehicle_stats[vehicle_id]["route"]["end_time"] = minutes_to_time_str(solution.Max(time_var_end), config)

    # Convert vehicle stats to list
    vehicles = list(vehicle_stats.values())
    
    # Remove empty vehicles
    vehicles = [v for v in vehicles if v["delivery_ids"]]

    return {
        "fields": merged_data.get("fields", {}),  # Preserve field descriptions if present
        "deliveries": deliveries,
        "vehicles": vehicles
    }
