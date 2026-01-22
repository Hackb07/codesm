"""ThreadSearch - full-text search across session messages"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from codesm.storage.storage import Storage
from codesm.session.topics import TopicInfo, get_topic_index

logger = logging.getLogger(__name__)

# Regex patterns for file paths
FILE_PATH_PATTERNS = [
    r'[`"\']([a-zA-Z0-9_./\\-]+\.[a-zA-Z0-9]+)[`"\']',  # Quoted/backticked paths
    r'(?:^|\s)(/[a-zA-Z0-9_./\\-]+\.[a-zA-Z0-9]+)',  # Absolute paths
    r'(?:^|\s)(\./[a-zA-Z0-9_./\\-]+\.[a-zA-Z0-9]+)',  # Relative paths with ./
    r'(?:file|path|edit|create|read|open):\s*([a-zA-Z0-9_./\\-]+)',  # Action prefixes
]


@dataclass
class SearchQuery:
    """Parsed search query with filters"""
    keywords: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    after: Optional[datetime] = None
    before: Optional[datetime] = None
    author: str = "me"
    
    def has_filters(self) -> bool:
        return bool(self.keywords or self.files or self.topics or self.after or self.before)


@dataclass
class ThreadSearchResult:
    """Search result with relevance information"""
    session_id: str
    title: str
    updated_at: datetime
    score: float
    snippet: str
    topics: Optional[TopicInfo] = None
    
    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "updated_at": self.updated_at.isoformat(),
            "score": self.score,
            "snippet": self.snippet,
            "topics": self.topics.to_dict() if self.topics else None,
        }


@dataclass
class SearchIndexEntry:
    """Cached metadata for a session"""
    session_id: str
    title: str
    updated_at: datetime
    content_lower: str  # Lowercased content for searching
    files: list[str]  # Files mentioned in the session
    word_count: int
    message_count: int


class ThreadSearch:
    """Full-text search service for session threads"""
    
    def __init__(self):
        self._index: dict[str, SearchIndexEntry] = {}
        self._index_built = False
    
    def _parse_duration(self, duration_str: str) -> Optional[timedelta]:
        """Parse duration string like '7d', '2w', '1m' into timedelta"""
        match = re.match(r'^(\d+)([dwmh])$', duration_str.lower())
        if not match:
            return None
        
        value = int(match.group(1))
        unit = match.group(2)
        
        if unit == 'h':
            return timedelta(hours=value)
        elif unit == 'd':
            return timedelta(days=value)
        elif unit == 'w':
            return timedelta(weeks=value)
        elif unit == 'm':
            return timedelta(days=value * 30)  # Approximate month
        return None
    
    def parse_query(self, query: str) -> SearchQuery:
        """Parse DSL query into SearchQuery object.
        
        Syntax:
        - `auth file:src/auth.py after:7d` - keyword "auth", file filter, date filter
        - `bugfix topic:security` - keyword "bugfix" in topic "security"
        - `error before:2024-01-01` - keyword with absolute date
        - `fix author:john` - keyword with author filter (future use)
        """
        parsed = SearchQuery()
        
        # Tokenize respecting quoted strings
        tokens = re.findall(r'(?:[^\s"]+|"[^"]*")+', query)
        
        for token in tokens:
            # Remove quotes if present
            if token.startswith('"') and token.endswith('"'):
                parsed.keywords.append(token[1:-1].lower())
                continue
            
            # Check for filter prefixes
            if ':' in token:
                prefix, value = token.split(':', 1)
                prefix = prefix.lower()
                
                if prefix == 'file':
                    parsed.files.append(value.lower())
                elif prefix == 'topic':
                    parsed.topics.append(value.lower())
                elif prefix == 'author':
                    parsed.author = value
                elif prefix == 'after':
                    # Try duration first (e.g., "7d")
                    delta = self._parse_duration(value)
                    if delta:
                        parsed.after = datetime.now() - delta
                    else:
                        # Try absolute date
                        try:
                            parsed.after = datetime.fromisoformat(value)
                        except ValueError:
                            pass
                elif prefix == 'before':
                    delta = self._parse_duration(value)
                    if delta:
                        parsed.before = datetime.now() - delta
                    else:
                        try:
                            parsed.before = datetime.fromisoformat(value)
                        except ValueError:
                            pass
                else:
                    # Unknown prefix, treat as keyword
                    parsed.keywords.append(token.lower())
            else:
                parsed.keywords.append(token.lower())
        
        return parsed
    
    def extract_files(self, content: str) -> list[str]:
        """Extract file paths mentioned in content"""
        files = set()
        
        for pattern in FILE_PATH_PATTERNS:
            matches = re.findall(pattern, content, re.MULTILINE)
            for match in matches:
                path = match.strip()
                # Filter out obviously non-file matches
                if len(path) > 3 and '.' in path and not path.startswith('http'):
                    files.add(path.lower())
        
        return list(files)
    
    def _build_index_entry(self, session_id: str) -> Optional[SearchIndexEntry]:
        """Build a search index entry for a session"""
        data = Storage.read(["session", session_id])
        if not data:
            return None
        
        messages = data.get("messages", [])
        
        # Build content from all messages
        content_parts = []
        for msg in messages:
            role = msg.get("role", "")
            text = msg.get("content", "")
            if role in ("user", "assistant") and text:
                content_parts.append(text)
        
        content = "\n".join(content_parts)
        content_lower = content.lower()
        
        # Extract files mentioned
        files = self.extract_files(content)
        
        # Parse updated_at
        try:
            updated_at = datetime.fromisoformat(data.get("updated_at", ""))
        except (ValueError, TypeError):
            updated_at = datetime.now()
        
        return SearchIndexEntry(
            session_id=session_id,
            title=data.get("title", "New Session"),
            updated_at=updated_at,
            content_lower=content_lower,
            files=files,
            word_count=len(content_lower.split()),
            message_count=len(messages),
        )
    
    def build_index(self, force: bool = False):
        """Build or rebuild the search index"""
        if self._index_built and not force:
            return
        
        keys = Storage.list(["session"])
        
        for key in keys:
            session_id = key[-1]  # Last part is session_id
            try:
                entry = self._build_index_entry(session_id)
                if entry:
                    self._index[session_id] = entry
            except Exception as e:
                logger.warning(f"Failed to index session {session_id}: {e}")
        
        self._index_built = True
    
    def invalidate(self, session_id: str):
        """Invalidate a session's index entry (call after session update)"""
        self._index.pop(session_id, None)
    
    def _score_match(self, entry: SearchIndexEntry, query: SearchQuery, topic_info: Optional[TopicInfo]) -> float:
        """Calculate relevance score for a match"""
        score = 0.0
        
        # Keyword matching
        for keyword in query.keywords:
            # Title match (high weight)
            if keyword in entry.title.lower():
                score += 10.0
            
            # Content match (count occurrences)
            occurrences = entry.content_lower.count(keyword)
            if occurrences > 0:
                # Diminishing returns for many occurrences
                score += min(occurrences * 2.0, 10.0)
        
        # Topic match boost
        if query.topics and topic_info:
            for topic in query.topics:
                if topic_info.primary.lower() == topic:
                    score += 5.0
                elif topic in [t.lower() for t in topic_info.secondary]:
                    score += 3.0
                # Check keywords too
                if topic in [k.lower() for k in topic_info.keywords]:
                    score += 2.0
        
        # File match boost
        if query.files:
            for file_filter in query.files:
                for file in entry.files:
                    if file_filter in file:
                        score += 8.0
                        break
        
        # Recency boost (sessions from last 7 days get a boost)
        days_old = (datetime.now() - entry.updated_at).days
        if days_old < 1:
            score += 3.0
        elif days_old < 7:
            score += 2.0
        elif days_old < 30:
            score += 1.0
        
        return score
    
    def _extract_snippet(self, entry: SearchIndexEntry, query: SearchQuery, max_len: int = 150) -> str:
        """Extract a relevant snippet from the content"""
        content = entry.content_lower
        
        # Find the first keyword occurrence
        best_pos = -1
        for keyword in query.keywords:
            pos = content.find(keyword)
            if pos != -1 and (best_pos == -1 or pos < best_pos):
                best_pos = pos
        
        if best_pos == -1:
            # No keyword found, return start of content
            snippet = content[:max_len]
        else:
            # Extract around the keyword
            start = max(0, best_pos - 50)
            end = min(len(content), best_pos + max_len - 50)
            snippet = content[start:end]
            if start > 0:
                snippet = "..." + snippet
        
        # Clean up snippet
        snippet = " ".join(snippet.split())  # Normalize whitespace
        if len(snippet) > max_len:
            snippet = snippet[:max_len] + "..."
        
        return snippet
    
    def search(self, query: str, limit: int = 20) -> list[ThreadSearchResult]:
        """Search sessions with DSL query.
        
        Args:
            query: Search query with optional DSL syntax
            limit: Maximum results to return
            
        Returns:
            List of ThreadSearchResult sorted by relevance
        """
        # Build index if needed
        self.build_index()
        
        parsed = self.parse_query(query)
        
        if not parsed.has_filters():
            return []
        
        topic_index = get_topic_index()
        results = []
        
        for session_id, entry in self._index.items():
            # Date filters
            if parsed.after and entry.updated_at < parsed.after:
                continue
            if parsed.before and entry.updated_at > parsed.before:
                continue
            
            # Get topic info
            topic_info = topic_index.get_topics(session_id)
            
            # Topic filter
            if parsed.topics:
                if not topic_info:
                    continue
                topic_match = False
                for topic in parsed.topics:
                    if (topic_info.primary.lower() == topic or 
                        topic in [t.lower() for t in topic_info.secondary] or
                        topic in [k.lower() for k in topic_info.keywords]):
                        topic_match = True
                        break
                if not topic_match:
                    continue
            
            # File filter
            if parsed.files:
                file_match = False
                for file_filter in parsed.files:
                    for file in entry.files:
                        if file_filter in file:
                            file_match = True
                            break
                    if file_match:
                        break
                if not file_match:
                    continue
            
            # Keyword matching - at least one keyword must match
            if parsed.keywords:
                keyword_match = False
                for keyword in parsed.keywords:
                    if keyword in entry.content_lower or keyword in entry.title.lower():
                        keyword_match = True
                        break
                if not keyword_match:
                    continue
            
            # Calculate score
            score = self._score_match(entry, parsed, topic_info)
            
            if score > 0:
                snippet = self._extract_snippet(entry, parsed)
                results.append(ThreadSearchResult(
                    session_id=session_id,
                    title=entry.title,
                    updated_at=entry.updated_at,
                    score=score,
                    snippet=snippet,
                    topics=topic_info,
                ))
        
        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        
        return results[:limit]
    
    def reindex_session(self, session_id: str):
        """Reindex a specific session"""
        entry = self._build_index_entry(session_id)
        if entry:
            self._index[session_id] = entry
        else:
            self._index.pop(session_id, None)


# Global instance
_thread_search: Optional[ThreadSearch] = None


def get_thread_search() -> ThreadSearch:
    """Get the global ThreadSearch instance"""
    global _thread_search
    if _thread_search is None:
        _thread_search = ThreadSearch()
    return _thread_search


def search_threads(query: str, limit: int = 20) -> list[ThreadSearchResult]:
    """Convenience function to search threads"""
    return get_thread_search().search(query, limit)
