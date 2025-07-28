import yaml
import os
from typing import Any, Dict

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

def load_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)

def save_config(config: Dict[str, Any]) -> None:
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    config = load_config()
    
    def update_nested(config_dict: Dict[str, Any], key: str, value: Any) -> None:
        if "." in key:
            parent, child = key.split(".", 1)
            if parent not in config_dict:
                config_dict[parent] = {}
            update_nested(config_dict[parent], child, value)
        else:
            config_dict[key] = value
    
    for key, value in updates.items():
        update_nested(config, key, value)
    
    save_config(config)
    return config

def get_config_value(key: str) -> Any:
    config = load_config()
    parts = key.split(".")
    
    for part in parts:
        if isinstance(config, dict) and part in config:
            config = config[part]
        else:
            return None
            
    return config
