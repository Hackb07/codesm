"""LSP client implementation using JSON-RPC over stdin/stdout"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field
from urllib.parse import quote, unquote, urlparse

from .servers import ServerConfig

logger = logging.getLogger(__name__)


@dataclass
class Diagnostic:
    path: str
    line: int
    column: int
    message: str
    severity: str  # "error", "warning", "info", "hint"
    source: Optional[str] = None


@dataclass
class Range:
    start_line: int  # 1-based
    start_char: int  # 1-based
    end_line: int  # 1-based
    end_char: int  # 1-based


@dataclass
class Location:
    path: str
    range: Range


@dataclass
class Symbol:
    name: str
    kind: int
    path: str
    range: Range
    container_name: Optional[str] = None


@dataclass
class Hover:
    contents: str
    range: Optional[Range] = None


@dataclass
class CallHierarchyItem:
    name: str
    kind: int
    path: str
    range: Range
    detail: Optional[str] = None
    _raw: Optional[dict] = field(default=None, repr=False)


@dataclass
class LSPClient:
    config: ServerConfig
    root_path: str
    process: Optional[asyncio.subprocess.Process] = None
    _request_id: int = 0
    _pending: dict[int, asyncio.Future] = field(default_factory=dict)
    _diagnostics: dict[str, list[Diagnostic]] = field(default_factory=dict)
    _reader_task: Optional[asyncio.Task] = None
    _initialized: bool = False
    _open_docs: dict[str, dict] = field(default_factory=dict)
    server_capabilities: dict = field(default_factory=dict)

    async def start(self) -> bool:
        """Start the language server process."""
        try:
            self.process = await asyncio.create_subprocess_exec(
                *self.config.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.root_path,
            )
            self._reader_task = asyncio.create_task(self._read_messages())
            return True
        except FileNotFoundError:
            logger.warning(f"LSP server not found: {self.config.command[0]}")
            return False
        except Exception as e:
            logger.error(f"Failed to start LSP server: {e}")
            return False

    def _path_to_uri(self, path: str) -> str:
        """Convert a file path to a file:// URI with proper encoding."""
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = Path(self.root_path).resolve() / path
        else:
            file_path = file_path.resolve()
        return file_path.as_uri()

    def _uri_to_path(self, uri: str) -> str:
        """Convert a file:// URI to an absolute path."""
        if uri.startswith("file://"):
            parsed = urlparse(uri)
            return unquote(parsed.path)
        return uri

    def _lsp_range_to_range(self, lsp_range: dict) -> Range:
        """Convert LSP 0-based range to 1-based Range."""
        return Range(
            start_line=lsp_range.get("start", {}).get("line", 0) + 1,
            start_char=lsp_range.get("start", {}).get("character", 0) + 1,
            end_line=lsp_range.get("end", {}).get("line", 0) + 1,
            end_char=lsp_range.get("end", {}).get("character", 0) + 1,
        )

    async def initialize(self) -> bool:
        """Send initialize request to the server."""
        if not self.process:
            return False

        root_path_abs = Path(self.root_path).resolve()
        root_uri = root_path_abs.as_uri()

        result = await self._request("initialize", {
            "processId": None,
            "rootUri": root_uri,
            "rootPath": str(root_path_abs),
            "capabilities": {
                "textDocument": {
                    "publishDiagnostics": {
                        "relatedInformation": True,
                    },
                    "synchronization": {
                        "didOpen": True,
                        "didChange": True,
                        "didClose": True,
                    },
                    "definition": {
                        "dynamicRegistration": False,
                    },
                    "references": {
                        "dynamicRegistration": False,
                    },
                    "hover": {
                        "dynamicRegistration": False,
                        "contentFormat": ["plaintext", "markdown"],
                    },
                    "documentSymbol": {
                        "dynamicRegistration": False,
                        "hierarchicalDocumentSymbolSupport": True,
                    },
                    "callHierarchy": {
                        "dynamicRegistration": False,
                    },
                },
                "workspace": {
                    "symbol": {
                        "dynamicRegistration": False,
                    },
                    "configuration": True,
                    "workspaceFolders": True,
                },
            },
            "workspaceFolders": [
                {"uri": root_uri, "name": root_path_abs.name}
            ],
        })
        
        if result is not None:
            self.server_capabilities = result.get("capabilities", {})
            await self._notify("initialized", {})
            self._initialized = True
            return True
        return False

    async def did_open(self, path: str, text: Optional[str] = None) -> None:
        """Notify the server that a file was opened."""
        if not self._initialized:
            return

        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = Path(self.root_path).resolve() / path
        else:
            file_path = file_path.resolve()

        uri = file_path.as_uri()
        
        if uri in self._open_docs:
            return

        if text is None:
            try:
                text = file_path.read_text()
            except Exception as e:
                logger.warning(f"Failed to read file {path}: {e}")
                return

        language_id = self._get_language_id(str(file_path))
        version = 1
        
        self._open_docs[uri] = {"version": version, "text": text}

        await self._notify("textDocument/didOpen", {
            "textDocument": {
                "uri": uri,
                "languageId": language_id,
                "version": version,
                "text": text,
            }
        })

    async def did_change(self, path: str, text: str) -> None:
        """Notify the server that a file changed."""
        if not self._initialized:
            return

        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = Path(self.root_path).resolve() / path
        else:
            file_path = file_path.resolve()

        uri = file_path.as_uri()
        
        if uri not in self._open_docs:
            await self.did_open(path, text)
            return

        self._open_docs[uri]["version"] += 1
        self._open_docs[uri]["text"] = text
        version = self._open_docs[uri]["version"]

        await self._notify("textDocument/didChange", {
            "textDocument": {
                "uri": uri,
                "version": version,
            },
            "contentChanges": [{"text": text}],
        })

    async def _ensure_open(self, path: str, text: Optional[str] = None) -> str:
        """Ensure a document is open and return its URI."""
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = Path(self.root_path).resolve() / path
        else:
            file_path = file_path.resolve()

        uri = file_path.as_uri()
        
        if uri not in self._open_docs:
            await self.did_open(str(file_path), text)
        
        return uri

    def get_diagnostics(self, path: Optional[str] = None) -> list[Diagnostic]:
        """Get diagnostics, optionally filtered by path."""
        if path:
            return self._diagnostics.get(path, [])
        
        all_diags = []
        for diags in self._diagnostics.values():
            all_diags.extend(diags)
        return all_diags

    async def shutdown(self) -> None:
        """Shutdown the language server."""
        if not self.process:
            return

        try:
            if self._initialized:
                await self._request("shutdown", None, timeout=5.0)
                await self._notify("exit", None)
        except Exception:
            pass

        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                self.process.kill()

        self._initialized = False

    async def _request(
        self, method: str, params: Any, timeout: float = 30.0
    ) -> Optional[Any]:
        """Send a request and wait for response."""
        if not self.process or not self.process.stdin:
            return None

        self._request_id += 1
        request_id = self._request_id

        message = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future

        await self._send_message(message)

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            logger.warning(f"LSP request timed out: {method}")
            return None

    async def _notify(self, method: str, params: Any) -> None:
        """Send a notification (no response expected)."""
        if not self.process or not self.process.stdin:
            return

        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        await self._send_message(message)

    async def _send_message(self, message: dict) -> None:
        """Send a JSON-RPC message."""
        if not self.process or not self.process.stdin:
            return

        content = json.dumps(message)
        header = f"Content-Length: {len(content)}\r\n\r\n"
        
        try:
            self.process.stdin.write(header.encode() + content.encode())
            await self.process.stdin.drain()
        except Exception as e:
            logger.error(f"Failed to send LSP message: {e}")

    async def _read_messages(self) -> None:
        """Read and handle messages from the server."""
        if not self.process or not self.process.stdout:
            return

        try:
            while True:
                header = await self._read_header()
                if header is None:
                    break

                content_length = self._parse_content_length(header)
                if content_length is None:
                    continue

                content = await self.process.stdout.read(content_length)
                if not content:
                    break

                try:
                    message = json.loads(content.decode())
                    await self._handle_message(message)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON from LSP server: {e}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"LSP reader error: {e}")

    async def _read_header(self) -> Optional[bytes]:
        """Read the header section of a message."""
        if not self.process or not self.process.stdout:
            return None

        header = b""
        while True:
            line = await self.process.stdout.readline()
            if not line:
                return None
            header += line
            if header.endswith(b"\r\n\r\n"):
                return header

    def _parse_content_length(self, header: bytes) -> Optional[int]:
        """Parse Content-Length from header."""
        for line in header.decode().split("\r\n"):
            if line.lower().startswith("content-length:"):
                try:
                    return int(line.split(":", 1)[1].strip())
                except ValueError:
                    return None
        return None

    async def _handle_message(self, message: dict) -> None:
        """Handle an incoming message."""
        if "id" in message and "result" in message:
            # Response
            request_id = message["id"]
            if request_id in self._pending:
                self._pending[request_id].set_result(message.get("result"))
                del self._pending[request_id]

        elif "id" in message and "error" in message:
            # Error response
            request_id = message["id"]
            if request_id in self._pending:
                error = message["error"]
                logger.warning(f"LSP error: {error.get('message', error)}")
                self._pending[request_id].set_result(None)
                del self._pending[request_id]

        elif "id" in message and "method" in message:
            # Request from server - needs a response
            request_id = message["id"]
            method = message["method"]
            
            if method == "workspace/configuration":
                result = [{}]
            elif method == "client/registerCapability":
                result = None
            elif method == "window/workDoneProgress/create":
                result = None
            else:
                result = None

            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result,
            }
            await self._send_message(response)

        elif "method" in message:
            # Notification from server (no id)
            method = message["method"]
            params = message.get("params", {})

            if method == "textDocument/publishDiagnostics":
                self._handle_diagnostics(params)
            elif method == "window/logMessage":
                level = params.get("type", 4)
                msg = params.get("message", "")
                if level <= 2:
                    logger.warning(f"LSP: {msg}")

    def _handle_diagnostics(self, params: dict) -> None:
        """Handle publishDiagnostics notification."""
        uri = params.get("uri", "")
        diagnostics = params.get("diagnostics", [])

        path = self._uri_to_path(uri)
        severity_map = {1: "error", 2: "warning", 3: "info", 4: "hint"}

        self._diagnostics[path] = [
            Diagnostic(
                path=path,
                line=d.get("range", {}).get("start", {}).get("line", 0) + 1,
                column=d.get("range", {}).get("start", {}).get("character", 0) + 1,
                message=d.get("message", ""),
                severity=severity_map.get(d.get("severity", 4), "hint"),
                source=d.get("source"),
            )
            for d in diagnostics
        ]

    def _get_language_id(self, path: str) -> str:
        """Get the language ID for a file path."""
        ext_map = {
            ".py": "python",
            ".pyi": "python",
            ".ts": "typescript",
            ".tsx": "typescriptreact",
            ".js": "javascript",
            ".jsx": "javascriptreact",
            ".rs": "rust",
            ".go": "go",
        }
        for ext, lang in ext_map.items():
            if path.endswith(ext):
                return lang
        return "plaintext"

    def _parse_location(self, loc: dict) -> Optional[Location]:
        """Parse an LSP Location to our Location type."""
        uri = loc.get("uri", "")
        lsp_range = loc.get("range")
        if not lsp_range:
            return None
        return Location(
            path=self._uri_to_path(uri),
            range=self._lsp_range_to_range(lsp_range),
        )

    def _parse_hover_contents(self, contents: Any) -> str:
        """Parse hover contents to a string."""
        if isinstance(contents, str):
            return contents
        elif isinstance(contents, dict):
            return contents.get("value", "")
        elif isinstance(contents, list):
            parts = []
            for item in contents:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(item.get("value", ""))
            return "\n".join(parts)
        return ""

    def _parse_symbol(self, sym: dict, default_path: str) -> Symbol:
        """Parse an LSP SymbolInformation or DocumentSymbol to our Symbol type."""
        location = sym.get("location")
        if location:
            path = self._uri_to_path(location.get("uri", ""))
            lsp_range = location.get("range", {})
        else:
            path = default_path
            lsp_range = sym.get("range", sym.get("selectionRange", {}))

        return Symbol(
            name=sym.get("name", ""),
            kind=sym.get("kind", 0),
            path=path,
            range=self._lsp_range_to_range(lsp_range),
            container_name=sym.get("containerName"),
        )

    def _flatten_document_symbols(
        self, symbols: list[dict], path: str, container: Optional[str] = None
    ) -> list[Symbol]:
        """Flatten hierarchical document symbols."""
        result = []
        for sym in symbols:
            lsp_range = sym.get("selectionRange", sym.get("range", {}))
            symbol = Symbol(
                name=sym.get("name", ""),
                kind=sym.get("kind", 0),
                path=path,
                range=self._lsp_range_to_range(lsp_range),
                container_name=container,
            )
            result.append(symbol)
            children = sym.get("children", [])
            if children:
                result.extend(
                    self._flatten_document_symbols(children, path, sym.get("name"))
                )
        return result

    async def definition(
        self, path: str, line: int, character: int
    ) -> list[Location]:
        """Get definition locations for a symbol at the given position."""
        if not self._initialized:
            return []

        uri = await self._ensure_open(path)
        result = await self._request("textDocument/definition", {
            "textDocument": {"uri": uri},
            "position": {"line": line - 1, "character": character - 1},
        })

        if result is None:
            return []

        locations = []
        if isinstance(result, dict):
            result = [result]
        for item in result:
            loc = self._parse_location(item)
            if loc:
                locations.append(loc)
        return locations

    async def references(
        self, path: str, line: int, character: int, include_declaration: bool = True
    ) -> list[Location]:
        """Get all references to a symbol at the given position."""
        if not self._initialized:
            return []

        uri = await self._ensure_open(path)
        result = await self._request("textDocument/references", {
            "textDocument": {"uri": uri},
            "position": {"line": line - 1, "character": character - 1},
            "context": {"includeDeclaration": include_declaration},
        })

        if result is None:
            return []

        locations = []
        for item in result:
            loc = self._parse_location(item)
            if loc:
                locations.append(loc)
        return locations

    async def hover(
        self, path: str, line: int, character: int
    ) -> Optional[Hover]:
        """Get hover information for a symbol at the given position."""
        if not self._initialized:
            return None

        uri = await self._ensure_open(path)
        result = await self._request("textDocument/hover", {
            "textDocument": {"uri": uri},
            "position": {"line": line - 1, "character": character - 1},
        })

        if result is None:
            return None

        contents = self._parse_hover_contents(result.get("contents", ""))
        lsp_range = result.get("range")
        return Hover(
            contents=contents,
            range=self._lsp_range_to_range(lsp_range) if lsp_range else None,
        )

    async def document_symbols(self, path: str) -> list[Symbol]:
        """Get all symbols in a document."""
        if not self._initialized:
            return []

        uri = await self._ensure_open(path)
        abs_path = self._uri_to_path(uri)
        result = await self._request("textDocument/documentSymbol", {
            "textDocument": {"uri": uri},
        })

        if result is None:
            return []

        if not result:
            return []

        if "range" in result[0] or "selectionRange" in result[0]:
            return self._flatten_document_symbols(result, abs_path)
        else:
            return [self._parse_symbol(sym, abs_path) for sym in result]

    async def workspace_symbols(self, query: str) -> list[Symbol]:
        """Search for symbols across the workspace."""
        if not self._initialized:
            return []

        result = await self._request("workspace/symbol", {"query": query})

        if result is None:
            return []

        return [self._parse_symbol(sym, "") for sym in result]

    async def prepare_call_hierarchy(
        self, path: str, line: int, character: int
    ) -> list[CallHierarchyItem]:
        """Prepare call hierarchy at the given position."""
        if not self._initialized:
            return []

        uri = await self._ensure_open(path)
        result = await self._request("textDocument/prepareCallHierarchy", {
            "textDocument": {"uri": uri},
            "position": {"line": line - 1, "character": character - 1},
        })

        if result is None:
            return []

        items = []
        for item in result:
            lsp_range = item.get("selectionRange", item.get("range", {}))
            items.append(CallHierarchyItem(
                name=item.get("name", ""),
                kind=item.get("kind", 0),
                path=self._uri_to_path(item.get("uri", "")),
                range=self._lsp_range_to_range(lsp_range),
                detail=item.get("detail"),
                _raw=item,
            ))
        return items

    async def incoming_calls(self, item: CallHierarchyItem) -> list[dict]:
        """Get incoming calls to a call hierarchy item."""
        if not self._initialized or not item._raw:
            return []

        result = await self._request("callHierarchy/incomingCalls", {
            "item": item._raw,
        })

        if result is None:
            return []

        calls = []
        for call in result:
            from_item = call.get("from", {})
            lsp_range = from_item.get("selectionRange", from_item.get("range", {}))
            calls.append({
                "from": CallHierarchyItem(
                    name=from_item.get("name", ""),
                    kind=from_item.get("kind", 0),
                    path=self._uri_to_path(from_item.get("uri", "")),
                    range=self._lsp_range_to_range(lsp_range),
                    detail=from_item.get("detail"),
                    _raw=from_item,
                ),
                "fromRanges": [
                    self._lsp_range_to_range(r) for r in call.get("fromRanges", [])
                ],
            })
        return calls

    async def outgoing_calls(self, item: CallHierarchyItem) -> list[dict]:
        """Get outgoing calls from a call hierarchy item."""
        if not self._initialized or not item._raw:
            return []

        result = await self._request("callHierarchy/outgoingCalls", {
            "item": item._raw,
        })

        if result is None:
            return []

        calls = []
        for call in result:
            to_item = call.get("to", {})
            lsp_range = to_item.get("selectionRange", to_item.get("range", {}))
            calls.append({
                "to": CallHierarchyItem(
                    name=to_item.get("name", ""),
                    kind=to_item.get("kind", 0),
                    path=self._uri_to_path(to_item.get("uri", "")),
                    range=self._lsp_range_to_range(lsp_range),
                    detail=to_item.get("detail"),
                    _raw=to_item,
                ),
                "fromRanges": [
                    self._lsp_range_to_range(r) for r in call.get("fromRanges", [])
                ],
            })
        return calls
