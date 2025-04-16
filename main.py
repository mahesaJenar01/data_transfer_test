import os
import json
import asyncio
import uvicorn
from asyncio import Queue
from pyngrok import ngrok
from pydantic import BaseModel
from typing import List, Union, Optional
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import FileResponse, StreamingResponse

from setup_ngrok import start_ngrok
from src.setup_logger import setup_logger
from src.token_manager import TokenManager
from src.config_cache import MultiConfigCache
from src.preparing_data import preparing_data
from src.setup_credentials import create_service
from src.transaction_tracker import TransactionTracker
from src.spreadsheets.use_sheet import update_use_sheet
from src.spreadsheets.batch_update import batch_update_spreadsheet

# Create service and logger
service = create_service()
logger = setup_logger('main', 'DEBUG')

# Get the USE_SHEET_ID from environment variables
use_sheet_id = os.getenv('USE_SHEET_ID')
if not use_sheet_id:
    logger.error('USE_SHEET_ID not found in environment variables')
    raise ValueError('USE_SHEET_ID environment variable is required')

# Initialize token manager
token_manager = TokenManager(service, use_sheet_id)

# Initialize FastAPI application
app = FastAPI(
    title='Multi-Sheet Data Transfer',
    description='An API that transfers data across multiple spreadsheets.',
    version='2.0.0'
)

connected_clients = {}

@app.get('/sse')
async def sse():
    """
    Endpoint for Server-Sent Events (SSE) to push real-time updates to clients
    """
    client_id = id(asyncio.current_task())
    queue = Queue()
    connected_clients[client_id] = queue
    
    logger.debug(f'Client {client_id} connected to SSE')
    
    async def event_generator():
        try:
            while True:
                # Send initial connection message
                if queue.empty():
                    yield "data: {\"type\": \"connected\"}\n\n"
                    
                # Wait for messages from the queue
                message = await queue.get()
                if message is None:
                    break
                    
                yield f"data: {message}\n\n"
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            # Clean up when client disconnects
            if client_id in connected_clients:
                del connected_clients[client_id]
                logger.debug(f'Client {client_id} disconnected from SSE')
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'  # Prevents proxies from buffering the response
        }
    )

async def notify_clients(event_type, data=None):
    """
    Notify all connected clients about a configuration change
    
    Args:
        event_type (str): Type of event (e.g., 'config_updated')
        data (dict, optional): Additional data to send with the event
    """
    if not connected_clients:
        return
        
    event_data = {
        "type": event_type
    }
    
    if data:
        event_data.update(data)
        
    message = json.dumps(event_data)
    
    # Send to all connected clients
    for client_id, queue in list(connected_clients.items()):
        await queue.put(message)
    
    logger.debug(f'Notified {len(connected_clients)} clients: {event_type}')

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
async def get_config(request: Request, referer: Optional[str] = Header(None), origin: Optional[str] = Header(None), x_ui_request: Optional[str] = Header(None)):
    """
    Return all configurations (global settings and sheet configs).
    
    Hides sheet_id for external API requests (like Postman) but includes it for web UI requests.
    """
    # Get the original configurations
    global_settings = config_cache.get_global_settings()
    sheet_configs = config_cache.get_all_sheet_configs()
    
    # Check if the request is coming from our UI
    # Method 1: Check for a custom header that our UI will send
    is_ui_request = x_ui_request == "true"
    
    # Method 2: Check referer/origin (request coming from our domain)
    request_host = request.headers.get("host", "")
    is_same_origin = False
    
    if referer:
        # Check if referer contains our host
        is_same_origin = request_host in referer
    elif origin:
        # Check if origin matches our host
        is_same_origin = request_host in origin
    
    # Is this request from our UI?
    from_ui = is_ui_request or is_same_origin
    
    logger.debug(f"Request from UI: {from_ui}, Host: {request_host}, Referer: {referer}, Origin: {origin}")
    
    if from_ui:
        # For UI requests, include all data including sheet_id
        return {
            "global_settings": global_settings,
            "sheet_configs": sheet_configs
        }
    else:
        # For external API requests (like Postman), filter out sheet_id
        filtered_configs = []
        for config in sheet_configs:
            # Create a copy without sheet_id
            filtered_config = {k: v for k, v in config.items() if k != "sheet_id"}
            filtered_configs.append(filtered_config)
        
        return {
            "global_settings": global_settings,
            "sheet_configs": filtered_configs
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
    Add a new sheet configuration (UI method).
    '''
    # Check if a configuration with this sheet name already exists
    existing_config = config_cache.get_sheet_config_by_name(config.sheet_name)
    if existing_config:
        raise HTTPException(status_code=400, detail=f"Configuration for sheet '{config.sheet_name}' already exists")
    
    sheet_id = config_cache.add_sheet_config(config.dict())
    
    update_sheet_names_in_use_sheet()
    
    logger.debug(f'Added sheet config: {config.dict()}')
    
    # Notify clients about the change
    await notify_clients("config_updated")
    
    return {
        'message': 'Sheet configuration added successfully.',
        'sheet_id': sheet_id,
        'config': config_cache.get_sheet_config(sheet_id)
    }

# New endpoint for token-based sheet configuration addition
@app.post('/add_sheet_config/{token}')
async def add_sheet_config_with_token(token: str, config: SheetConfig):
    '''
    Add a new sheet configuration using a one-time authentication token.
    The token will expire immediately after use.
    '''
    # Validate the token
    is_valid, error_message = token_manager.validate_token(token)
    if not is_valid:
        raise HTTPException(status_code=401, detail=error_message)
    
    # Check if a configuration with this sheet name already exists
    existing_config = config_cache.get_sheet_config_by_name(config.sheet_name)
    if existing_config:
        raise HTTPException(status_code=400, detail=f"Configuration for sheet '{config.sheet_name}' already exists")
    
    # Use and expire the token (one-time use only)
    if not token_manager.use_token(token):
        raise HTTPException(status_code=401, detail="Failed to use token")
    
    # Add the configuration
    sheet_id = config_cache.add_sheet_config(config.dict())
    
    # Associate the sheet_id with the token (for record-keeping only)
    token_manager.associate_sheet_id(token, sheet_id)
    
    update_sheet_names_in_use_sheet()
    
    logger.debug(f'Added sheet config via one-time token: {config.dict()}')
    
    # Notify clients about the change
    await notify_clients("config_updated")
    
    return {
        'message': 'Sheet configuration added successfully. The token has been expired and cannot be used again.',
        'sheet_id': sheet_id,
        'config': config_cache.get_sheet_config(sheet_id),
        'token_usage_left': 0
    }

@app.put('/update_sheet_config/{sheet_id}')
async def update_sheet_config(sheet_id: str, config: SheetConfig):
    '''
    Update an existing sheet configuration (UI method).
    '''
    # Check if the configuration exists
    existing_config = config_cache.get_sheet_config(sheet_id)
    if not existing_config:
        raise HTTPException(status_code=404, detail=f"Sheet configuration with ID '{sheet_id}' not found")
    
    name_conflict = config_cache.get_sheet_config_by_name(config.sheet_name)
    if name_conflict and name_conflict.get('sheet_id') != sheet_id:
        raise HTTPException(status_code=400, detail=f"Configuration for sheet '{config.sheet_name}' already exists")
    
    previous_config = config_cache.update_sheet_config(sheet_id, config.dict())
    
    update_sheet_names_in_use_sheet()
    
    logger.debug(f'Updated sheet config: {config.dict()}')
    
    # Notify clients about the change
    await notify_clients("config_updated")
    
    return {
        'message': 'Sheet configuration updated successfully.',
        'previous_config': previous_config,
        'current_config': config_cache.get_sheet_config(sheet_id)
    }

@app.delete('/delete_sheet_config/{sheet_id}')
async def delete_sheet_config(sheet_id: str):
    '''
    Delete a sheet configuration (UI method).
    '''
    # Check if the configuration exists
    existing_config = config_cache.get_sheet_config(sheet_id)
    if not existing_config:
        raise HTTPException(status_code=404, detail=f"Sheet configuration with ID '{sheet_id}' not found")
    
    success = config_cache.delete_sheet_config(sheet_id)
    
    update_sheet_names_in_use_sheet()
    
    logger.debug(f'Deleted sheet config with ID: {sheet_id}')
    
    # Notify clients about the change
    await notify_clients("config_updated")
    
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
            
            # Notify clients that data was processed
            await notify_clients("data_processed", {
                "sheet_name": data.sheet_name
            })
            
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

# Get token stats endpoint (for admins)
@app.get("/admin/token_stats")
async def get_token_stats():
    """
    Return statistics about token usage
    """
    return {
        "token_stats": token_manager.get_token_stats()
    }

# Schedule to retry processing saved error data
@app.on_event("startup")
async def startup_event():
    """
    Run at startup to initialize necessary components
    """
    # Generate authentication tokens
    tokens = token_manager.generate_tokens(count=3, length=12)
    logger.info(f"Generated {len(tokens)} authentication tokens")
    
    # Write tokens to Use Sheet (B3, B4, B5)
    token_manager.write_tokens_to_sheet(tokens)
    
    # Update Use sheet with all sheet names from configurations
    update_sheet_names_in_use_sheet()
    
    logger.info("Application startup complete")

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