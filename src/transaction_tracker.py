import os
import json
from pathlib import Path
from typing import List, Set
from .setup_logger import setup_logger

logger = setup_logger('transaction_tracker', 'INFO')

class TransactionTracker:
    def __init__(self, storage_file: str = "transaction_history.json"):
        """
        Initialize the TransactionTracker with a storage file path.
        
        Args:
            storage_file (str): Name of the file to store transaction IDs
        """
        # Store file in main directory
        self.storage_file = os.path.join(os.getcwd(), storage_file)
        self._transaction_sets: dict[str, Set[str]] = {}
        self._load_transactions()

    def _load_transactions(self) -> None:
        """Load transaction IDs from the storage file."""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    # Convert lists back to sets
                    self._transaction_sets = {
                        sheet: set(transactions) 
                        for sheet, transactions in data.items()
                    }
        except Exception as e:
            logger.error(f"Error loading transaction history: {e}")
            self._transaction_sets = {}

    def _save_transactions(self) -> None:
        """Save transaction IDs to the storage file."""
        try:
            # Convert sets to lists for JSON serialization
            data = {
                sheet: list(transactions)
                for sheet, transactions in self._transaction_sets.items()
            }
            with open(self.storage_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Error saving transaction history: {e}")

    def filter_new_transactions(self, sheet_name: str, transaction_ids: List[str]) -> List[str]:
        """
        Filter out previously processed transaction IDs and return only new ones.
        Maintains separate transaction history for each sheet.
        
        Args:
            sheet_name (str): Name of the sheet these transactions come from
            transaction_ids (List[str]): List of transaction IDs to check
            
        Returns:
            List[str]: List of transaction IDs that haven't been processed yet
        """
        if not transaction_ids:
            return []

        # Get or create set for this sheet
        if sheet_name not in self._transaction_sets:
            logger.info(f"First time processing sheet: {sheet_name}")
            self._transaction_sets[sheet_name] = set()

        # Convert incoming IDs to set for comparison
        new_ids_set = set(transaction_ids)
        
        # Find truly new transactions
        new_transactions = new_ids_set - self._transaction_sets[sheet_name]
        
        if new_transactions:
            # Update the set with new transactions
            self._transaction_sets[sheet_name].update(new_transactions)
            self._save_transactions()
            
            # Log new transactions found
            logger.info(f"Found {len(new_transactions)} new transactions in {sheet_name}")
        else:
            logger.debug(f"No new transactions found in {sheet_name}")

        # Return list of new transaction IDs in the same order they were received
        return [tx_id for tx_id in transaction_ids if tx_id in new_transactions]

    def get_tracked_sheets(self) -> List[str]:
        """
        Get a list of all sheets being tracked.
        
        Returns:
            List[str]: List of sheet names
        """
        return list(self._transaction_sets.keys())

    def get_transaction_count(self, sheet_name: str) -> int:
        """
        Get the count of tracked transactions for a specific sheet.
        
        Args:
            sheet_name (str): Name of the sheet
            
        Returns:
            int: Number of tracked transactions
        """
        if sheet_name in self._transaction_sets:
            return len(self._transaction_sets[sheet_name])
        return 0

    def cleanup_old_transactions(self, max_age_days: int = 30) -> None:
        """
        Remove transaction IDs older than specified days to prevent unlimited growth.
        This is a placeholder for future implementation if needed.
        
        Args:
            max_age_days (int): Maximum age of transaction IDs to keep
        """
        # TODO: Implement cleanup logic if needed
        # This would require storing timestamps with transaction IDs
        pass