"""
JSON formatter for document output.

This module provides a formatter for converting Document models to JSON.
"""

import json
from typing import Dict, Any, List, Union, Optional, TextIO
from pathlib import Path

from ..models.document import Document, Section, Table
from ..utils.exceptions import FormatError
from ..utils.validators import validate_json_output
from ..utils.logger import get_logger
from .base import BaseFormatter

logger = get_logger(__name__)

class JSONFormatter(BaseFormatter):
    """
    Formatter for converting Document models to JSON.
    """
    
    def __init__(self, pretty_print: bool = True, ensure_ascii: bool = False):
        """
        Initialize the JSON formatter.
        
        Args:
            pretty_print: Whether to format the JSON with indentation
            ensure_ascii: Whether to escape non-ASCII characters
        """
        super().__init__()
        self.pretty_print = pretty_print
        self.ensure_ascii = ensure_ascii
    
    def format(self, document: Document) -> str:
        """
        Format the document as a JSON string.
        
        Args:
            document: Document model to format
            
        Returns:
            JSON string
            
        Raises:
            FormatError: If formatting fails
        """
        try:
            # Convert document to dictionary
            doc_dict = self._document_to_dict(document)
            
            # Convert to JSON string
            indent = 2 if self.pretty_print else None
            json_str = json.dumps(
                doc_dict, 
                indent=indent, 
                ensure_ascii=self.ensure_ascii
            )
            
            return json_str
        
        except Exception as e:
            raise FormatError(f"Failed to format document as JSON: {str(e)}")
    
    def format_and_write(self, 
                         document: Document, 
                         output_path: Optional[Union[str, Path, TextIO]] = None) -> str:
        """
        Format the document as JSON and optionally write to a file.
        
        Args:
            document: Document model to format
            output_path: Path or file-like object to write to (optional)
            
        Returns:
            JSON string
            
        Raises:
            FormatError: If formatting or writing fails
        """
        # Format the document
        formatted_content = self.format(document)
        
        # Validate and write to file if requested
        if output_path is not None:
            try:
                doc_dict = self._document_to_dict(document)
                validate_json_output(doc_dict, output_path)
            except Exception as e:
                raise FormatError(f"Failed to write JSON output: {str(e)}")
        
        return formatted_content
    
    def _document_to_dict(self, document: Document) -> Dict[str, Any]:
        """
        Convert a Document model to a dictionary.
        
        Args:
            document: Document model to convert
            
        Returns:
            Dictionary representation of the document
        """
        return {
            "title": document.title,
            "pages": document.pages,
            "sections": [self._section_to_dict(section) for section in document.sections]
        }
    
    def _section_to_dict(self, section: Section) -> Dict[str, Any]:
        """
        Convert a Section model to a dictionary.
        
        Args:
            section: Section model to convert
            
        Returns:
            Dictionary representation of the section
        """
        return {
            "title": section.title,
            "level": section.level,
            "pages": section.pages,
            "content": section.content,
            "tables": [self._table_to_dict(table) for table in section.tables],
            "subsections": [self._section_to_dict(subsection) for subsection in section.subsections]
        }
    
    def _table_to_dict(self, table: Table) -> Dict[str, Any]:
        """
        Convert a Table model to a dictionary.
        
        Args:
            table: Table model to convert
            
        Returns:
            Dictionary representation of the table
        """
        return {
            "caption": table.caption,
            "page": table.page,
            "position": list(table.position),  # Convert tuple to list for JSON
            "data": table.data
        }