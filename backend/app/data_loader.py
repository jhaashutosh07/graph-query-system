"""
Data loading and preprocessing module.

This module handles:
1. Downloading dataset from external sources
2. Parsing CSV/JSON/Parquet files
3. Data validation and cleaning
4. Normalization for graph ingestion
"""

import os
import logging
import pandas as pd
import re
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class DataLoader:
    """
    Load and preprocess business dataset for graph construction.
    
    Dataset should contain:
    - Orders (order_id, customer_id, order_date, ...)
    - Deliveries (delivery_id, order_id, delivery_date, ...)
    - Invoices (invoice_id, order_id, invoice_date, ...)
    - Payments (payment_id, invoice_id, amount, ...)
    - Customers, Products, Addresses (supporting entities)
    """
    
    def __init__(self, data_dir: str = "./data"):
        """Initialize data loader"""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.data = {}
    
    def load_csv_files(self, file_mapping: Dict[str, str]) -> Dict[str, pd.DataFrame]:
        """
        Load multiple CSV files.
        
        Args:
            file_mapping: {entity_type: file_path} mapping
            e.g., {"Order": "orders.csv", "Invoice": "invoices.csv"}
        
        Returns:
            Dictionary of DataFrames
        """
        for entity_type, filename in file_mapping.items():
            filepath = self.data_dir / filename
            
            if not filepath.exists():
                logger.warning(f"File not found: {filepath}")
                continue
            
            try:
                df = pd.read_csv(filepath)
                self.data[entity_type] = df
                logger.info(f"Loaded {entity_type}: {len(df)} records")
            except Exception as e:
                logger.error(f"Error loading {filename}: {e}")
        
        return self.data
    
    def load_parquet_files(self, file_mapping: Dict[str, str]) -> Dict[str, pd.DataFrame]:
        """Load Parquet files (faster for large datasets)"""
        for entity_type, filename in file_mapping.items():
            filepath = self.data_dir / filename
            
            if not filepath.exists():
                logger.warning(f"File not found: {filepath}")
                continue
            
            try:
                df = pd.read_parquet(filepath)
                self.data[entity_type] = df
                logger.info(f"Loaded {entity_type}: {len(df)} records")
            except Exception as e:
                logger.error(f"Error loading {filename}: {e}")
        
        return self.data
    
    def normalize_entity(self, df: pd.DataFrame, entity_type: str) -> pd.DataFrame:
        """
        Normalize entity data for graph ingestion.
        
        Args:
            df: Raw DataFrame
            entity_type: Entity type for context-specific normalization
        
        Returns:
            Normalized DataFrame
        """
        df = df.copy()
        
        # Derive entity ID column name (e.g., Order -> order_id, OrderItem -> order_item_id)
        # This must align with GraphConstructor.ENTITY_SCHEMA unique_property values.
        snake = re.sub(r'(?<!^)([A-Z])', r'_\1', entity_type).lower()
        id_field = f"{snake}_id"

        if id_field not in df.columns:
            raise KeyError(f"Missing expected ID column '{id_field}' for entity_type='{entity_type}'")

        # Remove duplicates based on entity ID
        df = df.drop_duplicates(subset=[id_field], keep='first')
        
        # Convert dates to ISO format
        date_columns = [col for col in df.columns if 'date' in col.lower()]
        for col in date_columns:
            try:
                df[col] = pd.to_datetime(df[col]).dt.isoformat()
            except Exception as e:
                logger.warning(f"Could not parse {col} as date: {e}")
        
        # Handle numeric fields
        numeric_cols = [col for col in df.columns if col.endswith('_amount') or col.endswith('_price')]
        for col in numeric_cols:
            try:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            except Exception as e:
                logger.warning(f"Could not convert {col} to numeric: {e}")
        
        # Remove rows with missing critical keys
        df = df.dropna(subset=[id_field])
        
        # Convert DataFrame rows to list of dicts
        records = df.to_dict('records')
        
        return records
    
    def extract_relationships(self,
                            source_df: pd.DataFrame,
                            source_entity: str,
                            source_id_col: str,
                            target_id_col: str) -> List[tuple]:
        """
        Extract relationships between entities.
        
        Args:
            source_df: Source DataFrame
            source_entity: Source entity type
            source_id_col: Column name with source ID
            target_id_col: Column name with target ID
        
        Returns:
            List of (source_id, target_id) tuples
        """
        # Remove rows with missing IDs
        df = source_df.dropna(subset=[source_id_col, target_id_col])
        
        # Extract and deduplicate relationships
        relationships = [
            (row[source_id_col], row[target_id_col])
            for _, row in df.iterrows()
        ]
        
        return list(set(relationships))  # Deduplicate
    
    def validate_data(self) -> Dict[str, Any]:
        """
        Validate loaded data for consistency.
        
        Returns:
            Validation report
        """
        report = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "stats": {}
        }
        
        for entity_type, df in self.data.items():
            snake = re.sub(r'(?<!^)([A-Z])', r'_\1', entity_type).lower()
            id_field = f"{snake}_id"
            
            # Check for missing IDs
            if id_field in df.columns:
                missing = df[id_field].isna().sum()
                if missing > 0:
                    report["warnings"].append(
                        f"{entity_type}: {missing} records missing {id_field}"
                    )
            
            # Check for duplicates
            if id_field in df.columns:
                duplicates = df[id_field].duplicated().sum()
                if duplicates > 0:
                    report["warnings"].append(
                        f"{entity_type}: {duplicates} duplicate {id_field} values"
                    )
            
            report["stats"][entity_type] = len(df)
        
        return report


if __name__ == "__main__":
    loader = DataLoader("./data")
    
    # Example usage
    file_mapping = {
        "Order": "orders.csv",
        "Invoice": "invoices.csv",
        "Delivery": "deliveries.csv"
    }
    
    data = loader.load_csv_files(file_mapping)
    validation = loader.validate_data()
    
    print("Validation Report:")
    print(f"  Valid: {validation['valid']}")
    print(f"  Warnings: {len(validation['warnings'])}")
    for warning in validation['warnings']:
        print(f"    - {warning}")
