"""Code Review Tool - Reviews code changes using the CodeReviewer"""

import asyncio
import logging
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from .base import Tool

if TYPE_CHECKING:
    from codesm.tool.registry import ToolRegistry

logger = logging.getLogger(__name__)


class CodeReviewTool(Tool):
    """Reviews code changes for bugs, security issues, and best practices."""
    
    name = "code_review"
    description = "Review code changes for bugs, security issues, and improvements. Supports git staged/branch diffs, PRs, and session changes."
    
    def __init__(self, parent_tools: "ToolRegistry | None" = None):
        super().__init__()
        self._parent_tools = parent_tools
    
    def set_parent(self, tools: "ToolRegistry"):
        """Set parent tools (called by Agent after init)"""
        self._parent_tools = tools
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "description": "Review mode: 'staged' (git staged), 'branch:<name>' (compare to branch), 'files:<path1>,<path2>' (specific files), 'pr:<number>' (GitHub PR), 'session' (current session changes)",
                },
                "focus": {
                    "type": "string",
                    "enum": ["bugs", "security", "performance", "style", "all"],
                    "description": "Focus area for review (default: all)",
                },
                "auto_fix": {
                    "type": "boolean",
                    "description": "Generate auto-fix patches for issues found (default: false)",
                },
            },
            "required": ["mode"],
        }
    
    async def execute(self, args: dict, context: dict) -> str:
        from codesm.review.reviewer import CodeReviewer
        
        mode = args.get("mode", "staged")
        focus = args.get("focus", "all")
        auto_fix = args.get("auto_fix", False)
        cwd = context.get("cwd", ".")
        session = context.get("session")
        
        try:
            if mode == "session":
                if not session:
                    return "Error: No active session. Use 'staged' or 'branch:<name>' mode instead."
                files_to_review = await self._get_session_changes(session, cwd)
            elif mode.startswith("pr:"):
                pr_number = mode.split(":", 1)[1]
                files_to_review = await self._get_pr_diff(pr_number, cwd)
            else:
                files_to_review = await self._get_files_for_mode(mode, cwd)
        except Exception as e:
            return f"Error getting files to review: {e}"
        
        if not files_to_review:
            return "No files to review. Check that your mode is correct and files exist."
        
        reviewer = CodeReviewer()
        try:
            result = await reviewer.review_files(files_to_review)
            
            if focus != "all":
                result = self._filter_by_focus(result, focus)
            
            output = result.format_for_display()
            
            # Generate auto-fix patches if requested
            if auto_fix and result.issues:
                fixes = await self._generate_fixes(result, files_to_review, reviewer)
                if fixes:
                    output += "\n\n## Auto-Fix Patches\n\n" + fixes
            
            return output
        except Exception as e:
            logger.exception("Code review failed")
            return f"Error during code review: {e}"
        finally:
            await reviewer.close()
    
    async def _get_session_changes(self, session, cwd: str) -> list[dict]:
        """Get files changed during the current session."""
        files = []
        
        # Get undo history to find edited files
        history = session.get_undo_history()
        edited_files = set()
        
        for entry in history._undo_stack:
            from codesm.undo_history import TransactionGroup
            if isinstance(entry, TransactionGroup):
                for edit in entry.edits:
                    edited_files.add(edit.file_path)
            else:
                edited_files.add(entry.file_path)
        
        for file_path in edited_files:
            path = Path(file_path)
            if not path.exists():
                continue
            
            try:
                content = path.read_text()
                
                # Try to get git diff for this file
                diff = ""
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "git", "diff", "--", str(path),
                        cwd=cwd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, _ = await proc.communicate()
                    if proc.returncode == 0:
                        diff = stdout.decode()
                except Exception:
                    pass
                
                files.append({
                    "path": str(path),
                    "content": content,
                    "diff": diff,
                })
            except Exception as e:
                logger.debug(f"Could not read {file_path}: {e}")
        
        return files
    
    async def _get_pr_diff(self, pr_number: str, cwd: str) -> list[dict]:
        """Get files changed in a GitHub PR using gh CLI."""
        files = []
        
        # Get PR diff using gh CLI
        try:
            proc = await asyncio.create_subprocess_exec(
                "gh", "pr", "diff", pr_number, "--patch",
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                raise RuntimeError(f"gh pr diff failed: {stderr.decode()}")
            
            full_diff = stdout.decode()
            
            # Parse the patch to get individual files
            current_file = None
            current_diff_lines = []
            
            for line in full_diff.split("\n"):
                if line.startswith("diff --git"):
                    # Save previous file
                    if current_file and current_diff_lines:
                        file_path = Path(cwd) / current_file
                        content = ""
                        if file_path.exists():
                            try:
                                content = file_path.read_text()
                            except Exception:
                                pass
                        files.append({
                            "path": current_file,
                            "content": content,
                            "diff": "\n".join(current_diff_lines),
                        })
                    
                    # Extract new file path
                    parts = line.split(" b/")
                    if len(parts) > 1:
                        current_file = parts[1]
                    current_diff_lines = [line]
                elif current_file:
                    current_diff_lines.append(line)
            
            # Don't forget the last file
            if current_file and current_diff_lines:
                file_path = Path(cwd) / current_file
                content = ""
                if file_path.exists():
                    try:
                        content = file_path.read_text()
                    except Exception:
                        pass
                files.append({
                    "path": current_file,
                    "content": content,
                    "diff": "\n".join(current_diff_lines),
                })
            
        except FileNotFoundError:
            raise RuntimeError("GitHub CLI (gh) not installed. Install it with: https://cli.github.com/")
        
        return files
    
    async def _generate_fixes(self, result, files: list[dict], reviewer) -> str:
        """Generate code fix patches for issues found."""
        fixes = []
        
        # Group issues by file
        issues_by_file = {}
        for issue in result.issues:
            if issue.fix and issue.severity in ("critical", "warning"):
                if issue.file not in issues_by_file:
                    issues_by_file[issue.file] = []
                issues_by_file[issue.file].append(issue)
        
        for file_path, issues in issues_by_file.items():
            file_content = next(
                (f["content"] for f in files if f["path"].endswith(file_path) or file_path.endswith(f["path"])),
                None
            )
            if not file_content:
                continue
            
            fix_desc = []
            for i, issue in enumerate(issues[:3], 1):  # Limit to 3 fixes per file
                line_info = f" (line {issue.line})" if issue.line else ""
                fix_desc.append(f"**{i}. {issue.description}**{line_info}")
                fix_desc.append(f"   → {issue.fix}")
            
            fixes.append(f"### {file_path}\n\n" + "\n".join(fix_desc))
        
        return "\n\n".join(fixes) if fixes else ""
    
    async def _get_files_for_mode(self, mode: str, cwd: str) -> list[dict]:
        """Get files to review based on the mode."""
        files = []
        
        if mode == "staged":
            files = await self._get_staged_files(cwd)
        elif mode.startswith("branch:"):
            branch = mode.split(":", 1)[1]
            files = await self._get_branch_diff(cwd, branch)
        elif mode.startswith("files:"):
            paths = mode.split(":", 1)[1].split(",")
            files = await self._get_specific_files(paths, cwd)
        else:
            raise ValueError(f"Invalid mode: {mode}. Use 'staged', 'branch:<name>', or 'files:<paths>'")
        
        return files
    
    async def _get_staged_files(self, cwd: str) -> list[dict]:
        """Get git staged files with their diffs."""
        files = []
        
        diff_cmd = ["git", "diff", "--cached", "--name-only"]
        proc = await asyncio.create_subprocess_exec(
            *diff_cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise RuntimeError(f"git diff failed: {stderr.decode()}")
        
        staged_paths = [p.strip() for p in stdout.decode().strip().split("\n") if p.strip()]
        
        for path in staged_paths:
            full_path = Path(cwd) / path
            if not full_path.exists() or not full_path.is_file():
                continue
            
            diff_proc = await asyncio.create_subprocess_exec(
                "git", "diff", "--cached", path,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            diff_stdout, _ = await diff_proc.communicate()
            
            try:
                content = full_path.read_text()
            except Exception:
                content = ""
            
            files.append({
                "path": str(full_path),
                "content": content,
                "diff": diff_stdout.decode() if diff_stdout else "",
            })
        
        return files
    
    async def _get_branch_diff(self, cwd: str, branch: str) -> list[dict]:
        """Get files changed compared to a branch."""
        files = []
        
        diff_cmd = ["git", "diff", f"{branch}..HEAD", "--name-only"]
        proc = await asyncio.create_subprocess_exec(
            *diff_cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise RuntimeError(f"git diff failed: {stderr.decode()}")
        
        changed_paths = [p.strip() for p in stdout.decode().strip().split("\n") if p.strip()]
        
        for path in changed_paths:
            full_path = Path(cwd) / path
            if not full_path.exists() or not full_path.is_file():
                continue
            
            diff_proc = await asyncio.create_subprocess_exec(
                "git", "diff", f"{branch}..HEAD", "--", path,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            diff_stdout, _ = await diff_proc.communicate()
            
            try:
                content = full_path.read_text()
            except Exception:
                content = ""
            
            files.append({
                "path": str(full_path),
                "content": content,
                "diff": diff_stdout.decode() if diff_stdout else "",
            })
        
        return files
    
    async def _get_specific_files(self, paths: list[str], cwd: str) -> list[dict]:
        """Get content of specific files."""
        files = []
        
        for path in paths:
            path = path.strip()
            full_path = Path(path) if Path(path).is_absolute() else Path(cwd) / path
            
            if not full_path.exists() or not full_path.is_file():
                continue
            
            try:
                content = full_path.read_text()
            except Exception:
                continue
            
            files.append({
                "path": str(full_path),
                "content": content,
                "diff": "",
            })
        
        return files
    
    def _filter_by_focus(self, result, focus: str):
        """Filter review issues by focus area."""
        from codesm.review.reviewer import ReviewResult
        
        focus_keywords = {
            "bugs": ["bug", "error", "logic", "null", "none", "undefined", "race", "condition"],
            "security": ["security", "injection", "xss", "csrf", "secret", "password", "auth", "sql"],
            "performance": ["performance", "n+1", "loop", "memory", "leak", "slow", "optimize"],
            "style": ["naming", "style", "format", "convention", "readability", "documentation"],
        }
        
        keywords = focus_keywords.get(focus, [])
        if not keywords:
            return result
        
        filtered_issues = []
        for issue in result.issues:
            desc_lower = issue.description.lower()
            if any(kw in desc_lower for kw in keywords):
                filtered_issues.append(issue)
        
        return ReviewResult(
            issues=filtered_issues,
            summary=result.summary,
            files_reviewed=result.files_reviewed,
        )
