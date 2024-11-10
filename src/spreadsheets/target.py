import googleapiclient.discovery
from ..setup_logger import setup_logger

logger = setup_logger('retrieve_target_spreadsheet_values', 'ERROR')

class SpreadsheetError(Exception):
    """Custom exception for spreadsheet operations"""
    pass

def retrieve_target_spreadsheet_values(spreadsheet_id: str, service: 'googleapiclient.discovery.Resource') -> tuple[list, list]:
    """
    Retrieving the target spreadsheet values. Which in this case are BANK and NAME.

    Args:
        spreadsheet_id (str): Spreadsheet targeted IDs.
        service ('googleapiclient.discovery.Resource'): Google api client resources instance.

    Returns:
        tuple[list, list]: A tuple containing two lists - (bank_values, name_values).

    Raises:
        SpreadsheetError: If there's an error retrieving values from the spreadsheet
    """
    try:
        ranges = ['E13:E5002', 'C13:C5002']
 
        values = service.spreadsheets().values().batchGet(
            spreadsheetId=spreadsheet_id, 
            ranges=ranges
        ).execute()

        return (values['valueRanges'][1]['values'], values['valueRanges'][0]['values'])
    except Exception as e:
        logger.error(f'An unexpected error occurred: {e}')
        raise SpreadsheetError(f"Failed to retrieve spreadsheet values: {str(e)}")