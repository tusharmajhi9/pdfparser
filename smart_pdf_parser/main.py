"""
Smart PDF Parser main entry point.

This module provides the main entry point for the Smart PDF Parser application.
"""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())