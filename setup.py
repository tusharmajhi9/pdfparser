"""
Setup script for the Smart PDF Parser package.
"""

from setuptools import setup, find_packages
import os
import re

# Get version from __init__.py
with open(os.path.join("smart_pdf_parser", "__init__.py"), "r") as f:
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", f.read(), re.M)
    if version_match:
        version = version_match.group(1)
    else:
        raise RuntimeError("Unable to find version string")

# Read long description from README.md
with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

# Read requirements from requirements.txt
with open("requirements.txt", "r") as f:
    requirements = f.read().splitlines()

setup(
    name="smart_pdf_parser",
    version=version,
    description="A package for extracting structured content from PDF files",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Smart PDF Parser Team",
    author_email="info@smartpdfparser.example.com",
    url="https://github.com/example/smart_pdf_parser",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Text Processing :: Markup",
        "Topic :: Office/Business",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "smart-pdf-parser=smart_pdf_parser.cli:main",
        ],
    },
)