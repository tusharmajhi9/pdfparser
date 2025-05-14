"""
Input and output validation utilities.

This module provides functions for validating inputs and outputs throughout the application.
"""

import os
import fitz  # PyMuPDF
import logging
from typing import List, Dict, Any, Union, Optional, BinaryIO, TextIO
import json
from pathlib import Path

from ..utils.exceptions import PDFInputError, FileAccessError, ValidationError
from ..utils.logger import get_logger

logger = get_logger(__name__)

def validate_pdf_file(file_path: Union[str, Path, BinaryIO]) -> fitz.Document:
    """
    Validate and open a PDF file.
    
    Args:
        file_path: Path to the PDF file or file-like object
        
    Returns:
        PyMuPDF Document object
        
    Raises:
        PDFInputError: If the file is not a valid PDF
        FileAccessError: If the file cannot be accessed
    """
    logger.debug(f"Validating PDF file: {file_path}")
    
    try:
        if isinstance(file_path, (str, Path)):
            if not os.path.exists(file_path):
                raise FileAccessError(f"File not found: {file_path}")
            
            if not os.path.isfile(file_path):
                raise PDFInputError(f"Path is not a file: {file_path}")
            
            # Check file extension
            if not str(file_path).lower().endswith('.pdf'):
                logger.warning(f"File does not have .pdf extension: {file_path}")
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                raise PDFInputError(f"File is empty: {file_path}")
            
            if file_size > 1_000_000_000:  # 1 GB
                logger.warning(f"Large PDF file detected ({file_size} bytes), may cause performance issues")
        
        # Open the PDF file
        pdf_document = fitz.open(file_path)
        
        # Basic validation
        if pdf_document.page_count == 0:
            raise PDFInputError(f"PDF file contains no pages")
        
        # Check if document is encrypted
        if pdf_document.is_encrypted:
            if not pdf_document.is_decrypted:
                raise PDFInputError(f"PDF file is encrypted and requires a password")
            logger.info(f"PDF file is encrypted but has been successfully decrypted")
        
        logger.info(f"Successfully validated PDF with {pdf_document.page_count} pages")
        return pdf_document
    
    except fitz.FileDataError as e:
        raise PDFInputError(f"Invalid PDF file: {str(e)}")
    except fitz.EmptyFileError:
        raise PDFInputError(f"Empty or corrupted PDF file")
    except fitz.FileNotFoundError:
        raise FileAccessError(f"File not found: {file_path}")
    except Exception as e:
        if "password required" in str(e).lower():
            raise PDFInputError(f"PDF file is encrypted and requires a password")
        raise PDFInputError(f"Error opening PDF file: {str(e)}")


def validate_output_path(file_path: Union[str, Path], create_dirs: bool = True) -> str:
    """
    Validate and prepare an output file path.
    
    Args:
        file_path: Path where the output will be written
        create_dirs: Whether to create parent directories if they don't exist
        
    Returns:
        Validated file path as string
        
    Raises:
        FileAccessError: If the path is invalid or cannot be written to
    """
    logger.debug(f"Validating output path: {file_path}")
    
    path = Path(file_path)
    
    # Check if the directory exists
    parent_dir = path.parent
    if not parent_dir.exists():
        if create_dirs:
            logger.info(f"Creating output directory: {parent_dir}")
            try:
                parent_dir.mkdir(parents=True)
            except Exception as e:
                raise FileAccessError(f"Failed to create directory {parent_dir}: {str(e)}")
        else:
            raise FileAccessError(f"Output directory does not exist: {parent_dir}")
    
    # Check if the directory is writable
    if not os.access(parent_dir, os.W_OK):
        raise FileAccessError(f"Output directory is not writable: {parent_dir}")
    
    # Check if the file already exists
    if path.exists():
        if not path.is_file():
            raise FileAccessError(f"Output path exists but is not a file: {file_path}")
        
        if not os.access(path, os.W_OK):
            raise FileAccessError(f"Output file exists but is not writable: {file_path}")
        
        logger.warning(f"Output file already exists and will be overwritten: {file_path}")
    
    return str(path)


def validate_json_output(data: Dict[str, Any], output_file: Optional[Union[str, Path, TextIO]] = None) -> str:
    """
    Validate JSON output data and optionally write to file.
    
    Args:
        data: Dictionary to be validated as JSON
        output_file: File to write the JSON data to (optional)
        
    Returns:
        JSON string
        
    Raises:
        ValidationError: If the data cannot be serialized to JSON
    """
    try:
        # Serialize with pretty printing
        json_str = json.dumps(data, indent=2, sort_keys=False, ensure_ascii=False)
        
        # Write to file if specified
        if output_file is not None:
            if isinstance(output_file, (str, Path)):
                # Validate output path
                file_path = validate_output_path(output_file)
                
                # Write to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(json_str)
                    logger.info(f"JSON output written to {file_path}")
            else:
                # Write to file-like object
                output_file.write(json_str)
                logger.info(f"JSON output written to file handle")
        
        return json_str
    
    except (TypeError, ValueError) as e:
        raise ValidationError(f"Failed to serialize output to JSON: {str(e)}")
    except Exception as e:
        raise ValidationError(f"Error writing JSON output: {str(e)}")


def validate_markdown_output(markdown: str, output_file: Optional[Union[str, Path, TextIO]] = None) -> str:
    """
    Validate Markdown output and optionally write to file.
    
    Args:
        markdown: Markdown string to validate
        output_file: File to write the Markdown to (optional)
        
    Returns:
        Validated Markdown string
        
    Raises:
        ValidationError: If the Markdown is invalid or cannot be written
    """
    # Basic validation
    if not markdown:
        logger.warning("Empty Markdown output")
    
    # Check for basic Markdown structure
    if not any(line.startswith('#') for line in markdown.split('\n')):
        logger.warning("Markdown output contains no headings")
    
    # Write to file if specified
    if output_file is not None:
        try:
            if isinstance(output_file, (str, Path)):
                # Validate output path
                file_path = validate_output_path(output_file)
                
                # Write to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(markdown)
                    logger.info(f"Markdown output written to {file_path}")
            else:
                # Write to file-like object
                output_file.write(markdown)
                logger.info(f"Markdown output written to file handle")
        except Exception as e:
            raise ValidationError(f"Error writing Markdown output: {str(e)}")
    
    return markdown


def validate_ascii_output(ascii_tree: str, output_file: Optional[Union[str, Path, TextIO]] = None) -> str:
    """
    Validate ASCII tree output and optionally write to file.
    
    Args:
        ascii_tree: ASCII tree string to validate
        output_file: File to write the ASCII tree to (optional)
        
    Returns:
        Validated ASCII tree string
        
    Raises:
        ValidationError: If the ASCII tree is invalid or cannot be written
    """
    # Basic validation
    if not ascii_tree:
        logger.warning("Empty ASCII tree output")
    
    # Write to file if specified
    if output_file is not None:
        try:
            if isinstance(output_file, (str, Path)):
                # Validate output path
                file_path = validate_output_path(output_file)
                
                # Write to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(ascii_tree)
                    logger.info(f"ASCII tree output written to {file_path}")
            else:
                # Write to file-like object
                output_file.write(ascii_tree)
                logger.info(f"ASCII tree output written to file handle")
        except Exception as e:
            raise ValidationError(f"Error writing ASCII tree output: {str(e)}")
    
    return ascii_tree