"""
MCP Server Inspection Tool.
Allows inspecting available tools, prompts, and resources on an MCP server.
"""

import asyncio
import json
import logging
import time
from typing import Any, Type, Dict, List, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict
import aiohttp

logger = logging.getLogger(__name__)


class McpInspectInput(BaseModel):
    """Input schema for MCP server inspection tool."""

    resource_type: str = Field(
        default="all",
        description="What to inspect: 'tools', 'prompts', 'resources', or 'all'"
    )


class McpInspectTool(BaseTool):
    """Tool for inspecting available tools, prompts, and resources on an MCP server."""

    name: str = "mcp_inspect"
    description: str = "List available tools, prompts, and resources from the MCP server"
    args_schema: Type[BaseModel] = McpInspectInput
    return_type: str = "str"

    # MCP server connection details
    server_name: str = Field(..., description="Name of the MCP server")
    server_url: str = Field(..., description="URL of the MCP server")
    server_headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP headers for authentication")
    timeout: int = Field(default=30, description="Request timeout in seconds")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __getstate__(self):
        """Custom serialization for pickle compatibility."""
        state = self.__dict__.copy()
        # Convert headers dict to regular dict to avoid any reference issues
        if 'server_headers' in state and state['server_headers'] is not None:
            state['server_headers'] = dict(state['server_headers'])
        return state

    def __setstate__(self, state):
        """Custom deserialization for pickle compatibility."""
        # Initialize Pydantic internal attributes if needed
        if '__pydantic_fields_set__' not in state:
            state['__pydantic_fields_set__'] = set(state.keys())
        if '__pydantic_extra__' not in state:
            state['__pydantic_extra__'] = None
        if '__pydantic_private__' not in state:
            state['__pydantic_private__'] = None

        # Update object state
        self.__dict__.update(state)

    def _run(self, resource_type: str = "all") -> str:
        """Inspect the MCP server for available resources."""
        try:
            # Always create a new event loop for sync context
            # This avoids issues with existing event loops in threads
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self._run_in_new_loop, resource_type)
                return future.result(timeout=self.timeout)
        except Exception as e:
            logger.error(f"Error inspecting MCP server '{self.server_name}': {e}")
            return f"Error inspecting MCP server: {e}"

    def _run_in_new_loop(self, resource_type: str) -> str:
        """Run the async inspection in a new event loop."""
        return asyncio.run(self._inspect_server(resource_type))

    async def _inspect_server(self, resource_type: str) -> str:
        """Perform the actual MCP server inspection."""
        results = {}

        # Determine what to inspect
        inspect_tools = resource_type in ["all", "tools"]
        inspect_prompts = resource_type in ["all", "prompts"]
        inspect_resources = resource_type in ["all", "resources"]

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:

            # List tools
            if inspect_tools:
                try:
                    tools = await self._list_tools(session)
                    results["tools"] = tools
                except Exception as e:
                    logger.warning(f"Failed to list tools from {self.server_name}: {e}")
                    results["tools"] = {"error": str(e)}

            # List prompts
            if inspect_prompts:
                try:
                    prompts = await self._list_prompts(session)
                    results["prompts"] = prompts
                except Exception as e:
                    logger.warning(f"Failed to list prompts from {self.server_name}: {e}")
                    results["prompts"] = {"error": str(e)}

            # List resources
            if inspect_resources:
                try:
                    resources = await self._list_resources(session)
                    results["resources"] = resources
                except Exception as e:
                    logger.warning(f"Failed to list resources from {self.server_name}: {e}")
                    results["resources"] = {"error": str(e)}

        return self._format_results(results, resource_type)

    def _parse_sse(self, text: str) -> Dict[str, Any]:
        """Parse Server-Sent Events (SSE) format response."""
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('data:'):
                json_str = line[5:].strip()
                return json.loads(json_str)
        raise ValueError("No data found in SSE response")

    async def _list_tools(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """List available tools from the MCP server."""
        request = {
            "jsonrpc": "2.0",
            "id": f"list_tools_{int(time.time())}",
            "method": "tools/list",
            "params": {}
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **self.server_headers
        }

        async with session.post(self.server_url, json=request, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"HTTP {response.status}: {await response.text()}")

            # Handle both JSON and SSE responses
            content_type = response.headers.get('Content-Type', '')
            if 'text/event-stream' in content_type:
                # Parse SSE format
                text = await response.text()
                data = self._parse_sse(text)
            else:
                data = await response.json()

            if "error" in data:
                raise Exception(f"MCP Error: {data['error']}")

            return data.get("result", {})

    async def _list_prompts(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """List available prompts from the MCP server."""
        request = {
            "jsonrpc": "2.0",
            "id": f"list_prompts_{int(time.time())}",
            "method": "prompts/list",
            "params": {}
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **self.server_headers
        }

        async with session.post(self.server_url, json=request, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"HTTP {response.status}: {await response.text()}")

            # Handle both JSON and SSE responses
            content_type = response.headers.get('Content-Type', '')
            if 'text/event-stream' in content_type:
                text = await response.text()
                data = self._parse_sse(text)
            else:
                data = await response.json()

            if "error" in data:
                raise Exception(f"MCP Error: {data['error']}")

            return data.get("result", {})

    async def _list_resources(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """List available resources from the MCP server."""
        request = {
            "jsonrpc": "2.0",
            "id": f"list_resources_{int(time.time())}",
            "method": "resources/list",
            "params": {}
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **self.server_headers
        }

        async with session.post(self.server_url, json=request, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"HTTP {response.status}: {await response.text()}")

            # Handle both JSON and SSE responses
            content_type = response.headers.get('Content-Type', '')
            if 'text/event-stream' in content_type:
                text = await response.text()
                data = self._parse_sse(text)
            else:
                data = await response.json()

            if "error" in data:
                raise Exception(f"MCP Error: {data['error']}")

            return data.get("result", {})

    def _format_results(self, results: Dict[str, Any], resource_type: str) -> str:
        """Format the inspection results for display."""
        output_lines = [f"=== MCP Server Inspection: {self.server_name} ==="]
        output_lines.append(f"Server URL: {self.server_url}")
        output_lines.append("")

        # Format tools
        if "tools" in results:
            if "error" in results["tools"]:
                output_lines.append(f"❌ TOOLS: Error - {results['tools']['error']}")
            else:
                tools = results["tools"].get("tools", [])
                output_lines.append(f"🔧 TOOLS ({len(tools)} available):")
                if tools:
                    for tool in tools:
                        name = tool.get("name", "Unknown")
                        desc = tool.get("description", "No description")
                        output_lines.append(f"  • {name}: {desc}")
                else:
                    output_lines.append("  (No tools available)")
                output_lines.append("")

        # Format prompts
        if "prompts" in results:
            if "error" in results["prompts"]:
                output_lines.append(f"❌ PROMPTS: Error - {results['prompts']['error']}")
            else:
                prompts = results["prompts"].get("prompts", [])
                output_lines.append(f"💬 PROMPTS ({len(prompts)} available):")
                if prompts:
                    for prompt in prompts:
                        name = prompt.get("name", "Unknown")
                        desc = prompt.get("description", "No description")
                        output_lines.append(f"  • {name}: {desc}")
                else:
                    output_lines.append("  (No prompts available)")
                output_lines.append("")

        # Format resources
        if "resources" in results:
            if "error" in results["resources"]:
                output_lines.append(f"❌ RESOURCES: Error - {results['resources']['error']}")
            else:
                resources = results["resources"].get("resources", [])
                output_lines.append(f"📁 RESOURCES ({len(resources)} available):")
                if resources:
                    for resource in resources:
                        uri = resource.get("uri", "Unknown")
                        name = resource.get("name", uri)
                        desc = resource.get("description", "No description")
                        output_lines.append(f"  • {name}: {desc}")
                        output_lines.append(f"    URI: {uri}")
                else:
                    output_lines.append("  (No resources available)")
                output_lines.append("")

        return "\n".join(output_lines)