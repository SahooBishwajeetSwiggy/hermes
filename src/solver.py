from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from src.utils import expand_vehicle_types


def create_routing_model(distance_matrix, demands, time_matrix, time_windows, amounts, config):
    # Initialize vehicle parameters
    vehicle_capacities, vehicle_distances, vehicle_type_list, vehicle_fixed_costs, vehicle_delivery_costs = expand_vehicle_types(config)
    num_vehicles = len(vehicle_capacities)
    config["num_vehicles"] = num_vehicles

    # Create routing model
    manager = pywrapcp.RoutingIndexManager(len(distance_matrix), num_vehicles, config["depot_index"])
    routing = pywrapcp.RoutingModel(manager)

    # 1. Cost Optimization - Primary Objective
    def cost_callback(from_index, to_index):
        try:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            vehicle_idx = routing.VehicleIndex(from_index)
            
            if vehicle_idx < 0 or vehicle_idx >= len(vehicle_delivery_costs):
                return 0

            # Combine distance cost (weighted lower) with delivery and fixed costs
            distance = int(distance_matrix[from_node][to_node])
            distance_cost = int(distance * 0.005)
            delivery_cost = vehicle_delivery_costs[vehicle_idx] if to_node != config["depot_index"] else 0
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
            service_time = config["service_time"] if to_node != config["depot_index"] else 0
            return travel_time + service_time
        except Exception:
            return 0

    time_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.AddDimension(
        time_callback_index,
        config["service_time"],  # allow waiting time
        config["working_hours"],  # maximum time per vehicle
        False,  # Don't force start cumul to zero since we have time windows
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
    # Calculate penalty based on order amount (5% of bill value)
    PROFIT_MARGIN_PERCENT = 10
    
    for node in range(1, len(distance_matrix)):
        order_amount = amounts[node]
        penalty = min(1000, int(order_amount * PROFIT_MARGIN_PERCENT / 100))
        routing.AddDisjunction([manager.NodeToIndex(node)], penalty)

    # Solver settings
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.AUTOMATIC
    search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_parameters.time_limit.seconds = 5

    solution = routing.SolveWithParameters(search_parameters)
    return routing, manager, solution
