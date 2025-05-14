"""
Table model for representing tables extracted from PDF documents.

This module defines the Table class, which represents a table extracted from a PDF.
"""

from __future__ import annotations
from typing import List, Dict, Optional, Tuple, Any
from pydantic import BaseModel, Field, validator
import logging

from ..utils.logger import get_logger

logger = get_logger(__name__)

class Table(BaseModel):
    """Model representing a table extracted from the PDF."""
    
    caption: Optional[str] = Field(None, description="Table caption if available")
    page: int = Field(..., description="Page number where the table appears")
    position: Tuple[float, float, float, float] = Field(
        ..., 
        description="Position of the table on the page (x0, y0, x1, y1)"
    )
    data: List[List[str]] = Field(
        ..., 
        description="Table data as a list of rows, each row being a list of cell values"
    )
    
    @validator('data')
    def validate_table_data(cls, v):
        """Ensure table data is properly structured."""
        if not v:
            raise ValueError("Table data cannot be empty")
        
        # Check if all rows have the same number of columns
        row_lengths = {len(row) for row in v}
        if len(row_lengths) > 1:
            logger.warning(f"Table has inconsistent row lengths: {row_lengths}")
            
            # Standardize row lengths
            max_length = max(row_lengths)
            standardized_data = []
            
            for row in v:
                if len(row) < max_length:
                    # Pad short rows with empty cells
                    standardized_row = row + [""] * (max_length - len(row))
                    standardized_data.append(standardized_row)
                elif len(row) > max_length:
                    # Truncate long rows
                    standardized_data.append(row[:max_length])
                else:
                    standardized_data.append(row)
            
            return standardized_data
        
        return v
    
    @validator('page')
    def validate_page(cls, v):
        """Ensure page number is positive."""
        if v < 1:
            raise ValueError("Page number must be at least 1")
        return v
    
    @validator('position')
    def validate_position(cls, v):
        """Ensure position coordinates are valid."""
        x0, y0, x1, y1 = v
        
        # Check if coordinates define a valid rectangle
        if x0 >= x1 or y0 >= y1:
            raise ValueError(f"Invalid table position: {v} (coordinates must define a valid rectangle)")
        
        return v
    
    def get_cell(self, row: int, col: int) -> str:
        """
        Get the value of a specific cell.
        
        Args:
            row: Row index (0-based)
            col: Column index (0-based)
            
        Returns:
            Cell value
            
        Raises:
            IndexError: If row or column is out of bounds
        """
        if row < 0 or row >= len(self.data):
            raise IndexError(f"Row index {row} out of bounds (0-{len(self.data)-1})")
        
        table_row = self.data[row]
        
        if col < 0 or col >= len(table_row):
            raise IndexError(f"Column index {col} out of bounds (0-{len(table_row)-1})")
        
        return table_row[col]
    
    def get_column(self, col: int) -> List[str]:
        """
        Get all values in a specific column.
        
        Args:
            col: Column index (0-based)
            
        Returns:
            List of cell values in the column
            
        Raises:
            IndexError: If column is out of bounds
        """
        if not self.data:
            return []
        
        if col < 0 or col >= len(self.data[0]):
            raise IndexError(f"Column index {col} out of bounds (0-{len(self.data[0])-1})")
        
        return [row[col] for row in self.data if col < len(row)]
    
    def get_row(self, row: int) -> List[str]:
        """
        Get all values in a specific row.
        
        Args:
            row: Row index (0-based)
            
        Returns:
            List of cell values in the row
            
        Raises:
            IndexError: If row is out of bounds
        """
        if row < 0 or row >= len(self.data):
            raise IndexError(f"Row index {row} out of bounds (0-{len(self.data)-1})")
        
        return self.data[row]
    
    def get_dimensions(self) -> Tuple[int, int]:
        """
        Get the dimensions of the table.
        
        Returns:
            Tuple of (rows, columns)
        """
        rows = len(self.data)
        cols = len(self.data[0]) if rows > 0 else 0
        return rows, cols
    
    def to_markdown(self) -> str:
        """
        Convert table to Markdown format.
        
        Returns:
            Markdown representation of the table
        """
        if not self.data:
            return ""
        
        md_lines = []
        
        # Add caption if available
        if self.caption:
            md_lines.append(f"**{self.caption}**\n")
        
        # Header row
        md_lines.append("| " + " | ".join(self.data[0]) + " |")
        
        # Separator row
        md_lines.append("| " + " | ".join(["---"] * len(self.data[0])) + " |")
        
        # Data rows
        for row in self.data[1:]:
            # Ensure row has same number of columns as header
            padded_row = row + [""] * (len(self.data[0]) - len(row))
            truncated_row = padded_row[:len(self.data[0])]
            md_lines.append("| " + " | ".join(truncated_row) + " |")
        
        return "\n".join(md_lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert table to dictionary representation.
        
        Returns:
            Dictionary representation of the table
        """
        return {
            "caption": self.caption,
            "page": self.page,
            "position": self.position,
            "data": self.data
        }