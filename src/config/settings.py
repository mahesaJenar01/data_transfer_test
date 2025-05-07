import os
from pathlib import Path
from dotenv import load_dotenv
from ..utils.logger import setup_logger

logger = setup_logger('config_settings', 'INFO')

# Determine paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # Path to project root
ENV_PATH = BASE_DIR / '.env'

# Load environment variables
if not load_dotenv(ENV_PATH):
    logger.warning(f'Could not find .env file at {ENV_PATH}')

# API settings
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', 8000))
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')

# Google API settings
USE_SHEET_ID = os.getenv('USE_SHEET_ID')
if not USE_SHEET_ID:
    logger.error('USE_SHEET_ID not found in environment variables')
    raise ValueError('USE_SHEET_ID environment variable is required')

# Ngrok settings
NGROK_ENABLED = os.getenv('NGROK_ENABLED', 'True').lower() in ('true', '1', 't')
NGROK_AUTH_TOKEN = os.getenv('NGROK_AUTH_TOKEN')

# Cache settings
CACHE_EXPIRATION_MINUTES = int(os.getenv('CACHE_EXPIRATION_MINUTES', 30))

# File paths
CREDENTIALS_PATH = BASE_DIR / 'credentials.json'
TOKEN_PATH = BASE_DIR / 'token.json'
CONFIG_CACHE_PATH = BASE_DIR / 'data' / 'config_cache.json'
TRANSACTION_HISTORY_PATH = BASE_DIR / 'data' / 'transaction_history.json'
TOKEN_INFO_PATH = BASE_DIR / 'data' / 'token_info.json'

# Create data directory if it doesn't exist
DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)

# Static files settings
STATIC_DIR = BASE_DIR / 'static'
CSS_DIR = STATIC_DIR / 'css'
JS_DIR = STATIC_DIR / 'js'

# Ensure static directories exist
CSS_DIR.mkdir(parents=True, exist_ok=True)
JS_DIR.mkdir(parents=True, exist_ok=True)