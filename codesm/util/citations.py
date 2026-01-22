"""File citations utility - format file paths as clickable markdown links"""

import re
import urllib.parse
from pathlib import Path
from typing import Optional


def file_link(path: str | Path, line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """Create a clickable markdown link to a file.
    
    Args:
        path: Absolute or relative file path
        line: Optional line number (1-indexed)
        end_line: Optional end line for a range
        
    Returns:
        Markdown link like [filename](file:///path/to/file#L10-L20)
    """
    path = Path(path)
    abs_path = path.resolve() if not path.is_absolute() else path
    
    # URL-encode the path for special characters
    encoded_path = urllib.parse.quote(str(abs_path), safe='/')
    
    # Build the URL
    url = f"file://{encoded_path}"
    
    # Add line fragment if specified
    if line is not None:
        if end_line is not None and end_line > line:
            url += f"#L{line}-L{end_line}"
        else:
            url += f"#L{line}"
    
    # Use filename as link text
    display_name = path.name
    
    return f"[{display_name}]({url})"


def file_link_with_path(path: str | Path, line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """Create a clickable markdown link showing the relative path.
    
    Args:
        path: Absolute or relative file path
        line: Optional line number (1-indexed)
        end_line: Optional end line for a range
        
    Returns:
        Markdown link like [src/foo/bar.py](file:///abs/path/to/file#L10)
    """
    path = Path(path)
    abs_path = path.resolve() if not path.is_absolute() else path
    
    # URL-encode the path
    encoded_path = urllib.parse.quote(str(abs_path), safe='/')
    
    # Build the URL
    url = f"file://{encoded_path}"
    
    if line is not None:
        if end_line is not None and end_line > line:
            url += f"#L{line}-L{end_line}"
        else:
            url += f"#L{line}"
    
    # Use relative path for display if possible
    try:
        cwd = Path.cwd()
        if abs_path.is_relative_to(cwd):
            display = str(abs_path.relative_to(cwd))
        else:
            display = str(path)
    except ValueError:
        display = str(path)
    
    return f"[{display}]({url})"


def cite_file(path: str | Path, line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """Shorthand alias for file_link_with_path."""
    return file_link_with_path(path, line, end_line)


def cite_match(path: str, line: int, content: str, max_content_len: int = 100) -> str:
    """Format a search match with file link and content preview.
    
    Args:
        path: File path
        line: Line number where match was found
        content: The matching line content
        max_content_len: Maximum length of content to show
        
    Returns:
        Formatted string like: [file.py](file://...#L10): `matching content...`
    """
    link = file_link_with_path(path, line)
    
    # Truncate content if needed
    content = content.strip()
    if len(content) > max_content_len:
        content = content[:max_content_len] + "..."
    
    # Escape backticks in content
    content = content.replace("`", "\\`")
    
    return f"{link}: `{content}`"


def convert_paths_to_links(text: str, base_dir: Optional[Path] = None) -> str:
    """Convert file paths in text to clickable links.
    
    This function finds file paths in text and converts them to markdown links.
    Handles formats like:
    - /absolute/path/file.py
    - ./relative/path.ts
    - src/module/file.js
    - file.py:42 (with line numbers)
    
    Args:
        text: Text containing file paths
        base_dir: Base directory for resolving relative paths
        
    Returns:
        Text with file paths converted to markdown links
    """
    if base_dir is None:
        base_dir = Path.cwd()
    
    # Pattern to match file paths with optional line numbers
    # Matches: /path/file.ext, ./path/file.ext, path/file.ext, file.ext:123
    path_pattern = re.compile(
        r'(?<![(\[])' # Not already in a link
        r'(?P<path>'
        r'(?:\.?/)?'  # Optional ./ or /
        r'(?:[a-zA-Z0-9_\-]+/)*'  # Directory components
        r'[a-zA-Z0-9_\-]+\.[a-zA-Z0-9]+'  # filename.ext
        r')'
        r'(?::(?P<line>\d+))?'  # Optional :line_number
        r'(?![\w/])'  # Not followed by more path
    )
    
    def replace_path(match):
        path_str = match.group('path')
        line_str = match.group('line')
        
        # Try to resolve the path
        path = Path(path_str)
        if not path.is_absolute():
            full_path = base_dir / path
        else:
            full_path = path
        
        # Only convert if file exists
        if full_path.exists():
            line = int(line_str) if line_str else None
            return file_link_with_path(full_path, line)
        
        # Return original if file doesn't exist
        return match.group(0)
    
    return path_pattern.sub(replace_path, text)


def format_grep_output(grep_output: str, base_dir: Optional[Path] = None) -> str:
    """Convert grep/ripgrep output to use clickable file links.
    
    Input format: path/to/file.py:42:matching content
    Output format: [file.py](file://...#L42): `matching content`
    
    Args:
        grep_output: Raw grep output with path:line:content format
        base_dir: Base directory for resolving paths
        
    Returns:
        Formatted output with clickable links
    """
    if base_dir is None:
        base_dir = Path.cwd()
    
    lines = grep_output.strip().split('\n')
    formatted = []
    
    for line in lines:
        if not line.strip():
            continue
        
        # Parse grep format: path:line:content or path:line-content
        # Handle Windows paths with drive letters (C:\path)
        match = re.match(r'^(.+?):(\d+)[:\-](.*)$', line)
        if match:
            path_str, line_num, content = match.groups()
            
            # Resolve path
            path = Path(path_str)
            if not path.is_absolute():
                path = base_dir / path
            
            formatted.append(cite_match(str(path), int(line_num), content))
        else:
            # Not a grep line, keep as-is
            formatted.append(line)
    
    return '\n'.join(formatted)


def format_file_list(files: list[str | Path], base_dir: Optional[Path] = None) -> str:
    """Format a list of files as clickable links.
    
    Args:
        files: List of file paths
        base_dir: Base directory for display
        
    Returns:
        Markdown formatted list of file links
    """
    if base_dir is None:
        base_dir = Path.cwd()
    
    lines = []
    for f in files:
        path = Path(f)
        if not path.is_absolute():
            path = base_dir / path
        lines.append(f"- {file_link_with_path(path)}")
    
    return '\n'.join(lines)
