from typing import List, Union, Optional
from pydantic import BaseModel

class GlobalSettings(BaseModel):
    """Model for global application settings."""
    transfer_destination: str = "LAYER 1"

class SheetConfig(BaseModel):
    """Model for sheet configuration data."""
    sheet_id: Optional[str] = None
    dana_used: str
    sheet_name: str
    spreadsheet_ids: str
    bank_destination: str
    bank_name_destination: str

class OnChange(BaseModel):
    """Model for on_change webhook data from spreadsheets."""
    send_time: str
    sheet_name: str
    associate_rows: List[int]
    transaction_id: List[str]
    values: List[List[Union[int, str]]]

class ErrorResponse(BaseModel):
    """Model for standardized error responses."""
    message: str
    detail: Optional[str] = None
    
class SuccessResponse(BaseModel):
    """Model for standardized success responses."""
    message: str
    data: Optional[dict] = None