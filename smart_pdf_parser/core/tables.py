"""
Table detection and extraction functionality.

This module provides specialized functions for detecting and extracting tables
from PDF documents, using geometric analysis of the page content.
"""

import fitz  # PyMuPDF
from typing import List, Tuple, Dict, Any, Optional, Set
import numpy as np
from collections import defaultdict

from ..models.document import Table
from ..utils.exceptions import TableExtractionError
from ..utils.logger import get_logger

logger = get_logger(__name__)

class TableDetector:
    """
    Class for detecting and extracting tables from PDF documents.
    """
    
    def __init__(self,
                 min_rows: int = 2,
                 min_cols: int = 2,
                 min_cell_height: float = 5.0,
                 min_cell_width: float = 10.0,
                 line_tolerance: float = 2.0,
                 intersect_tolerance: float = 3.0,
                 table_padding: float = 5.0):
        """
        Initialize the table detector with configuration parameters.
        
        Args:
            min_rows: Minimum number of rows to consider as a table
            min_cols: Minimum number of columns to consider as a table
            min_cell_height: Minimum height of a cell in points
            min_cell_width: Minimum width of a cell in points
            line_tolerance: Tolerance for line alignment in points
            intersect_tolerance: Tolerance for line intersection in points
            table_padding: Padding around detected tables in points
        """
        self.min_rows = min_rows
        self.min_cols = min_cols
        self.min_cell_height = min_cell_height
        self.min_cell_width = min_cell_width
        self.line_tolerance = line_tolerance
        self.intersect_tolerance = intersect_tolerance
        self.table_padding = table_padding
    
    def detect_tables(self, page: fitz.Page, page_num: int) -> List[Table]:
        """
        Detect tables on a PDF page.
        
        Args:
            page: PyMuPDF page object
            page_num: Page number (1-based) for logging and result reporting
            
        Returns:
            List of detected Table objects
            
        Raises:
            TableExtractionError: If table detection fails
        """
        try:
            tables = []
            
            # Get all drawings (lines, rectangles) from the page
            drawings = page.get_drawings()
            
            if not drawings:
                return []
            
            # Extract lines from drawings
            h_lines, v_lines = self._extract_lines_from_drawings(drawings)
            
            # If insufficient lines, check for explicit tables using rectangles
            if len(h_lines) < self.min_rows or len(v_lines) < self.min_cols:
                rect_tables = self._detect_rectangle_tables(drawings, page)
                if rect_tables:
                    return rect_tables
            
            # Find potential tables using line intersections
            table_regions = self._find_table_regions(h_lines, v_lines)
            
            # Extract table data for each detected region
            for i, region in enumerate(table_regions):
                table_bounds = region["bounds"]
                h_group = region["h_lines"]
                v_group = region["v_lines"]
                
                # Extract table content using detected grid
                table_data = self._extract_table_data(page, h_group, v_group, table_bounds)
                
                # Validate table data
                if (table_data and 
                    len(table_data) >= self.min_rows and 
                    any(len(row) >= self.min_cols for row in table_data)):
                    
                    # Create table model
                    table = Table(
                        caption=f"Table {i + 1} on page {page_num}",
                        page=page_num,
                        position=table_bounds,
                        data=table_data
                    )
                    
                    tables.append(table)
            
            # For complex pages, try alternative detection methods if no tables found
            if not tables:
                # Try to detect tables using text alignment patterns
                text_tables = self._detect_tables_from_text(page, page_num)
                if text_tables:
                    tables.extend(text_tables)
            
            logger.debug(f"Detected {len(tables)} tables on page {page_num}")
            return tables
        
        except Exception as e:
            raise TableExtractionError(f"Error detecting tables on page {page_num}: {str(e)}")
    
    def _extract_lines_from_drawings(self, drawings: List[Dict[str, Any]]) -> Tuple[List[Tuple], List[Tuple]]:
        """
        Extract horizontal and vertical lines from page drawings.
        
        Args:
            drawings: List of drawing dictionaries from PyMuPDF
            
        Returns:
            Tuple of (horizontal_lines, vertical_lines), each line as (x0, y0, x1, y1)
        """
        h_lines = []
        v_lines = []
        
        for drawing in drawings:
            if drawing["type"] == "l":  # Line
                p1, p2 = drawing["pts"]
                x0, y0 = p1
                x1, y1 = p2
                
                # Check line length
                length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
                
                # Classify as horizontal or vertical
                if abs(y1 - y0) < self.line_tolerance:  # Horizontal line
                    h_lines.append((min(x0, x1), y0, max(x0, x1), y1))
                
                elif abs(x1 - x0) < self.line_tolerance:  # Vertical line
                    v_lines.append((x0, min(y0, y1), x1, max(y0, y1)))
        
        # Also extract lines from rectangles
        for drawing in drawings:
            if drawing["type"] == "re":  # Rectangle
                rect = drawing["rect"]
                x0, y0, x1, y1 = rect
                
                # Add rectangle edges as lines
                h_lines.append((x0, y0, x1, y0))  # Top
                h_lines.append((x0, y1, x1, y1))  # Bottom
                v_lines.append((x0, y0, x0, y1))  # Left
                v_lines.append((x1, y0, x1, y1))  # Right
        
        return h_lines, v_lines
    
    def _detect_rectangle_tables(self, drawings: List[Dict[str, Any]], page: fitz.Page) -> List[Table]:
        """
        Detect tables formed by explicit rectangles.
        
        Args:
            drawings: List of drawing dictionaries from PyMuPDF
            page: PyMuPDF page object
            
        Returns:
            List of detected Table objects
        """
        tables = []
        cell_rects = []
        
        # Extract rectangles from drawings
        for drawing in drawings:
            if drawing["type"] == "re":  # Rectangle
                rect = drawing["rect"]
                x0, y0, x1, y1 = rect
                
                # Check if this could be a table cell (minimum size)
                if x1 - x0 >= self.min_cell_width and y1 - y0 >= self.min_cell_height:
                    cell_rects.append(rect)
        
        # If insufficient rectangles, no tables
        if len(cell_rects) < self.min_rows * self.min_cols:
            return []
        
        # Group rectangles into potential tables
        rect_groups = self._group_rectangles(cell_rects)
        
        # Process each group as a potential table
        for group in rect_groups:
            if len(group) < self.min_rows * self.min_cols:
                continue
            
            # Find table bounds
            x_coords = [rect[0] for rect in group] + [rect[2] for rect in group]
            y_coords = [rect[1] for rect in group] + [rect[3] for rect in group]
            
            table_bounds = (
                min(x_coords) - self.table_padding,
                min(y_coords) - self.table_padding,
                max(x_coords) + self.table_padding,
                max(y_coords) + self.table_padding
            )
            
            # Extract text from each cell
            table_data = self._extract_data_from_rectangles(page, group)
            
            if table_data and len(table_data) >= self.min_rows and len(table_data[0]) >= self.min_cols:
                # Create table model
                table = Table(
                    caption=None,  # No caption detected
                    page=page.number + 1,  # 1-based page number
                    position=table_bounds,
                    data=table_data
                )
                
                tables.append(table)
        
        return tables
    
    def _group_rectangles(self, rectangles: List[Tuple[float, float, float, float]]) -> List[List[Tuple]]:
        """
        Group rectangles that are likely part of the same table.
        
        Args:
            rectangles: List of rectangle coordinates (x0, y0, x1, y1)
            
        Returns:
            List of rectangle groups, each group being a list of rectangles
        """
        if not rectangles:
            return []
        
        groups = []
        visited = set()
        
        for i, rect1 in enumerate(rectangles):
            if i in visited:
                continue
            
            # Start a new group
            group = [rect1]
            visited.add(i)
            
            # Check for alignment with other rectangles
            for j, rect2 in enumerate(rectangles):
                if j in visited:
                    continue
                
                # Check if rect2 is aligned with any rectangle in the current group
                if self._is_aligned_with_group(rect2, group):
                    group.append(rect2)
                    visited.add(j)
            
            if len(group) >= self.min_rows * self.min_cols:
                groups.append(group)
        
        return groups
    
    def _is_aligned_with_group(self, rect: Tuple[float, float, float, float], 
                              group: List[Tuple[float, float, float, float]]) -> bool:
        """
        Check if a rectangle is aligned with any rectangle in a group.
        
        Args:
            rect: Rectangle coordinates (x0, y0, x1, y1)
            group: List of rectangle coordinates
            
        Returns:
            True if aligned, False otherwise
        """
        for r in group:
            # Check horizontal alignment (sharing y-coordinate)
            y_aligned = (
                abs(rect[1] - r[1]) < self.line_tolerance or  # Top edges aligned
                abs(rect[3] - r[3]) < self.line_tolerance or  # Bottom edges aligned
                abs(rect[1] - r[3]) < self.line_tolerance or  # Top edge with bottom edge
                abs(rect[3] - r[1]) < self.line_tolerance     # Bottom edge with top edge
            )
            
            # Check vertical alignment (sharing x-coordinate)
            x_aligned = (
                abs(rect[0] - r[0]) < self.line_tolerance or  # Left edges aligned
                abs(rect[2] - r[2]) < self.line_tolerance or  # Right edges aligned
                abs(rect[0] - r[2]) < self.line_tolerance or  # Left edge with right edge
                abs(rect[2] - r[0]) < self.line_tolerance     # Right edge with left edge
            )
            
            if x_aligned or y_aligned:
                return True
        
        return False
    
    def _extract_data_from_rectangles(self, page: fitz.Page, 
                                     rectangles: List[Tuple[float, float, float, float]]) -> List[List[str]]:
        """
        Extract table data from a group of rectangles.
        
        Args:
            page: PyMuPDF page object
            rectangles: List of rectangle coordinates
            
        Returns:
            Table data as a list of rows, each row being a list of cell values
        """
        # Find unique x and y coordinates to define the grid
        x_coords = sorted(set([r[0] for r in rectangles] + [r[2] for r in rectangles]))
        y_coords = sorted(set([r[1] for r in rectangles] + [r[3] for r in rectangles]))
        
        # Remove coordinates that are too close
        x_coords = self._filter_close_coordinates(x_coords)
        y_coords = self._filter_close_coordinates(y_coords)
        
        # Create table cells
        table_data = []
        
        for i in range(len(y_coords) - 1):
            row = []
            for j in range(len(x_coords) - 1):
                # Cell bounds
                cell_x0 = x_coords[j]
                cell_y0 = y_coords[i]
                cell_x1 = x_coords[j + 1]
                cell_y1 = y_coords[i + 1]
                
                # Extract text from this cell
                cell_text = page.get_text("text", clip=(cell_x0, cell_y0, cell_x1, cell_y1))
                cell_text = cell_text.strip()
                
                row.append(cell_text)
            
            if any(cell for cell in row):  # Skip empty rows
                table_data.append(row)
        
        return table_data
    
    def _filter_close_coordinates(self, coords: List[float]) -> List[float]:
        """
        Filter out coordinates that are very close to each other.
        
        Args:
            coords: List of coordinates
            
        Returns:
            Filtered list of coordinates
        """
        if not coords:
            return []
        
        filtered = [coords[0]]
        
        for coord in coords[1:]:
            if coord - filtered[-1] > self.line_tolerance:
                filtered.append(coord)
        
        return filtered
    
    def _find_table_regions(self, h_lines: List[Tuple], v_lines: List[Tuple]) -> List[Dict[str, Any]]:
        """
        Find potential table regions based on line intersections.
        
        Args:
            h_lines: List of horizontal lines (x0, y0, x1, y1)
            v_lines: List of vertical lines (x0, y0, x1, y1)
            
        Returns:
            List of potential table regions
        """
        # Group lines by position
        h_groups = self._group_lines_by_position(h_lines, axis=1)  # Group by y-coordinate
        v_groups = self._group_lines_by_position(v_lines, axis=0)  # Group by x-coordinate
        
        # Find table candidates
        table_regions = []
        
        for h_group in h_groups:
            for v_group in v_groups:
                # Check if these groups form a grid
                if self._is_valid_grid(h_group, v_group):
                    # Find table bounds
                    x0 = min(line[0] for line in v_group) - self.table_padding
                    y0 = min(line[1] for line in h_group) - self.table_padding
                    x1 = max(line[2] for line in v_group) + self.table_padding
                    y1 = max(line[3] for line in h_group) + self.table_padding
                    
                    table_regions.append({
                        "bounds": (x0, y0, x1, y1),
                        "h_lines": h_group,
                        "v_lines": v_group
                    })
        
        # Merge overlapping regions
        merged_regions = self._merge_overlapping_regions(table_regions)
        
        return merged_regions
    
    def _group_lines_by_position(self, lines: List[Tuple], axis: int) -> List[List[Tuple]]:
        """
        Group lines that have similar positions along the specified axis.
        
        Args:
            lines: List of lines (x0, y0, x1, y1)
            axis: Axis to group by (0 for x, 1 for y)
            
        Returns:
            List of groups, each group being a list of lines
        """
        if not lines:
            return []
        
        # Sort lines by position
        sorted_lines = sorted(lines, key=lambda line: line[axis])
        
        groups = []
        current_group = [sorted_lines[0]]
        current_pos = sorted_lines[0][axis]
        
        for line in sorted_lines[1:]:
            line_pos = line[axis]
            
            # Check if this line is close to the current group
            if abs(line_pos - current_pos) <= self.line_tolerance:
                # Add to current group
                current_group.append(line)
            else:
                # Start a new group
                if len(current_group) >= 2:  # Only keep groups with multiple lines
                    groups.append(current_group)
                
                current_group = [line]
                current_pos = line_pos
        
        # Add the last group
        if len(current_group) >= 2:
            groups.append(current_group)
        
        return groups
    
    def _is_valid_grid(self, h_lines: List[Tuple], v_lines: List[Tuple]) -> bool:
        """
        Check if horizontal and vertical lines form a valid grid.
        
        Args:
            h_lines: Horizontal lines
            v_lines: Vertical lines
            
        Returns:
            True if a valid grid, False otherwise
        """
        # Check if we have enough lines
        if len(h_lines) < self.min_rows or len(v_lines) < self.min_cols:
            return False
        
        # Count intersections
        intersections = 0
        
        for h_line in h_lines:
            h_x0, h_y0, h_x1, h_y1 = h_line
            
            for v_line in v_lines:
                v_x0, v_y0, v_x1, v_y1 = v_line
                
                # Check if lines intersect
                if (h_x0 - self.intersect_tolerance <= v_x0 <= h_x1 + self.intersect_tolerance and
                    v_y0 - self.intersect_tolerance <= h_y0 <= v_y1 + self.intersect_tolerance):
                    intersections += 1
        
        # Need a minimum number of intersections for a valid grid
        min_intersections = min(len(h_lines), len(v_lines))
        return intersections >= min_intersections
    
    def _merge_overlapping_regions(self, regions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge table regions that overlap significantly.
        
        Args:
            regions: List of table regions
            
        Returns:
            List of merged regions
        """
        if not regions:
            return []
        
        # Sort regions by top-left corner
        sorted_regions = sorted(regions, key=lambda r: (r["bounds"][1], r["bounds"][0]))
        
        merged = []
        current = sorted_regions[0]
        
        for region in sorted_regions[1:]:
            # Check if regions overlap
            if self._regions_overlap(current["bounds"], region["bounds"]):
                # Merge regions
                current = self._merge_regions(current, region)
            else:
                # Non-overlapping region, add current to results and continue
                merged.append(current)
                current = region
        
        # Add the last region
        merged.append(current)
        
        return merged
    
    def _regions_overlap(self, bounds1: Tuple[float, float, float, float], 
                        bounds2: Tuple[float, float, float, float]) -> bool:
        """
        Check if two regions overlap.
        
        Args:
            bounds1: First region bounds (x0, y0, x1, y1)
            bounds2: Second region bounds (x0, y0, x1, y1)
            
        Returns:
            True if regions overlap, False otherwise
        """
        x0_1, y0_1, x1_1, y1_1 = bounds1
        x0_2, y0_2, x1_2, y1_2 = bounds2
        
        # Check if one region is completely to the left/right/above/below the other
        if x1_1 < x0_2 or x1_2 < x0_1 or y1_1 < y0_2 or y1_2 < y0_1:
            return False
        
        return True
    
    def _merge_regions(self, region1: Dict[str, Any], region2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two table regions.
        
        Args:
            region1: First table region
            region2: Second table region
            
        Returns:
            Merged region
        """
        bounds1 = region1["bounds"]
        bounds2 = region2["bounds"]
        
        # Merge bounds
        merged_bounds = (
            min(bounds1[0], bounds2[0]),
            min(bounds1[1], bounds2[1]),
            max(bounds1[2], bounds2[2]),
            max(bounds1[3], bounds2[3])
        )
        
        # Merge line groups
        merged_h_lines = list(set(region1["h_lines"] + region2["h_lines"]))
        merged_v_lines = list(set(region1["v_lines"] + region2["v_lines"]))
        
        return {
            "bounds": merged_bounds,
            "h_lines": merged_h_lines,
            "v_lines": merged_v_lines
        }
    
    def _extract_table_data(self, page: fitz.Page, h_lines: List[Tuple], 
                           v_lines: List[Tuple], table_bounds: Tuple[float, float, float, float]) -> List[List[str]]:
        """
        Extract table data using the grid defined by horizontal and vertical lines.
        
        Args:
            page: PyMuPDF page object
            h_lines: Horizontal lines defining rows
            v_lines: Vertical lines defining columns
            table_bounds: Table boundaries (x0, y0, x1, y1)
            
        Returns:
            Table data as a list of rows, each row being a list of cell values
        """
        # Get unique y-coordinates from horizontal lines
        y_coords = sorted(set(line[1] for line in h_lines))
        
        # Get unique x-coordinates from vertical lines
        x_coords = sorted(set(line[0] for line in v_lines))
        
        # Remove coordinates that are too close
        y_coords = self._filter_close_coordinates(y_coords)
        x_coords = self._filter_close_coordinates(x_coords)
        
        if len(y_coords) < 2 or len(x_coords) < 2:
            return []
        
        # Create table cells
        table_data = []
        
        for i in range(len(y_coords) - 1):
            row = []
            for j in range(len(x_coords) - 1):
                # Cell bounds
                cell_x0 = x_coords[j]
                cell_y0 = y_coords[i]
                cell_x1 = x_coords[j + 1]
                cell_y1 = y_coords[i + 1]
                
                # Extract text from this cell
                cell_text = page.get_text("text", clip=(cell_x0, cell_y0, cell_x1, cell_y1))
                cell_text = cell_text.strip()
                
                row.append(cell_text)
            
            if any(cell for cell in row):  # Skip empty rows
                table_data.append(row)
        
        return table_data
    
    def _detect_tables_from_text(self, page: fitz.Page, page_num: int) -> List[Table]:
        """
        Detect tables based on text alignment patterns.
        
        Args:
            page: PyMuPDF page object
            page_num: Page number (1-based)
            
        Returns:
            List of detected Table objects
        """
        tables = []
        
        # Get text blocks
        blocks = page.get_text("dict")["blocks"]
        text_blocks = [b for b in blocks if b["type"] == 0]  # Type 0 is text
        
        if not text_blocks:
            return []
        
        # Look for tabular text patterns
        # This is a simplistic approach - in a real implementation, you would
        # need more sophisticated analysis of text positions
        
        # Find groups of lines with similar x-positions (potential columns)
        spans_by_line = defaultdict(list)
        
        for block in text_blocks:
            for line in block.get("lines", []):
                line_y = line["bbox"][1]  # y-coordinate of the line
                
                for span in line.get("spans", []):
                    span_x = span["bbox"][0]  # x-coordinate of the span
                    
                    spans_by_line[line_y].append({
                        "text": span.get("text", "").strip(),
                        "x": span_x,
                        "bbox": span["bbox"]
                    })
        
        # Look for lines with multiple text spans at similar x-positions
        x_positions = defaultdict(list)
        
        for line_y, spans in spans_by_line.items():
            if len(spans) < self.min_cols:
                continue
            
            for span in spans:
                x_positions[round(span["x"] / 5) * 5].append(line_y)
        
        # Find x-positions that appear in multiple lines (potential columns)
        column_x_positions = []
        
        for x_pos, lines in x_positions.items():
            if len(set(lines)) >= self.min_rows:
                column_x_positions.append(x_pos)
        
        if len(column_x_positions) < self.min_cols:
            return []
        
        # Group lines into potential tables
        line_groups = []
        current_group = []
        last_y = None
        
        for line_y in sorted(spans_by_line.keys()):
            if last_y is None or line_y - last_y < self.min_cell_height * 2:
                current_group.append(line_y)
            else:
                if len(current_group) >= self.min_rows:
                    line_groups.append(current_group)
                current_group = [line_y]
            
            last_y = line_y
        
        if len(current_group) >= self.min_rows:
            line_groups.append(current_group)
        
        # Create tables from line groups
        for group_idx, line_group in enumerate(line_groups):
            if len(line_group) < self.min_rows:
                continue
            
            table_data = []
            
            for line_y in line_group:
                spans = spans_by_line[line_y]
                
                # Sort spans by x-position
                spans.sort(key=lambda s: s["x"])
                
                row = []
                last_x = None
                cell_text = ""
                
                for span in spans:
                    if last_x is None or span["x"] - last_x > self.min_cell_width:
                        if cell_text:
                            row.append(cell_text)
                            cell_text = ""
                    
                    cell_text += span["text"] + " "
                    last_x = span["x"]
                
                if cell_text:
                    row.append(cell_text.strip())
                
                if len(row) >= self.min_cols:
                    table_data.append(row)
            
            # Ensure all rows have the same number of columns
            max_cols = max(len(row) for row in table_data) if table_data else 0
            for i, row in enumerate(table_data):
                if len(row) < max_cols:
                    table_data[i] = row + [""] * (max_cols - len(row))
            
            if table_data and len(table_data) >= self.min_rows and max_cols >= self.min_cols:
                # Find table bounds
                min_x = float('inf')
                min_y = float('inf')
                max_x = float('-inf')
                max_y = float('-inf')
                
                for line_y in line_group:
                    for span in spans_by_line[line_y]:
                        bbox = span["bbox"]
                        min_x = min(min_x, bbox[0])
                        min_y = min(min_y, bbox[1])
                        max_x = max(max_x, bbox[2])
                        max_y = max(max_y, bbox[3])
                
                # Create table model
                table = Table(
                    caption=f"Text Table {group_idx + 1} on page {page_num}",
                    page=page_num,
                    position=(min_x, min_y, max_x, max_y),
                    data=table_data
                )
                
                tables.append(table)
        
        return tables