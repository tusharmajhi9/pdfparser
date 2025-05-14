"""
Base formatter interface for document output.

This module defines the base class for document formatters,
which convert Document models into various output formats.
"""

from abc import ABC, abstractmethod
from typing import Union, Optional, TextIO, Dict, Any
import os
from pathlib import Path

from ..models.document import Document
from ..utils.exceptions import FormatError
from ..utils.logger import get_logger

logger = get_logger(__name__)

class BaseFormatter(ABC):
    """
    Abstract base class for document formatters.
    """
    
    def __init__(self):
        """Initialize the formatter."""
        pass
    
    @abstractmethod
    def format(self, document: Document) -> str:
        """
        Format the document into a string.
        
        Args:
            document: Document model to format
            
        Returns:
            Formatted document string
            
        Raises:
            FormatError: If formatting fails
        """
        pass
    
    def write_to_file(self, 
                      formatted_content: str, 
                      output_path: Union[str, Path, TextIO],
                      create_dirs: bool = True) -> None:
        """
        Write formatted content to a file.
        
        Args:
            formatted_content: Formatted content string
            output_path: Path or file-like object to write to
            create_dirs: Whether to create parent directories if they don't exist
            
        Raises:
            FormatError: If writing to file fails
        """
        try:
            # If output_path is a file-like object, write directly
            if hasattr(output_path, 'write'):
                output_path.write(formatted_content)
                return
            
            # Otherwise, treat as a file path
            path = Path(output_path)
            
            # Create parent directories if needed
            if create_dirs:
                os.makedirs(path.parent, exist_ok=True)
            
            # Write to file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(formatted_content)
            
            logger.info(f"Output written to {path}")
        
        except Exception as e:
            raise FormatError(f"Failed to write output to {output_path}: {str(e)}")
    
    def format_and_write(self, 
                         document: Document, 
                         output_path: Optional[Union[str, Path, TextIO]] = None) -> str:
        """
        Format the document and optionally write to a file.
        
        Args:
            document: Document model to format
            output_path: Path or file-like object to write to (optional)
            
        Returns:
            Formatted document string
            
        Raises:
            FormatError: If formatting or writing fails
        """
        # Format the document
        formatted_content = self.format(document)
        
        # Write to file if requested
        if output_path is not None:
            self.write_to_file(formatted_content, output_path)
        
        return formatted_content