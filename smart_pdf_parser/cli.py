"""
Command-line interface for the Smart PDF Parser.

This module provides a command-line interface for the Smart PDF Parser,
allowing users to convert PDF documents to various output formats.
"""

import argparse
import sys
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple

from .core.parser import PDFParser
from .formatters.json_formatter import JSONFormatter
from .formatters.markdown_formatter import MarkdownFormatter
from .formatters.ascii_formatter import ASCIIFormatter
from .utils.logger import configure_logging, get_logger
from .utils.exceptions import PDFParserError, FileAccessError, FormatError

logger = get_logger(__name__)

def parse_args(args: List[str] = None) -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Args:
        args: Command-line arguments (defaults to sys.argv[1:])
        
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Smart PDF Parser: Extract structured content from PDF files",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Input options
    parser.add_argument(
        "input_file",
        help="Path to the input PDF file"
    )
    
    # Output options
    parser.add_argument(
        "-o", "--output",
        help="Path to the output file(s). Use %ext% placeholder for format-specific extensions"
    )
    
    parser.add_argument(
        "-f", "--format",
        choices=["json", "markdown", "md", "ascii", "txt", "all"],
        default="all",
        help="Output format (default: all formats)"
    )
    
    # Parser options
    parser.add_argument(
        "--no-toc",
        action="store_true",
        help="Disable TOC-based structure extraction"
    )
    
    parser.add_argument(
        "--no-headings",
        action="store_true",
        help="Disable heading detection"
    )
    
    parser.add_argument(
        "--no-tables",
        action="store_true",
        help="Disable table detection"
    )
    
    parser.add_argument(
        "--min-heading-size",
        type=float,
        default=12.0,
        help="Minimum font size to consider as a heading"
    )
    
    parser.add_argument(
        "--heading-threshold",
        type=float,
        default=1.2,
        help="Ratio above normal text size to consider as heading"
    )
    
    # ASCII formatter options
    parser.add_argument(
        "--unicode-tree",
        action="store_true",
        help="Use Unicode box drawing characters for ASCII tree"
    )
    
    # Markdown formatter options
    parser.add_argument(
        "--no-page-numbers",
        action="store_true",
        help="Don't include page numbers in output"
    )
    
    parser.add_argument(
        "--no-toc-in-md",
        action="store_true",
        help="Don't include table of contents in Markdown output"
    )
    
    parser.add_argument(
        "--toc-depth",
        type=int,
        default=3,
        help="Maximum depth for table of contents"
    )
    
    # Logging options
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error", "critical"],
        default="info",
        help="Set logging level"
    )
    
    parser.add_argument(
        "--log-file",
        help="Path to log file"
    )
    
    # Version
    parser.add_argument(
        "-v", "--version",
        action="store_true",
        help="Show version information"
    )
    
    return parser.parse_args(args)

def get_output_paths(input_file: str, 
                     output_pattern: Optional[str], 
                     formats: List[str]) -> Dict[str, str]:
    """
    Get output file paths based on input file and requested formats.
    
    Args:
        input_file: Input file path
        output_pattern: Output file pattern (with optional %ext% placeholder)
        formats: List of requested output formats
        
    Returns:
        Dictionary mapping format names to output file paths
    """
    input_path = Path(input_file)
    input_stem = input_path.stem
    
    output_paths = {}
    
    for fmt in formats:
        ext = {"json": "json", "markdown": "md", "md": "md", "ascii": "txt", "txt": "txt"}[fmt]
        
        if output_pattern:
            if "%ext%" in output_pattern:
                output_path = output_pattern.replace("%ext%", ext)
            else:
                output_path = output_pattern
                
                # Ensure the extension matches the format
                path_obj = Path(output_path)
                if path_obj.suffix.lower() != f".{ext}":
                    output_path = f"{output_path}.{ext}"
        else:
            # Default to input_name.ext
            output_path = input_path.with_name(f"{input_stem}.{ext}")
        
        output_paths[fmt] = str(output_path)
    
    return output_paths

def main(args: List[str] = None) -> int:
    """
    Main entry point for the command-line interface.
    
    Args:
        args: Command-line arguments (defaults to sys.argv[1:])
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Parse arguments
    parsed_args = parse_args(args)
    
    # Show version and exit if requested
    if parsed_args.version:
        from . import __version__
        print(f"Smart PDF Parser v{__version__}")
        return 0
    
    # Configure logging
    configure_logging(
        level=parsed_args.log_level.upper(),
        log_file=parsed_args.log_file
    )
    
    # Log start
    logger.info(f"Smart PDF Parser starting with input file: {parsed_args.input_file}")
    
    try:
        # Get requested formats
        formats = []
        if parsed_args.format == "all":
            formats = ["json", "markdown", "ascii"]
        elif parsed_args.format == "md":
            formats = ["markdown"]
        elif parsed_args.format == "txt":
            formats = ["ascii"]
        else:
            formats = [parsed_args.format]
        
        # Get output paths
        output_paths = get_output_paths(
            parsed_args.input_file,
            parsed_args.output,
            formats
        )
        
        # Initialize parser
        parser = PDFParser(
            detect_tables=not parsed_args.no_tables,
            use_toc=not parsed_args.no_toc,
            detect_headings=not parsed_args.no_headings,
            min_heading_size=parsed_args.min_heading_size,
            heading_size_threshold=parsed_args.heading_threshold
        )
        
        # Parse the document
        document = parser.parse(parsed_args.input_file)
        
        # Initialize formatters
        formatters = {
            "json": JSONFormatter(pretty_print=True),
            "markdown": MarkdownFormatter(
                include_page_numbers=not parsed_args.no_page_numbers,
                include_toc=not parsed_args.no_toc_in_md,
                max_toc_depth=parsed_args.toc_depth
            ),
            "ascii": ASCIIFormatter(
                include_page_numbers=not parsed_args.no_page_numbers,
                unicode_box_drawing=parsed_args.unicode_tree
            )
        }
        
        # Format and write outputs
        for fmt in formats:
            formatter = formatters[fmt]
            output_path = output_paths[fmt]
            
            logger.info(f"Writing {fmt} output to {output_path}")
            formatter.format_and_write(document, output_path)
        
        logger.info("PDF parsing completed successfully")
        return 0
    
    except FileNotFoundError as e:
        logger.error(f"Input file not found: {e}")
        print(f"Error: Input file not found: {e}", file=sys.stderr)
        return 1
    
    except FileAccessError as e:
        logger.error(f"File access error: {e}")
        print(f"Error: Cannot access file: {e}", file=sys.stderr)
        return 2
    
    except FormatError as e:
        logger.error(f"Formatting error: {e}")
        print(f"Error: Failed to format output: {e}", file=sys.stderr)
        return 3
    
    except PDFParserError as e:
        logger.error(f"PDF parsing error: {e}")
        print(f"Error: Failed to parse PDF: {e}", file=sys.stderr)
        return 4
    
    except KeyboardInterrupt:
        logger.warning("Processing interrupted by user")
        print("Processing interrupted by user", file=sys.stderr)
        return 130
    
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print(f"Error: An unexpected error occurred: {e}", file=sys.stderr)
        return 5

if __name__ == "__main__":
    sys.exit(main())