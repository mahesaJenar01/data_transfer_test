import uvicorn
from pyngrok import ngrok
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Union, Optional, Any
import os

from setup_ngrok import start_ngrok
from src.setup_logger import setup_logger
from src.config_cache import MultiConfigCache
from src.setup_credentials import create_service
from src.preparing_data import preparing_data
from src.transaction_tracker import TransactionTracker
from src.spreadsheets.use_sheet import update_use_sheet
from src.spreadsheets.batch_update import batch_update_spreadsheet

# Create service and logger
service = create_service()
logger = setup_logger('main', 'DEBUG')

# Initialize FastAPI application
app = FastAPI(
    title='Multi-Sheet Data Transfer',
    description='An API that transfers data across multiple spreadsheets.',
    version='2.0.0'
)

# Create static folder if it doesn't exist
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize config cache
config_cache = MultiConfigCache()

# Pydantic models for request validation
class GlobalSettings(BaseModel):
    transfer_destination: str = "LAYER 1"

class SheetConfig(BaseModel):
    sheet_id: Optional[str] = None
    dana_used: str
    sheet_name: str
    spreadsheet_ids: str
    bank_destination: str
    bank_name_destination: str

class OnChange(BaseModel):
    send_time: str
    sheet_name: str
    associate_rows: List[int]
    transaction_id: List[str]
    values: List[List[Union[int, str]]]

# Structure to store error data with its original sheet name
class ErrorData:
    def __init__(self):
        self.sheet_error_data = {}  # Dictionary to store error data by sheet name
    
    def add(self, sheet_name, data):
        """Add error data for a specific sheet"""
        if sheet_name not in self.sheet_error_data:
            self.sheet_error_data[sheet_name] = []
        self.sheet_error_data[sheet_name].extend(data)
        logger.debug(f'Saved error data for sheet {sheet_name}: {len(data)} items')
    
    def get(self, sheet_name):
        """Get error data for a specific sheet"""
        return self.sheet_error_data.get(sheet_name, [])
    
    def remove(self, sheet_name):
        """Remove error data for a specific sheet after successful processing"""
        if sheet_name in self.sheet_error_data:
            del self.sheet_error_data[sheet_name]
            logger.debug(f'Cleared error data for sheet {sheet_name}')
    
    def has_data(self, sheet_name):
        """Check if there's error data for a specific sheet"""
        return sheet_name in self.sheet_error_data and len(self.sheet_error_data[sheet_name]) > 0

# Function to update the "Use sheet" with all configured sheet names
def update_sheet_names_in_use_sheet():
    """
    Updates the "Use sheet" B2 cell with all sheet names from configurations.
    """
    sheet_configs = config_cache.get_all_sheet_configs()
    sheet_names = [config.get("sheet_name") for config in sheet_configs if config.get("sheet_name")]
    
    # Update the Use sheet with all configured sheet names
    if sheet_names:
        update_use_sheet(service, sheet_names=sheet_names)
        logger.debug(f'Updated Use sheet with sheet names: {", ".join(sheet_names)}')
    else:
        logger.debug('No sheet names to update in Use sheet')

@app.get("/")
async def root():
    """
    Serve the main configuration UI page
    """
    return FileResponse('static/index.html')

@app.get("/get_config")
async def get_config():
    """
    Return all configurations (global settings and sheet configs)
    """
    return {
        "global_settings": config_cache.get_global_settings(),
        "sheet_configs": config_cache.get_all_sheet_configs()
    }

@app.post('/update_global_settings')
async def update_global_settings(settings: GlobalSettings):
    '''
    Update global settings.
    '''
    # Update global settings
    previous_settings = config_cache.update_global_settings(settings.dict())
    
    logger.debug(f'Updated global settings: {settings.dict()}')
    return {
        'message': 'Global settings updated successfully.',
        'previous_settings': previous_settings, 
        'current_settings': config_cache.get_global_settings()
    }

@app.post('/add_sheet_config')
async def add_sheet_config(config: SheetConfig):
    '''
    Add a new sheet configuration.
    '''
    # Check if a configuration with this sheet name already exists
    existing_config = config_cache.get_sheet_config_by_name(config.sheet_name)
    if existing_config:
        raise HTTPException(status_code=400, detail=f"Configuration for sheet '{config.sheet_name}' already exists")
    
    # Add the new configuration
    sheet_id = config_cache.add_sheet_config(config.dict())
    
    # Update Use sheet with all configured sheet names
    update_sheet_names_in_use_sheet()
    
    logger.debug(f'Added sheet config: {config.dict()}')
    return {
        'message': 'Sheet configuration added successfully.',
        'sheet_id': sheet_id,
        'config': config_cache.get_sheet_config(sheet_id)
    }

@app.put('/update_sheet_config/{sheet_id}')
async def update_sheet_config(sheet_id: str, config: SheetConfig):
    '''
    Update an existing sheet configuration.
    '''
    # Check if the configuration exists
    existing_config = config_cache.get_sheet_config(sheet_id)
    if not existing_config:
        raise HTTPException(status_code=404, detail=f"Sheet configuration with ID '{sheet_id}' not found")
    
    # Check if sheet name conflict with different configuration
    name_conflict = config_cache.get_sheet_config_by_name(config.sheet_name)
    if name_conflict and name_conflict.get('sheet_id') != sheet_id:
        raise HTTPException(status_code=400, detail=f"Configuration for sheet '{config.sheet_name}' already exists")
    
    # Update the configuration
    previous_config = config_cache.update_sheet_config(sheet_id, config.dict())
    
    # Update Use sheet with all configured sheet names
    update_sheet_names_in_use_sheet()
    
    logger.debug(f'Updated sheet config: {config.dict()}')
    return {
        'message': 'Sheet configuration updated successfully.',
        'previous_config': previous_config,
        'current_config': config_cache.get_sheet_config(sheet_id)
    }

@app.delete('/delete_sheet_config/{sheet_id}')
async def delete_sheet_config(sheet_id: str):
    '''
    Delete a sheet configuration.
    '''
    # Check if the configuration exists
    existing_config = config_cache.get_sheet_config(sheet_id)
    if not existing_config:
        raise HTTPException(status_code=404, detail=f"Sheet configuration with ID '{sheet_id}' not found")
    
    # Delete the configuration
    success = config_cache.delete_sheet_config(sheet_id)
    
    # Update Use sheet with all configured sheet names
    update_sheet_names_in_use_sheet()
    
    logger.debug(f'Deleted sheet config with ID: {sheet_id}')
    return {
        'message': 'Sheet configuration deleted successfully.',
        'deleted_config': existing_config
    }

# Initialize transaction tracker
transaction_tracker = TransactionTracker()
# Initialize error data tracker
save_error_data = ErrorData()

@app.post('/on_change')
async def processing_data(data: OnChange):
    '''
    Processing Data sent from post on change end point.
    '''
    try:
        # Get the configuration for this sheet
        sheet_config = config_cache.get_sheet_config_by_name(data.sheet_name)
        if not sheet_config:
            logger.warning(f'No configuration found for sheet: {data.sheet_name}')
            return {
                'message': 'No configuration found for this sheet.',
                'result': 'Skipped due to missing configuration'
            }
        
        # Get global settings
        global_settings = config_cache.get_global_settings()
        
        # Combine global settings with sheet config
        config = {**sheet_config, **global_settings}
        
        # Filter out previously processed transactions
        new_transaction_ids = transaction_tracker.filter_new_transactions(
            data.sheet_name,
            data.transaction_id
        )
        
        if not new_transaction_ids:
            logger.debug('No new transactions to process')
            return {
                'message': 'No new transactions to process.',
                'result': 'Skipped duplicate transactions'
            }
            
        # Get indices of new transactions
        new_indices = [
            i for i, tx_id in enumerate(data.transaction_id)
            if tx_id in new_transaction_ids
        ]
        
        # Filter values to only include new transactions
        copy_data = [data.values[i] for i in new_indices]

        # Check if there are saved error data for this sheet
        if save_error_data.has_data(data.sheet_name):
            error_data = save_error_data.get(data.sheet_name)
            logger.debug(f'Retrieved saved error data for sheet {data.sheet_name}: {len(error_data)} items')
            copy_data.extend(error_data)
            # Clear the error data for this sheet
            save_error_data.remove(data.sheet_name)

        # Prepare data for spreadsheet
        formatted_data = preparing_data(
            config=config, 
            values=copy_data, 
            service=service
        )

        # Process and update spreadsheet
        if not isinstance(formatted_data, str):
            result = ''
            for value in formatted_data:
                if len(value['values'][0]) == 7:
                    result = result + f'\nName: {value["values"][0][0]}'

            logger.debug(result)
            return {
                'message': 'Data sent successfully.',
                'result': batch_update_spreadsheet(
                    service, 
                    config['spreadsheet_ids'], 
                    formatted_data
                )
            }

        # Log and return error if data preparation fails
        logger.debug(formatted_data)
        return {
            'message': 'Data cannot be sent.',
            'result': formatted_data
        }
    except Exception as e:
        # Save error data for potential retry, associated with its sheet name
        if 'copy_data' in locals() and copy_data and 'data' in locals() and data:
            save_error_data.add(data.sheet_name, copy_data)
            logger.error(f'Saved error data for sheet {data.sheet_name} for later retry')
            
        logger.error(f'Unexpected error: {e}')
        return {
            'message': 'An unexpected error occurred',
            'error': str(e)
        }, 500

# Schedule to retry processing saved error data
@app.on_event("startup")
async def startup_event():
    """
    Run at startup to initialize necessary components
    """
    # Update Use sheet with all sheet names from configurations
    update_sheet_names_in_use_sheet()

# Main entry point
if __name__ == '__main__':
    # Start ngrok tunnel
    ngrok_tunnel = start_ngrok()
    
    # Update use sheet with the ngrok URL
    update_use_sheet(service, api_url=ngrok_tunnel.public_url)

    # Start the FastAPI application
    try:
        uvicorn.run(app, host='0.0.0.0', port=8000)
    finally:
        # Clean up the ngrok tunnel when the application exits
        ngrok.kill()