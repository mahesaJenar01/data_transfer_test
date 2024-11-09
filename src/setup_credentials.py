import os.path
import traceback

from .setup_logger import setup_logger
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
logger = setup_logger('create_services', 'INFO')

def create_service():
    """Creates and configures Google Sheets API service."""
    try:
        logger.info('Starting credentials setup')
        credentials = None

        # Log the current working directory and files
        logger.debug(f'Working directory: {os.getcwd()}')
        logger.debug(f'Files in directory: {os.listdir()}')
        
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