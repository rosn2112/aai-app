from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aai_app.config import AppConfig


DEFAULT_MCP_SERVERS = {
    "notion": {
        "enabled": False,
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@notionhq/notion-mcp-server"],
        "env": {},
        "import_tool": "search",
        "import_arg": "query",
        "export_tool": "create_page",
        "export_title_arg": "title",
        "export_content_arg": "content",
        "description": "Example Notion MCP server profile. Add auth env values before use.",
    }
}


@dataclass
class MCPServerConfig:
    name: str
    enabled: bool
    transport: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    import_tool: str | None = None
    import_arg: str = "query"
    export_tool: str | None = None
    export_title_arg: str = "title"
    export_content_arg: str = "content"
    description: str = ""


def ensure_integrations_config(config: AppConfig) -> Path:
    path = config.integrations_path
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_MCP_SERVERS, indent=2), encoding="utf-8")
    return path


def load_integration_configs(config: AppConfig) -> list[MCPServerConfig]:
    path = ensure_integrations_config(config)
    data = json.loads(path.read_text(encoding="utf-8"))
    servers: list[MCPServerConfig] = []
    for name, entry in data.items():
        servers.append(
            MCPServerConfig(
                name=name,
                enabled=bool(entry.get("enabled", False)),
                transport=entry.get("transport", "stdio"),
                command=entry.get("command", ""),
                args=list(entry.get("args", [])),
                env=dict(entry.get("env", {})),
                import_tool=entry.get("import_tool"),
                import_arg=entry.get("import_arg", "query"),
                export_tool=entry.get("export_tool"),
                export_title_arg=entry.get("export_title_arg", "title"),
                export_content_arg=entry.get("export_content_arg", "content"),
                description=entry.get("description", ""),
            )
        )
    return servers


def get_integration(config: AppConfig, name: str) -> MCPServerConfig:
    target = name.strip().lower()
    for server in load_integration_configs(config):
        if server.name.lower() == target:
            return server
    raise ValueError(f"No MCP integration named '{name}' is configured.")


def _flatten_tool_result(result: Any) -> str:
    content = getattr(result, "content", None)
    if not content:
        return str(result)
    parts: list[str] = []
    for item in content:
        text_value = getattr(item, "text", None)
        if text_value:
            parts.append(text_value)
            continue
        if isinstance(item, dict) and "text" in item:
            parts.append(str(item["text"]))
            continue
        parts.append(str(item))
    return "\n\n".join(part.strip() for part in parts if str(part).strip())


async def _call_stdio_tool(server: MCPServerConfig, tool_name: str, arguments: dict[str, str]) -> str:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as exc:
        raise RuntimeError(
            "MCP support is not installed. Run `pip install -e '.[mcp]'` or re-run `./install.sh`."
        ) from exc

    if server.transport != "stdio":
        raise RuntimeError(f"Unsupported MCP transport: {server.transport}")
    if not server.command:
        raise RuntimeError(f"MCP integration '{server.name}' is missing a command.")

    params = StdioServerParameters(
        command=server.command,
        args=server.args,
        env=server.env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            return _flatten_tool_result(result)


def import_from_mcp(config: AppConfig, server_name: str, query: str) -> str:
    server = get_integration(config, server_name)
    if not server.enabled:
        raise RuntimeError(
            f"MCP integration '{server.name}' is disabled. Edit {config.integrations_path} to enable it."
        )
    if not server.import_tool:
        raise RuntimeError(f"MCP integration '{server.name}' does not define an import tool.")
    arguments = {server.import_arg: query}
    return asyncio.run(_call_stdio_tool(server, server.import_tool, arguments))


def export_to_mcp(config: AppConfig, server_name: str, title: str, content: str) -> str:
    server = get_integration(config, server_name)
    if not server.enabled:
        raise RuntimeError(
            f"MCP integration '{server.name}' is disabled. Edit {config.integrations_path} to enable it."
        )
    if not server.export_tool:
        raise RuntimeError(f"MCP integration '{server.name}' does not define an export tool.")
    arguments = {
        server.export_title_arg: title,
        server.export_content_arg: content,
    }
    return asyncio.run(_call_stdio_tool(server, server.export_tool, arguments))
