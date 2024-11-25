import uvicorn
from pyngrok import ngrok
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Union
from setup_ngrok import start_ngrok
from src.setup_logger import setup_logger
from googleapiclient.errors import HttpError
from src.preparing_data import preparing_data
from src.setup_credentials import create_service
from src.spreadsheets.target import SpreadsheetError
from src.spreadsheets.use_sheet import update_use_sheet
from src.spreadsheets.batch_update import batch_update_spreadsheet

service = create_service()
logger = setup_logger('main', 'DEBUG')

app = FastAPI(
    title='Data Transfer',
    description='An API that transfer data across spreadsheets.',
    version='1.0.0'
)

config= {
    'dana_used': '', 
    'spreadsheet_ids': '', 
    'bank_destination': '',
    'bank_name_destination': '',
    'transfer_destination': 'LAYER 1'
}

class UpdateConfig(BaseModel):
    dana_used: str
    sheet_name: str
    spreadsheet_ids: str
    bank_destination: str
    bank_name_destination: str

class OnChange(BaseModel):
    send_time: str
    sheet_name: str
    associate_rows: List[int]
    transaction_id: List[str]
    values: List[List[Union[int, str]]]

@app.post('/update_config')
async def update_config(update: UpdateConfig):
    '''
    Update or create configuration.
    '''
    
    previous_config = config.copy()
    config['dana_used']= update.dana_used
    config['spreadsheet_ids']= update.spreadsheet_ids
    config['bank_destination']= update.bank_destination
    config['bank_name_destination']= update.bank_name_destination

    update_use_sheet(service, sheet_name=update.sheet_name)
    
    logger.debug(
        f'Updated config: \nDana Used: {config['dana_used']}\nSpreadsheets Id: {config['spreadsheet_ids']}\nTransfer Destination: {config['transfer_destination']}'
    )
    return {
        'message': 'Configuration update successfully.',
        'previous_config': previous_config, 
        'current_config': config
    }

save_error_data= [[
    "Jesus Christ",
    50,
    50000,
    "",
    "",
    -150,
    ""
]]

@app.post('/on_change')
async def processing_data(data: OnChange):
    '''
    Processing Data sent from post on change end point.
    '''
    try:
        copy_data= data.values.copy()

        if save_error_data:
            copy_data.extend(save_error_data)
            save_error_data.clear()

        formatted_data= preparing_data(
            config=config, 
            values=copy_data, 
            service=service
        )

        if not isinstance(formatted_data, str):
            result = ''
            for value in formatted_data:
                if len(value['values'][0]) == 7:
                    result = result + f'\nName: {value['values'][0][0]}'

            logger.debug(result)
            return {
                'message': 'Data send successfully.',
                'result': batch_update_spreadsheet(
                    service, 
                    config['spreadsheet_ids'], 
                    formatted_data
                )
            }

        logger.debug(formatted_data)
        return {
            'message': 'Data cannot be send.',
            'result': formatted_data
        }
    except SpreadsheetError as e:
        save_error_data.append(copy_data)

        logger.error(f'Spreadsheet operation failed: {e}')
        return {
            'message': 'Failed to process data',
            'error': str(e)
        }, 500
    except HttpError as he:
        save_error_data.append(copy_data)

        logger.error(f'HTTP Error occurred: {he}')
        return {
            'message': 'Google Sheets API error',
            'error': str(he)
        }, 500
    except Exception as e:
        save_error_data.append(copy_data)

        logger.error(f'Unexpected error: {e}')
        return {
            'message': 'An unexpected error occurred',
            'error': str(e)
        }, 500

if __name__ == '__main__':
    # Start ngrok tunnel
    ngrok_tunnel = start_ngrok()
    update_use_sheet(service, api_url=ngrok_tunnel.public_url)

    # Start the FastAPI application
    try:
        uvicorn.run(app, host='0.0.0.0', port=8000)
    finally:
        # Clean up the ngrok tunnel when the application exits
        ngrok.kill()