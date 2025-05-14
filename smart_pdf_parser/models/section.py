"""
Section model for representing document structure.

This module defines the Section class, which represents a section or subsection
in the logical structure of a document.
"""

from __future__ import annotations
from typing import List, Optional, Tuple, Set, Dict, Any
from pydantic import BaseModel, Field, validator, root_validator
from typing import TYPE_CHECKING, List
if TYPE_CHECKING:
    from .table import Table
import logging

from ..utils.logger import get_logger

logger = get_logger(__name__)

class Section(BaseModel):
    """Model representing a section in the document."""
    
    title: str = Field(..., description="Section title")
    level: int = Field(..., ge=1, description="Heading level (1 for top-level, 2 for subsection, etc.)")
    pages: List[int] = Field(..., description="List of page numbers covered by this section")
    content: str = Field("", description="Plain text content of the section")
    tables: List["Table"] = Field(default_factory=list, description="Tables within this section")
    subsections: List["Section"] = Field(default_factory=list, description="Subsections within this section")
    
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
    
    def add_subsection(self, subsection: "Section") -> None:
        """
        Add a subsection to this section.
        
        Args:
            subsection: Section to add as a subsection
            
        Raises:
            ValueError: If subsection level is not greater than parent level
        """
        if subsection.level <= self.level:
            raise ValueError(f"Subsection level ({subsection.level}) must be greater than "
                            f"parent section level ({self.level})")
        self.subsections.append(subsection)
    
    def get_page_range(self) -> Tuple[int, int]:
        """
        Get the first and last page of the section.
        
        Returns:
            Tuple of (first_page, last_page)
            
        Raises:
            ValueError: If section has no pages
        """
        if not self.pages:
            raise ValueError("Section has no pages")
        return min(self.pages), max(self.pages)
    
    def get_all_subsections(self) -> List["Section"]:
        """
        Get all subsections recursively.
        
        Returns:
            List of all subsections at all levels
        """
        result = []
        
        def collect(section, acc):
            for subsection in section.subsections:
                acc.append(subsection)
                collect(subsection, acc)
        
        collect(self, result)
        return result
    
    def get_all_tables(self) -> List["Table"]:
        """
        Get all tables in this section and its subsections.
        
        Returns:
            List of all tables
        """
        result = list(self.tables)
        
        for subsection in self.subsections:
            result.extend(subsection.get_all_tables())
        
        return result
    
    def get_subsection_by_title(self, title: str) -> Optional["Section"]:
        """
        Find a subsection by title.
        
        Args:
            title: Title to search for
            
        Returns:
            Matching section or None if not found
        """
        for subsection in self.subsections:
            if subsection.title == title:
                return subsection
            
            # Recursive search
            result = subsection.get_subsection_by_title(title)
            if result:
                return result
        
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert section to dictionary representation.
        
        Returns:
            Dictionary representation of the section
        """
        return {
            "title": self.title,
            "level": self.level,
            "pages": self.pages,
            "content": self.content,
            "tables": [table.to_dict() for table in self.tables],
            "subsections": [subsection.to_dict() for subsection in self.subsections]
        }