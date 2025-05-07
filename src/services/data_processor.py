from datetime import datetime
import googleapiclient.discovery
from typing import List, Tuple, Union, Dict

from ..utils.logger import setup_logger
from ..spreadsheets.target import retrieve_target_spreadsheet_values

logger = setup_logger('data_processor', 'INFO')

def get_cells_to_input(
        dana_used: str, 
        total_range: int,
        spreadsheet_ids: str, 
        service: 'googleapiclient.discovery.Resource'
) -> Union[Tuple[List[int], List[int]], str]:
    """
    Get available cells for input in the target spreadsheet.
    
    Args:
        dana_used: Dana used value
        total_range: Total number of rows needed
        spreadsheet_ids: Target spreadsheet ID
        service: Google Sheets API service
        
    Returns:
        Tuple of name ranges and bank ranges, or error message as string
    """
    result = retrieve_target_spreadsheet_values(spreadsheet_ids, service)

    if isinstance(result, str):
        return result

    bank_list, name_list = result
    
    # Handle case when spreadsheet is empty
    if not bank_list and not name_list:
        logger.info(f"Spreadsheet {spreadsheet_ids} is empty. Using default starting position at row 13.")
        # Start from row 13 if spreadsheet is empty
        name_ranges = list(range(13, 13 + total_range))
        bank_ranges = list(range(13, 13 + total_range))
        return name_ranges, bank_ranges
    
    name_ranges = []
    bank_ranges = []
    
    # Calculate how far we need to check based on available data and required slots
    max_check = max(len(name_list), len(bank_list)) + total_range
    
    for cell_indices in range(13, 13 + max_check):
        list_indices = cell_indices - 13
        
        # Check if we're beyond the available data
        if list_indices >= len(name_list) or not name_list[list_indices]:
            name_ranges.append(cell_indices)
            
            # If we're beyond bank list or it's empty or different from dana_used, add to bank_ranges
            if (list_indices >= len(bank_list) or 
                not bank_list[list_indices] or 
                bank_list[list_indices][0] != dana_used):
                bank_ranges.append(cell_indices)
            
            # Stop if we have enough ranges
            if len(name_ranges) == total_range:
                break
    
    if not name_ranges:
        logger.warning(f"Could not find empty cells in spreadsheet {spreadsheet_ids}")
        return "Could not find empty cells in the spreadsheet"
    
    return name_ranges, bank_ranges

def get_current_time():
    """Get the current time formatted as HH:MM:SS."""
    return datetime.now().strftime("%H:%M:%S")

def preparing_data(
        config: dict, 
        values: List[List[Union[str, int]]], 
        service: 'googleapiclient.discovery.Resource'
) -> Union[List[Dict[str, Union[list, str]]], str]:
    """
    Prepare data for batch update to target spreadsheet.
    
    Args:
        config: Configuration dictionary
        values: Values to prepare
        service: Google Sheets API service
        
    Returns:
        List of prepared data or error message as string
    """
    try:
        data_ranges = get_cells_to_input(
            config['dana_used'], 
            len(values), 
            config['spreadsheet_ids'], 
            service
        )

        if isinstance(data_ranges, str):
            return data_ranges
        
        name_ranges, bank_ranges = data_ranges
        
        logger.debug(f"Found {len(name_ranges)} name ranges and {len(bank_ranges)} bank ranges")

        data = []
        for i in range(len(name_ranges)):
            if i >= len(values):
                logger.warning(f"Not enough values provided, expected {len(name_ranges)}, got {len(values)}")
                break
                
            if 'KIRIM DANA KE' in values[i][0]:
                values[i][0] = f"{values[i][0]} {config['transfer_destination']}"
            elif 'KIRIM UANG' in values[i][0]:
                if config['bank_destination'] and config['bank_name_destination']:
                    result = 'KIRIM DANA KE '
                    result = result + config['bank_destination']
                    result = result + ' ' + config['bank_name_destination']
                    result = result + ' ' + config['transfer_destination']

                    values[i][0] = result

            # Append the formula for the "KREDIT YANG DIPROSES" range
            values[i][1] = f'=G{name_ranges[i]}/1000'
            
            # Check of whether the biaya bank has a value or not and if it's not a send money
            if values[i][5] and "KIRIM DANA KE" not in values[i][0]:
                values[i][5] = f'=IF(OR(ISNUMBER(G{name_ranges[i]}),OR(ISNUMBER(H{name_ranges[i]}),ISNUMBER(I{name_ranges[i]}))),{values[i][5]},"")'
            
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
                if i >= len(data) / 2:  # Avoid adding more bank entries than we have data
                    break
                    
                data.append({
                    'range': f'C{bank_ranges[i]}', 
                    'values': [[
                        config['dana_used']
                    ]]
                })

        return data
    except Exception as e:
        logger.error(f"Error in preparing_data: {e}")
        return f"Error preparing data: {str(e)}"