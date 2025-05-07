import os.path
import traceback
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

from ..utils.logger import setup_logger

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
logger = setup_logger('authentication', 'INFO')

def create_service():
    """Creates and configures Google Sheets API service."""
    try:
        logger.info('Starting credentials setup')
        credentials = None

        # Log the current working directory and files
        logger.debug(f'Working directory: {os.getcwd()}')
        
        if os.path.exists('credentials.json'):
            logger.debug('credentials.json found')
        else:
            logger.error('credentials.json not found!')
            return None

        if os.path.exists('token.json'):
            logger.debug('Loading existing token.json')
            try:
                credentials = Credentials.from_authorized_user_file('token.json', SCOPES)
                logger.debug('Successfully loaded token.json')
            except Exception as e:
                logger.error(f'Error loading token.json: {str(e)}')
                credentials = None

        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                logger.debug('Attempting to refresh expired credentials')
                try:
                    credentials.refresh(Request())
                    logger.debug('Successfully refreshed credentials')
                except Exception as e:
                    logger.error(f'Error refreshing credentials: {str(e)}')
                    logger.error(traceback.format_exc())
                    credentials = None
            if not credentials or not credentials.valid:
                logger.debug('Starting new OAuth flow')
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', SCOPES
                    )
                    credentials = flow.run_local_server(port=0)
                    logger.debug('Successfully completed OAuth flow')
                    
                    # Save the credentials if OAuth flow succeeds
                    try:
                        with open('token.json', 'w') as token:
                            token.write(credentials.to_json())
                        logger.debug('Successfully saved token.json')
                    except Exception as e:
                        logger.error(f'Error saving token.json: {str(e)}')
                        logger.error(traceback.format_exc())
                except Exception as e:
                    logger.error(f'Error in OAuth flow: {str(e)}')
                    logger.error(traceback.format_exc())
                    return None

        logger.info('Building Google Sheets service')
        service = build('sheets', 'v4', credentials=credentials)
        logger.info('Successfully created Google Sheets service')
        return service

    except HttpError as he:
        logger.error(f'HttpError occurred: {he}')
        logger.error(traceback.format_exc())
        return None
    except Exception as e:
        logger.error(f'Unexpected error in create_service: {str(e)}')
        logger.error(traceback.format_exc())
        return None

def handle_token_error(error_message, shutdown_event=None):
    """
    Check if an error is related to token expiration and shutdown if necessary
    
    Args:
        error_message: Error message to check
        shutdown_event: Event to signal for shutdown
    """
    if "invalid_grant" in str(error_message) and ("expired" in str(error_message) or "revoked" in str(error_message)):
        logger.error(f"Authentication token has expired or been revoked: {error_message}")
        logger.info("Initiating application shutdown due to token error")
        
        # Set the shutdown event to stop background tasks
        if shutdown_event:
            shutdown_event.set()
            
            # Schedule shutdown
            import asyncio
            asyncio.create_task(shutdown_application())

async def shutdown_application():
    """
    Perform graceful shutdown with a timeout
    """
    logger.info("Shutting down application due to token error")
    import asyncio
    await asyncio.sleep(3)  # Brief delay to allow logging
    import sys
    sys.exit(0)  # Force exit the application