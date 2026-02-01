"""LSP tool for code intelligence features"""

from pathlib import Path
from typing import Optional
from .base import Tool
from codesm.util.citations import file_link_with_path


# LSP Symbol Kind mapping (from LSP spec)
SYMBOL_KINDS = {
    1: "File",
    2: "Module",
    3: "Namespace",
    4: "Package",
    5: "Class",
    6: "Method",
    7: "Property",
    8: "Field",
    9: "Constructor",
    10: "Enum",
    11: "Interface",
    12: "Function",
    13: "Variable",
    14: "Constant",
    15: "String",
    16: "Number",
    17: "Boolean",
    18: "Array",
    19: "Object",
    20: "Key",
    21: "Null",
    22: "EnumMember",
    23: "Struct",
    24: "Event",
    25: "Operator",
    26: "TypeParameter",
}


def symbol_kind_name(kind: int) -> str:
    """Convert LSP symbol kind number to readable name."""
    return SYMBOL_KINDS.get(kind, f"Unknown({kind})")


class LSPTool(Tool):
    name = "lsp"
    description = "Language Server Protocol features: go-to-definition, find references, hover info, symbols, and call hierarchy."

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "definition",
                        "references",
                        "hover",
                        "document_symbols",
                        "workspace_symbols",
                        "call_hierarchy_incoming",
                        "call_hierarchy_outgoing",
                    ],
                    "description": "The LSP action to perform",
                },
                "path": {
                    "type": "string",
                    "description": "Absolute file path (required for most actions)",
                },
                "line": {
                    "type": "integer",
                    "description": "1-based line number (required for position-based actions)",
                },
                "column": {
                    "type": "integer",
                    "description": "1-based column number (required for position-based actions)",
                },
                "query": {
                    "type": "string",
                    "description": "Search query for workspace_symbols action",
                },
                "include_declaration": {
                    "type": "boolean",
                    "description": "Include declaration in references (default: true)",
                },
            },
            "required": ["action"],
        }

    async def execute(self, args: dict, context: dict) -> str:
        from codesm import lsp
        from codesm.lsp.servers import get_server_for_file

        action: str = args.get("action", "")
        file_path: Optional[str] = args.get("path")
        line: Optional[int] = args.get("line")
        column: Optional[int] = args.get("column")
        query: Optional[str] = args.get("query")
        include_declaration: bool = args.get("include_declaration", True)

        # Validate path exists for path-based actions
        if file_path:
            path = Path(file_path)
            if not path.exists():
                return f"Error: File not found: {file_path}"
            file_path = str(path.resolve())

        # Get the appropriate client
        if file_path:
            server_key = get_server_for_file(file_path)
            if not server_key or server_key not in lsp._clients:
                return f"Error: No LSP server available for {file_path}"
            client = lsp._clients[server_key]
        else:
            # For workspace_symbols, use any available client
            if not lsp._clients:
                return "Error: No LSP servers running"
            client = next(iter(lsp._clients.values()))

        # Route to appropriate action
        if action == "definition":
            return await self._goto_definition(client, file_path, line, column)
        elif action == "references":
            return await self._find_references(client, file_path, line, column, include_declaration)
        elif action == "hover":
            return await self._hover(client, file_path, line, column)
        elif action == "document_symbols":
            return await self._document_symbols(client, file_path)
        elif action == "workspace_symbols":
            return await self._workspace_symbols(client, query)
        elif action == "call_hierarchy_incoming":
            return await self._call_hierarchy(client, file_path, line, column, "incoming")
        elif action == "call_hierarchy_outgoing":
            return await self._call_hierarchy(client, file_path, line, column, "outgoing")
        else:
            return f"Error: Unknown action '{action}'"

    async def _goto_definition(self, client, path: Optional[str], line: Optional[int], column: Optional[int]) -> str:
        if not path or not line or not column:
            return "Error: definition requires path, line, and column"

        locations = await client.definition(path, line, column)

        if not locations:
            return f"No definition found at {path}:{line}:{column}"

        lines = [f"**Definition(s)** for position {line}:{column}:", ""]
        for loc in locations:
            link = file_link_with_path(loc.path, loc.range.start_line)
            lines.append(f"- {link}:{loc.range.start_char}")

        return "\n".join(lines)

    async def _find_references(
        self, client, path: Optional[str], line: Optional[int], column: Optional[int], include_declaration: bool
    ) -> str:
        if not path or not line or not column:
            return "Error: references requires path, line, and column"

        locations = await client.references(path, line, column, include_declaration)

        if not locations:
            return f"No references found at {path}:{line}:{column}"

        lines = [f"**References** ({len(locations)} found):", ""]
        for loc in locations:
            link = file_link_with_path(loc.path, loc.range.start_line)
            lines.append(f"- {link}:{loc.range.start_char}")

        return "\n".join(lines)

    async def _hover(self, client, path: Optional[str], line: Optional[int], column: Optional[int]) -> str:
        if not path or not line or not column:
            return "Error: hover requires path, line, and column"

        hover_info = await client.hover(path, line, column)

        if not hover_info:
            return f"No hover information at {path}:{line}:{column}"

        lines = ["**Hover Info**", ""]

        # Add location if available
        if hover_info.range:
            link = file_link_with_path(path, hover_info.range.start_line)
            lines.append(f"Location: {link}")
            lines.append("")

        # Add content (may already be markdown)
        content = hover_info.contents.strip()
        if content:
            lines.append(content)

        return "\n".join(lines)

    async def _document_symbols(self, client, path: Optional[str]) -> str:
        if not path:
            return "Error: document_symbols requires path"

        symbols = await client.document_symbols(path)

        if not symbols:
            return f"No symbols found in {path}"

        lines = [f"**Symbols in** {file_link_with_path(path)}:", ""]
        for sym in symbols:
            kind = symbol_kind_name(sym.kind)
            link = file_link_with_path(sym.path, sym.range.start_line)
            container = f" (in {sym.container_name})" if sym.container_name else ""
            lines.append(f"- **{sym.name}** [{kind}] {link}{container}")

        return "\n".join(lines)

    async def _workspace_symbols(self, client, query: Optional[str]) -> str:
        if not query:
            return "Error: workspace_symbols requires query"

        symbols = await client.workspace_symbols(query)

        if not symbols:
            return f"No symbols found matching '{query}'"

        lines = [f"**Workspace Symbols** matching '{query}' ({len(symbols)} found):", ""]
        for sym in symbols:
            kind = symbol_kind_name(sym.kind)
            if sym.path:
                link = file_link_with_path(sym.path, sym.range.start_line)
                location = f" {link}"
            else:
                location = ""
            container = f" (in {sym.container_name})" if sym.container_name else ""
            lines.append(f"- **{sym.name}** [{kind}]{location}{container}")

        return "\n".join(lines)

    async def _call_hierarchy(
        self, client, path: Optional[str], line: Optional[int], column: Optional[int], direction: str
    ) -> str:
        if not path or not line or not column:
            return f"Error: call_hierarchy_{direction} requires path, line, and column"

        # First prepare the call hierarchy item
        items = await client.prepare_call_hierarchy(path, line, column)

        if not items:
            return f"No callable found at {path}:{line}:{column}"

        # Get the first item (usually there's only one)
        item = items[0]
        item_link = file_link_with_path(item.path, item.range.start_line)
        item_kind = symbol_kind_name(item.kind)

        if direction == "incoming":
            calls = await client.incoming_calls(item)
            if not calls:
                return f"No incoming calls to **{item.name}** [{item_kind}] at {item_link}"

            lines = [f"**Incoming Calls** to **{item.name}** [{item_kind}] ({len(calls)} found):", ""]
            for call in calls:
                caller = call["from"]
                caller_link = file_link_with_path(caller.path, caller.range.start_line)
                caller_kind = symbol_kind_name(caller.kind)
                detail = f" - {caller.detail}" if caller.detail else ""
                lines.append(f"- **{caller.name}** [{caller_kind}] {caller_link}{detail}")

        else:  # outgoing
            calls = await client.outgoing_calls(item)
            if not calls:
                return f"No outgoing calls from **{item.name}** [{item_kind}] at {item_link}"

            lines = [f"**Outgoing Calls** from **{item.name}** [{item_kind}] ({len(calls)} found):", ""]
            for call in calls:
                callee = call["to"]
                callee_link = file_link_with_path(callee.path, callee.range.start_line)
                callee_kind = symbol_kind_name(callee.kind)
                detail = f" - {callee.detail}" if callee.detail else ""
                lines.append(f"- **{callee.name}** [{callee_kind}] {callee_link}{detail}")

        return "\n".join(lines)
