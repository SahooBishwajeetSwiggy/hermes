from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List
import io
import os
from contextlib import redirect_stdout

from app.api.models.routing import RoutingInput, RoutingSolutionOutput
from app.api.auth.permissions import verify_admin_or_warehouse_access
from app.api.routes.auth import get_current_user
from app.api.models.users import UserResponse
from app.db.yaml_config import YamlConfig

from app.services.solver import create_routing_model
from app.services.utils import generate_solver_input
from app.services.printer import print_solution
from app.services.solution_formatter import get_dropped_deliveries, format_solution_output

router = APIRouter()
yaml_config = YamlConfig()

@router.post("/{warehouse_id}/solve", response_model=RoutingSolutionOutput)
async def solve_routing(
    warehouse_id: str,
    routing_input: RoutingInput,
    _: None = Depends(verify_admin_or_warehouse_access),
    current_user: UserResponse = Depends(get_current_user)
):
    # Load warehouse specific configuration
    config = yaml_config.get_warehouse_config(warehouse_id)
    if not config:
        raise HTTPException(status_code=404, detail="Warehouse configuration not found")

    try:
        CITY_NAME = config.get("city")
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__))) 
        OSM_PATH = os.path.join(
            BASE_DIR, "db", "maps", f"{CITY_NAME.lower()}.osm"
        )

        GRAPHML_PATH = os.path.join(
            BASE_DIR, "db", "maps", f"{CITY_NAME.lower()}.graphml"
        )

        # Generate solver input with warehouse-specific config
        solver_input = generate_solver_input(routing_input.dict(), config, OSM_PATH, GRAPHML_PATH)
        
        # Create and solve routing model
        routing, manager, solution = create_routing_model(
            solver_input["distance_matrix"],
            solver_input["demands"],
            solver_input["time_matrix"],
            solver_input["time_windows"],
            solver_input["amounts"],
            solver_input["sizes"],
            config
        )

        if not solution:
            raise HTTPException(status_code=400, detail="No solution found")

        # Capture the printed report
        output = io.StringIO()
        with redirect_stdout(output):
            print_solution(solver_input, routing, manager, solution, config)
        report = output.getvalue()

        # Get dropped deliveries
        dropped = get_dropped_deliveries(routing, manager, solution, solver_input, routing_input.dict())

        # Format solution
        formatted_solution = format_solution_output(routing, manager, solution, solver_input, routing_input.dict(), config)
        
        formatted_solution["report"] = report
        formatted_solution["dropped_deliveries"] = dropped

        return formatted_solution

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
