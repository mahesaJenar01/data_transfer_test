import os
import random
import string
import json
from typing import Dict, Optional, List, Tuple
import googleapiclient.discovery

from ..utils.logger import setup_logger

logger = setup_logger('token_service', 'INFO')

class TokenManager:
    def __init__(self, service: 'googleapiclient.discovery.Resource', use_sheet_id: str):
        """
        Initialize the token manager with Google Sheets service and Use Sheet ID.
        
        Args:
            service (googleapiclient.discovery.Resource): Google Sheets API service
            use_sheet_id (str): ID of the Use Sheet
        """
        self.service = service
        self.use_sheet_id = use_sheet_id
        self.tokens = {}  # Store token info: {token: {"usage_left": count, "sheet_ids": [ids]}}
        self.sheet_id_to_token = {}  # Map sheet_ids back to tokens
        
        # Make sure data directory exists
        os.makedirs('data', exist_ok=True)
        
        # Load tokens from file if exists
        self._token_file = 'data/token_info.json'
        self._load_tokens()
    
    def _load_tokens(self) -> None:
        """Load token information from file if exists."""
        try:
            if os.path.exists(self._token_file):
                with open(self._token_file, 'r') as f:
                    data = json.load(f)
                    self.tokens = data.get("tokens", {})
                    self.sheet_id_to_token = data.get("sheet_id_to_token", {})
                    logger.info(f"Loaded {len(self.tokens)} tokens from file")
        except Exception as e:
            logger.error(f"Error loading token information: {e}")
            self.tokens = {}
            self.sheet_id_to_token = {}
    
    def _save_tokens(self) -> None:
        """Save token information to file."""
        try:
            # Make sure data directory exists
            os.makedirs(os.path.dirname(self._token_file), exist_ok=True)
            
            data = {
                "tokens": self.tokens,
                "sheet_id_to_token": self.sheet_id_to_token
            }
            with open(self._token_file, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving token information: {e}")
    
    def generate_tokens(self, count: int = 3, length: int = 12) -> List[str]:
        """
        Generate exactly 3 new authentication tokens, replacing any existing ones.
        
        Args:
            count (int): Number of tokens to generate (default 3)
            length (int): Length of each token
            
        Returns:
            List[str]: List of generated tokens
        """
        # Generate new tokens
        new_tokens = []
        for _ in range(count):
            # Generate random token with alphanumeric characters
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
            new_tokens.append(token)
            
            # Initialize token with usage limit
            self.tokens[token] = {
                "usage_left": 1,  # Initial usage limit
                "sheet_ids": []
            }
        
        # Remove all old tokens that aren't in the new set
        old_tokens = list(self.tokens.keys())
        for old_token in old_tokens:
            if old_token not in new_tokens:
                # Remove associations for sheet_ids linked to this token
                if old_token in self.tokens:
                    for sheet_id in self.tokens[old_token]["sheet_ids"]:
                        if sheet_id in self.sheet_id_to_token:
                            del self.sheet_id_to_token[sheet_id]
                    
                    # Remove the token itself
                    del self.tokens[old_token]
        
        # Save the updated tokens
        self._save_tokens()
        
        logger.info(f"Generated {len(new_tokens)} new tokens, purged old tokens")
        return new_tokens
    
    def write_tokens_to_sheet(self, tokens: List[str]) -> bool:
        """
        Write tokens to the Use Sheet.
        
        Args:
            tokens (List[str]): List of tokens to write
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure we have exactly 3 tokens
            if len(tokens) < 3:
                tokens.extend([''] * (3 - len(tokens)))
            
            # Update cells B3, B4, B5
            ranges = ['B3', 'B4', 'B5']
            data = []
            
            for i in range(3):
                data.append({
                    "range": ranges[i],
                    "values": [[tokens[i]]]
                })
            
            body = {
                'valueInputOption': 'RAW',
                'data': data
            }
            
            result = self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.use_sheet_id,
                body=body
            ).execute()
            
            logger.info(f"Wrote {result.get('totalUpdatedCells')} tokens to Use Sheet")
            return True
        except Exception as e:
            logger.error(f"Error writing tokens to sheet: {e}")
            return False
    
    def validate_token(self, token: str) -> Tuple[bool, str]:
        """
        Validate a token and check if it has usage left.
        
        Args:
            token (str): Token to validate
            
        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        if token not in self.tokens:
            return False, "Invalid token"
        
        if self.tokens[token]["usage_left"] <= 0:
            return False, "Token usage limit exceeded"
        
        return True, ""
    
    def validate_sheet_id(self, sheet_id: str) -> Tuple[bool, str, Optional[str]]:
        """
        Validate a sheet_id and check if its associated token has usage left.
        
        Args:
            sheet_id (str): Sheet ID to validate
            
        Returns:
            Tuple[bool, str, Optional[str]]: (is_valid, error_message, token)
        """
        if sheet_id not in self.sheet_id_to_token:
            return False, "Invalid sheet_id", None
        
        token = self.sheet_id_to_token[sheet_id]
        
        if token not in self.tokens:
            return False, "Token no longer exists", None
        
        if self.tokens[token]["usage_left"] <= 0:
            return False, "Token usage limit exceeded", None
        
        return True, "", token
    
    def associate_sheet_id(self, token: str, sheet_id: str) -> None:
        """
        Record association between token and sheet_id for tracking purposes only.
        This doesn't enable further API access as tokens expire after first use.
        
        Args:
            token (str): Token
            sheet_id (str): Sheet ID to associate
        """
        if token in self.tokens:
            if sheet_id not in self.tokens[token]["sheet_ids"]:
                self.tokens[token]["sheet_ids"].append(sheet_id)
            
            # We still maintain this mapping for record-keeping only
            self.sheet_id_to_token[sheet_id] = token
            self._save_tokens()
    
    def use_token(self, token: str) -> bool:
        """
        Use a token once and expire it completely.
        
        Args:
            token (str): Token to use
            
        Returns:
            bool: True if successful, False if token invalid or no usage left
        """
        if token not in self.tokens:
            return False
        
        if self.tokens[token]["usage_left"] <= 0:
            return False
        
        # Completely expire the token by setting usage_left to 0
        self.tokens[token]["usage_left"] = 0
        self._save_tokens()
        logger.info(f"Token {token[:4]}*** used and expired")
        
        return True
    
    def get_token_stats(self) -> Dict:
        """
        Get statistics about token usage.
        
        Returns:
            Dict: Token statistics
        """
        stats = {}
        for token, info in self.tokens.items():
            # Mask the full token for security reasons
            masked_token = token[:4] + "***"
            stats[masked_token] = {
                "usage_left": info["usage_left"],
                "sheet_ids_count": len(info["sheet_ids"])
            }
        
        return stats