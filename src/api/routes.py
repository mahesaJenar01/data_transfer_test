from fastapi.responses import FileResponse
from fastapi import APIRouter, HTTPException, Depends

from . import models
from .dependencies import (
    get_service, 
    get_config_cache, 
    get_token_manager,
    get_transaction_tracker,
    get_error_data,
    is_ui_request
)
from .sse import notify_clients
from ..services.data_processor import preparing_data
from ..spreadsheets.use_sheet import update_use_sheet
from ..spreadsheets.batch_update import batch_update_spreadsheet
from ..utils.logger import setup_logger

router = APIRouter()
logger = setup_logger('api_routes', 'INFO')

# Function to update the "Use sheet" with all configured sheet names
def update_sheet_names_in_use_sheet():
    """
    Updates the "Use sheet" B2 cell with all sheet names from configurations.
    """
    config_cache = get_config_cache()
    service = get_service()
    
    sheet_configs = config_cache.get_all_sheet_configs()
    sheet_names = [config.get("sheet_name") for config in sheet_configs if config.get("sheet_name")]
    
    # Update the Use sheet with all configured sheet names
    if sheet_names:
        update_use_sheet(service, sheet_names=sheet_names)
        logger.debug(f'Updated Use sheet with sheet names: {", ".join(sheet_names)}')
    else:
        logger.debug('No sheet names to update in Use sheet')

@router.get("/")
async def root():
    """
    Serve the main configuration UI page
    """
    return FileResponse('static/index.html')

@router.get("/get_config")
async def get_config(from_ui: bool = Depends(is_ui_request)):
    """
    Return all configurations (global settings and sheet configs).
    
    Hides sheet_id for external API requests (like Postman) but includes it for web UI requests.
    """
    config_cache = get_config_cache()
    
    # Get the original configurations
    global_settings = config_cache.get_global_settings()
    sheet_configs = config_cache.get_all_sheet_configs()
    
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

@router.post('/update_global_settings')
async def update_global_settings(settings: models.GlobalSettings):
    '''
    Update global settings.
    '''
    config_cache = get_config_cache()
    
    # Update global settings
    previous_settings = config_cache.update_global_settings(settings.dict())
    
    logger.debug(f'Updated global settings: {settings.dict()}')
    return {
        'message': 'Global settings updated successfully.',
        'previous_settings': previous_settings, 
        'current_settings': config_cache.get_global_settings()
    }

@router.post('/add_sheet_config')
async def add_sheet_config(config: models.SheetConfig):
    '''
    Add a new sheet configuration (UI method).
    '''
    config_cache = get_config_cache()
    
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

@router.post('/add_sheet_config/{token}')
async def add_sheet_config_with_token(token: str, config: models.SheetConfig):
    '''
    Add a new sheet configuration using a one-time authentication token.
    The token will expire immediately after use.
    '''
    config_cache = get_config_cache()
    token_manager = get_token_manager()
    
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

@router.put('/update_sheet_config/{sheet_id}')
async def update_sheet_config(sheet_id: str, config: models.SheetConfig):
    '''
    Update an existing sheet configuration (UI method).
    '''
    config_cache = get_config_cache()
    
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

@router.delete('/delete_sheet_config/{sheet_id}')
async def delete_sheet_config(sheet_id: str):
    '''
    Delete a sheet configuration (UI method).
    '''
    config_cache = get_config_cache()
    
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

@router.post('/on_change')
async def processing_data(data: models.OnChange):
    '''
    Processing Data sent from post on change end point.
    '''
    config_cache = get_config_cache()
    transaction_tracker = get_transaction_tracker()
    error_data = get_error_data()
    service = get_service()
    
    try:
        # Get the configuration for this sheet
        sheet_config = config_cache.get_sheet_config_by_name(data.sheet_name)
        if not sheet_config:
            logger.warning(f'No configuration found for sheet: {data.sheet_name}')
            return {
                'message': 'No configuration found for this sheet.',
                'result': 'Skipped due to missing configuration'
            }
        
        # Update the last_accessed timestamp for this configuration
        config_cache.update_last_accessed(data.sheet_name)
        logger.info(f"Updated access timestamp for '{data.sheet_name}'")
        
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
        if error_data.has_data(data.sheet_name):
            saved_error_data = error_data.get(data.sheet_name)
            logger.debug(f'Retrieved saved error data for sheet {data.sheet_name}: {len(saved_error_data)} items')
            copy_data.extend(saved_error_data)
            # Clear the error data for this sheet
            error_data.remove(data.sheet_name)

        # Prepare data for spreadsheet
        formatted_data = preparing_data(
            config=config, 
            values=copy_data, 
            service=service
        )

        if isinstance(formatted_data, str):
            logger.debug(formatted_data)
            return {
                'message': 'Data cannot be sent.',
                'result': formatted_data
            }

        # Process and update spreadsheet
        if not isinstance(formatted_data, str):
            result = ''
            for value in formatted_data:
                if len(value['values'][0]) == 7:
                    result = result + f'\nName: {value["values"][0][0]}'

            logger.debug(result)
            
            if result is None:
                logger.debug("Failed to update spreadsheet")
                return {
                    'message': 'Failed to update spreadsheet.',
                    'result': 'Error occurred during spreadsheet update'
                }

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
        if 'copy_data' in locals() and copy_data and data:
            error_data.add(data.sheet_name, copy_data)
            logger.error(f'Saved error data for sheet {data.sheet_name} for later retry')
                
        logger.error(f'Unexpected error: {e}')
        
        return {
            'message': 'An unexpected error occurred',
            'error': str(e)
        }, 500

@router.get("/admin/expiration-status")
async def get_expiration_status():
    """
    Return expiration status for all configurations
    """
    config_cache = get_config_cache()
    
    return {
        "expiration_minutes": config_cache.expiration_minutes,
        "configurations": config_cache.get_expiration_status()
    }

@router.get("/admin/token_stats")
async def get_token_stats():
    """
    Return statistics about token usage
    """
    token_manager = get_token_manager()
    
    return {
        "token_stats": token_manager.get_token_stats()
    }