import os
import json
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

from ..utils.logger import setup_logger

logger = setup_logger('config_service', 'INFO')

class MultiConfigCache:
    def __init__(self, cache_file: str = 'data/config_cache.json', expiration_minutes: int = 30):
        """
        Initialize the MultiConfigCache with a cache file for multiple sheet configurations.
        
        Args:
            cache_file (str): Name of the file to store configuration cache
            expiration_minutes (int): Number of minutes of inactivity before a configuration expires
        """
        # Make sure data directory exists
        os.makedirs('data', exist_ok=True)
        
        # Store file in the data directory
        self.cache_file = cache_file
        self.expiration_minutes = expiration_minutes
        self.config_cache: Dict[str, Any] = {
            "global_settings": {
                "transfer_destination": "LAYER 1"
            },
            "sheet_configs": []
        }
        self._load_cache()

    def _load_cache(self) -> None:
        """Load configurations from the cache file."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    loaded_cache = json.load(f)
                    
                    # Ensure it has the expected structure
                    if "global_settings" in loaded_cache and "sheet_configs" in loaded_cache:
                        self.config_cache = loaded_cache
                        
                        # Ensure all configs have a last_accessed timestamp
                        for config in self.config_cache["sheet_configs"]:
                            if "last_accessed" not in config:
                                # Set to current time if not present
                                config["last_accessed"] = time.time()
                    else:
                        # Convert from old format if needed
                        if not isinstance(loaded_cache, dict) or "global_settings" not in loaded_cache:
                            old_config = loaded_cache
                            # Create new structure and add old config as first sheet if it has required fields
                            self.config_cache = {
                                "global_settings": {
                                    "transfer_destination": old_config.get("transfer_destination", "LAYER 1")
                                },
                                "sheet_configs": []
                            }
                            
                            # Only add old config if it has minimum required fields
                            if "sheet_name" in old_config and "spreadsheet_ids" in old_config:
                                # Generate a unique ID for the old config
                                sheet_id = str(uuid.uuid4())
                                old_config["sheet_id"] = sheet_id
                                old_config["last_accessed"] = time.time()  # Add timestamp
                                self.config_cache["sheet_configs"].append(old_config)
                                logger.info(f"Converted old single config to multi-config format with ID: {sheet_id}")
                            
                            # Save the new structure
                            self._save_cache()
            else:
                # Initialize with default configuration if no cache exists
                self._save_cache()
        except Exception as e:
            logger.error(f"Error loading configuration cache: {e}")

    def _save_cache(self) -> None:
        """Save configurations to the cache file."""
        try:
            # Make sure the data directory exists
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            
            with open(self.cache_file, 'w') as f:
                json.dump(self.config_cache, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving configuration cache: {e}")

    def get_global_settings(self) -> Dict[str, Any]:
        """
        Get the global settings.
        
        Returns:
            Dict[str, Any]: Global settings dictionary
        """
        return self.config_cache.get("global_settings", {}).copy()

    def update_global_settings(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update the global settings and save to cache.
        
        Args:
            new_settings (Dict[str, Any]): New settings to update
        
        Returns:
            Dict[str, Any]: Previous settings
        """
        # Create a copy of the previous settings
        previous_settings = self.get_global_settings()
        
        # Ensure global_settings exists
        if "global_settings" not in self.config_cache:
            self.config_cache["global_settings"] = {}
        
        # Update the settings with new values
        for key, value in new_settings.items():
            self.config_cache["global_settings"][key] = value
        
        # Save the updated configuration
        self._save_cache()
        
        return previous_settings

    def get_all_sheet_configs(self) -> List[Dict[str, Any]]:
        """
        Get all sheet configurations.
        
        Returns:
            List[Dict[str, Any]]: List of all sheet configurations
        """
        return self.config_cache.get("sheet_configs", []).copy()

    def get_sheet_config(self, sheet_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific sheet configuration by ID.
        
        Args:
            sheet_id (str): ID of the sheet configuration
            
        Returns:
            Optional[Dict[str, Any]]: Sheet configuration or None if not found
        """
        for config in self.config_cache.get("sheet_configs", []):
            if config.get("sheet_id") == sheet_id:
                return config.copy()
        return None

    def get_sheet_config_by_name(self, sheet_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific sheet configuration by sheet name.
        
        Args:
            sheet_name (str): Name of the sheet
            
        Returns:
            Optional[Dict[str, Any]]: Sheet configuration or None if not found
        """
        for config in self.config_cache.get("sheet_configs", []):
            if config.get("sheet_name") == sheet_name:
                return config.copy()
        return None

    def add_sheet_config(self, config: Dict[str, Any]) -> str:
        """
        Add a new sheet configuration.
        
        Args:
            config (Dict[str, Any]): New sheet configuration
            
        Returns:
            str: Generated sheet ID
        """
        # Generate a unique ID for this configuration
        sheet_id = str(uuid.uuid4())
        config["sheet_id"] = sheet_id
        
        # Add current timestamp
        config["last_accessed"] = time.time()
        
        # Initialize sheet_configs if it doesn't exist
        if "sheet_configs" not in self.config_cache:
            self.config_cache["sheet_configs"] = []
        
        # Add the configuration
        self.config_cache["sheet_configs"].append(config)
        
        # Save the updated configuration
        self._save_cache()
        logger.info(f"Added new sheet config with ID: {sheet_id}, name: {config.get('sheet_name')}")
        
        return sheet_id

    def update_sheet_config(self, sheet_id: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update an existing sheet configuration.
        
        Args:
            sheet_id (str): ID of the sheet configuration to update
            config (Dict[str, Any]): Updated configuration
            
        Returns:
            Optional[Dict[str, Any]]: Previous configuration or None if not found
        """
        for i, existing_config in enumerate(self.config_cache.get("sheet_configs", [])):
            if existing_config.get("sheet_id") == sheet_id:
                # Create a copy of the previous configuration
                previous_config = existing_config.copy()
                
                # Preserve the sheet_id
                config["sheet_id"] = sheet_id
                
                # Preserve or update the last_accessed timestamp
                config["last_accessed"] = existing_config.get("last_accessed", time.time())
                
                # Update the configuration
                self.config_cache["sheet_configs"][i] = config
                
                # Save the updated configuration
                self._save_cache()
                
                return previous_config
        
        return None

    def update_last_accessed(self, sheet_name: str) -> bool:
        """
        Update the last_accessed timestamp for a sheet configuration.
        
        Args:
            sheet_name (str): Name of the sheet
            
        Returns:
            bool: True if updated, False if configuration not found
        """
        for i, config in enumerate(self.config_cache.get("sheet_configs", [])):
            if config.get("sheet_name") == sheet_name:
                # Update the timestamp
                self.config_cache["sheet_configs"][i]["last_accessed"] = time.time()
                
                # Save the updated configuration
                self._save_cache()
                
                logger.debug(f"Updated last_accessed timestamp for sheet: {sheet_name}")
                return True
        
        logger.warning(f"Could not update timestamp for sheet: {sheet_name} - not found")
        return False

    def check_expired_configs(self) -> List[Dict[str, Any]]:
        """
        Check for expired configurations and return them.
        
        Returns:
            List[Dict[str, Any]]: List of expired configurations
        """
        now = time.time()
        expired_configs = []
        
        for config in self.config_cache.get("sheet_configs", []):
            last_accessed = config.get("last_accessed", 0)
            elapsed_minutes = (now - last_accessed) / 60
            
            if elapsed_minutes > self.expiration_minutes:
                expired_configs.append(config.copy())
        
        return expired_configs

    def delete_expired_configs(self) -> List[Tuple[str, str]]:
        """
        Delete expired configurations.
        
        Returns:
            List[Tuple[str, str]]: List of (sheet_id, sheet_name) tuples of deleted configurations
        """
        now = time.time()
        to_delete = []
        deleted_info = []
        
        # Find expired configurations
        for i, config in enumerate(self.config_cache.get("sheet_configs", [])):
            last_accessed = config.get("last_accessed", 0)
            elapsed_minutes = (now - last_accessed) / 60
            
            if elapsed_minutes > self.expiration_minutes:
                to_delete.append(i)
                deleted_info.append((
                    config.get("sheet_id", "unknown"),
                    config.get("sheet_name", "unknown")
                ))
                logger.info(f"Configuration for '{config.get('sheet_name')}' expired after {elapsed_minutes:.1f} minutes of inactivity")
        
        # Delete in reverse order to avoid index issues
        for index in sorted(to_delete, reverse=True):
            del self.config_cache["sheet_configs"][index]
        
        # Save if any were deleted
        if to_delete:
            self._save_cache()
            logger.info(f"Deleted {len(to_delete)} expired configurations")
        
        return deleted_info

    def delete_sheet_config(self, sheet_id: str) -> bool:
        """
        Delete a sheet configuration.
        
        Args:
            sheet_id (str): ID of the sheet configuration to delete
            
        Returns:
            bool: True if configuration was deleted, False otherwise
        """
        for i, config in enumerate(self.config_cache.get("sheet_configs", [])):
            if config.get("sheet_id") == sheet_id:
                # Remove the configuration
                del self.config_cache["sheet_configs"][i]
                
                # Save the updated configuration
                self._save_cache()
                
                return True
        
        return False

    def get_expiration_status(self) -> List[Dict[str, Any]]:
        """
        Get expiration status for all configurations.
        
        Returns:
            List[Dict[str, Any]]: List of configurations with expiration details
        """
        now = time.time()
        status_list = []
        
        for config in self.config_cache.get("sheet_configs", []):
            last_accessed = config.get("last_accessed", 0)
            elapsed_minutes = (now - last_accessed) / 60
            remaining_minutes = max(0, self.expiration_minutes - elapsed_minutes)
            
            status = {
                "sheet_id": config.get("sheet_id"),
                "sheet_name": config.get("sheet_name"),
                "last_accessed": datetime.fromtimestamp(last_accessed).isoformat(),
                "elapsed_minutes": round(elapsed_minutes, 1),
                "remaining_minutes": round(remaining_minutes, 1),
                "expires_at": datetime.fromtimestamp(last_accessed + (self.expiration_minutes * 60)).isoformat(),
                "is_expired": elapsed_minutes > self.expiration_minutes
            }
            
            status_list.append(status)
        
        return status_list