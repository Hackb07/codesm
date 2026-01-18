"""Tests for the snapshot/undo system"""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

from codesm.snapshot import Snapshot
from codesm.snapshot.snapshot import Patch, FileDiff


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory"""
    temp_dir = tempfile.mkdtemp(prefix="codesm_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def snapshot(temp_workspace):
    """Create a Snapshot instance for testing"""
    return Snapshot(temp_workspace, project_id="test_project")


class TestSnapshot:
    """Test the Snapshot class"""
    
    @pytest.mark.asyncio
    async def test_track_creates_snapshot(self, snapshot, temp_workspace):
        """Test that track() creates a snapshot hash"""
        test_file = temp_workspace / "test.txt"
        test_file.write_text("Hello, World!")
        
        hash_val = await snapshot.track()
        
        assert hash_val is not None
        assert len(hash_val) == 40  # Git tree hash is 40 chars
    
    @pytest.mark.asyncio
    async def test_track_returns_different_hash_on_change(self, snapshot, temp_workspace):
        """Test that track() returns different hash when files change"""
        test_file = temp_workspace / "test.txt"
        test_file.write_text("Initial content")
        
        hash1 = await snapshot.track()
        
        test_file.write_text("Modified content")
        
        hash2 = await snapshot.track()
        
        assert hash1 != hash2
    
    @pytest.mark.asyncio
    async def test_patch_returns_changed_files(self, snapshot, temp_workspace):
        """Test that patch() returns list of changed files"""
        test_file = temp_workspace / "test.txt"
        test_file.write_text("Initial content")
        
        initial_hash = await snapshot.track()
        
        test_file.write_text("Modified content")
        
        patch = await snapshot.patch(initial_hash)
        
        assert patch.hash == initial_hash
        assert str(test_file) in patch.files
    
    @pytest.mark.asyncio
    async def test_restore_reverts_to_snapshot(self, snapshot, temp_workspace):
        """Test that restore() reverts files to snapshot state"""
        test_file = temp_workspace / "test.txt"
        original_content = "Original content"
        test_file.write_text(original_content)
        
        initial_hash = await snapshot.track()
        
        test_file.write_text("Modified content")
        
        success = await snapshot.restore(initial_hash)
        
        assert success
        assert test_file.read_text() == original_content
    
    @pytest.mark.asyncio
    async def test_revert_files_reverts_specific_file(self, snapshot, temp_workspace):
        """Test that revert_files() only reverts specified files"""
        file1 = temp_workspace / "file1.txt"
        file2 = temp_workspace / "file2.txt"
        
        file1.write_text("File 1 original")
        file2.write_text("File 2 original")
        
        initial_hash = await snapshot.track()
        
        file1.write_text("File 1 modified")
        file2.write_text("File 2 modified")
        
        patches = [Patch(hash=initial_hash, files=[str(file1)])]
        reverted = await snapshot.revert_files(patches)
        
        assert str(file1) in reverted
        assert file1.read_text() == "File 1 original"
        assert file2.read_text() == "File 2 modified"
    
    @pytest.mark.asyncio
    async def test_diff_returns_unified_diff(self, snapshot, temp_workspace):
        """Test that diff() returns a unified diff string"""
        test_file = temp_workspace / "test.txt"
        test_file.write_text("Line 1\nLine 2\nLine 3\n")
        
        initial_hash = await snapshot.track()
        
        test_file.write_text("Line 1\nModified Line 2\nLine 3\n")
        
        diff = await snapshot.diff(initial_hash)
        
        assert "-Line 2" in diff or "- Line 2" in diff.replace("\t", " ")
        assert "+Modified Line 2" in diff or "+ Modified Line 2" in diff.replace("\t", " ")
    
    @pytest.mark.asyncio
    async def test_cleanup_removes_git_dir(self, snapshot, temp_workspace):
        """Test that cleanup() removes the snapshot git directory"""
        test_file = temp_workspace / "test.txt"
        test_file.write_text("Content")
        
        await snapshot.track()
        assert snapshot.git_dir.exists()
        
        success = await snapshot.cleanup()
        
        assert success
        assert not snapshot.git_dir.exists()
    
    @pytest.mark.asyncio
    async def test_handles_new_files(self, snapshot, temp_workspace):
        """Test tracking new files created after initial snapshot"""
        existing_file = temp_workspace / "existing.txt"
        existing_file.write_text("Existing content")
        
        initial_hash = await snapshot.track()
        
        new_file = temp_workspace / "new.txt"
        new_file.write_text("New content")
        
        patch = await snapshot.patch(initial_hash)
        
        assert str(new_file) in patch.files
    
    @pytest.mark.asyncio
    async def test_handles_deleted_files(self, snapshot, temp_workspace):
        """Test tracking deleted files"""
        test_file = temp_workspace / "test.txt"
        test_file.write_text("Content")
        
        initial_hash = await snapshot.track()
        
        test_file.unlink()
        
        patch = await snapshot.patch(initial_hash)
        
        assert str(test_file) in patch.files


class TestPatch:
    """Test the Patch dataclass"""
    
    def test_patch_creation(self):
        """Test creating a Patch"""
        patch = Patch(hash="abc123", files=["/path/to/file.txt"])
        
        assert patch.hash == "abc123"
        assert len(patch.files) == 1
    
    def test_patch_empty_files(self):
        """Test Patch with empty files list"""
        patch = Patch(hash="abc123")
        
        assert patch.files == []


class TestFileDiff:
    """Test the FileDiff dataclass"""
    
    def test_filediff_creation(self):
        """Test creating a FileDiff"""
        diff = FileDiff(
            file="test.txt",
            before="old content",
            after="new content",
            additions=5,
            deletions=3,
        )
        
        assert diff.file == "test.txt"
        assert diff.before == "old content"
        assert diff.after == "new content"
        assert diff.additions == 5
        assert diff.deletions == 3
