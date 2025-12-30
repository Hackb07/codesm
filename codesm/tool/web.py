"""Web search and fetch tool"""

import httpx
from .base import Tool


class WebTool(Tool):
    name = "web"
    description = "Fetch content from a URL. Useful for reading documentation, API responses, etc."

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch",
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST"],
                    "description": "HTTP method (default: GET)",
                },
                "headers": {
                    "type": "object",
                    "description": "Optional HTTP headers",
                },
            },
            "required": ["url"],
        }

    async def execute(self, args: dict, context: dict) -> str:
        url = args["url"]
        method = args.get("method", "GET")
        headers = args.get("headers", {})

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if method == "GET":
                    response = await client.get(url, headers=headers, follow_redirects=True)
                else:
                    response = await client.post(url, headers=headers, follow_redirects=True)

                response.raise_for_status()

                # Try to return formatted content
                content_type = response.headers.get("content-type", "")

                if "json" in content_type:
                    return f"Status: {response.status_code}\n\n{response.text}"
                elif "html" in content_type:
                    # Strip HTML tags for readability
                    import re
                    text = re.sub(r"<[^>]+>", "", response.text)
                    text = re.sub(r"\s+", " ", text).strip()
                    return f"Status: {response.status_code}\n\n{text[:10000]}"  # Limit size
                else:
                    return f"Status: {response.status_code}\n\n{response.text[:10000]}"

        except httpx.TimeoutException:
            return f"Error: Request timed out for {url}"
        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {e.response.text[:500]}"
        except Exception as e:
            return f"Error fetching {url}: {str(e)}"
