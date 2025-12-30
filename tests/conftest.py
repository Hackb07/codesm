"""Pytest configuration and shared fixtures"""

import pytest
import tempfile
import os
from pathlib import Path

# Set test storage directory to avoid polluting user data
os.environ["CODESM_DATA_DIR"] = tempfile.mkdtemp()


@pytest.fixture(autouse=True)
def clean_storage():
    """Clean storage before each test"""
    from codesm.storage.storage import Storage
    
    # Use a fresh temp dir for each test
    Storage.BASE_DIR = Path(tempfile.mkdtemp())
    yield
