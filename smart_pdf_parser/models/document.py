"""
Data models for the PDF document structure.

This module defines Pydantic models for the document, sections, and tables to ensure
type safety and validation throughout the application.
"""

from __future__ import annotations
from typing import List, Dict, Optional, Union, Tuple, Set
from pydantic import BaseModel, Field, validator, root_validator
import logging

logger = logging.getLogger(__name__)

class Table(BaseModel):
    """Model representing a table extracted from the PDF."""
    
    caption: Optional[str] = Field(None, description="Table caption if available")
    page: int = Field(..., description="Page number where the table appears")
    position: Tuple[float, float, float, float] = Field(
        ..., 
        description="Position of the table on the page (x0, y0, x1, y1)"
    )
    data: List[List[str]] = Field(
        ..., 
        description="Table data as a list of rows, each row being a list of cell values"
    )
    
    @validator('data')
    def validate_table_data(cls, v):
        """Ensure table data is properly structured."""
        if not v:
            raise ValueError("Table data cannot be empty")
        
        # Check if all rows have the same number of columns
        row_lengths = {len(row) for row in v}
        if len(row_lengths) > 1:
            logger.warning(f"Table has inconsistent row lengths: {row_lengths}")
        
        return v
    
    def to_markdown(self) -> str:
        """Convert table to Markdown format."""
        if not self.data:
            return ""
        
        md_lines = []
        
        # Add caption if available
        if self.caption:
            md_lines.append(f"**{self.caption}**\n")
        
        # Header row
        md_lines.append("| " + " | ".join(self.data[0]) + " |")
        
        # Separator row
        md_lines.append("| " + " | ".join(["---"] * len(self.data[0])) + " |")
        
        # Data rows
        for row in self.data[1:]:
            # Ensure row has same number of columns as header
            padded_row = row + [""] * (len(self.data[0]) - len(row))
            truncated_row = padded_row[:len(self.data[0])]
            md_lines.append("| " + " | ".join(truncated_row) + " |")
        
        return "\n".join(md_lines)


class Section(BaseModel):
    """Model representing a section in the document."""
    
    title: str = Field(..., description="Section title")
    level: int = Field(..., ge=1, description="Heading level (1 for top-level, 2 for subsection, etc.)")
    pages: List[int] = Field(..., description="List of page numbers covered by this section")
    content: str = Field("", description="Plain text content of the section")
    tables: List[Table] = Field(default_factory=list, description="Tables within this section")
    subsections: List[Section] = Field(default_factory=list, description="Subsections within this section")
    
    @validator('level')
    def validate_level(cls, v):
        """Ensure section level is positive."""
        if v < 1:
            raise ValueError("Section level must be at least 1")
        return v
    
    @validator('pages')
    def validate_pages(cls, v):
        """Ensure pages are valid and in order."""
        if not v:
            raise ValueError("Section must cover at least one page")
        
        # Check if pages are in ascending order
        if sorted(v) != v:
            logger.warning(f"Section pages not in ascending order: {v}")
            return sorted(v)
        
        return v
    
    @root_validator
    def check_section_consistency(cls, values):
        """Ensure subsections are within parent's page range."""
        pages = set(values.get('pages', []))
        subsections = values.get('subsections', [])
        
        for subsection in subsections:
            subsection_pages = set(subsection.pages)
            if not subsection_pages.issubset(pages):
                logger.warning(
                    f"Subsection '{subsection.title}' contains pages {subsection_pages - pages} "
                    f"not in parent section '{values.get('title')}'"
                )
        
        return values
    
    def add_subsection(self, subsection: Section) -> None:
        """Add a subsection to this section."""
        if subsection.level <= self.level:
            raise ValueError(f"Subsection level ({subsection.level}) must be greater than "
                            f"parent section level ({self.level})")
        self.subsections.append(subsection)
    
    def get_page_range(self) -> Tuple[int, int]:
        """Get the first and last page of the section."""
        if not self.pages:
            raise ValueError("Section has no pages")
        return min(self.pages), max(self.pages)


class Document(BaseModel):
    """Model representing the entire PDF document."""
    
    title: str = Field(..., description="Document title")
    pages: int = Field(..., gt=0, description="Total number of pages")
    sections: List[Section] = Field(default_factory=list, description="Top-level sections")
    
    @validator('pages')
    def validate_pages(cls, v):
        """Ensure page count is positive."""
        if v <= 0:
            raise ValueError("Document must have at least one page")
        return v
    
    @root_validator
    def check_document_consistency(cls, values):
        """Ensure sections cover valid page ranges."""
        total_pages = values.get('pages', 0)
        sections = values.get('sections', [])
        
        all_section_pages: Set[int] = set()
        for section in sections:
            for page in section.pages:
                if page < 1 or page > total_pages:
                    raise ValueError(f"Section '{section.title}' references invalid page {page}. "
                                    f"Document has {total_pages} pages.")
                all_section_pages.add(page)
        
        # Check if there are pages not covered by any section
        missing_pages = set(range(1, total_pages + 1)) - all_section_pages
        if missing_pages:
            logger.warning(f"Pages not covered by any section: {missing_pages}")
        
        return values
    
    def add_section(self, section: Section) -> None:
        """Add a top-level section to the document."""
        if section.level != 1:
            raise ValueError(f"Top-level section must have level 1, got {section.level}")
        self.sections.append(section)
    
    def get_all_sections(self) -> List[Section]:
        """Get a flattened list of all sections, including subsections."""
        result = []
        
        def collect_sections(sections, acc):
            for section in sections:
                acc.append(section)
                collect_sections(section.subsections, acc)
        
        collect_sections(self.sections, result)
        return result