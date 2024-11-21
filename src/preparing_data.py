from datetime import datetime
import googleapiclient.discovery
from typing import List, Tuple, Union, Dict
from .spreadsheets.target import retrieve_target_spreadsheet_values

def get_cells_to_input(
        dana_used: str, 
        total_range: int,
        spreadsheet_ids: str, 
        service: 'googleapiclient.discovery.Resource'
) -> Tuple[List[str]]:
    result = retrieve_target_spreadsheet_values(spreadsheet_ids, service)

    if isinstance(result, str):
        return result

    bank_list= result[0]
    name_list= result[1]
    
    name_ranges= []
    bank_ranges= []
    for cell_indices in range(13, len(name_list)):
        list_indices= cell_indices - 13

        if not name_list[list_indices]:
            name_ranges.append(cell_indices)

            # If its empty or its different, then append it.
            if not bank_list[list_indices] or bank_list[list_indices][0] != dana_used:
                bank_ranges.append(cell_indices)
            
            if len(name_ranges) == total_range:
                break

    return name_ranges, bank_ranges

def get_current_time():
    return datetime.now().strftime("%H:%M:%S")

def preparing_data(
        config: dict, 
        values: List[List[Union[str, int]]], 
        service: 'googleapiclient.discovery.Resource'
) -> List[Dict[str, Union[List, str]]]:
    data_ranges= get_cells_to_input(
        config['dana_used'], 
        len(values), 
        config['spreadsheet_ids'], 
        service
    )

    if isinstance(data_ranges, str):
        return data_ranges
    
    name_ranges, bank_ranges= data_ranges

    data= []
    for i in range(len(name_ranges)):
        if 'KIRIM DANA KE' in values[i][0]:
            values[i][0]= f'{values[i][0]} {config['transfer_destination']}'
        elif 'KIRIM UANG' in values[i][0]:
            if config['bank_destination'] and config['bank_name_destination']:
                result= 'KIRIM DANA KE '
                result= result+ config['bank_destination']
                result= result+ ' '+ config['bank_name_destination']
                result= result+ ' '+ config['transfer_destination']

                values[i][0]= result

        data.append({
            'range': f'E{name_ranges[i]}', 
            'values': [values[i]]
        })

        if not values[i][2]:
            data.append({
                'range': f'B{name_ranges[i]}', 
                'values': [[
                    get_current_time(), 
                    config['dana_used'], 
                    '-'
                ]]
            })

    if bank_ranges:
        for i in range(len(bank_ranges)):
            data.append({
                'range': f'C{bank_ranges[i]}', 
                'values': [[
                    config['dana_used']
                ]]
            })

    return data