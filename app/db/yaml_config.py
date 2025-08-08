import yaml
from pathlib import Path
from typing import Dict, List, Union, Optional

class YamlConfig:
    def __init__(self, db_path: str = "app/db/data"):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)

    def _get_config_path(self, warehouse_id: str) -> Path:
        return self.db_path.parent / "warehouse_configs" / f"{warehouse_id}.yaml"

    def _get_global_config_path(self) -> Path:
        return self.db_path.parent / "global_config.yaml"

    def _ensure_config_dir(self):
        config_dir = self.db_path.parent / "warehouse_configs"
        config_dir.mkdir(parents=True, exist_ok=True)

    def _read_yaml(self, path: Path) -> Dict:
        if not path.exists():
            return {}
        with open(path, 'r') as f:
            return yaml.safe_load(f) or {}

    def _write_yaml(self, path: Path, data: Dict):
        yaml.add_representer(
            list,
            lambda dumper, data: dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)
        )

        with open(path, 'w') as f:
            yaml.dump(data, f, sort_keys=False, default_flow_style=False)

    def _delete_warehouse_config(self, warehouse_id: str):
        config_path = self._get_config_path(warehouse_id)
        if config_path.exists():
            config_path.unlink()

    def get_global_config(self) -> Dict:
        """Get the global configuration from global_config.yaml"""
        return self._read_yaml(self._get_global_config_path())

    def get_warehouse_config(self, warehouse_id: str = None) -> Union[Dict, List[Dict]]:
        """Get configuration for a specific warehouse or all warehouses"""
        self._ensure_config_dir()
        
        if warehouse_id:
            config_path = self._get_config_path(warehouse_id)
            return self._read_yaml(config_path)
        
        # If no warehouse_id provided, return all configs
        configs = []
        config_dir = self.db_path.parent / "warehouse_configs"
        for config_file in config_dir.glob("*.yaml"):
            warehouse_id = config_file.stem
            config = self._read_yaml(config_file)
            config["warehouse_id"] = warehouse_id
            configs.append(config)
        return configs

    def _calculate_minutes(self, time_str: str) -> int:
        """Calculate minutes from time string (HH:MM or HH:MM:SS)"""
        parts = time_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        return hours * 60 + minutes
    
    def update_warehouse_config(self, warehouse_id: str, db=None):
        """Update or create configuration for a warehouse"""
        self._ensure_config_dir()
        
        global_config = self.get_global_config()
        vehicle_types = global_config.get("vehicle_types", {})
        
        warehouse = db.find_one("warehouses", {"id": warehouse_id}) if db else None

        start_time = "09:00"
        end_time = "18:00"
        if warehouse and "operating_hours" in warehouse:
            start_time_parts = warehouse["operating_hours"]["start"].split(".")[0].split(":")[0:2]
            end_time_parts = warehouse["operating_hours"]["end"].split(".")[0].split(":")[0:2]
            start_time = ":".join(start_time_parts)
            end_time = ":".join(end_time_parts)

        # Create base config
        new_config = {
            "average_speed": int(warehouse.get("config", {}).get("average_speed", 10)) if warehouse else 10,
            "depot_index": warehouse.get("config", {}).get("depot_index", 0) if warehouse else 0,
            "enable_time_windows": warehouse.get("config", {}).get("enable_time_windows", True) if warehouse else True,
            "service_time": warehouse.get("config", {}).get("service_time", 5) if warehouse else 5,
            "time_config": {
                "day_start": start_time,
                "day_end": end_time,
            },
            "vehicle_types": {}
        }

        start_minutes = self._calculate_minutes(start_time)
        end_minutes = self._calculate_minutes(end_time)
        working_minutes = end_minutes - start_minutes
        new_config["working_hours"] = working_minutes
        new_config["time_config"]["depot_window"] = [0, working_minutes]

        existing_config = self._read_yaml(self._get_config_path(warehouse_id))
        if existing_config:
            for key in ["average_speed", "depot_index", "enable_time_windows", 
                        "service_time", "working_hours", "time_config"]:
                if key in existing_config:
                    new_config[key] = existing_config[key]

        if warehouse and "operating_hours" in warehouse:
            start_time_parts = warehouse["operating_hours"]["start"].split(".")[0].split(":")[0:2]
            end_time_parts = warehouse["operating_hours"]["end"].split(".")[0].split(":")[0:2]
            start_time = ":".join(start_time_parts)
            end_time = ":".join(end_time_parts)
            new_config["time_config"]["day_start"] = start_time
            new_config["time_config"]["day_end"] = end_time

            start_minutes = self._calculate_minutes(start_time)
            end_minutes = self._calculate_minutes(end_time)
            working_minutes = end_minutes - start_minutes
            new_config["working_hours"] = working_minutes
            new_config["time_config"]["depot_window"] = [0, working_minutes]

        # Count vehicles by type
        vehicle_counts = {}
        if db:
            vehicles = [
                v for v in db.find_all("vehicles")
                if v["warehouse_id"] == warehouse_id and v.get("availability_status", True)
            ]
            for vehicle in vehicles:
                v_type = vehicle["vehicle_type"]
                vehicle_counts[v_type] = vehicle_counts.get(v_type, 0) + 1

        for v_type, specs in vehicle_types.items():
            count = vehicle_counts.get(v_type, 0)
            
            new_config["vehicle_types"][v_type] = {
                **specs,  # Get latest specs from global config
                "count": count  # Use actual count from database
            }

        config_path = self._get_config_path(warehouse_id)
        self._write_yaml(config_path, new_config)
        return new_config

