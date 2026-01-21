"""
Lazy Tools System for Dynamic Tool Loading

This module implements a lazy loading system for tools to reduce token usage.
Instead of binding all tools upfront (which can consume 100k+ tokens with
30-100 toolkits), only meta-tools are initially available. The model can then
discover and invoke any tool through the meta-tools.

Key components:
- ToolRegistry: Organizes tools by toolkit with type, description, and tool metadata
- Meta-tools: list_toolkits, get_tool_schema, invoke_tool
- Tool index generation for system prompts

Meta-tools:
- list_toolkits(): Lists all toolkits with type, description, tool count and tool names
- get_tool_schema(toolkit, tool): Gets detailed schema for a SINGLE tool (efficient lookup)
- invoke_tool(toolkit, tool, args): Invokes any tool with the given arguments

Usage:
    from alita_sdk.runtime.tools.lazy_tools import ToolRegistry, create_meta_tools

    # Create registry from all tools
    registry = ToolRegistry.from_tools(all_tools)

    # Create meta-tools that can access the registry
    meta_tools = create_meta_tools(registry)

    # Generate compressed index for system prompt
    index = registry.generate_index()
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union
from collections import defaultdict

from langchain_core.tools import BaseTool, ToolException
from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import BaseModel, Field

from ..utils.constants import TOOLKIT_NAME_META, TOOL_NAME_META, TOOLKIT_TYPE_META

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Registry that organizes tools by toolkit for efficient lookup and lazy loading.

    The registry maintains a hierarchical structure:
        toolkit_name -> tool_name -> Tool instance

    It also provides:
    - Compressed index generation for system prompts
    - Tool schema extraction for the model to understand arguments
    - Statistics about available toolkits and tools
    """

    def __init__(self):
        self._toolkits: Dict[str, Dict[str, BaseTool]] = defaultdict(dict)
        self._tool_to_toolkit: Dict[str, str] = {}  # Reverse lookup: tool_name -> toolkit_name
        self._toolkit_descriptions: Dict[str, str] = {}
        self._toolkit_types: Dict[str, str] = {}  # toolkit_name -> toolkit_type (e.g., 'jira', 'github')

    @classmethod
    def from_tools(cls, tools: List[BaseTool]) -> "ToolRegistry":
        """
        Create a ToolRegistry from a list of tools.

        Tools are organized by toolkit name extracted from:
        1. tool.metadata['toolkit_name'] (preferred)
        2. tool.metadata['toolkit_type']
        3. Parsed from tool.name (e.g., 'github_create_issue' -> 'github')
        4. Falls back to 'default' toolkit

        Args:
            tools: List of BaseTool instances

        Returns:
            ToolRegistry instance with tools organized by toolkit
        """
        registry = cls()

        # Log all incoming tools for debugging
        logger.info(f"[TOOL_REGISTRY] Creating registry from {len(tools)} tools")
        all_tool_names = [t.name if hasattr(t, 'name') else str(type(t)) for t in tools]
        logger.info(f"[TOOL_REGISTRY] All incoming tools: {all_tool_names}")

        # Check for indexer tools in incoming tools
        indexer_tools_incoming = [n for n in all_tool_names if 'index' in n.lower()]
        if indexer_tools_incoming:
            logger.warning(f"[TOOL_REGISTRY] Indexer tools in incoming list: {indexer_tools_incoming}")

        for tool in tools:
            if not isinstance(tool, BaseTool):
                logger.debug(f"Skipping non-BaseTool: {type(tool)}")
                continue

            toolkit_name = registry._extract_toolkit_name(tool)
            tool_name = tool.name

            # Log each tool being added
            logger.debug(f"[TOOL_REGISTRY] Adding tool '{tool_name}' to toolkit '{toolkit_name}'")

            # Store tool in registry
            registry._toolkits[toolkit_name][tool_name] = tool
            registry._tool_to_toolkit[tool_name] = toolkit_name

            # Try to extract toolkit description from first tool
            if toolkit_name not in registry._toolkit_descriptions:
                desc = registry._extract_toolkit_description(tool, toolkit_name)
                if desc:
                    registry._toolkit_descriptions[toolkit_name] = desc

            # Extract toolkit type from first tool of this toolkit
            if toolkit_name not in registry._toolkit_types:
                toolkit_type = registry._extract_toolkit_type(tool, toolkit_name)
                if toolkit_type:
                    registry._toolkit_types[toolkit_name] = toolkit_type

        # Log final registry contents
        for tk_name, tk_tools in registry._toolkits.items():
            tool_names_in_tk = list(tk_tools.keys())
            logger.info(f"[TOOL_REGISTRY] Toolkit '{tk_name}' has {len(tool_names_in_tk)} tools: {tool_names_in_tk}")
            # Check for indexer tools in this toolkit
            indexer_in_tk = [n for n in tool_names_in_tk if 'index' in n.lower()]
            if indexer_in_tk:
                logger.warning(f"[TOOL_REGISTRY] Indexer tools in toolkit '{tk_name}': {indexer_in_tk}")

        logger.info(
            f"ToolRegistry initialized with {len(registry._toolkits)} toolkits, "
            f"{sum(len(t) for t in registry._toolkits.values())} tools"
        )

        return registry

    def _extract_toolkit_name(self, tool: BaseTool) -> str:
        """Extract toolkit name from a tool."""
        # Try metadata first
        if hasattr(tool, 'metadata') and tool.metadata:
            if TOOLKIT_NAME_META in tool.metadata:
                return tool.metadata[TOOLKIT_NAME_META]
            if 'toolkit_type' in tool.metadata:
                return tool.metadata['toolkit_type']

        # Try parsing from tool name (e.g., 'github_create_issue' -> 'github')
        tool_name = tool.name
        if '_' in tool_name:
            # Common pattern: toolkit_action or toolkit_noun_action
            parts = tool_name.split('_')
            # Use first part as toolkit unless it's a common verb
            common_verbs = {'get', 'set', 'create', 'update', 'delete', 'list', 'search', 'add', 'remove'}
            if parts[0].lower() not in common_verbs:
                return parts[0]

        # Default fallback
        return 'default'

    def _extract_toolkit_description(self, tool: BaseTool, toolkit_name: str) -> str:
        """Try to extract or generate a toolkit description."""
        # Check if tool has toolkit description in metadata
        if hasattr(tool, 'metadata') and tool.metadata:
            if 'toolkit_description' in tool.metadata:
                return tool.metadata['toolkit_description']

        # Generate from toolkit name
        toolkit_descriptions = {
            'github': 'GitHub repository management - issues, PRs, files, branches',
            'jira': 'Jira project tracking - issues, sprints, boards, transitions',
            'confluence': 'Confluence documentation - pages, spaces, search',
            'slack': 'Slack messaging - channels, messages, threads',
            'artifact': 'File storage and retrieval - upload, download, search',
            'memory': 'Conversation memory and context management',
            'planning': 'Task planning and tracking',
            'default': 'General purpose tools',
        }
        return toolkit_descriptions.get(toolkit_name, f'{toolkit_name} toolkit')

    def _extract_toolkit_type(self, tool: BaseTool, toolkit_name: str) -> str:
        """
        Extract toolkit type from a tool.

        Toolkit type is the integration type (e.g., 'jira', 'github', 'confluence')
        which helps categorize the toolkit's purpose.
        """
        # Check tool metadata for explicit toolkit_type
        if hasattr(tool, 'metadata') and tool.metadata:
            if TOOLKIT_TYPE_META in tool.metadata:
                return tool.metadata[TOOLKIT_TYPE_META]
            # Also check for 'type' which some tools use
            if 'type' in tool.metadata:
                return tool.metadata['type']

        # Fallback: use toolkit_name as type
        return toolkit_name

    def get_toolkit_names(self) -> List[str]:
        """Get list of all toolkit names."""
        return list(self._toolkits.keys())

    def get_toolkit_tools(self, toolkit_name: str) -> Dict[str, BaseTool]:
        """Get all tools in a toolkit."""
        return dict(self._toolkits.get(toolkit_name, {}))

    def get_tool(self, toolkit_name: str, tool_name: str) -> Optional[BaseTool]:
        """Get a specific tool by toolkit and tool name."""
        return self._toolkits.get(toolkit_name, {}).get(tool_name)

    def get_tool_by_name(self, tool_name: str) -> Optional[BaseTool]:
        """Get a tool by name only (searches all toolkits)."""
        toolkit_name = self._tool_to_toolkit.get(tool_name)
        if toolkit_name:
            return self._toolkits[toolkit_name].get(tool_name)
        return None

    def get_toolkit_for_tool(self, tool_name: str) -> Optional[str]:
        """Get the toolkit name for a given tool."""
        return self._tool_to_toolkit.get(tool_name)

    def get_toolkit_type(self, toolkit_name: str) -> Optional[str]:
        """Get the type for a toolkit."""
        return self._toolkit_types.get(toolkit_name)

    # Maximum number of tools to bind directly (above this, use meta-tools)
    MAX_DIRECT_BIND_TOOLS = 25

    def select_toolkits_for_query(self, query: str) -> List[str]:
        """
        Select relevant toolkits based on user query using keyword matching.

        This is a fast, pre-LLM selection that narrows down which toolkits
        are likely needed for the user's request. The selected toolkits'
        tools can then be bound to the LLM instead of meta-tools.

        Returns EMPTY list when:
        - No keywords match (use meta-tools for general queries)
        - Too many tools would be selected (use meta-tools for efficiency)

        Args:
            query: User's input query/message

        Returns:
            List of toolkit names that are relevant to the query,
            or EMPTY list to indicate meta-tools should be used
        """
        query_lower = query.lower()
        selected = set()

        # Keyword patterns for each toolkit type
        type_keywords = {
            'github': ['github', 'repository', 'repo', 'commit', 'branch', 'pull request', 'pr', 'issue', 'git', 'code', 'merge'],
            'jira': ['jira', 'ticket', 'sprint', 'backlog', 'story', 'epic', 'bug', 'board', 'kanban'],
            'confluence': ['confluence', 'wiki', 'documentation', 'docs', 'page', 'space', 'knowledge base'],
            'slack': ['slack', 'message', 'channel', 'thread', 'dm'],
            'artifact': ['artifact', 'upload', 'download', 'storage', 'attachment'],
            'azure_devops': ['azure devops', 'ado', 'devops', 'pipeline', 'work item'],
            'testrail': ['testrail', 'test case', 'test run'],
            'memory': ['remember', 'context', 'history', 'previous conversation'],
            'planning': ['plan', 'planning', 'todo', 'schedule'],
        }

        # Check each toolkit type against keywords
        for toolkit_type, keywords in type_keywords.items():
            for keyword in keywords:
                if keyword in query_lower:
                    # Find all toolkits of this type
                    for toolkit_name, tk_type in self._toolkit_types.items():
                        if tk_type == toolkit_type:
                            selected.add(toolkit_name)
                    break

        # Also match against toolkit names directly (exact match)
        for toolkit_name in self._toolkits.keys():
            if toolkit_name.lower() in query_lower:
                selected.add(toolkit_name)

        # If no matches, return EMPTY - use meta-tools for general queries
        if not selected:
            logger.info(f"[ToolRegistry] No keyword matches for query, will use meta-tools")
            return []

        # Check tool count - if too many, return empty to use meta-tools
        tool_count = sum(len(self._toolkits[tk]) for tk in selected if tk in self._toolkits)
        if tool_count > self.MAX_DIRECT_BIND_TOOLS:
            logger.info(f"[ToolRegistry] Selection has {tool_count} tools (>{self.MAX_DIRECT_BIND_TOOLS}), will use meta-tools")
            return []

        logger.info(f"[ToolRegistry] Selected {len(selected)} toolkits ({tool_count} tools) for query: {list(selected)}")
        return list(selected)

    def get_tools_for_toolkits(self, toolkit_names: List[str]) -> List[BaseTool]:
        """
        Get all tools from the specified toolkits.

        Args:
            toolkit_names: List of toolkit names to get tools from

        Returns:
            List of BaseTool instances from those toolkits
        """
        tools = []
        for toolkit_name in toolkit_names:
            if toolkit_name in self._toolkits:
                tools.extend(self._toolkits[toolkit_name].values())
        return tools

    def get_toolkit_description(self, toolkit_name: str) -> Optional[str]:
        """Get the description for a toolkit."""
        return self._toolkit_descriptions.get(toolkit_name)

    def get_tool_schema(self, toolkit_name: str, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the schema for a specific tool.

        Returns:
            Dict with 'name', 'description', 'parameters' (JSON Schema format)
        """
        tool = self.get_tool(toolkit_name, tool_name)
        if not tool:
            return None

        schema = {
            'name': tool.name,
            'description': tool.description or '',
        }

        # Extract parameters schema
        if hasattr(tool, 'args_schema') and tool.args_schema:
            try:
                schema['parameters'] = tool.args_schema.model_json_schema()
            except Exception as e:
                logger.debug(f"Could not extract schema for {tool_name}: {e}")
                schema['parameters'] = {}
        else:
            schema['parameters'] = {}

        return schema

    def generate_index(self) -> str:
        """
        Generate a readable index of all toolkits grouped by type.

        Format:
            ## Type (N tools):
              tools: tool1, tool2, tool3, ...

              Instances:
              - toolkit_name: description

        Returns:
            Formatted string suitable for inclusion in system prompt
        """
        # Log what we're generating index for
        logger.info(f"[TOOL_REGISTRY] Generating index for {len(self._toolkits)} toolkits")
        for tk_name, tk_tools in self._toolkits.items():
            tool_names = list(tk_tools.keys())
            logger.info(f"[TOOL_REGISTRY] Index will include toolkit '{tk_name}' with tools: {tool_names}")
            # Check for indexer tools
            indexer_tools = [n for n in tool_names if 'index' in n.lower()]
            if indexer_tools:
                logger.warning(f"[TOOL_REGISTRY] INDEX GENERATION: Indexer tools in '{tk_name}': {indexer_tools}")

        # Group toolkits by type
        toolkits_by_type: Dict[str, List[str]] = defaultdict(list)
        for toolkit_name in self._toolkits.keys():
            toolkit_type = self._toolkit_types.get(toolkit_name, toolkit_name)
            toolkits_by_type[toolkit_type].append(toolkit_name)

        toolkit_count = len(self._toolkits)
        type_count = len(toolkits_by_type)
        tool_count = sum(len(tools) for tools in self._toolkits.values())

        # Build example with first available toolkit
        first_type = next(iter(toolkits_by_type.keys()), 'github')
        first_toolkit = toolkits_by_type[first_type][0] if toolkits_by_type[first_type] else 'docs'
        first_tool = next(iter(self._toolkits[first_toolkit].keys()), 'read_file') if first_toolkit in self._toolkits else 'read_file'

        lines = [
            "# Available Tools",
            "",
            "You have 2 meta-tools to access all functionality:",
            "- get_tool_schema(toolkit, tool) - Get parameter schema for a tool BEFORE calling it",
            f"- invoke_tool(toolkit, tool, arguments) - Execute a tool",
            "",
            "IMPORTANT: Each toolkit name (e.g., 'sdk', 'docs', 'core') targets a DIFFERENT repository.",
            "Use the EXACT toolkit name to work with that specific repo. The toolkit name IS the repo selector.",
            "",
            "SCHEMA EFFICIENCY: Toolkits of the same type share identical schemas.",
            "Get schema once per tool (e.g., get_tool_schema('sdk', 'search_code')), then reuse that knowledge",
            "for other toolkits of same type - just change the toolkit name in invoke_tool.",
            "",
            f"Example: invoke_tool(toolkit=\"{first_toolkit}\", tool=\"{first_tool}\", arguments={{...}})",
            ""
        ]

        for toolkit_type in sorted(toolkits_by_type.keys()):
            toolkit_names = sorted(toolkits_by_type[toolkit_type])

            # Get tools from first toolkit of this type (all should have same tools)
            first_toolkit_of_type = toolkit_names[0]
            tools = self._toolkits[first_toolkit_of_type]
            tool_names = sorted(tools.keys())
            tool_count_for_type = len(tool_names)

            # Type header - clearly marked as TYPE not name
            lines.append(f"## Type: {toolkit_type}")

            # ALWAYS show actual toolkit names prominently
            if len(toolkit_names) == 1:
                lines.append(f"  Toolkit name: \"{toolkit_names[0]}\"")
                desc = self._toolkit_descriptions.get(toolkit_names[0], '')
                if desc:
                    lines.append(f"  Description: {desc}")
            else:
                lines.append(f"  Toolkit names (use one of these exactly):")
                for toolkit_name in toolkit_names:
                    desc = self._toolkit_descriptions.get(toolkit_name, '')
                    if desc:
                        lines.append(f"    - \"{toolkit_name}\": {desc}")
                    else:
                        lines.append(f"    - \"{toolkit_name}\"")

            # Tools list
            tools_str = ', '.join(tool_names)
            lines.append(f"  Tools ({tool_count_for_type}): {tools_str}")

            lines.append("")  # Blank line between types

        lines.append(f"Total: {toolkit_count} toolkits, {tool_count} tools")

        return '\n'.join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the registry."""
        return {
            'toolkit_count': len(self._toolkits),
            'tool_count': sum(len(tools) for tools in self._toolkits.values()),
            'toolkits': {
                name: len(tools) for name, tools in self._toolkits.items()
            }
        }


# ============================================================================
# Meta-Tools for Lazy Loading
# ============================================================================

class ListToolkitsInput(BaseModel):
    """Input schema for list_toolkits tool."""
    pass  # No input required


class GetToolkitToolsInput(BaseModel):
    """Input schema for get_toolkit_tools tool."""
    toolkit: str = Field(description="Name of the toolkit to get tools from")


class GetToolSchemaInput(BaseModel):
    """Input schema for get_tool_schema tool."""
    toolkit: str = Field(description="Name of the toolkit containing the tool")
    tool: str = Field(description="Name of the specific tool to get schema for")


class InvokeToolInput(BaseModel):
    """Input schema for invoke_tool tool."""
    toolkit: str = Field(description="Name of the toolkit containing the tool")
    tool: str = Field(description="Name of the tool to invoke")
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to pass to the tool as a JSON object"
    )


class ListToolkitsTool(BaseTool):
    """
    Meta-tool that lists all available toolkits with descriptions.

    This tool provides an overview of what toolkits are available,
    helping the model discover capabilities without loading all tool definitions.
    """

    name: str = "list_toolkits"
    description: str = (
        "List all available toolkits with their descriptions and tool counts. "
        "Use this to discover what capabilities are available before invoking specific tools. "
        "IMPORTANT: Use the 'name' field (not 'toolkit_type') when calling get_tool_schema or invoke_tool."
    )
    args_schema: type[BaseModel] = ListToolkitsInput
    registry: ToolRegistry = Field(exclude=True)

    def _run(
        self,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """List all available toolkits grouped by type."""
        # Group toolkits by type
        toolkits_by_type: Dict[str, List[Dict]] = defaultdict(list)

        for toolkit_name in sorted(self.registry.get_toolkit_names()):
            tools = self.registry.get_toolkit_tools(toolkit_name)
            desc = self.registry.get_toolkit_description(toolkit_name) or ''
            toolkit_type = self.registry.get_toolkit_type(toolkit_name) or toolkit_name

            toolkits_by_type[toolkit_type].append({
                'name': toolkit_name,
                'description': desc,
            })

        # Build result organized by type
        result = []
        for toolkit_type in sorted(toolkits_by_type.keys()):
            instances = toolkits_by_type[toolkit_type]
            # Get tools from first instance (all same type have same tools)
            first_instance = instances[0]['name']
            tools = self.registry.get_toolkit_tools(first_instance)

            # Build toolkit entries with 'name' as primary identifier
            toolkit_entries = []
            for inst in instances:
                toolkit_entries.append({
                    'name': inst['name'],  # USE THIS for invoke_tool/get_tool_schema
                    'description': inst['description']
                })

            result.append({
                'toolkit_type': toolkit_type,  # Category/type (do NOT use this for tool calls)
                'toolkits': toolkit_entries,   # USE 'name' from these entries
                'tools': sorted(tools.keys()),
                'tool_count': len(tools),
            })

        return json.dumps(result, indent=2)


class GetToolkitToolsTool(BaseTool):
    """
    Meta-tool that returns detailed schemas for all tools in a toolkit.

    This allows the model to understand the exact parameters required
    for each tool before invoking them.
    """

    name: str = "get_toolkit_tools"
    description: str = (
        "Get detailed information about all tools in a specific toolkit, "
        "including their descriptions and parameter schemas. "
        "Use this to understand how to call tools before using invoke_tool."
    )
    args_schema: type[BaseModel] = GetToolkitToolsInput
    registry: ToolRegistry = Field(exclude=True)

    def _run(
        self,
        toolkit: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Get tools and schemas for a toolkit."""
        tools = self.registry.get_toolkit_tools(toolkit)

        if not tools:
            available = self.registry.get_toolkit_names()
            return f"Toolkit '{toolkit}' not found. Available toolkits: {', '.join(available)}"

        result = []
        for tool_name in sorted(tools.keys()):
            schema = self.registry.get_tool_schema(toolkit, tool_name)
            if schema:
                result.append(schema)

        return json.dumps(result, indent=2)


class GetToolSchemaTool(BaseTool):
    """
    Meta-tool that returns the schema for a single specific tool.

    This is more efficient than get_toolkit_tools when you know which
    tool you need - it returns just one tool's schema instead of all
    tools in the toolkit.
    """

    name: str = "get_tool_schema"
    description: str = (
        "Get detailed schema for a single specific tool, including its description "
        "and parameter definitions. Use this when you know which tool you need, "
        "instead of get_toolkit_tools which returns all tools in a toolkit. "
        "IMPORTANT: Tool schemas are universal - they are the same for ALL targets/repos/instances. "
        "Once you retrieve a schema (e.g., for 'create_issue'), you do NOT need to call this again "
        "for different repositories. The schema shows what parameters are available; repo/target is just one parameter."
    )
    args_schema: type[BaseModel] = GetToolSchemaInput
    registry: ToolRegistry = Field(exclude=True)

    def _run(
        self,
        toolkit: str,
        tool: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Get schema for a specific tool."""
        # First try exact toolkit/tool match
        schema = self.registry.get_tool_schema(toolkit, tool)

        if not schema:
            # Try to find tool by name only (in case toolkit is wrong/unknown)
            actual_tool = self.registry.get_tool_by_name(tool)
            if actual_tool:
                actual_toolkit = self.registry.get_toolkit_for_tool(tool)
                schema = self.registry.get_tool_schema(actual_toolkit, tool)
                if schema:
                    schema['note'] = f"Tool found in toolkit '{actual_toolkit}' (not '{toolkit}')"
            else:
                # Tool not found - provide helpful error
                available_toolkits = self.registry.get_toolkit_names()
                if toolkit in available_toolkits:
                    available_tools = list(self.registry.get_toolkit_tools(toolkit).keys())
                    return json.dumps({
                        'error': f"Tool '{tool}' not found in toolkit '{toolkit}'",
                        'available_tools': available_tools[:30],
                        'hint': 'Use list_toolkits() to see all toolkits or get_toolkit_tools(toolkit) for all tools'
                    }, indent=2)
                else:
                    return json.dumps({
                        'error': f"Toolkit '{toolkit}' not found",
                        'available_toolkits': available_toolkits,
                        'hint': 'Use list_toolkits() to see all available toolkits'
                    }, indent=2)

        return json.dumps(schema, indent=2)


class InvokeToolTool(BaseTool):
    """
    Meta-tool that invokes any tool from any toolkit.

    This is the key tool that enables lazy loading - instead of binding
    all tools directly to the LLM, we bind only this meta-tool which can
    then invoke any tool from the registry.
    """

    name: str = "invoke_tool"
    description: str = (
        "Invoke a specific tool from a toolkit with the required arguments. "
        "IMPORTANT: You MUST call get_tool_schema(toolkit, tool) first to learn "
        "the required parameters before calling invoke_tool. "
        "Arguments must be provided as a JSON object matching the tool's schema."
    )
    args_schema: type[BaseModel] = InvokeToolInput
    registry: ToolRegistry = Field(exclude=True)

    def _run(
        self,
        toolkit: str,
        tool: str,
        arguments: Dict[str, Any] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Invoke a tool from the registry."""
        arguments = arguments or {}

        # Get the tool
        actual_tool = self.registry.get_tool(toolkit, tool)

        if not actual_tool:
            # Try to find by tool name only
            actual_tool = self.registry.get_tool_by_name(tool)
            if actual_tool:
                # Found it, update toolkit for the message
                toolkit = self.registry.get_toolkit_for_tool(tool)
            else:
                # Not found - provide helpful error
                available_toolkits = self.registry.get_toolkit_names()
                if toolkit in available_toolkits:
                    available_tools = list(self.registry.get_toolkit_tools(toolkit).keys())
                    return (
                        f"Tool '{tool}' not found in toolkit '{toolkit}'. "
                        f"Available tools in {toolkit}: {', '.join(available_tools[:20])}"
                        f"{'...' if len(available_tools) > 20 else ''}"
                    )
                else:
                    return (
                        f"Toolkit '{toolkit}' not found. "
                        f"Available toolkits: {', '.join(available_toolkits)}"
                    )

        # Invoke the tool
        try:
            logger.info(f"[LazyTools] Invoking {toolkit}.{tool} with args: {arguments}")
            result = actual_tool.invoke(arguments)
            return str(result) if result is not None else "Tool executed successfully (no output)"
        except ToolException as e:
            # Even for ToolException, show the expected schema
            return self._format_invocation_error(toolkit, tool, arguments, str(e))
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error invoking {toolkit}.{tool}: {e}", exc_info=True)
            return self._format_invocation_error(toolkit, tool, arguments, error_msg)

    def _format_invocation_error(self, toolkit: str, tool: str, provided_args: Dict[str, Any], error_msg: str) -> str:
        """Format a helpful error message with expected schema details."""
        # Try to get schema - first with provided toolkit, then by tool name only
        schema = self.registry.get_tool_schema(toolkit, tool)
        actual_toolkit = toolkit

        if not schema:
            # Toolkit name might be wrong - try to find by tool name
            actual_toolkit_name = self.registry.get_toolkit_for_tool(tool)
            if actual_toolkit_name:
                schema = self.registry.get_tool_schema(actual_toolkit_name, tool)
                actual_toolkit = actual_toolkit_name
                logger.debug(f"Schema lookup fallback: {toolkit}.{tool} -> {actual_toolkit}.{tool}")

        lines = [f"ERROR: Invalid arguments for {actual_toolkit}.{tool}"]
        if actual_toolkit != toolkit:
            lines.append(f"(Note: toolkit '{toolkit}' resolved to '{actual_toolkit}')")
        lines.append("")
        lines.append(f"You provided: {json.dumps(provided_args)}")
        lines.append("")

        # Always try to show expected parameters
        if schema:
            params = schema.get('parameters', {})
            properties = params.get('properties', {})
            required = params.get('required', [])

            # If no properties from parameters, try getting from schema directly
            if not properties and 'properties' in schema:
                properties = schema['properties']
            if not required and 'required' in schema:
                required = schema['required']

            if properties:
                # Show required parameters
                if required:
                    lines.append("REQUIRED parameters:")
                    for req_param in required:
                        prop = properties.get(req_param, {})
                        param_type = prop.get('type', 'any')
                        desc = prop.get('description', '')
                        if desc:
                            lines.append(f"  - {req_param} ({param_type}): {desc}")
                        else:
                            lines.append(f"  - {req_param} ({param_type})")
                    lines.append("")

                # Show optional parameters
                optional = [p for p in properties.keys() if p not in required]
                if optional:
                    lines.append("OPTIONAL parameters:")
                    for opt_param in optional[:10]:  # Limit to 10
                        prop = properties.get(opt_param, {})
                        param_type = prop.get('type', 'any')
                        desc = prop.get('description', '')
                        if desc:
                            lines.append(f"  - {opt_param} ({param_type}): {desc}")
                        else:
                            lines.append(f"  - {opt_param} ({param_type})")
                    if len(optional) > 10:
                        lines.append(f"  ... and {len(optional) - 10} more")
                    lines.append("")

                # Generate example with required params
                example_args = {}
                for req_param in required:
                    prop = properties.get(req_param, {})
                    param_type = prop.get('type', 'string')
                    if param_type == 'string':
                        example_args[req_param] = f"<{req_param}>"
                    elif param_type == 'integer':
                        example_args[req_param] = 123
                    elif param_type == 'boolean':
                        example_args[req_param] = True
                    elif param_type == 'array':
                        example_args[req_param] = []
                    elif param_type == 'object':
                        example_args[req_param] = {}
                    else:
                        example_args[req_param] = f"<{req_param}>"

                lines.append("CORRECT usage:")
                lines.append(f'invoke_tool(toolkit="{toolkit}", tool="{tool}", arguments={json.dumps(example_args)})')
            else:
                lines.append(f"Original error: {error_msg}")
        else:
            lines.append(f"Original error: {error_msg}")
            lines.append(f"(Could not retrieve schema for {toolkit}.{tool})")

        return "\n".join(lines)

    async def _arun(
        self,
        toolkit: str,
        tool: str,
        arguments: Dict[str, Any] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Async version of invoke_tool."""
        arguments = arguments or {}

        actual_tool = self.registry.get_tool(toolkit, tool)

        if not actual_tool:
            actual_tool = self.registry.get_tool_by_name(tool)
            if not actual_tool:
                available_toolkits = self.registry.get_toolkit_names()
                if toolkit in available_toolkits:
                    available_tools = list(self.registry.get_toolkit_tools(toolkit).keys())
                    return (
                        f"Tool '{tool}' not found in toolkit '{toolkit}'. "
                        f"Available tools: {', '.join(available_tools[:20])}"
                    )
                else:
                    return f"Toolkit '{toolkit}' not found. Available: {', '.join(available_toolkits)}"

        try:
            logger.info(f"[LazyTools] Async invoking {toolkit}.{tool} with args: {arguments}")
            if hasattr(actual_tool, 'ainvoke'):
                result = await actual_tool.ainvoke(arguments)
            else:
                result = actual_tool.invoke(arguments)
            return str(result) if result is not None else "Tool executed successfully (no output)"
        except ToolException as e:
            return self._format_invocation_error(toolkit, tool, arguments, str(e))
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error invoking {toolkit}.{tool}: {e}", exc_info=True)
            return self._format_invocation_error(toolkit, tool, arguments, error_msg)


def create_meta_tools(registry: ToolRegistry) -> List[BaseTool]:
    """
    Create the set of meta-tools for lazy tool loading.

    Args:
        registry: ToolRegistry containing all available tools

    Returns:
        List of meta-tools [get_tool_schema, invoke_tool]
        Note: list_toolkits removed - toolkit info is in system prompt index
    """
    return [
        GetToolSchemaTool(registry=registry),
        InvokeToolTool(registry=registry),
    ]


# ============================================================================
# Utility Functions
# ============================================================================

def estimate_token_savings(registry: ToolRegistry, tokens_per_tool: int = 300) -> Dict[str, Any]:
    """
    Estimate token savings from using lazy tools.

    Args:
        registry: ToolRegistry with all tools
        tokens_per_tool: Estimated tokens per tool definition (conservative default)

    Returns:
        Dict with token estimates
    """
    total_tools = len(registry._tool_to_toolkit)
    meta_tools_count = 3  # list_toolkits, get_toolkit_tools, invoke_tool
    index_tokens = len(registry.generate_index()) // 4  # Rough estimate

    traditional_tokens = total_tools * tokens_per_tool
    lazy_tokens = (meta_tools_count * tokens_per_tool) + index_tokens

    return {
        'total_tools': total_tools,
        'traditional_approach_tokens': traditional_tokens,
        'lazy_approach_tokens': lazy_tokens,
        'estimated_savings': traditional_tokens - lazy_tokens,
        'savings_percentage': round((1 - lazy_tokens / traditional_tokens) * 100, 1) if traditional_tokens > 0 else 0
    }
