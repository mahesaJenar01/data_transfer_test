import uvicorn
from pyngrok import ngrok
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Union
from setup_ngrok import start_ngrok
from src.setup_logger import setup_logger
from src.preparing_data import preparing_data
from src.setup_credentials import create_service
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
    'transfer_destination': 'LAYER 1'
}

class UpdateConfig(BaseModel):
    dana_used: str
    sheet_name: str
    spreadsheet_ids: str

class OnChange(BaseModel):
    send_time: str
    sheet_name: str
    associate_rows: List[int]
    transaction_id: List[str]
    values: List[List[Union[int, str]]]

@app.post('/update_config')
async def update_config(update: UpdateConfig):
    """
    Update or create configuration.
    """
    
    previous_config = config.copy()
    config['dana_used']= update.dana_used
    config['spreadsheet_ids']= update.spreadsheet_ids

    update_use_sheet(service, sheet_name=update.sheet_name)

    return {
        'message': 'Configuration update successfully.',
        'previous_config': previous_config, 
        'current_config': config
    }

@app.post('/on_change')
async def processing_data(data: OnChange):
    """
    Proccessing Data sent from post on change end point.
    """
    data= preparing_data(
        dana_used=config['dana_used'], 
        spreadsheet_id=config['spreadsheet_ids'], 
        values=data.values, 
        service=service
    )

    result= ''
    for value in data:
        if len(value['values'][0]) == 7:
            result = result + f'\nName: {value["values"][0][0]}'

    logger.debug(result)
    return {
        'message': 'Data send successfully.',
        'result': batch_update_spreadsheet(service, config['spreadsheet_ids'], data)
    }

if __name__ == "__main__":
    # Start ngrok tunnel
    ngrok_tunnel = start_ngrok()
    update_use_sheet(service, api_url=ngrok_tunnel.public_url)

    # Start the FastAPI application
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000)
    finally:
        # Clean up the ngrok tunnel when the application exits
        ngrok.kill()