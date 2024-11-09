import googleapiclient.discovery
from typing import List, Dict, Union
from ..setup_logger import setup_logger
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
        service (googleapiclient.discovery.Resource): The authorized Google Sheets API service instance.
        spreadsheet_id (str): The ID of the spreadsheet to update.
        data (List[Dict[str, Union[list, str, int]]]): A list of dictionaries containing the range and values for each update.
            Each dictionary should contain:
                - 'range' (str): The A1 notation of the target range (e.g., "Sheet1!A1:B2").
                - 'values' (list): A 2D list of values to insert in the specified range.

    Example:
        data = [
            {
                "range": "Sheet1!A1:B2",
                "values": [
                    ["Value1", "Value2"],
                    ["Value3", "Value4"]
                ]
            },
            {
                "range": "Sheet1!C1:D2",
                "values": [
                    ["Value5", "Value6"],
                    ["Value7", "Value8"]
                ]
            }
        ]

    The function will send all data in a single batch request to minimize API calls.

    Returns:
        None

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
        
        return f'{result.get('totalUpdatedCells')} cells updated.'
    except HttpError as error:
        logger.error(f'An error occurred: {error}')
        return None