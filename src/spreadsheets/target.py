import time
import googleapiclient.discovery
from typing import Tuple, List, Union
from ..utils.logger import setup_logger

logger = setup_logger('target_spreadsheet', 'ERROR')

class SpreadsheetError(Exception):
    """Custom exception for spreadsheet operations"""
    pass

def retrieve_target_spreadsheet_values(
    spreadsheet_id: str, 
    service: 'googleapiclient.discovery.Resource',
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> Union[Tuple[List, List], str]:
    """
    Retrieving the target spreadsheet values with retry logic for network errors.
    
    Args:
        spreadsheet_id: Spreadsheet targeted IDs.
        service: Google api client resources instance.
        max_retries: Maximum number of retry attempts.
        retry_delay: Delay between retry attempts in seconds.

    Returns:
        tuple[list, list]: A tuple containing two lists - (bank_values, name_values).
        str: Error message if operation fails

    Raises:
        SpreadsheetError: If there's an error retrieving values from the spreadsheet
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            if not spreadsheet_id:
                return 'Spreadsheets target IDs not set just yet.'

            ranges = ['E13:E5002', 'C13:C5002']
     
            values = service.spreadsheets().values().batchGet(
                spreadsheetId=spreadsheet_id, 
                ranges=ranges
            ).execute()

            # Check if valueRanges exists and has at least 2 elements
            if 'valueRanges' not in values or len(values['valueRanges']) < 2:
                logger.warning(f"Unexpected response format from spreadsheet {spreadsheet_id}")
                return ([], [])

            # Safely get values with fallback to empty list if range is empty
            bank_values = values['valueRanges'][1].get('values', [])
            name_values = values['valueRanges'][0].get('values', [])

            # Log information about empty spreadsheets
            if not bank_values or not name_values:
                logger.info(f"One or both ranges are empty in spreadsheet {spreadsheet_id}")
                
            return (bank_values, name_values)
        
        except Exception as e:
            last_error = e
            
            # Check if it's a network error
            if "getaddrinfo failed" in str(e) or "connection" in str(e).lower():
                logger.warning(f"Network error (attempt {attempt + 1}/{max_retries}): {e}")
                
                # Only retry for network errors
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                    continue
            
            # For other errors or final attempt, log and return error message
            logger.error(f'An unexpected error occurred: {e}')
            return f"Failed to retrieve spreadsheet values: {str(e)}"