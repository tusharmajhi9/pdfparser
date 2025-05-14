"""
Markdown formatter for document output.

This module provides a formatter for converting Document models to Markdown.
"""

from typing import Union, Optional, TextIO, List
from pathlib import Path

from ..models.document import Document, Section, Table
from ..utils.exceptions import FormatError
from ..utils.validators import validate_markdown_output
from ..utils.logger import get_logger
from .base import BaseFormatter

logger = get_logger(__name__)

class MarkdownFormatter(BaseFormatter):
    """
    Formatter for converting Document models to Markdown.
    """
    
    def __init__(self, 
                 include_page_numbers: bool = True,
                 include_toc: bool = True,
                 max_toc_depth: int = 3):
        """
        Initialize the Markdown formatter.
        
        Args:
            include_page_numbers: Whether to include page numbers in section headings
            include_toc: Whether to include a table of contents at the start
            max_toc_depth: Maximum heading level to include in the TOC
        """
        super().__init__()
        self.include_page_numbers = include_page_numbers
        self.include_toc = include_toc
        self.max_toc_depth = max_toc_depth
    
    def format(self, document: Document) -> str:
        """
        Format the document as Markdown.
        
        Args:
            document: Document model to format
            
        Returns:
            Markdown string
            
        Raises:
            FormatError: If formatting fails
        """
        try:
            md_lines = []
            
            # Document title
            md_lines.append(f"# {document.title}")
            md_lines.append("")
            
            # Table of contents (if requested)
            if self.include_toc:
                md_lines.extend(self._generate_toc(document))
                md_lines.append("")
                md_lines.append("---")
                md_lines.append("")
            
            # Sections
            for section in document.sections:
                md_lines.extend(self._format_section(section))
            
            return "\n".join(md_lines)
        
        except Exception as e:
            raise FormatError(f"Failed to format document as Markdown: {str(e)}")
    
    def format_and_write(self, 
                         document: Document, 
                         output_path: Optional[Union[str, Path, TextIO]] = None) -> str:
        """
        Format the document as Markdown and optionally write to a file.
        
        Args:
            document: Document model to format
            output_path: Path or file-like object to write to (optional)
            
        Returns:
            Markdown string
            
        Raises:
            FormatError: If formatting or writing fails
        """
        # Format the document
        formatted_content = self.format(document)
        
        # Validate and write to file if requested
        if output_path is not None:
            try:
                validate_markdown_output(formatted_content, output_path)
            except Exception as e:
                raise FormatError(f"Failed to write Markdown output: {str(e)}")
        
        return formatted_content
    
    def _generate_toc(self, document: Document) -> List[str]:
        """
        Generate a table of contents for the document.
        
        Args:
            document: Document model
            
        Returns:
            List of Markdown lines for the TOC
        """
        toc_lines = ["## Table of Contents", ""]
        
        def add_section_to_toc(section: Section, indent: int = 0):
            # Skip if beyond max depth
            if section.level > self.max_toc_depth:
                return
            
            # Add indent spaces
            indentation = "  " * indent
            
            # Create TOC entry with link
            link_target = section.title.lower().replace(" ", "-").replace(".", "")
            link_target = "".join(c for c in link_target if c.isalnum() or c == "-")
            
            toc_lines.append(f"{indentation}- [{section.title}](#{link_target})")
            
            # Add subsections
            for subsection in section.subsections:
                add_section_to_toc(subsection, indent + 1)
        
        # Add all sections to TOC
        for section in document.sections:
            add_section_to_toc(section)
        
        return toc_lines
    
    def _format_section(self, section: Section, include_content: bool = True) -> List[str]:
        """
        Format a section as Markdown.
        
        Args:
            section: Section model to format
            include_content: Whether to include the section content
            
        Returns:
            List of Markdown lines for the section
        """
        md_lines = []
        
        # Section heading with appropriate level of #
        heading_prefix = "#" * section.level
        md_lines.append(f"{heading_prefix} {section.title}")
        
        # Add page range if requested
        if self.include_page_numbers and section.pages:
            start_page = min(section.pages)
            end_page = max(section.pages)
            
            if start_page == end_page:
                md_lines.append(f"*Page {start_page}*")
            else:
                md_lines.append(f"*Pages {start_page}-{end_page}*")
            
            md_lines.append("")
        
        # Add section content if requested
        if include_content and section.content:
            md_lines.append(section.content.strip())
            md_lines.append("")
        
        # Add tables
        for table in section.tables:
            md_table = table.to_markdown()
            if md_table:
                md_lines.append(md_table)
                md_lines.append("")
        
        # Add subsections
        for subsection in section.subsections:
            md_lines.extend(self._format_section(subsection))
        
        return md_lines