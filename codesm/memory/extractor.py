"""Extract memories from sessions"""

import re
import uuid

from ..storage.storage import Storage
from .models import MemoryItem


class MemoryExtractor:
    async def extract_from_session(self, session_id: str) -> list[MemoryItem]:
        memories: list[MemoryItem] = []

        session_data = Storage.read(["sessions", session_id])
        if session_data is None:
            return memories

        messages = session_data.get("messages", [])
        patches = session_data.get("patches", [])
        project_id = session_data.get("project_id")

        memories.extend(
            self._extract_remember_requests(messages, session_id, project_id)
        )

        if patches:
            solution = self._extract_solution_from_patches(patches, session_id, project_id)
            if solution:
                memories.append(solution)

        return memories

    def _extract_remember_requests(
        self,
        messages: list[dict],
        session_id: str,
        project_id: str | None,
    ) -> list[MemoryItem]:
        memories: list[MemoryItem] = []

        remember_patterns = [
            r"remember\s+(?:that\s+)?(.+)",
            r"always\s+(.+)",
            r"never\s+(.+)",
            r"prefer\s+(.+)",
        ]

        for msg in messages:
            if msg.get("role") != "user":
                continue

            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    part.get("text", "") for part in content if isinstance(part, dict)
                )

            content_lower = content.lower()

            for pattern in remember_patterns:
                match = re.search(pattern, content_lower, re.IGNORECASE)
                if match:
                    extracted = match.group(1).strip()
                    if len(extracted) > 10:
                        memories.append(
                            MemoryItem(
                                id=str(uuid.uuid4()),
                                type="preference",
                                text=extracted,
                                project_id=project_id,
                                source_session_id=session_id,
                            )
                        )
                    break

        return memories

    def _extract_solution_from_patches(
        self,
        patches: list[dict],
        session_id: str,
        project_id: str | None,
    ) -> MemoryItem | None:
        if not patches:
            return None

        files_changed = set()
        for patch in patches:
            file_path = patch.get("file") or patch.get("path")
            if file_path:
                files_changed.add(file_path)

        if not files_changed:
            return None

        if len(files_changed) == 1:
            text = f"Modified {list(files_changed)[0]} to implement changes"
        elif len(files_changed) <= 5:
            files_list = ", ".join(sorted(files_changed))
            text = f"Modified files: {files_list}"
        else:
            text = f"Modified {len(files_changed)} files including {', '.join(sorted(files_changed)[:3])} and others"

        return MemoryItem(
            id=str(uuid.uuid4()),
            type="solution",
            text=text,
            project_id=project_id,
            source_session_id=session_id,
        )
