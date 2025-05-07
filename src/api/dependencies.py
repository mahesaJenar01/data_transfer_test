import os
from typing import Optional
from fastapi import Depends, Header, Request

from ..utils.logger import setup_logger
from ..services.token_service import TokenManager
from ..services.authentication import create_service
from ..services.config_service import MultiConfigCache
from ..services.transaction_service import TransactionTracker

logger = setup_logger('api_dependencies', 'INFO')

# Configure expiration in minutes
EXPIRATION_MINUTES = 30

# Initialize services as module-level singletons
_service = None
_config_cache = None
_token_manager = None
_transaction_tracker = None

def get_use_sheet_id() -> str:
    """Get the USE_SHEET_ID from environment variables."""
    use_sheet_id = os.getenv('USE_SHEET_ID')
    if not use_sheet_id:
        logger.error('USE_SHEET_ID not found in environment variables')
        raise ValueError('USE_SHEET_ID environment variable is required')
    return use_sheet_id

def get_service():
    """Get or create Google Sheets API service."""
    global _service
    if _service is None:
        _service = create_service()
        if _service is None:
            raise ValueError("Failed to create Google service")
    return _service

def get_token_manager(service = Depends(get_service)):
    """Get or create token manager."""
    global _token_manager
    if _token_manager is None:
        use_sheet_id = get_use_sheet_id()
        _token_manager = TokenManager(service, use_sheet_id)
    return _token_manager

def get_config_cache():
    """Get or create configuration cache."""
    global _config_cache
    if _config_cache is None:
        _config_cache = MultiConfigCache(expiration_minutes=EXPIRATION_MINUTES)
    return _config_cache

def get_transaction_tracker():
    """Get or create transaction tracker."""
    global _transaction_tracker
    if _transaction_tracker is None:
        _transaction_tracker = TransactionTracker()
    return _transaction_tracker

class ErrorData:
    """Structure to store error data with its original sheet name."""
    def __init__(self):
        self.sheet_error_data = {}  # Dictionary to store error data by sheet name
    
    def add(self, sheet_name, data):
        """Add error data for a specific sheet"""
        if sheet_name not in self.sheet_error_data:
            self.sheet_error_data[sheet_name] = []
        self.sheet_error_data[sheet_name].extend(data)
        logger.debug(f'Saved error data for sheet {sheet_name}: {len(data)} items')
    
    def get(self, sheet_name):
        """Get error data for a specific sheet"""
        return self.sheet_error_data.get(sheet_name, [])
    
    def remove(self, sheet_name):
        """Remove error data for a specific sheet after successful processing"""
        if sheet_name in self.sheet_error_data:
            del self.sheet_error_data[sheet_name]
            logger.debug(f'Cleared error data for sheet {sheet_name}')
    
    def has_data(self, sheet_name):
        """Check if there's error data for a specific sheet"""
        return sheet_name in self.sheet_error_data and len(self.sheet_error_data[sheet_name]) > 0

def get_error_data():
    """Get the error data tracker instance."""
    return ErrorData()

async def is_ui_request(
    request: Request, 
    referer: Optional[str] = Header(None), 
    origin: Optional[str] = Header(None), 
    x_ui_request: Optional[str] = Header(None)
) -> bool:
    """
    Check if the request is coming from our UI.
    
    Returns:
        bool: True if the request is from our UI, False otherwise
    """
    # Method 1: Check for a custom header that our UI will send
    is_ui_request = x_ui_request == "true"
    
    # Method 2: Check referer/origin (request coming from our domain)
    request_host = request.headers.get("host", "")
    is_same_origin = False
    
    if referer:
        # Check if referer contains our host
        is_same_origin = request_host in referer
    elif origin:
        # Check if origin matches our host
        is_same_origin = request_host in origin
    
    # Is this request from our UI?
    from_ui = is_ui_request or is_same_origin
    
    logger.debug(f"Request from UI: {from_ui}, Host: {request_host}, Referer: {referer}, Origin: {origin}")
    
    return from_ui