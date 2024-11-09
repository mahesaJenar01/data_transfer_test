from typing import Dict
import googleapiclient.discovery
from ..setup_logger import setup_logger

logger = setup_logger('retrieve_target_spreadsheet_values', 'ERROR')

def retrieve_target_spreadsheet_values(spreadsheet_id: str, service: 'googleapiclient.discovery.Resource') -> Dict[str, str]:
    """
    Retrieving the target spreadsheet values. Which in this case are BANK and NAME.

    Args:
        spreadsheet_id (str): Spreadsheet targeted IDs.
        service ('googleapiclient.discovery.Resource'): Goole api client resources instance.

    Returns:
        Dict[str, str]: The values retrieved from target spreadsheet.
    """
    try:
        ranges = ['E13:E5002', 'C13:C5002']
 
        values = service.spreadsheets().values().batchGet(
            spreadsheetId=spreadsheet_id, 
            ranges=ranges
        ).execute()

        return (values['valueRanges'][1]['values'], values['valueRanges'][0]['values'])
    except Exception as e:
        logger.error(f'An unexpected error occured: {e}')