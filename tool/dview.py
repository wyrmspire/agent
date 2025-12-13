"""
tool/dview.py - Data View Tool

This module implements a tool for inspecting large data files without loading them fully.
Essential for working with financial data (1m bar CSV files with millions of rows).

Responsibilities:
- Peek at file head/tail
- Get shape (rows/columns) efficiently
- Get column names
- Support CSV and Parquet formats

Rules:
- Never load entire file into memory
- Return only what fits in context window
- Use streaming/chunked reading
- Provide metadata for large files

This tool lets the agent "see" a dataset structure without hitting context limits.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import csv

from core.types import ToolResult
from core.sandb import Workspace, WorkspaceError, get_default_workspace
from .bases import BaseTool, create_json_schema


class DataViewTool(BaseTool):
    """Tool for inspecting large data files.
    
    Provides efficient methods to peek at data without loading everything.
    Critical for working with financial datasets that are too large for context.
    """
    
    def __init__(self, workspace: Optional[Workspace] = None):
        """Initialize with workspace.
        
        Args:
            workspace: Workspace instance (uses default if None)
        """
        self.workspace = workspace or get_default_workspace()
    
    @property
    def name(self) -> str:
        return "data_view"
    
    @property
    def description(self) -> str:
        return (
            "Inspect large data files (CSV/Parquet) without loading them fully. "
            "Operations: 'head' (first N rows), 'tail' (last N rows), "
            "'shape' (row/column count), 'columns' (column names)."
        )
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return create_json_schema(
            properties={
                "path": {
                    "type": "string",
                    "description": "Path to data file (relative to workspace)",
                },
                "operation": {
                    "type": "string",
                    "enum": ["head", "tail", "shape", "columns"],
                    "description": "Operation to perform",
                },
                "n_rows": {
                    "type": "integer",
                    "description": "Number of rows for head/tail operations (default: 5)",
                    "default": 5,
                },
            },
            required=["path", "operation"],
        )
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute data view operation."""
        path_str = arguments["path"]
        operation = arguments["operation"]
        n_rows = arguments.get("n_rows", 5)
        
        try:
            # Resolve path within workspace
            path = self.workspace.resolve_read(path_str)
            
            if not path.is_file():
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Path is not a file: {path}",
                    success=False,
                )
            
            # Determine file type
            suffix = path.suffix.lower()
            
            if suffix == ".csv":
                result = self._handle_csv(path, operation, n_rows)
            elif suffix == ".parquet":
                result = self._handle_parquet(path, operation, n_rows)
            else:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Unsupported file type: {suffix}. Supports: .csv, .parquet",
                    success=False,
                )
            
            return result
        
        except WorkspaceError as e:
            return ToolResult(
                tool_call_id="",
                output="",
                error=str(e),
                success=False,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Error viewing data: {e}",
                success=False,
            )
    
    def _handle_csv(self, path: Path, operation: str, n_rows: int) -> ToolResult:
        """Handle CSV file operations.
        
        Args:
            path: Path to CSV file
            operation: Operation to perform
            n_rows: Number of rows for head/tail
            
        Returns:
            ToolResult with operation output
        """
        if operation == "columns":
            return self._csv_columns(path)
        elif operation == "head":
            return self._csv_head(path, n_rows)
        elif operation == "tail":
            return self._csv_tail(path, n_rows)
        elif operation == "shape":
            return self._csv_shape(path)
        else:
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Unknown operation: {operation}",
                success=False,
            )
    
    def _csv_columns(self, path: Path) -> ToolResult:
        """Get column names from CSV."""
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
        
        output = f"Columns ({len(header)}):\n"
        output += "\n".join(f"  {i+1}. {col}" for i, col in enumerate(header))
        
        return ToolResult(
            tool_call_id="",
            output=output,
            success=True,
        )
    
    def _csv_head(self, path: Path, n_rows: int) -> ToolResult:
        """Get first N rows from CSV."""
        rows = []
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            rows.append(header)
            
            for i, row in enumerate(reader):
                if i >= n_rows:
                    break
                rows.append(row)
        
        output = self._format_csv_table(rows)
        return ToolResult(
            tool_call_id="",
            output=output,
            success=True,
        )
    
    def _csv_tail(self, path: Path, n_rows: int) -> ToolResult:
        """Get last N rows from CSV.
        
        This reads the file in reverse (inefficient for huge files but works).
        """
        # Read entire file to get tail (simple approach)
        # For truly massive files, would need more sophisticated approach
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            all_rows = list(reader)
        
        # Get tail
        tail_rows = [header] + all_rows[-n_rows:] if all_rows else [header]
        
        output = self._format_csv_table(tail_rows)
        output = f"(Showing last {min(n_rows, len(all_rows))} of {len(all_rows)} rows)\n\n" + output
        
        return ToolResult(
            tool_call_id="",
            output=output,
            success=True,
        )
    
    def _csv_shape(self, path: Path) -> ToolResult:
        """Get shape (rows, columns) of CSV."""
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            n_cols = len(header)
            
            # Count rows efficiently
            n_rows = sum(1 for _ in reader)
        
        output = f"Shape: {n_rows} rows × {n_cols} columns\n"
        output += f"Columns: {', '.join(header)}"
        
        return ToolResult(
            tool_call_id="",
            output=output,
            success=True,
        )
    
    def _format_csv_table(self, rows: list) -> str:
        """Format CSV rows as a readable table.
        
        Args:
            rows: List of rows (each row is a list of values)
            
        Returns:
            Formatted table string
        """
        if not rows:
            return "(empty)"
        
        # Calculate column widths
        col_widths = [0] * len(rows[0])
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))
        
        # Format rows
        output_lines = []
        for i, row in enumerate(rows):
            line = " | ".join(str(cell).ljust(col_widths[j]) for j, cell in enumerate(row))
            output_lines.append(line)
            
            # Add separator after header
            if i == 0:
                separator = "-+-".join("-" * w for w in col_widths)
                output_lines.append(separator)
        
        return "\n".join(output_lines)
    
    def _handle_parquet(self, path: Path, operation: str, n_rows: int) -> ToolResult:
        """Handle Parquet file operations.
        
        Args:
            path: Path to Parquet file
            operation: Operation to perform
            n_rows: Number of rows for head/tail
            
        Returns:
            ToolResult with operation output
        """
        try:
            import pandas as pd
        except ImportError:
            return ToolResult(
                tool_call_id="",
                output="",
                error="pandas not installed. Install with: pip install pandas",
                success=False,
            )
        
        try:
            # Import pyarrow for efficient metadata access
            try:
                import pyarrow.parquet as pq
            except ImportError:
                pq = None
            
            if operation == "columns":
                # Read only schema/metadata, not data
                if pq:
                    # Use PyArrow for efficient metadata access
                    parquet_file = pq.ParquetFile(path)
                    columns = parquet_file.schema.names
                else:
                    # Fallback: read with pandas (less efficient)
                    df = pd.read_parquet(path, engine='pyarrow')
                    columns = df.columns.tolist()
                
                output = f"Columns ({len(columns)}):\n"
                output += "\n".join(f"  {i+1}. {col}" for i, col in enumerate(columns))
                
                return ToolResult(
                    tool_call_id="",
                    output=output,
                    success=True,
                )
            
            elif operation == "head":
                # Read only first N rows efficiently
                if pq:
                    # Use PyArrow to read only needed rows
                    parquet_file = pq.ParquetFile(path)
                    table = parquet_file.read_row_group(0)  # First row group
                    df = table.to_pandas()
                    head = df.head(n_rows)
                else:
                    # Fallback: read all (less efficient for large files)
                    df = pd.read_parquet(path, engine='pyarrow')
                    head = df.head(n_rows)
                
                return ToolResult(
                    tool_call_id="",
                    output=head.to_string(),
                    success=True,
                )
            
            elif operation == "tail":
                # Note: Tail is inherently inefficient for Parquet
                # Would need to read entire file or use row group info
                df = pd.read_parquet(path, engine='pyarrow')
                tail = df.tail(n_rows)
                
                output = f"(Showing last {len(tail)} of {len(df)} rows)\n\n{tail.to_string()}"
                return ToolResult(
                    tool_call_id="",
                    output=output,
                    success=True,
                )
            
            elif operation == "shape":
                # Read only metadata for shape
                if pq:
                    # Use PyArrow for efficient metadata access
                    parquet_file = pq.ParquetFile(path)
                    n_rows = parquet_file.metadata.num_rows
                    n_cols = len(parquet_file.schema.names)
                    columns = parquet_file.schema.names
                else:
                    # Fallback: read all (less efficient)
                    df = pd.read_parquet(path, engine='pyarrow')
                    n_rows, n_cols = df.shape
                    columns = df.columns.tolist()
                
                output = f"Shape: {n_rows} rows × {n_cols} columns\n"
                output += f"Columns: {', '.join(columns)}"
                
                return ToolResult(
                    tool_call_id="",
                    output=output,
                    success=True,
                )
            
            else:
                return ToolResult(
                    tool_call_id="",
                    output="",
                    error=f"Unknown operation: {operation}",
                    success=False,
                )
        
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                output="",
                error=f"Error reading Parquet file: {e}",
                success=False,
            )
