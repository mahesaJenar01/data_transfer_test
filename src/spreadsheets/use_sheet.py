import sys
import time
import googleapiclient.discovery
from typing import List, Optional

from ..utils.logger import setup_logger
from ..config.settings import USE_SHEET_ID

logger = setup_logger('use_sheet', 'INFO')

def update_use_sheet(
        service: 'googleapiclient.discovery.Resource', *, 
        sheet_names: Optional[List[str]] = None, 
        api_url: str = '',
        max_retries: int = 3,
        retry_delay: float = 1.0
) -> None:
    """
    Update the use sheet with a comma-separated list of sheet names or API URL with retry mechanism.

    Args:
        service: Google Sheets API service
        sheet_names: List of sheet names to update. Defaults to None.
        api_url: API URL to update. Defaults to ''.
        max_retries: Maximum number of retry attempts. Defaults to 3.
        retry_delay: Delay between retry attempts in seconds. Defaults to 1.0.
    
    Raises:
        SystemExit: If all retry attempts fail
    """
    if not USE_SHEET_ID:
        logger.error('USE_SHEET_ID not found in environment variables')
        raise ValueError('USE_SHEET_ID environment variable is required')
    
    last_error = None
    for attempt in range(max_retries):
        try:
            if api_url:
                logger.debug('API URL provided; updating cell B1.')
                service.spreadsheets().values().update(
                    spreadsheetId=USE_SHEET_ID, 
                    range='B1', 
                    valueInputOption='RAW', 
                    body={
                        'values': [[f'{api_url}/on_change']]
                    }
                ).execute()
            elif sheet_names is not None:
                # Join all sheet names with commas and update cell B2
                sheet_names_str = ", ".join(sheet_names)
                logger.debug(f'Updating sheet names in cell B2: {sheet_names_str}')
                service.spreadsheets().values().update(
                    spreadsheetId=USE_SHEET_ID, 
                    range='B2', 
                    valueInputOption='RAW', 
                    body={
                        'values': [[sheet_names_str]]
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