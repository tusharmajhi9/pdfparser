"""
ASCII formatter for document outline output.

This module provides a formatter for converting Document models to ASCII tree outlines.
"""

from typing import Union, Optional, TextIO, List
from pathlib import Path

from ..models.document import Document, Section
from ..utils.exceptions import FormatError
from ..utils.validators import validate_ascii_output
from ..utils.logger import get_logger
from .base import BaseFormatter

logger = get_logger(__name__)

class ASCIIFormatter(BaseFormatter):
    """
    Formatter for converting Document models to ASCII tree outlines.
    """
    
    def __init__(self, 
                 include_page_numbers: bool = True,
                 unicode_box_drawing: bool = False):
        """
        Initialize the ASCII formatter.
        
        Args:
            include_page_numbers: Whether to include page numbers
            unicode_box_drawing: Whether to use Unicode box drawing characters
        """
        super().__init__()
        self.include_page_numbers = include_page_numbers
        self.unicode_box_drawing = unicode_box_drawing
        
        # Set characters for tree drawing
        if unicode_box_drawing:
            self.branch = "├── "
            self.last_branch = "└── "
            self.pipe = "│   "
            self.space = "    "
        else:
            self.branch = "|-- "
            self.last_branch = "`-- "
            self.pipe = "|   "
            self.space = "    "
    
    def format(self, document: Document) -> str:
        """
        Format the document as an ASCII tree outline.
        
        Args:
            document: Document model to format
            
        Returns:
            ASCII tree string
            
        Raises:
            FormatError: If formatting fails
        """
        try:
            lines = []
            
            # Document title
            lines.append(document.title)
            
            # Format sections
            sections = document.sections
            for i, section in enumerate(sections):
                is_last = (i == len(sections) - 1)
                prefix = self.last_branch if is_last else self.branch
                indent = ""
                
                lines.extend(self._format_section(section, prefix, indent, is_last))
            
            return "\n".join(lines)
        
        except Exception as e:
            raise FormatError(f"Failed to format document as ASCII tree: {str(e)}")
    
    def format_and_write(self, 
                         document: Document, 
                         output_path: Optional[Union[str, Path, TextIO]] = None) -> str:
        """
        Format the document as ASCII tree and optionally write to a file.
        
        Args:
            document: Document model to format
            output_path: Path or file-like object to write to (optional)
            
        Returns:
            ASCII tree string
            
        Raises:
            FormatError: If formatting or writing fails
        """
        # Format the document
        formatted_content = self.format(document)
        
        # Validate and write to file if requested
        if output_path is not None:
            try:
                validate_ascii_output(formatted_content, output_path)
            except Exception as e:
                raise FormatError(f"Failed to write ASCII tree output: {str(e)}")
        
        return formatted_content
    
    def _format_section(self, section: Section, prefix: str, indent: str, is_last: bool) -> List[str]:
        """
        Format a section as part of an ASCII tree.
        
        Args:
            section: Section to format
            prefix: Prefix for this section (branch or last_branch)
            indent: Indentation string
            is_last: Whether this is the last section at this level
            
        Returns:
            List of lines for this section and its subsections
        """
        lines = []
        
        # Format section title with page numbers if requested
        title = section.title
        
        if self.include_page_numbers and section.pages:
            start_page = min(section.pages)
            end_page = max(section.pages)
            
            if start_page == end_page:
                title += f" [Page {start_page}]"
            else:
                title += f" [Pages {start_page}-{end_page}]"
        
        # Add section line
        lines.append(f"{indent}{prefix}{title}")
        
        # Indentation for subsections
        next_indent = indent + (self.space if is_last else self.pipe)
        
        # Format subsections
        subsections = section.subsections
        for i, subsection in enumerate(subsections):
            is_last_child = (i == len(subsections) - 1)
            child_prefix = self.last_branch if is_last_child else self.branch
            
            lines.extend(self._format_section(subsection, child_prefix, next_indent, is_last_child))
        
        return lines