import googleapiclient.discovery
from ..setup_logger import setup_logger

logger = setup_logger('use_sheet', 'INFO')

use_sheet_id = '1orcBlB2rteNGCSFp9rB1eeiw8v_5RNL9r4-_3IMuGoE'

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