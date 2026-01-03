"""Web fetch tool - fetches content from URLs"""

import httpx
from .base import Tool


class WebFetchTool(Tool):
    name = "webfetch"
    description = """Fetch and read content from a specific URL.
- Use when the user provides a URL to read
- Use to read documentation pages
- Returns content as readable text/markdown
- Supports HTML pages, converting them to readable text"""

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch content from",
                },
                "format": {
                    "type": "string",
                    "enum": ["text", "markdown", "html"],
                    "description": "Output format (default: markdown)",
                },
            },
            "required": ["url"],
        }

    async def execute(self, args: dict, context: dict) -> str:
        url = args["url"]
        format_type = args.get("format", "markdown")

        if not url.startswith(("http://", "https://")):
            return "Error: URL must start with http:// or https://"

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                )
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                text = response.text

                # Convert HTML to readable text
                if "html" in content_type and format_type in ("text", "markdown"):
                    text = self._html_to_text(text)

                # Limit response size
                if len(text) > 50000:
                    text = text[:50000] + "\n\n... (content truncated)"

                return text

        except httpx.TimeoutException:
            return f"Error: Request timed out for {url}"
        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} for {url}"
        except Exception as e:
            return f"Error fetching {url}: {str(e)}"

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to readable text"""
        import re

        # Remove script and style elements
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<head[^>]*>.*?</head>', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Convert common elements to markdown-ish format
        text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'\n# \1\n', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n## \1\n', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'\n### \1\n', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<h[4-6][^>]*>(.*?)</h[4-6]>', r'\n#### \1\n', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Links
        text = re.sub(r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', r'[\2](\1)', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Lists
        text = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Paragraphs and breaks
        text = re.sub(r'<p[^>]*>', '\n\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<br[^>]*/?>', '\n', text, flags=re.IGNORECASE)
        
        # Code blocks
        text = re.sub(r'<pre[^>]*>(.*?)</pre>', r'\n```\n\1\n```\n', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Bold and italic
        text = re.sub(r'<(strong|b)[^>]*>(.*?)</\1>', r'**\2**', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<(em|i)[^>]*>(.*?)</\1>', r'*\2*', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove remaining HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Clean up HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        
        # Clean up whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        
        return text.strip()
