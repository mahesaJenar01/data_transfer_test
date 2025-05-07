import googleapiclient.discovery
from typing import List, Dict, Union
from ..utils.logger import setup_logger
from googleapiclient.errors import HttpError

logger = setup_logger('batch_update_spreadsheet', 'ERROR')

def batch_update_spreadsheet(
        service: 'googleapiclient.discovery.Resource', 
        spreadsheet_id: str, 
        data: List[Dict[str, Union[list, str, int]]]
):
    """
    Sends batch data to the specified Google Sheets spreadsheet.

    Args:
        service: The authorized Google Sheets API service instance.
        spreadsheet_id: The ID of the spreadsheet to update.
        data: A list of dictionaries containing the range and values for each update.
            Each dictionary should contain:
                - 'range' (str): The A1 notation of the target range (e.g., "Sheet1!A1:B2").
                - 'values' (list): A 2D list of values to insert in the specified range.

    Returns:
        str: Status message indicating cells updated or None if error

    Raises:
        HttpError: If the API request fails.
    """

    body = {
        'valueInputOption': 'USER_ENTERED', 
        'data': data
    }

    try:
        result = service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body
        ).execute()
        
        return f'{result.get("totalUpdatedCells")} cells updated.'
    except HttpError as he:
        logger.error(f'HttpError occurred: {he}')
        return None
    except Exception as e:
        logger.error(f'An unexpected error occurred: {e}')
        return None