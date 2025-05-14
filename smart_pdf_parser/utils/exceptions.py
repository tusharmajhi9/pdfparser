"""
Custom exceptions for the Smart PDF Parser.

This module defines specific exception types for different error scenarios
in the application, allowing for more precise error handling.
"""

class PDFParserError(Exception):
    """Base exception for all Smart PDF Parser errors."""
    pass


class PDFInputError(PDFParserError):
    """Exception raised for errors in the input PDF file."""
    pass


class FileAccessError(PDFParserError):
    """Exception raised when a file cannot be accessed or read."""
    pass


class PDFStructureError(PDFParserError):
    """Exception raised when the PDF structure cannot be properly parsed."""
    pass


class PDFTOCError(PDFStructureError):
    """Exception raised when there are issues extracting the table of contents."""
    pass


class TableExtractionError(PDFParserError):
    """Exception raised when tables cannot be properly extracted."""
    pass


class FormatError(PDFParserError):
    """Exception raised when output cannot be properly formatted."""
    pass


class ValidationError(PDFParserError):
    """Exception raised when data validation fails."""
    pass