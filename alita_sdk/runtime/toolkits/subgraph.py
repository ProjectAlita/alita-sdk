from typing import List, Any,  Optional
import logging
import yaml

from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph

from ..langchain.langraph_agent import create_graph, SUBGRAPH_REGISTRY
from ..tools.graph import GraphTool
from ..utils.utils import clean_string

logger = logging.getLogger(__name__)


def _resolve_bypass_chain(target: str, bypass_mapping: dict, all_printer_related: set, max_depth: int = 100) -> str:
    """
    Recursively follow bypass mapping chain to find the first non-printer target.

    Args:
        target: Starting target node ID
        bypass_mapping: Mapping of printer_id -> successor_id
        all_printer_related: Set of all printer and reset node IDs
        max_depth: Maximum chain depth to prevent infinite loops

    Returns:
        Final non-printer target node ID
    """
    visited = set()
    depth = 0

    while target in all_printer_related or target in bypass_mapping:
        if depth >= max_depth:
            logger.error(f"Maximum bypass chain depth ({max_depth}) exceeded for target '{target}'")
            break

        if target in visited:
            logger.error(f"Circular reference detected in bypass chain starting from '{target}'")
            break

        visited.add(target)

        if target in bypass_mapping:
            target = bypass_mapping[target]
            depth += 1
            logger.debug(f"Following bypass chain: depth={depth}, target={target}")
        else:
            # Target is in all_printer_related but not in bypass mapping
            logger.warning(f"Target '{target}' is a printer node without bypass mapping")
            break

    return target


def _filter_printer_nodes_from_yaml(yaml_schema: str) -> str:
    """
    Filter out PrinterNodes and their reset nodes from a YAML schema.

    This function removes:
    1. Nodes with type='printer'
    2. Reset nodes (pattern: {node_id}_reset)
    3. Rewires transitions to bypass removed printer nodes
    4. Removes printer nodes from interrupt configurations

    Args:
        yaml_schema: Original YAML schema string

    Returns:
        Filtered YAML schema string without PrinterNodes
    """
    try:
        schema_dict = yaml.safe_load(yaml_schema)

        if not schema_dict or 'nodes' not in schema_dict:
            return yaml_schema

        nodes = schema_dict.get('nodes', [])

        # Step 1: Identify printer nodes and build bypass mapping
        printer_nodes = set()
        printer_reset_nodes = set()
        printer_bypass_mapping = {}  # printer_node_id -> actual_successor_id

        # First pass: Identify all printer nodes and reset nodes
        for node in nodes:
            node_id = node.get('id')
            node_type = node.get('type')

            if not node_id:
                continue

            # Identify reset nodes by naming pattern
            if node_id.endswith('_reset'):
                printer_reset_nodes.add(node_id)
                continue

            # Identify main printer nodes
            if node_type == 'printer':
                printer_nodes.add(node_id)

        # Second pass: Build bypass mapping for printer nodes
        for node in nodes:
            node_id = node.get('id')
            node_type = node.get('type')

            if not node_id or node_type != 'printer':
                continue

            # Try standard pattern first: Printer -> Printer_reset -> NextNode
            reset_node_id = f"{node_id}_reset"
            reset_node = next((n for n in nodes if n.get('id') == reset_node_id), None)

            if reset_node:
                # Standard pattern with reset node
                actual_successor = reset_node.get('transition')
                if actual_successor:
                    printer_bypass_mapping[node_id] = actual_successor
                    logger.debug(f"Printer bypass mapping (standard): {node_id} -> {actual_successor}")
            else:
                # Direct transition pattern: Printer -> NextNode (no reset node)
                # Get the direct transition from the printer node
                direct_transition = node.get('transition')
                if direct_transition:
                    printer_bypass_mapping[node_id] = direct_transition
                    logger.debug(f"Printer bypass mapping (direct): {node_id} -> {direct_transition}")

        # Create the set of all printer-related nodes early so it can be used in rewiring
        all_printer_related = printer_nodes | printer_reset_nodes

        # Step 2: Filter out printer nodes and reset nodes
        filtered_nodes = []
        for node in nodes:
            node_id = node.get('id')
            node_type = node.get('type')

            # Skip printer nodes
            if node_type == 'printer':
                logger.debug(f"Filtering out printer node: {node_id}")
                continue

            # Skip reset nodes
            if node_id in printer_reset_nodes:
                logger.debug(f"Filtering out printer reset node: {node_id}")
                continue

            # Step 3: Rewire transitions in remaining nodes to bypass printer nodes
            # Use recursive resolution to handle chains of printers
            if 'transition' in node:
                transition = node['transition']
                if transition in printer_bypass_mapping or transition in all_printer_related:
                    new_transition = _resolve_bypass_chain(transition, printer_bypass_mapping, all_printer_related)
                    if new_transition != transition:
                        node['transition'] = new_transition
                        logger.debug(f"Rewired transition in node '{node_id}': {transition} -> {new_transition}")

            # Handle conditional outputs
            if 'condition' in node:
                condition = node['condition']
                if 'conditional_outputs' in condition:
                    new_outputs = []
                    for output in condition['conditional_outputs']:
                        if output in printer_bypass_mapping or output in all_printer_related:
                            resolved_output = _resolve_bypass_chain(output, printer_bypass_mapping, all_printer_related)
                            new_outputs.append(resolved_output)
                        else:
                            new_outputs.append(output)
                    condition['conditional_outputs'] = new_outputs

                if 'default_output' in condition:
                    default = condition['default_output']
                    if default in printer_bypass_mapping or default in all_printer_related:
                        condition['default_output'] = _resolve_bypass_chain(default, printer_bypass_mapping, all_printer_related)

            # Handle decision nodes
            if 'decision' in node:
                decision = node['decision']
                if 'nodes' in decision:
                    new_nodes = []
                    for decision_node in decision['nodes']:
                        if decision_node in printer_bypass_mapping or decision_node in all_printer_related:
                            resolved_node = _resolve_bypass_chain(decision_node, printer_bypass_mapping, all_printer_related)
                            new_nodes.append(resolved_node)
                        else:
                            new_nodes.append(decision_node)
                    decision['nodes'] = new_nodes

            # Handle routes (for router nodes)
            if 'routes' in node:
                routes = node['routes']
                if isinstance(routes, list):
                    new_routes = []
                    for route in routes:
                        if isinstance(route, dict) and 'target' in route:
                            target = route['target']
                            if target in printer_bypass_mapping or target in all_printer_related:
                                route['target'] = _resolve_bypass_chain(target, printer_bypass_mapping, all_printer_related)
                        new_routes.append(route)
                    node['routes'] = new_routes

            filtered_nodes.append(node)

        # Update the nodes in schema
        schema_dict['nodes'] = filtered_nodes

        # Step 4: Filter printer nodes from interrupt configurations
        if 'interrupt_before' in schema_dict:
            schema_dict['interrupt_before'] = [
                i for i in schema_dict['interrupt_before']
                if i not in all_printer_related
            ]

        if 'interrupt_after' in schema_dict:
            schema_dict['interrupt_after'] = [
                i for i in schema_dict['interrupt_after']
                if i not in all_printer_related
            ]

        # Update entry point if it points to a printer node
        # Use helper function to recursively resolve the chain
        if 'entry_point' in schema_dict:
            entry_point = schema_dict['entry_point']
            original_entry = entry_point

            # Check if entry point is a printer node (directly or in bypass mapping)
            if entry_point in all_printer_related or entry_point in printer_bypass_mapping:
                # Use helper function to resolve the chain
                resolved_entry = _resolve_bypass_chain(entry_point, printer_bypass_mapping, all_printer_related)

                if resolved_entry != original_entry:
                    schema_dict['entry_point'] = resolved_entry
                    logger.info(f"Updated entry point: {original_entry} -> {resolved_entry}")


        # Convert back to YAML
        filtered_yaml = yaml.dump(schema_dict, default_flow_style=False, sort_keys=False)
        return filtered_yaml

    except Exception as e:
        logger.error(f"Error filtering PrinterNodes from YAML: {e}", exc_info=True)
        # Return original YAML if filtering fails
        return yaml_schema


# TODO: deprecate next release (1/15/2026)
class SubgraphToolkit:

    @staticmethod
    def get_toolkit(
        client: Any,
        application_id: int,
        application_version_id: int,
        llm,
        app_api_key: str,
        selected_tools: list[str] = [],
        is_subgraph: bool = True,
        mcp_tokens: Optional[dict] = None,
        ignored_mcp_servers: Optional[list] = None
    ) -> List[BaseTool]:
        from .tools import get_tools
        # from langgraph.checkpoint.memory import MemorySaver

        app_details = client.get_app_details(application_id)
        version_details = client.get_app_version_details(application_id, application_version_id)
        tools = get_tools(version_details['tools'], alita_client=client, llm=llm,
                          mcp_tokens=mcp_tokens, ignored_mcp_servers=ignored_mcp_servers)

        # Get the subgraph name
        subgraph_name = app_details.get("name")
        
        # Get the original YAML
        yaml_schema = version_details['instructions']

        # Filter PrinterNodes from YAML if this is a subgraph
        if is_subgraph:
            yaml_schema = _filter_printer_nodes_from_yaml(yaml_schema)
            logger.info(f"Filtered PrinterNodes from subgraph pipeline '{subgraph_name}'")

        # Populate the registry for flattening approach
        SUBGRAPH_REGISTRY[subgraph_name] = {
            'yaml': yaml_schema,  # Use filtered YAML
            'tools': tools,
            'flattened': False
        }
        
        # For backward compatibility, still create a compiled graph stub
        # This is mainly used for identification in the parent graph's tools list
        # For now the graph toolkit will have its own ephemeral in memory checkpoint memory.
        graph = create_graph(
            client=llm,
            tools=tools,
            yaml_schema=yaml_schema,  # Use filtered YAML
            debug=False,
            store=None,
            memory=MemorySaver(),
            for_subgraph=is_subgraph,  # Pass flag to create_graph
        )

        cleaned_subgraph_name = clean_string(subgraph_name)
        # Tag the graph stub for parent lookup
        graph.name = cleaned_subgraph_name
        
        # Return the compiled graph stub for backward compatibility
        return [GraphTool(description=app_details['description'], name=subgraph_name, graph=graph)]