import os
from pathlib import Path
import googleapiclient.discovery
from ..setup_logger import setup_logger
from dotenv import load_dotenv

logger = setup_logger('use_sheet', 'INFO')

# Get the current file's directory and find the .env file
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent.parent
env_path = root_dir / '.env'

# Load the .env file
if not load_dotenv(env_path):
    logger.error(f'Could not find .env file at {env_path}')
    raise FileNotFoundError(f'.env file not found at {env_path}')

# Get the USE_SHEET_ID from environment variables
use_sheet_id = os.getenv('USE_SHEET_ID')

if not use_sheet_id:
    logger.error('USE_SHEET_ID not found in environment variables')
    raise ValueError('USE_SHEET_ID environment variable is required')

def update_use_sheet(
        service: 'googleapiclient.discovery.Resource', *, 
        sheet_name: str = '', 
        api_url: str = ''
) -> None:
    try:
        if api_url:
            logger.debug('API URL provided; updating cell B2.')
            service.spreadsheets().values().update(
                spreadsheetId=use_sheet_id, 
                range='B2', 
                valueInputOption='RAW', 
                body={
                    'values': [[f'{api_url}/on_change']]
                }
            ).execute()
        else:
            service.spreadsheets().values().update(
                spreadsheetId=use_sheet_id, 
                range='B1', 
                valueInputOption='RAW', 
                body={
                    'values': [[sheet_name]]
                }
            ).execute()
        
        logger.info('Successfully updated use sheet.')
    except Exception as e:
        logger.error(f'An error occurred in update_use_sheet: {e}')