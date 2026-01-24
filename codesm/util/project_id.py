"""Compute stable project ID from directory path"""

import hashlib
from pathlib import Path


def get_project_id(directory: Path | str) -> str:
    """Generate a stable, short project ID from a directory path.
    
    Uses first 12 chars of SHA1 hash of the resolved path.
    This ensures the same directory always gets the same ID.
    """
    resolved = str(Path(directory).resolve())
    return hashlib.sha1(resolved.encode()).hexdigest()[:12]
