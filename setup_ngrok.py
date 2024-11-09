import os
from pyngrok import ngrok
from src.setup_logger import setup_logger

logger = setup_logger('start_ngrok', 'INFO')
def start_ngrok():
    # Get the ngrok auth token from environment variable
    ngrok_auth_token = os.getenv('NGROK_AUTH_TOKEN')
    
    if not ngrok_auth_token:
        logger.warning('Warning: NGROK_AUTH_TOKEN not found in environment variables')
        
        # Fallback to direct reading from .env file
        try:
            with open('.env', 'r') as f:
                for line in f:
                    if line.startswith('NGROK_AUTH_TOKEN'):
                        ngrok_auth_token = line.split('=')[1].strip()
                        logger.info('Token found directly in .env file')
                        break
        except Exception as e:
            logger.error(f'Error reading .env file directly: {e}')
    
    if not ngrok_auth_token:
        raise ValueError('NGROK_AUTH_TOKEN not found in environment variables or .env file')
    
    # Set the auth token
    ngrok.set_auth_token(ngrok_auth_token)
    logger.info('Successfully set ngrok auth token')
    
    # Open a ngrok tunnel to the API
    ngrok_tunnel = ngrok.connect(8000)
    logger.info(f'Public URL: {ngrok_tunnel.public_url}')
    return ngrok_tunnel