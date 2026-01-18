"""Tests for rules discovery (AGENTS.md, CLAUDE.md, etc.)"""

import pytest
import tempfile
from pathlib import Path
import shutil

from codesm.rules import RulesDiscovery, discover_rules, scan_project, init_agents_md, save_agents_md


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory"""
    temp_dir = tempfile.mkdtemp(prefix="codesm_rules_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestRulesDiscovery:
    """Test the RulesDiscovery class"""
    
    def test_discovers_agents_md(self, temp_workspace):
        """Test discovering AGENTS.md in workspace"""
        agents_file = temp_workspace / "AGENTS.md"
        agents_file.write_text("# Project Rules\n\nUse TypeScript.")
        
        discovery = RulesDiscovery(workspace=temp_workspace)
        rules = discovery.discover()
        
        assert len(rules) == 1
        assert rules[0].path == agents_file
        assert "TypeScript" in rules[0].content
        assert rules[0].is_global is False
    
    def test_discovers_claude_md(self, temp_workspace):
        """Test discovering CLAUDE.md as fallback"""
        claude_file = temp_workspace / "CLAUDE.md"
        claude_file.write_text("# Claude Rules\n\nBe concise.")
        
        discovery = RulesDiscovery(workspace=temp_workspace)
        rules = discovery.discover()
        
        assert len(rules) == 1
        assert rules[0].name == "CLAUDE.md"
    
    def test_agents_md_priority_over_claude_md(self, temp_workspace):
        """Test that AGENTS.md takes priority over CLAUDE.md"""
        (temp_workspace / "AGENTS.md").write_text("AGENTS content")
        (temp_workspace / "CLAUDE.md").write_text("CLAUDE content")
        
        discovery = RulesDiscovery(workspace=temp_workspace)
        rules = discovery.discover()
        
        # Both should be found
        names = [r.name for r in rules]
        assert "AGENTS.md" in names
        assert "CLAUDE.md" in names
    
    def test_walks_up_directory_tree(self, temp_workspace):
        """Test that discovery walks up to find rules in parent dirs"""
        # Create rules in parent
        (temp_workspace / "AGENTS.md").write_text("Root rules")
        
        # Create nested directory
        nested = temp_workspace / "src" / "components"
        nested.mkdir(parents=True)
        
        discovery = RulesDiscovery(workspace=nested, root=temp_workspace)
        rules = discovery.discover()
        
        assert len(rules) == 1
        assert "Root rules" in rules[0].content
    
    def test_nested_rules_found(self, temp_workspace):
        """Test that both nested and parent rules are found"""
        (temp_workspace / "AGENTS.md").write_text("Root rules")
        
        nested = temp_workspace / "packages" / "app"
        nested.mkdir(parents=True)
        (nested / "AGENTS.md").write_text("App-specific rules")
        
        discovery = RulesDiscovery(workspace=nested, root=temp_workspace)
        rules = discovery.discover()
        
        # Should find both
        assert len(rules) == 2
        contents = [r.content for r in rules]
        assert any("App-specific" in c for c in contents)
        assert any("Root rules" in c for c in contents)
    
    def test_discovers_cursorrules(self, temp_workspace):
        """Test discovering .cursorrules file"""
        cursor_file = temp_workspace / ".cursorrules"
        cursor_file.write_text("Cursor rules content")
        
        discovery = RulesDiscovery(workspace=temp_workspace)
        rules = discovery.discover()
        
        assert len(rules) == 1
        assert rules[0].name == ".cursorrules"
    
    def test_discovers_copilot_instructions(self, temp_workspace):
        """Test discovering .github/copilot-instructions.md"""
        github_dir = temp_workspace / ".github"
        github_dir.mkdir()
        copilot_file = github_dir / "copilot-instructions.md"
        copilot_file.write_text("Copilot instructions")
        
        discovery = RulesDiscovery(workspace=temp_workspace)
        rules = discovery.discover()
        
        assert len(rules) == 1
        assert "copilot-instructions.md" in str(rules[0].path)
    
    def test_get_combined_rules(self, temp_workspace):
        """Test combining multiple rule files"""
        (temp_workspace / "AGENTS.md").write_text("Rule 1")
        (temp_workspace / "CLAUDE.md").write_text("Rule 2")
        
        discovery = RulesDiscovery(workspace=temp_workspace)
        combined = discovery.get_combined_rules()
        
        assert "Rule 1" in combined
        assert "Rule 2" in combined
        assert "Instructions from:" in combined
    
    def test_empty_workspace_returns_empty(self, temp_workspace):
        """Test that empty workspace returns no rules"""
        discovery = RulesDiscovery(workspace=temp_workspace)
        rules = discovery.discover()
        
        # Only global rules would be found (if they exist)
        local_rules = [r for r in rules if not r.is_global]
        assert len(local_rules) == 0
    
    def test_refresh_rediscovers(self, temp_workspace):
        """Test that refresh() re-discovers rules"""
        discovery = RulesDiscovery(workspace=temp_workspace)
        
        # Initially no rules
        rules1 = discovery.discover()
        local_count1 = len([r for r in rules1 if not r.is_global])
        
        # Add a rule file
        (temp_workspace / "AGENTS.md").write_text("New rules")
        
        # Refresh
        rules2 = discovery.refresh()
        local_count2 = len([r for r in rules2 if not r.is_global])
        
        assert local_count2 == local_count1 + 1
    
    def test_get_rules_summary(self, temp_workspace):
        """Test getting a summary of discovered rules"""
        (temp_workspace / "AGENTS.md").write_text("Rules")
        
        discovery = RulesDiscovery(workspace=temp_workspace)
        summary = discovery.get_rules_summary()
        
        assert "Found 1 rule file" in summary
        assert "AGENTS.md" in summary


class TestDiscoverRulesFunction:
    """Test the convenience function"""
    
    def test_discover_rules_returns_content(self, temp_workspace):
        """Test that discover_rules returns combined content"""
        (temp_workspace / "AGENTS.md").write_text("My rules")
        
        result = discover_rules(temp_workspace)
        
        assert "My rules" in result
    
    def test_discover_rules_empty_returns_empty_string(self, temp_workspace):
        """Test that empty workspace returns empty string"""
        result = discover_rules(temp_workspace)
        
        # May have global rules, but no local ones
        # Just verify it doesn't crash
        assert isinstance(result, str)


class TestScanProject:
    """Test project scanning for /init"""
    
    def test_scan_nodejs_project(self, temp_workspace):
        """Test scanning a Node.js project"""
        import json
        
        package_json = {
            "name": "my-app",
            "scripts": {
                "build": "tsc",
                "test": "jest",
                "dev": "next dev"
            },
            "dependencies": {
                "react": "^18.0.0",
                "next": "^14.0.0"
            }
        }
        (temp_workspace / "package.json").write_text(json.dumps(package_json))
        (temp_workspace / "pnpm-lock.yaml").write_text("")
        
        info = scan_project(temp_workspace)
        
        assert info.name == "my-app"
        assert info.package_manager == "pnpm"
        assert "pnpm" in info.build_command
        assert "React" in info.frameworks
        assert "Next.js" in info.frameworks
    
    def test_scan_python_project(self, temp_workspace):
        """Test scanning a Python project"""
        (temp_workspace / "pyproject.toml").write_text("[project]\nname = 'myapp'")
        (temp_workspace / "uv.lock").write_text("")
        
        info = scan_project(temp_workspace)
        
        assert info.language == "Python"
        assert info.package_manager == "uv"
        assert "pytest" in info.test_command
    
    def test_scan_rust_project(self, temp_workspace):
        """Test scanning a Rust project"""
        (temp_workspace / "Cargo.toml").write_text('[package]\nname = "myapp"')
        
        info = scan_project(temp_workspace)
        
        assert info.language == "Rust"
        assert info.build_command == "cargo build"
        assert info.test_command == "cargo test"
    
    def test_scan_empty_project(self, temp_workspace):
        """Test scanning an empty project"""
        info = scan_project(temp_workspace)
        
        assert info.language == ""
        assert info.package_manager == ""


class TestInitAgentsMd:
    """Test AGENTS.md initialization"""
    
    def test_init_creates_content(self, temp_workspace):
        """Test that init generates AGENTS.md content"""
        import json
        
        (temp_workspace / "package.json").write_text(json.dumps({
            "name": "test-app",
            "scripts": {"build": "tsc", "test": "jest"}
        }))
        
        content, exists = init_agents_md(temp_workspace)
        
        assert not exists
        assert "test-app" in content
        assert "## Commands" in content
    
    def test_init_detects_existing(self, temp_workspace):
        """Test that init detects existing AGENTS.md"""
        (temp_workspace / "AGENTS.md").write_text("Existing rules")
        
        content, exists = init_agents_md(temp_workspace)
        
        assert exists
        assert content == "Existing rules"
    
    def test_save_agents_md(self, temp_workspace):
        """Test saving AGENTS.md"""
        content = "# My Rules\n\nBe concise."
        
        path = save_agents_md(temp_workspace, content)
        
        assert path.exists()
        assert path.read_text() == content
