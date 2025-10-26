"""Configuration manager for storing and loading application settings"""

import json
from pathlib import Path


class ConfigManager:
    """Manages application configuration persistence"""
    
    def __init__(self, config_file: str = ".ytdlp_gui_config.json"):
        """
        Initialize configuration manager
        
        Args:
            config_file: Name of the config file (stored in user's home directory)
        """
        self.config_file = Path.home() / config_file
        self.config = self.load()
    
    def load(self) -> dict:
        """
        Load configuration from file
        
        Returns:
            Dictionary containing configuration data
        """
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def save(self) -> None:
        """Save current configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception:
            pass
    
    def get(self, key: str, default=None):
        """
        Get configuration value
        
        Args:
            key: Configuration key
            default: Default value if key doesn't exist
            
        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)
    
    def set(self, key: str, value) -> None:
        """
        Set configuration value and save
        
        Args:
            key: Configuration key
            value: Value to set
        """
        self.config[key] = value
        self.save()

