import os
import json
from typing import Dict, Any
from pathlib import Path
from .setup_logger import setup_logger

logger = setup_logger('config_cache', 'INFO')

class ConfigCache:
    def __init__(self, cache_file: str = 'config_cache.json'):
        """
        Initialize the ConfigCache with a cache file.
        
        Args:
            cache_file (str): Name of the file to store configuration cache
        """
        # Store file in the same directory as the script
        self.cache_file = os.path.join(os.getcwd(), cache_file)
        self.config_cache: Dict[str, Any] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load configuration from the cache file."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    self.config_cache = json.load(f)
                logger.info(f"Loaded configuration from {self.cache_file}")
            else:
                # Initialize with default configuration if no cache exists
                self.config_cache = {
                    'dana_used': '', 
                    'spreadsheet_ids': '', 
                    'bank_destination': '',
                    'bank_name_destination': '',
                    'transfer_destination': 'LAYER 1'
                }
                self._save_cache()
        except Exception as e:
            logger.error(f"Error loading configuration cache: {e}")
            # Fallback to default configuration
            self.config_cache = {
                'dana_used': '', 
                'spreadsheet_ids': '', 
                'bank_destination': '',
                'bank_name_destination': '',
                'transfer_destination': 'LAYER 1'
            }

    def _save_cache(self) -> None:
        """Save configuration to the cache file."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.config_cache, f, indent=4)
            logger.info(f"Saved configuration to {self.cache_file}")
        except Exception as e:
            logger.error(f"Error saving configuration cache: {e}")

    def get_config(self) -> Dict[str, Any]:
        """
        Get the current configuration.
        
        Returns:
            Dict[str, Any]: Current configuration dictionary
        """
        return self.config_cache.copy()

    def update_config(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update the configuration and save to cache.
        
        Args:
            new_config (Dict[str, Any]): New configuration to update
        
        Returns:
            Dict[str, Any]: Previous configuration
        """
        # Create a copy of the previous configuration
        previous_config = self.config_cache.copy()
        
        # Update the configuration with new values
        for key, value in new_config.items():
            if key in self.config_cache:
                self.config_cache[key] = value
        
        # Save the updated configuration
        self._save_cache()
        
        return previous_config