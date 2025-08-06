import json
import os
from src.solver import create_routing_model
from src.printer import print_solution
from src.solution_formatter import get_dropped_deliveries, format_solution_output
from src.utils import generate_solver_input
from src.config_utils import load_config

INPUT_FILE = "data/input.json"

class RollingSolver:
    def __init__(self):
        self.archive_dir = "archive"
        self.current_dropped_deliveries = []
        self.iteration = 1
    
    def create_iteration_folder(self):
        iter_folder = os.path.join(self.archive_dir, f"iteration_{self.iteration}")
        os.makedirs(iter_folder, exist_ok=True)
        return iter_folder
    
    def save_to_archive(self, iter_folder, data, filename):
        filepath = os.path.join(iter_folder, filename)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
        return filepath
    
    def merge_with_dropped_deliveries(self, input_data):
        if not self.current_dropped_deliveries:
            return input_data
        merged_deliveries = input_data["deliveries"] + self.current_dropped_deliveries
        return {"deliveries": merged_deliveries}
    
    def solve_iteration(self):
        if not os.path.exists(INPUT_FILE):
            raise FileNotFoundError(f"Input file {INPUT_FILE} not found")

        with open(INPUT_FILE, 'r') as f:
            input_data = json.load(f)

        print(f"Input loaded successfully having {len(input_data['deliveries'])} deliveries")

        iter_folder = self.create_iteration_folder()
        self.save_to_archive(iter_folder, input_data, "input.json")
        
        merged_data = self.merge_with_dropped_deliveries(input_data)
        self.save_to_archive(iter_folder, merged_data, "merged_input.json")
        
        solver_input = generate_solver_input(merged_data)
        self.save_to_archive(iter_folder, solver_input, "solver_input.json")
        
        # Create and solve routing model
        routing, manager, solution = create_routing_model(
            solver_input["distance_matrix"],
            solver_input["demands"],
            solver_input["time_matrix"],
            solver_input["time_windows"],
            solver_input["amounts"],
            solver_input["sizes"],
            load_config()
        )
        
        if solution:
            # Print solution
            print_solution(solver_input, routing, manager, solution)
            
            # Format and save solution with vehicle assignments
            formatted_solution = format_solution_output(
                routing, manager, solution, solver_input, merged_data, load_config()
            )
            self.save_to_archive(iter_folder, formatted_solution, "output.json")
            
            # Get dropped deliveries in original format
            self.current_dropped_deliveries = get_dropped_deliveries(
                routing, manager, solution, solver_input, merged_data
            )
            
            # Save dropped deliveries
            if self.current_dropped_deliveries:
                dropped_data = {
                    "fields": input_data.get("fields", {}),
                    "deliveries": self.current_dropped_deliveries
                }
                self.save_to_archive(iter_folder, dropped_data, "dropped.json")
            
            self.iteration += 1
            return True, len(self.current_dropped_deliveries)
        else:
            print("[x] No solution found.")
            return False, 0

def main():
    solver = RollingSolver()
    
    while True:
        try:
            success, dropped_count = solver.solve_iteration()
            if success:
                print(f"\nIteration {solver.iteration-1} completed")
                print(f"Dropped deliveries: {dropped_count}")
                input("\nPress Enter to continue to next iteration...")
            else:
                print("\nFailed to find a solution. Check input data.")
                break
            
        except FileNotFoundError as e:
            print(f"\nError: {str(e)}")
            print("Please place the input file and press Enter to retry...")
            input()
            
        except Exception as e:
            print(f"\nError: {str(e)}")
            break

if __name__ == "__main__":
    main()


"""
To update config :

# Update vehicle count
update_config({"vehicle_types.EV_3W.count": 10})

# Update average speed
update_config({"average_speed": 15})

# Update multiple values
update_config({
    "time_config.day_start": "08:00",
    "time_config.day_end": "17:00",
    "working_hours": 540
})
"""