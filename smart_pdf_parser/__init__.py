"""
Smart PDF Parser - A package for extracting structured content from PDF files.

This package provides tools for extracting structured content from PDF files,
including sections, headings, tables, and page content, with support for various
output formats such as JSON, Markdown, and ASCII.
"""

__version__ = "1.0.0"
__author__ = "Smart PDF Parser Team"
__license__ = "MIT"

# Import main components
from .core.parser import PDFParser
from .formatters.json_formatter import JSONFormatter
from .formatters.markdown_formatter import MarkdownFormatter
from .formatters.ascii_formatter import ASCIIFormatter
from .utils.logger import configure_logging, get_logger
from .models import Document, Section, Table

__all__ = [
    "PDFParser",
    "JSONFormatter",
    "MarkdownFormatter",
    "ASCIIFormatter",
    "configure_logging",
    "get_logger",
    "Document",
    "Section",
    "Table"
]