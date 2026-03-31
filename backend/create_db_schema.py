"""
Create database schema visualization and documentation.
This script generates a visual representation of the database schema.
"""
from app.db.models import (
    User, Profile, OKR, KeyResult, CheckIn, 
    Assessment, Review, ProgressHistory
)
from app.db.database import Base

def print_schema():
    """Print database schema information."""
    print("=" * 80)
    print("DATABASE SCHEMA DOCUMENTATION")
    print("=" * 80)
    print("\n")
    
    # Get all tables
    tables = Base.metadata.tables
    
    for table_name, table in sorted(tables.items()):
        print(f"Table: {table_name}")
        print("-" * 80)
        
        # Print columns
        for column in table.columns:
            col_info = f"  {column.name:20s} {str(column.type):20s}"
            
            if column.primary_key:
                col_info += " [PRIMARY KEY]"
            if column.foreign_keys:
                for fk in column.foreign_keys:
                    col_info += f" [FK -> {fk.column.table.name}.{fk.column.name}]"
            if column.nullable is False:
                col_info += " [NOT NULL]"
            if hasattr(column, 'default') and column.default is not None:
                col_info += f" [DEFAULT: {column.default}]"
            
            print(col_info)
        
        # Print relationships
        if hasattr(table, 'relationships'):
            print("\n  Relationships:")
            for rel in table.relationships:
                print(f"    -> {rel}")
        
        print("\n")

if __name__ == "__main__":
    print_schema()
