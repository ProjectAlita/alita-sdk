from typing import List, Any

from langgraph.graph.state import CompiledStateGraph

from ..langchain.langraph_agent import create_graph, SUBGRAPH_REGISTRY
from ..utils.utils import clean_string


class SubgraphToolkit:

    @staticmethod
    def get_toolkit(
        client: Any,
        application_id: int,
        application_version_id: int,
        llm,
        app_api_key: str,
        selected_tools: list[str] = []
    ) -> List[CompiledStateGraph]:
        from .tools import get_tools
        # from langgraph.checkpoint.memory import MemorySaver

        app_details = client.get_app_details(application_id)
        version_details = client.get_app_version_details(application_id, application_version_id)
        tools = get_tools(version_details['tools'], alita_client=client, llm=llm)

        # Get the subgraph name
        subgraph_name = app_details.get("name")
        
        # Populate the registry for flattening approach
        SUBGRAPH_REGISTRY[subgraph_name] = {
            'yaml': version_details['instructions'],
            'tools': tools,
            'flattened': False
        }
        
        # For backward compatibility, still create a compiled graph stub
        # This is mainly used for identification in the parent graph's tools list
        graph = create_graph(
            client=llm,
            tools=tools,
            yaml_schema=version_details['instructions'],
            debug=False,
            store=None,
            memory=None,
            for_subgraph=True,  # compile as raw subgraph
        )
        
        # Tag the graph stub for parent lookup
        graph.name = clean_string(subgraph_name)
        
        # Return the compiled graph stub for backward compatibility
        return [graph]