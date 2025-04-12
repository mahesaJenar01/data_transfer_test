import uvicorn
from pyngrok import ngrok
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Union
import os

from setup_ngrok import start_ngrok
from src.setup_logger import setup_logger
from src.config_cache import ConfigCache
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
    title='Data Transfer',
    description='An API that transfers data across spreadsheets.',
    version='1.0.0'
)

# Create static folder if it doesn't exist
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize config cache
config_cache = ConfigCache()
config = config_cache.get_config()

# Pydantic models for request validation
class UpdateConfig(BaseModel):
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

@app.get("/")
async def root():
    """
    Serve the main configuration UI page
    """
    return FileResponse('static/index.html')

@app.get("/get_config")
async def get_config():
    """
    Return the current configuration
    """
    return {"config": config_cache.get_config()}

@app.post('/update_config')
async def update_config(update: UpdateConfig):
    '''
    Update or create configuration.
    '''
    
    # Prepare config update dictionary
    config_update = {
        'dana_used': update.dana_used,
        'sheet_name': update.sheet_name, 
        'spreadsheet_ids': update.spreadsheet_ids,
        'bank_destination': update.bank_destination,
        'bank_name_destination': update.bank_name_destination
    }
    
    # Update configuration with caching
    previous_config = config_cache.update_config(config_update)

    # Update global config for current session
    global config
    config = config_cache.get_config()

    # Update use sheet with the sheet name
    update_use_sheet(service, sheet_name=update.sheet_name)
    
    logger.debug(
        f'Updated config: \nSheet Name: {config["sheet_name"]}\nDana Used: {config["dana_used"]}'
    )
    return {
        'message': 'Configuration update successfully.',
        'previous_config': previous_config, 
        'current_config': config
    }

# Initialize transaction tracker
transaction_tracker = TransactionTracker()
save_error_data = []

@app.post('/on_change')
async def processing_data(data: OnChange):
    '''
    Processing Data sent from post on change end point.
    '''
    try:
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

        # Append any previously saved error data
        if save_error_data:
            logger.debug(f'save_error_data: {save_error_data}')
            copy_data.extend(save_error_data)
            save_error_data.clear()
            logger.debug(f'copy_data: {copy_data}')

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
        # Save error data for potential retry
        if 'copy_data' in locals() and copy_data:
            save_error_data.extend(copy_data)
            
        logger.error(f'Unexpected error: {e}')
        return {
            'message': 'An unexpected error occurred',
            'error': str(e)
        }, 500

# Main entry point
if __name__ == '__main__':
    # Start ngrok tunnel
    ngrok_tunnel = start_ngrok()
    update_use_sheet(service, api_url=ngrok_tunnel.public_url)

    # Start the FastAPI application
    try:
        uvicorn.run(app, host='0.0.0.0', port=8000)
    finally:
        # Clean up the ngrok tunnel when the application exits
        ngrok.kill()