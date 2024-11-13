from datetime import datetime
import googleapiclient.discovery
from typing import List, Tuple, Union, Dict
from .spreadsheets.target import retrieve_target_spreadsheet_values

def get_cells_to_input(
        dana_used: str, 
        total_range: int,
        spreadsheet_id: str, 
        service: 'googleapiclient.discovery.Resource'
) -> Tuple[List[str]]:
    result = retrieve_target_spreadsheet_values(spreadsheet_id, service)
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
        dana_used: str, 
        spreadsheet_id: str, 
        values: List[List[Union[str, int]]], 
        service: 'googleapiclient.discovery.Resource', 
        transfer_destination: str
) -> List[Dict[str, Union[List, str]]]:
    name_ranges, bank_ranges= get_cells_to_input(
        dana_used, 
        len(values), 
        spreadsheet_id, 
        service
    )
    data= []
    for i in range(len(name_ranges)):
        if 'KIRIM DANA KE' in values[i][0]:
            values[i][0] = f'{values[i][0]} {transfer_destination}'

        data.append({
            'range': f'E{name_ranges[i]}', 
            'values': [values[i]]
        })

        if not values[i][2]:
            data.append({
                'range': f'B{name_ranges[i]}', 
                'values': [[
                    get_current_time(), 
                    dana_used, 
                    '-'
                ]]
            })

    if bank_ranges:
        for i in range(len(bank_ranges)):
            data.append({
                'range': f'C{bank_ranges[i]}', 
                'values': [[dana_used]]
            })

    return data