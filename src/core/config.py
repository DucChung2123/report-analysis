import os
import yaml
from dotenv import load_dotenv
from pathlib import Path
from typing import Any
load_dotenv()

class Config:
    def __init__(self):
        self.root_dir = Path(__file__).parent.parent.parent # configs folder path 
        self.config_data = self._load_config()
        
    def _load_config(self) -> dict[str, Any]:
        """
        Load config from config file in config folder

        Returns:
            dict[str, Any]: dictionary that contains config data
        """
        
        env = os.getenv("ENV", "default")
        
        default_config_path = self.root_dir / "configs" / "default.yaml"
        config_data = self._load_yaml(default_config_path)
        env_config_path = self.root_dir / "configs" / f"{env}.yaml"
        
        if env_config_path.exists():
            env_config = self._load_yaml(env_config_path)
            config_data = self._deep_merge(config_data, env_config)
            
        return config_data
        
    def _deep_merge(self,
                    dict1: dict[str, Any],
                    dict2: dict[str, Any]) -> dict[str, Any]:
        """
        Deep merge two dictionaries

        Args:
            dict1 (dict[str, Any]): default dictionary 
            dict2 (dict[str, Any]): dictionary that will be merged with dict1

        Returns:
            dict[str, Any]: merged dictionary
        """
        result_dict = dict1.copy()
        
        for key, value in dict2.items():
            if key in result_dict and isinstance(result_dict[key], dict) and isinstance(value, dict):
                result_dict[key] = self._deep_merge(result_dict[key], value)
            else:
                result_dict[key] = value
        return result_dict
    
    def _load_yaml(self, file_path: Path) -> dict[str, Any]:
        """
        Load yaml config file

        Args:
            path (Path): path to yaml file
        Returns:
            dict[str, Any]: final dictionary
        """
        if not file_path.exists():
            return {}
        
        with open(file_path, "r") as file:
            return yaml.safe_load(file) or {}
        
    def get(self, key: str, default: Any = None):
        """
        get the value of config from dot notation

        Args:
            key (str): the key followed by dot notation
            default (Any, optional): default value if key not found. Defaults to None.
        """
        parts = key.split(".")
        data = self.config_data
        for part in parts:
            if isinstance(data, dict) and part in data:
                data = data[part]
            else:
                return default
            
        return data
    
    def _make_path(self, path_str: str) -> Path:
        """
        Make path from string
        
        Args:
            path_str (str): path string
        
        Returns:
            (Path): path object
        """
        path = Path(path_str)
        
        if not path.is_absolute():
            path = self.ROOT_DIR / path
            
        path.mkdir(parents=True, exist_ok=True)
            
        return path

config = Config()

# if __name__ == "__main__":
#     print(config.get("api.model", "ngu"))