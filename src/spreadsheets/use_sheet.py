import os
import sys
import time
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
        api_url: str = '',
        max_retries: int = 3,
        retry_delay: float = 1.0
) -> None:
    """
    Update the use sheet with sheet name or API URL with retry mechanism.

    Args:
        service (googleapiclient.discovery.Resource): Google Sheets API service
        sheet_name (str, optional): Name of the sheet to update. Defaults to ''.
        api_url (str, optional): API URL to update. Defaults to ''.
        max_retries (int, optional): Maximum number of retry attempts. Defaults to 3.
        retry_delay (float, optional): Delay between retry attempts in seconds. Defaults to 1.0.
    
    Raises:
        SystemExit: If all retry attempts fail
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            if api_url:
                logger.debug('API URL provided; updating cell B1.')
                service.spreadsheets().values().update(
                    spreadsheetId=use_sheet_id, 
                    range='B1', 
                    valueInputOption='RAW', 
                    body={
                        'values': [[f'{api_url}/on_change']]
                    }
                ).execute()
            else:
                service.spreadsheets().values().update(
                    spreadsheetId=use_sheet_id, 
                    range='B2', 
                    valueInputOption='RAW', 
                    body={
                        'values': [[sheet_name]]
                    }
                ).execute()
            
            logger.info('Successfully updated use sheet.')
            return
        
        except Exception as e:
            last_error = e
            logger.warning(f'Attempt {attempt + 1} failed: {e}')
            
            # If it's the last attempt, log critical error and exit
            if attempt == max_retries - 1:
                error_message = f'CRITICAL: Failed to update use sheet after {max_retries} attempts. Unable to proceed.'
                logger.critical(error_message)
                logger.critical(f'Last error details: {last_error}')
                
                # Print to console for immediate visibility
                print(error_message, file=sys.stderr)
                
                # Exit the program with a non-zero status code to indicate failure
                sys.exit(1)
            
            # Wait before retrying
            time.sleep(retry_delay)
            
            # Exponential backoff: increase delay between attempts
            retry_delay *= 2