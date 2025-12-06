"""
Inventory Retrieval Toolkit.

A pure query toolkit for retrieving context from a pre-built knowledge graph.
This toolkit can be added to any agent to provide knowledge graph context.

This is NOT for ingestion - use IngestionPipeline for that.

Features:
- Search entities by name, type, or properties
- Get entity details with relations
- Retrieve source content via citations
- Impact analysis (upstream/downstream dependencies)
- Citation summaries

Usage:
    # Add to any agent as a toolkit
    retrieval = InventoryRetrievalToolkit(
        graph_path="/path/to/graph.json",
        base_directory="/path/to/source"  # For local content retrieval
    )
    
    tools = retrieval.get_tools()
    
    # Or use the API wrapper directly
    api = InventoryRetrievalApiWrapper(
        graph_path="/path/to/graph.json"
    )
    
    results = api.search_graph("UserService")
    entity = api.get_entity("UserService")
    content = api.get_entity_content("UserService")
"""

import logging
from pathlib import Path
from typing import Any, Optional, List, Dict

from pydantic import Field, create_model, PrivateAttr

from ...tools.elitea_base import BaseToolApiWrapper
from .knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)


# ========== Tool Parameter Schemas ==========

SearchGraphParams = create_model(
    "SearchGraphParams",
    query=(str, Field(description="Search query for finding entities. Supports token matching (e.g., 'chat message' finds 'ChatMessageHandler')")),
    entity_type=(Optional[str], Field(default=None, description="Filter by entity type (e.g., 'class', 'function', 'method'). Case-insensitive.")),
    layer=(Optional[str], Field(default=None, description="Filter by semantic layer: 'code' (classes/functions), 'service' (APIs/endpoints), 'data' (models/schemas), 'product' (features/menus), 'domain' (concepts/processes), 'documentation', 'configuration', 'testing', 'tooling', 'knowledge' (facts)")),
    file_pattern=(Optional[str], Field(default=None, description="Filter by file path pattern (glob-like, e.g., '**/chat*.py', 'api/v2/*.py')")),
    top_k=(Optional[int], Field(default=10, description="Number of results to return")),
)

SearchFactsParams = create_model(
    "SearchFactsParams",
    query=(Optional[str], Field(default=None, description="Optional search query to filter facts by subject/content")),
    fact_type=(Optional[str], Field(default=None, description="Filter by fact type: 'algorithm', 'behavior', 'validation', 'dependency', 'error_handling' (code), or 'decision', 'requirement', 'definition', 'date', 'reference', 'contact' (text)")),
    file_pattern=(Optional[str], Field(default=None, description="Filter by file path pattern (glob-like)")),
    top_k=(Optional[int], Field(default=20, description="Maximum number of facts to return")),
)

GetEntityParams = create_model(
    "GetEntityParams",
    entity_name=(str, Field(description="Name of entity to retrieve")),
    include_relations=(Optional[bool], Field(default=True, description="Include related entities")),
)

GetEntityContentParams = create_model(
    "GetEntityContentParams",
    entity_name=(str, Field(description="Name of entity to get source content for")),
)

ImpactAnalysisParams = create_model(
    "ImpactAnalysisParams",
    entity_name=(str, Field(description="Name of entity to analyze")),
    direction=(Optional[str], Field(default="downstream", description="'downstream' (what depends on this) or 'upstream' (what this depends on)")),
    max_depth=(Optional[int], Field(default=3, description="Maximum traversal depth")),
)

GetRelatedEntitiesParams = create_model(
    "GetRelatedEntitiesParams",
    entity_name=(str, Field(description="Name of entity")),
    relation_type=(Optional[str], Field(default=None, description="Filter by relation type")),
    direction=(Optional[str], Field(default="both", description="'outgoing', 'incoming', or 'both'")),
)

GetStatsParams = create_model(
    "GetStatsParams",
)

GetCitationsParams = create_model(
    "GetCitationsParams",
    query=(Optional[str], Field(default=None, description="Search query to filter citations")),
    file_path=(Optional[str], Field(default=None, description="Filter by file path")),
)

ListEntitiesByTypeParams = create_model(
    "ListEntitiesByTypeParams",
    entity_type=(str, Field(description="Type of entities to list (e.g., 'class', 'function', 'api_endpoint')")),
    limit=(Optional[int], Field(default=50, description="Maximum number of entities to return")),
)

ListEntitiesByLayerParams = create_model(
    "ListEntitiesByLayerParams",
    layer=(str, Field(description="Layer to list entities from: 'code' (classes/functions/methods), 'service' (APIs/RPCs), 'data' (models/schemas), 'product' (features/UI), 'domain' (concepts/processes), 'documentation', 'configuration', 'testing', 'tooling', 'knowledge' (facts), 'structure' (files)")),
    limit=(Optional[int], Field(default=50, description="Maximum number of entities to return")),
)

SearchByFileParams = create_model(
    "SearchByFileParams",
    file_pattern=(str, Field(description="File path pattern (glob-like, e.g., '**/chat*.py', 'api/v2/*.py', 'rpc/*.py')")),
    limit=(Optional[int], Field(default=50, description="Maximum number of entities to return")),
)

GetFileInfoParams = create_model(
    "GetFileInfoParams",
    file_path=(str, Field(description="Path to the file to get info for (can be partial, e.g., 'utils.py' or 'src/utils.py')")),
    include_entities=(Optional[bool], Field(default=True, description="Include list of entities defined in this file")),
)

ListFilesParams = create_model(
    "ListFilesParams",
    file_pattern=(Optional[str], Field(default=None, description="Optional file path pattern (glob-like, e.g., '**/*.py')")),
    file_type=(Optional[str], Field(default=None, description="Filter by file type: 'source_file', 'document_file', 'config_file', 'web_file'")),
    limit=(Optional[int], Field(default=50, description="Maximum number of files to return")),
)

AdvancedSearchParams = create_model(
    "AdvancedSearchParams",
    query=(Optional[str], Field(default=None, description="Text search query (optional)")),
    entity_types=(Optional[str], Field(default=None, description="Comma-separated entity types to include (e.g., 'class,function,method')")),
    layers=(Optional[str], Field(default=None, description="Comma-separated layers to include (e.g., 'code,service')")),
    file_patterns=(Optional[str], Field(default=None, description="Comma-separated file patterns (e.g., 'api/*.py,rpc/*.py')")),
    top_k=(Optional[int], Field(default=20, description="Maximum number of results")),
)


class InventoryRetrievalApiWrapper(BaseToolApiWrapper):
    """
    API Wrapper for Knowledge Graph Retrieval operations.
    
    Provides tools for querying a pre-built knowledge graph.
    This is a pure retrieval toolkit - no ingestion/mutation operations.
    
    The graph stores entity metadata and citations (file paths, line ranges).
    Content is retrieved on-demand from the base_directory or source toolkit.
    """
    
    # Graph persistence path (required)
    graph_path: str = Field(description="Path to the knowledge graph JSON file")
    
    # Base directory for local content retrieval (optional)
    # If set, get_entity_content will read from local files
    base_directory: Optional[str] = None
    
    # Source toolkits for remote content retrieval (optional)
    # Maps toolkit name -> toolkit instance for fetching content
    source_toolkits: Dict[str, Any] = Field(default_factory=dict)
    
    # Private attributes
    _knowledge_graph: Optional[KnowledgeGraph] = PrivateAttr(default=None)
    
    class Config:
        arbitrary_types_allowed = True
    
    def model_post_init(self, __context) -> None:
        """Initialize after model construction."""
        self._knowledge_graph = KnowledgeGraph()
        
        # Load graph (handle model_construct case where graph_path may not be set)
        graph_path = getattr(self, 'graph_path', None)
        if graph_path:
            try:
                self._knowledge_graph.load_from_json(graph_path)
                stats = self._knowledge_graph.get_stats()
                logger.info(
                    f"Loaded graph: {stats['node_count']} entities, "
                    f"{stats['edge_count']} relations"
                )
            except FileNotFoundError:
                logger.warning(f"Graph not found at {graph_path}")
            except Exception as e:
                logger.error(f"Failed to load graph: {e}")
    
    def _resolve_path(self, path: str) -> Optional[Path]:
        """Resolve path within base directory (if set)."""
        if not self.base_directory:
            return None
        
        base = Path(self.base_directory).resolve()
        
        if Path(path).is_absolute():
            target = Path(path).resolve()
        else:
            target = (base / path).resolve()
        
        # Security check
        try:
            target.relative_to(base)
            return target
        except ValueError:
            logger.warning(f"Path '{path}' is outside base directory")
            return None
    
    def _read_local_file(self, path: str) -> Optional[str]:
        """Read file content from base directory."""
        target = self._resolve_path(path)
        if target and target.exists() and target.is_file():
            try:
                return target.read_text(encoding='utf-8')
            except Exception as e:
                logger.warning(f"Failed to read {path}: {e}")
        return None
    
    def _read_local_file_lines(self, path: str, start_line: int, end_line: int) -> Optional[str]:
        """Read specific lines from a local file."""
        target = self._resolve_path(path)
        if not target or not target.exists():
            return None
        
        try:
            with open(target, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line)
            
            return ''.join(lines[start_idx:end_idx])
        except Exception as e:
            logger.warning(f"Failed to read lines from {path}: {e}")
        return None
    
    def _fetch_remote_content(
        self, 
        source_toolkit: str, 
        file_path: str,
        line_start: Optional[int] = None,
        line_end: Optional[int] = None
    ) -> Optional[str]:
        """Fetch content from a source toolkit."""
        if source_toolkit not in self.source_toolkits:
            return None
        
        toolkit = self.source_toolkits[source_toolkit]
        
        try:
            # Try get_files_content method (GitHub, ADO, etc.)
            if hasattr(toolkit, 'get_files_content'):
                content = toolkit.get_files_content(file_path)
                if content and line_start:
                    lines = content.split('\n')
                    end = line_end or (line_start + 100)
                    return '\n'.join(lines[line_start-1:end])
                return content
            
            # Try read_file method
            if hasattr(toolkit, 'read_file'):
                return toolkit.read_file(file_path)
            
        except Exception as e:
            logger.warning(f"Failed to fetch from {source_toolkit}: {e}")
        
        return None
    
    # ========== Tool Methods ==========
    
    def search_graph(
        self, 
        query: str, 
        entity_type: Optional[str] = None,
        layer: Optional[str] = None,
        file_pattern: Optional[str] = None,
        top_k: int = 10
    ) -> str:
        """
        Search for entities in the knowledge graph with enhanced matching.
        
        Supports:
        - Token-based matching: "chat message" finds "ChatMessageHandler"
        - File path patterns: "**/chat*.py" finds entities from chat files
        - Layer filtering: "code" includes classes, functions, methods
        - Type filtering: Case-insensitive matching
        
        Returns entity metadata with citations. Use get_entity_content
        to retrieve the actual source code.
        
        Args:
            query: Search query (matches entity names, descriptions, file paths)
            entity_type: Optional filter by type (class, function, api_endpoint, etc.)
            layer: Optional filter by layer (code, service, data, product, domain, etc.)
            file_pattern: Optional glob pattern for file paths
            top_k: Maximum number of results
        """
        self._log_tool_event(f"Searching: {query}", "search_graph")
        
        results = self._knowledge_graph.search(
            query, 
            top_k=top_k, 
            entity_type=entity_type,
            layer=layer,
            file_pattern=file_pattern,
        )
        
        if not results:
            filters = []
            if entity_type:
                filters.append(f"type={entity_type}")
            if layer:
                filters.append(f"layer={layer}")
            if file_pattern:
                filters.append(f"file={file_pattern}")
            filter_str = f" (filters: {', '.join(filters)})" if filters else ""
            return f"No entities found matching '{query}'{filter_str}"
        
        output = f"Found {len(results)} entities matching '{query}':\n\n"
        
        for i, result in enumerate(results, 1):
            entity = result['entity']
            match_field = result.get('match_field', '')
            score = result.get('score', 0)
            
            # Get citations (support both list and legacy single citation)
            citations = entity.get('citations', [])
            if not citations and 'citation' in entity:
                citations = [entity['citation']]
            
            entity_type_str = entity.get('type', 'unknown')
            layer_str = entity.get('layer', '')
            if not layer_str:
                # Infer layer from type
                layer_str = self._knowledge_graph.TYPE_TO_LAYER.get(entity_type_str.lower(), '')
            if layer_str:
                entity_type_str = f"{layer_str}/{entity_type_str}"
            
            output += f"{i:2}. **{entity.get('name')}** ({entity_type_str})\n"
            
            if citations:
                citation = citations[0]  # Primary citation
                file_path = citation.get('file_path', 'unknown')
                line_info = ""
                if citation.get('line_start'):
                    if citation.get('line_end'):
                        line_info = f":{citation['line_start']}-{citation['line_end']}"
                    else:
                        line_info = f":{citation['line_start']}"
                output += f"    📍 `{file_path}{line_info}`\n"
            elif entity.get('file_path'):
                output += f"    📍 `{entity['file_path']}`\n"
            
            # Show description if available
            description = entity.get('description', '')
            if not description and isinstance(entity.get('properties'), dict):
                description = entity['properties'].get('description', '')
            if description:
                desc = description[:120]
                if len(description) > 120:
                    desc += "..."
                output += f"    {desc}\n"
            
            output += "\n"
        
        return output
    
    def get_entity(self, entity_name: str, include_relations: bool = True) -> str:
        """
        Get detailed information about a specific entity.
        
        If multiple entities have the same name (e.g., 'Chat' as Feature vs command),
        shows all matches with their types.
        
        Returns metadata, citation, properties, and optionally relations.
        Use get_entity_content for the actual source code.
        """
        self._log_tool_event(f"Getting entity: {entity_name}", "get_entity")
        
        # Get all entities with this name
        entities = self._knowledge_graph.find_all_entities_by_name(entity_name)
        
        if not entities:
            # Try search as fallback
            results = self._knowledge_graph.search(entity_name, top_k=5)
            if results:
                entities = [r['entity'] for r in results]
        
        if not entities:
            return f"Entity '{entity_name}' not found"
        
        # If multiple matches, show disambiguation
        if len(entities) > 1:
            output = f"# Found {len(entities)} entities named '{entity_name}'\n\n"
            for i, entity in enumerate(entities, 1):
                etype = entity.get('type', 'unknown')
                layer = entity.get('layer', '') or self._knowledge_graph.TYPE_TO_LAYER.get(etype.lower(), '')
                fp = entity.get('file_path', '')
                
                type_str = f"{layer}/{etype}" if layer else etype
                output += f"{i}. **{entity.get('name')}** ({type_str})"
                if fp:
                    output += f" - `{fp}`"
                output += f"\n   ID: `{entity.get('id')}`\n\n"
            
            output += "\n---\n\n"
            output += "Showing details for the first match:\n\n"
            entity = entities[0]
        else:
            entity = entities[0]
            output = ""
        
        # Show details for the primary entity
        output += f"# {entity.get('name')}\n\n"
        
        etype = entity.get('type', 'unknown')
        layer = entity.get('layer', '') or self._knowledge_graph.TYPE_TO_LAYER.get(etype.lower(), '')
        
        output += f"**Type:** {etype}\n"
        if layer:
            output += f"**Layer:** {layer}\n"
        
        output += f"**ID:** `{entity.get('id')}`\n"
        
        # Citations (support both list and legacy single citation)
        citations = entity.get('citations', [])
        if not citations and 'citation' in entity:
            citations = [entity['citation']]
        
        if citations:
            output += f"\n**Locations ({len(citations)}):**\n"
            for citation in citations[:5]:
                if isinstance(citation, dict):
                    file_path = citation.get('file_path', 'unknown')
                    source = citation.get('source_toolkit', 'filesystem')
                    line_info = ""
                    if citation.get('line_start'):
                        line_info = f":{citation['line_start']}"
                        if citation.get('line_end'):
                            line_info += f"-{citation['line_end']}"
                    output += f"- `{file_path}{line_info}` ({source})\n"
            if len(citations) > 5:
                output += f"- ... and {len(citations) - 5} more citations\n"
        elif entity.get('file_path'):
            output += f"\n**Location:** `{entity['file_path']}`\n"
        
        # Description
        description = entity.get('description', '')
        if not description and isinstance(entity.get('properties'), dict):
            description = entity['properties'].get('description', '')
        if description:
            output += f"\n**Description:**\n{description}\n"
        
        # Properties
        skip_keys = {'id', 'name', 'type', 'layer', 'citation', 'citations', 'description', 'file_path', 'source_toolkit', 'properties'}
        props = {k: v for k, v in entity.items() if k not in skip_keys}
        
        # Also include nested properties
        if isinstance(entity.get('properties'), dict):
            for k, v in entity['properties'].items():
                if k not in skip_keys and k != 'description':
                    props[k] = v
        
        if props:
            output += f"\n**Properties:**\n"
            for key, value in props.items():
                if isinstance(value, (list, dict)):
                    output += f"- {key}: {len(value)} items\n"
                elif isinstance(value, str) and len(value) > 100:
                    output += f"- {key}: {value[:100]}...\n"
                else:
                    output += f"- {key}: {value}\n"
        
        # Relations
        if include_relations:
            entity_id = entity.get('id')
            if entity_id:
                relations = self._knowledge_graph.get_relations(entity_id, direction='both')
                if relations:
                    output += f"\n**Relations ({len(relations)}):**\n"
                    
                    outgoing = []
                    incoming = []
                    
                    for rel in relations:
                        if rel['source'] == entity_id:
                            target = self._knowledge_graph.get_entity(rel['target'])
                            target_name = target.get('name', rel['target']) if target else rel['target']
                            outgoing.append(f"→ {rel['relation_type']} → **{target_name}**")
                        else:
                            source = self._knowledge_graph.get_entity(rel['source'])
                            source_name = source.get('name', rel['source']) if source else rel['source']
                            incoming.append(f"← {rel['relation_type']} ← **{source_name}**")
                    
                    for r in outgoing[:5]:
                        output += f"- {r}\n"
                    if len(outgoing) > 5:
                        output += f"- ... and {len(outgoing) - 5} more outgoing\n"
                    
                    for r in incoming[:5]:
                        output += f"- {r}\n"
                    if len(incoming) > 5:
                        output += f"- ... and {len(incoming) - 5} more incoming\n"
        
        return output
    
    def get_entity_content(self, entity_name: str) -> str:
        """
        Retrieve the source content for an entity using its citation.
        
        This reads from the local filesystem or fetches from the source toolkit.
        Use this when you need to see the actual source code.
        """
        self._log_tool_event(f"Getting content for: {entity_name}", "get_entity_content")
        
        entity = self._knowledge_graph.find_entity_by_name(entity_name)
        
        if not entity:
            results = self._knowledge_graph.search(entity_name, top_k=1)
            if results:
                entity = results[0]['entity']
        
        if not entity:
            return f"Entity '{entity_name}' not found"
        
        citation = entity.get('citation', {})
        if not citation or not citation.get('file_path'):
            return f"Entity '{entity_name}' has no file citation"
        
        file_path = citation['file_path']
        source_toolkit = citation.get('source_toolkit', 'filesystem')
        line_start = citation.get('line_start')
        line_end = citation.get('line_end')
        
        content = None
        
        # Try local file first
        if self.base_directory:
            if line_start and line_end:
                content = self._read_local_file_lines(file_path, line_start, line_end)
            elif line_start:
                content = self._read_local_file_lines(file_path, line_start, line_start + 100)
            else:
                content = self._read_local_file(file_path)
        
        # Fall back to remote fetch
        if content is None and source_toolkit != 'filesystem':
            content = self._fetch_remote_content(
                source_toolkit, file_path, line_start, line_end
            )
        
        if content is None:
            location = f"{file_path}"
            if line_start:
                location += f":{line_start}"
                if line_end:
                    location += f"-{line_end}"
            
            return (
                f"Could not retrieve content for '{entity_name}'\n"
                f"Location: {location}\n"
                f"Source: {source_toolkit}\n\n"
                f"The file may not be accessible locally. "
                f"Ensure base_directory is set or the source toolkit is available."
            )
        
        # Format output
        location = f"{file_path}"
        if line_start:
            location += f":{line_start}"
            if line_end:
                location += f"-{line_end}"
        
        return f"**Source:** `{location}`\n\n```\n{content}\n```"
    
    def impact_analysis(
        self, 
        entity_name: str, 
        direction: str = "downstream",
        max_depth: int = 3
    ) -> str:
        """
        Analyze what entities would be impacted by changes.
        
        - **downstream**: What entities depend on this one (would be affected by changes)
        - **upstream**: What entities does this depend on (might cause issues here)
        
        Useful for:
        - Change impact assessment
        - Dependency analysis
        - Risk assessment before refactoring
        """
        self._log_tool_event(f"Impact analysis for: {entity_name}", "impact_analysis")
        
        entity = self._knowledge_graph.find_entity_by_name(entity_name)
        
        if not entity:
            results = self._knowledge_graph.search(entity_name, top_k=1)
            if results:
                entity = results[0]['entity']
        
        if not entity:
            return f"Entity '{entity_name}' not found"
        
        entity_id = entity.get('id')
        if not entity_id:
            return "Entity has no ID for analysis"
        
        impact = self._knowledge_graph.impact_analysis(
            entity_id, direction=direction, max_depth=max_depth
        )
        
        impacted = impact.get('impacted', [])
        
        if not impacted:
            return f"No {direction} dependencies found for '{entity_name}'"
        
        output = f"# Impact Analysis: {entity_name}\n\n"
        output += f"**Direction:** {direction}\n"
        output += f"**Total impacted:** {len(impacted)} entities\n\n"
        
        # Group by depth
        by_depth: Dict[int, List] = {}
        for item in impacted:
            depth = item['depth']
            if depth not in by_depth:
                by_depth[depth] = []
            by_depth[depth].append(item)
        
        for depth in sorted(by_depth.keys()):
            items = by_depth[depth]
            output += f"## Level {depth} ({len(items)} entities)\n\n"
            
            for item in items[:15]:
                ent = item['entity']
                citation = ent.get('citation', {})
                location = citation.get('file_path', 'unknown') if citation else 'unknown'
                output += f"- **{ent.get('name')}** ({ent.get('type')}) - `{location}`\n"
            
            if len(items) > 15:
                output += f"- ... and {len(items) - 15} more\n"
            
            output += "\n"
        
        return output
    
    def get_related_entities(
        self,
        entity_name: str,
        relation_type: Optional[str] = None,
        direction: str = "both"
    ) -> str:
        """
        Get entities related to a specific entity.
        
        Args:
            entity_name: Name of the entity
            relation_type: Optional filter by relation type (CALLS, IMPORTS, EXTENDS, etc.)
            direction: 'outgoing' (this → others), 'incoming' (others → this), or 'both'
        """
        self._log_tool_event(f"Getting related: {entity_name}", "get_related_entities")
        
        entity = self._knowledge_graph.find_entity_by_name(entity_name)
        
        if not entity:
            results = self._knowledge_graph.search(entity_name, top_k=1)
            if results:
                entity = results[0]['entity']
        
        if not entity:
            return f"Entity '{entity_name}' not found"
        
        entity_id = entity.get('id')
        if not entity_id:
            return "Entity has no ID"
        
        relations = self._knowledge_graph.get_relations(entity_id, direction=direction)
        
        # Filter by relation type if specified
        if relation_type:
            relations = [r for r in relations if r['relation_type'] == relation_type]
        
        if not relations:
            filter_str = f" of type '{relation_type}'" if relation_type else ""
            return f"No relations{filter_str} found for '{entity_name}'"
        
        output = f"# Related to: {entity_name}\n\n"
        
        # Group by relation type
        by_type: Dict[str, Dict[str, List]] = {}
        
        for rel in relations:
            rtype = rel['relation_type']
            if rtype not in by_type:
                by_type[rtype] = {'outgoing': [], 'incoming': []}
            
            if rel['source'] == entity_id:
                target = self._knowledge_graph.get_entity(rel['target'])
                by_type[rtype]['outgoing'].append(target or {'name': rel['target']})
            else:
                source = self._knowledge_graph.get_entity(rel['source'])
                by_type[rtype]['incoming'].append(source or {'name': rel['source']})
        
        for rtype, directions in by_type.items():
            output += f"## {rtype}\n\n"
            
            if directions['outgoing']:
                output += f"**Outgoing ({len(directions['outgoing'])}):**\n"
                for ent in directions['outgoing'][:10]:
                    output += f"- → **{ent.get('name')}** ({ent.get('type', 'unknown')})\n"
                if len(directions['outgoing']) > 10:
                    output += f"- ... and {len(directions['outgoing']) - 10} more\n"
            
            if directions['incoming']:
                output += f"**Incoming ({len(directions['incoming'])}):**\n"
                for ent in directions['incoming'][:10]:
                    output += f"- ← **{ent.get('name')}** ({ent.get('type', 'unknown')})\n"
                if len(directions['incoming']) > 10:
                    output += f"- ... and {len(directions['incoming']) - 10} more\n"
            
            output += "\n"
        
        return output
    
    def get_stats(self) -> str:
        """Get knowledge graph statistics."""
        stats = self._knowledge_graph.get_stats()
        schema = self._knowledge_graph.get_schema()
        
        output = "# Knowledge Graph Statistics\n\n"
        output += f"**Entities:** {stats['node_count']}\n"
        output += f"**Relations:** {stats['edge_count']}\n"
        
        if stats['entity_types']:
            output += f"\n## Entity Types\n"
            for etype, count in sorted(stats['entity_types'].items(), key=lambda x: -x[1]):
                output += f"- {etype}: {count}\n"
        
        if stats['relation_types']:
            output += f"\n## Relation Types\n"
            for rtype, count in sorted(stats['relation_types'].items(), key=lambda x: -x[1]):
                output += f"- {rtype}: {count}\n"
        
        if stats['source_toolkits']:
            output += f"\n## Sources\n"
            for source in stats['source_toolkits']:
                output += f"- {source}\n"
        
        if stats['last_saved']:
            output += f"\n**Last updated:** {stats['last_saved']}\n"
        
        return output
    
    def get_citations(
        self, 
        query: Optional[str] = None,
        file_path: Optional[str] = None
    ) -> str:
        """
        Get citations summary for entities.
        
        Use this to see which files contain which entities.
        
        Args:
            query: Optional search query to filter entities
            file_path: Optional file path to filter citations
        """
        self._log_tool_event(f"Getting citations (query={query}, file={file_path})", "get_citations")
        
        if query:
            citations = self._knowledge_graph.get_citations_for_query(query, top_k=20)
            if not citations:
                return f"No citations found for query '{query}'"
            
            output = f"# Citations for '{query}'\n\n"
            for citation in citations:
                output += f"- `{citation}`\n"
            return output
        
        # Get all citations grouped by file
        by_file = self._knowledge_graph.export_citations_summary()
        
        if file_path:
            # Filter to specific file
            by_file = {k: v for k, v in by_file.items() if file_path in k}
        
        if not by_file:
            if file_path:
                return f"No citations for file '{file_path}'"
            return "No citations in graph"
        
        output = f"# Citations ({len(by_file)} files)\n\n"
        
        for fpath, entities in list(by_file.items())[:30]:
            output += f"## `{fpath}`\n"
            for ent in entities[:10]:
                lines = ""
                if ent.get('line_start'):
                    lines = f" (L{ent['line_start']}"
                    if ent.get('line_end'):
                        lines += f"-{ent['line_end']}"
                    lines += ")"
                output += f"- **{ent['name']}** [{ent['type']}]{lines}\n"
            if len(entities) > 10:
                output += f"- ... and {len(entities) - 10} more\n"
            output += "\n"
        
        if len(by_file) > 30:
            output += f"\n... and {len(by_file) - 30} more files\n"
        
        return output
    
    def list_entities_by_type(self, entity_type: str, limit: int = 50) -> str:
        """
        List all entities of a specific type.
        
        Args:
            entity_type: Type to filter (class, function, api_endpoint, etc.)
            limit: Maximum entities to return
        """
        self._log_tool_event(f"Listing entities of type: {entity_type}", "list_entities_by_type")
        
        entities = self._knowledge_graph.get_entities_by_type(entity_type, limit=limit)
        
        if not entities:
            return f"No entities of type '{entity_type}' found"
        
        output = f"# Entities of type '{entity_type}' ({len(entities)})\n\n"
        
        for ent in entities:
            citation = ent.get('citation', {})
            location = citation.get('file_path', 'unknown') if citation else 'unknown'
            output += f"- **{ent.get('name')}** - `{location}`\n"
        
        if len(entities) == limit:
            output += f"\n*Limited to {limit} results*\n"
        
        return output
    
    def list_entities_by_layer(self, layer: str, limit: int = 50) -> str:
        """
        List all entities in a specific layer.
        
        Layers:
        - code: classes, functions, methods, modules
        - service: API endpoints, RPC methods, handlers
        - data: models, schemas, fields
        - product: features, UI components, menus
        - domain: concepts, processes, use cases
        - documentation: guides, sections, examples
        - configuration: settings, credentials
        - testing: test cases, fixtures
        - tooling: tools, toolkits, commands
        
        Args:
            layer: Layer to filter
            limit: Maximum entities to return
        """
        self._log_tool_event(f"Listing entities in layer: {layer}", "list_entities_by_layer")
        
        entities = self._knowledge_graph.get_entities_by_layer(layer, limit=limit)
        
        if not entities:
            available_layers = ", ".join(self._knowledge_graph.LAYER_TYPE_MAPPING.keys())
            return f"No entities in layer '{layer}' found. Available layers: {available_layers}"
        
        output = f"# Entities in layer '{layer}' ({len(entities)})\n\n"
        
        # Group by type
        by_type: Dict[str, List] = {}
        for ent in entities:
            etype = ent.get('type', 'unknown')
            if etype not in by_type:
                by_type[etype] = []
            by_type[etype].append(ent)
        
        for etype, ents in sorted(by_type.items(), key=lambda x: -len(x[1])):
            output += f"## {etype} ({len(ents)})\n"
            for ent in ents[:10]:
                file_path = ent.get('file_path', '')
                if file_path:
                    output += f"- **{ent.get('name')}** - `{file_path}`\n"
                else:
                    output += f"- **{ent.get('name')}**\n"
            if len(ents) > 10:
                output += f"- ... and {len(ents) - 10} more\n"
            output += "\n"
        
        return output
    
    def search_by_file(self, file_pattern: str, limit: int = 50) -> str:
        """
        Search for entities by file path pattern.
        
        Useful for finding all code elements in specific files or directories.
        
        Args:
            file_pattern: Glob-like pattern (e.g., "**/chat*.py", "api/v2/*.py", "rpc/*.py")
            limit: Maximum entities to return
        """
        self._log_tool_event(f"Searching by file: {file_pattern}", "search_by_file")
        
        entities = self._knowledge_graph.search_by_file(file_pattern, limit=limit)
        
        if not entities:
            return f"No entities found matching file pattern '{file_pattern}'"
        
        output = f"# Entities from files matching '{file_pattern}' ({len(entities)})\n\n"
        
        # Group by file
        by_file: Dict[str, List] = {}
        for ent in entities:
            fp = ent.get('file_path', 'unknown')
            if fp not in by_file:
                by_file[fp] = []
            by_file[fp].append(ent)
        
        for fp, ents in sorted(by_file.items()):
            output += f"## `{fp}` ({len(ents)} entities)\n"
            for ent in ents[:15]:
                output += f"- **{ent.get('name')}** ({ent.get('type', 'unknown')})\n"
            if len(ents) > 15:
                output += f"- ... and {len(ents) - 15} more\n"
            output += "\n"
        
        return output
    
    def search_facts(
        self,
        query: Optional[str] = None,
        fact_type: Optional[str] = None,
        file_pattern: Optional[str] = None,
        top_k: int = 20
    ) -> str:
        """
        Search for semantic facts extracted from code and documentation.
        
        Facts are structured knowledge extracted by LLM analysis:
        - Code facts: algorithm, behavior, validation, dependency, error_handling
        - Text facts: decision, requirement, definition, date, reference, contact
        
        Each fact has subject-predicate-object structure with citations.
        
        Args:
            query: Optional text search on fact subject/content
            fact_type: Filter by fact type (algorithm, behavior, decision, etc.)
            file_pattern: Filter by source file path pattern
            top_k: Maximum facts to return
        """
        self._log_tool_event(f"Searching facts: query={query}, type={fact_type}", "search_facts")
        
        import re
        
        results = []
        
        # Compile file pattern regex if provided
        file_regex = None
        if file_pattern:
            pattern = file_pattern.replace('.', r'\.').replace('**', '.*').replace('*', '[^/]*').replace('?', '.')
            try:
                file_regex = re.compile(pattern, re.IGNORECASE)
            except re.error:
                pass
        
        # Search all fact entities
        for node_id, data in self._knowledge_graph._graph.nodes(data=True):
            # Only look at fact entities
            if data.get('type', '').lower() != 'fact':
                continue
            
            # Filter by fact_type property
            props = data.get('properties', {})
            entity_fact_type = props.get('fact_type', '')
            
            if fact_type and entity_fact_type.lower() != fact_type.lower():
                continue
            
            # Filter by file pattern
            citations = data.get('citations', [])
            if not citations and 'citation' in data:
                citations = [data['citation']]
            
            file_path = ''
            for c in citations:
                if isinstance(c, dict):
                    file_path = c.get('file_path', '')
                    break
            
            if file_regex and file_path:
                if not file_regex.search(file_path):
                    continue
            
            # Filter by query (search in subject and predicate)
            if query:
                query_lower = query.lower()
                subject = props.get('subject', '').lower()
                predicate = props.get('predicate', '').lower()
                obj = props.get('object', '').lower()
                name = data.get('name', '').lower()
                
                if not any(query_lower in text for text in [subject, predicate, obj, name]):
                    continue
            
            results.append({
                'entity': dict(data),
                'file_path': file_path,
            })
        
        # Sort by file path, then by name
        results.sort(key=lambda x: (x['file_path'], x['entity'].get('name', '')))
        results = results[:top_k]
        
        if not results:
            filters = []
            if query:
                filters.append(f"query='{query}'")
            if fact_type:
                filters.append(f"type={fact_type}")
            if file_pattern:
                filters.append(f"file={file_pattern}")
            filter_str = f" (filters: {', '.join(filters)})" if filters else ""
            return f"No facts found{filter_str}"
        
        output = f"# Found {len(results)} facts\n\n"
        
        # Group by fact type
        by_type: Dict[str, List] = {}
        for r in results:
            ft = r['entity'].get('properties', {}).get('fact_type', 'unknown')
            if ft not in by_type:
                by_type[ft] = []
            by_type[ft].append(r)
        
        for ft, facts in sorted(by_type.items()):
            output += f"## {ft} ({len(facts)})\n\n"
            for f in facts:
                entity = f['entity']
                props = entity.get('properties', {})
                file_path = f['file_path']
                
                subject = props.get('subject', entity.get('name', 'unknown'))
                predicate = props.get('predicate', '')
                obj = props.get('object', '')
                confidence = props.get('confidence', 0)
                
                # Format as subject → predicate → object
                fact_text = f"**{subject}**"
                if predicate:
                    fact_text += f" → {predicate}"
                if obj:
                    fact_text += f" → {obj}"
                
                output += f"- {fact_text}\n"
                if file_path:
                    citation = entity.get('citation') or (entity.get('citations', [{}])[0] if entity.get('citations') else {})
                    line_info = ""
                    if isinstance(citation, dict) and citation.get('line_start'):
                        line_info = f":{citation['line_start']}"
                        if citation.get('line_end'):
                            line_info += f"-{citation['line_end']}"
                    output += f"  📍 `{file_path}{line_info}` (confidence: {confidence:.1%})\n"
                output += "\n"
        
        return output

    def get_file_info(self, file_path: str, include_entities: bool = True) -> str:
        """
        Get detailed information about a file node including all entities defined in it.
        
        File nodes are container entities that aggregate all code, facts, and other
        entities from a single source file.
        
        Args:
            file_path: Path to the file (can be partial, e.g., 'utils.py')
            include_entities: Whether to include list of entities defined in file
        """
        self._log_tool_event(f"Getting file info: {file_path}", "get_file_info")
        
        # Search for file entities matching the path
        file_types = {'file', 'source_file', 'document_file', 'config_file', 'web_file'}
        matches = []
        
        for node_id, data in self._knowledge_graph._graph.nodes(data=True):
            if data.get('type', '').lower() not in file_types:
                continue
            
            # Match by full path or partial path
            entity_path = data.get('properties', {}).get('full_path', '') or data.get('name', '')
            if file_path in entity_path or entity_path.endswith(file_path):
                matches.append(data)
        
        if not matches:
            return f"No file found matching '{file_path}'"
        
        if len(matches) > 1:
            output = f"# Multiple files match '{file_path}'\n\n"
            for m in matches:
                full_path = m.get('properties', {}).get('full_path', m.get('name'))
                output += f"- `{full_path}`\n"
            output += f"\nShowing first match:\n\n"
        else:
            output = ""
        
        file_entity = matches[0]
        props = file_entity.get('properties', {})
        
        output += f"# {file_entity.get('name')}\n\n"
        output += f"**Type:** {file_entity.get('type')}\n"
        output += f"**Path:** `{props.get('full_path', file_entity.get('name'))}`\n"
        output += f"**Extension:** {props.get('extension', 'unknown')}\n"
        output += f"**Lines:** {props.get('line_count', 'unknown')}\n"
        output += f"**Size:** {props.get('size_bytes', 0):,} bytes\n"
        output += f"**Content Hash:** `{props.get('content_hash', 'unknown')[:12]}...`\n\n"
        
        output += f"## Entity Summary\n\n"
        output += f"- **Code entities:** {props.get('code_entity_count', 0)}\n"
        output += f"- **Facts:** {props.get('fact_count', 0)}\n"
        output += f"- **Other entities:** {props.get('other_entity_count', 0)}\n"
        output += f"- **Total:** {props.get('entity_count', 0)}\n\n"
        
        if include_entities:
            # Find entities defined_in this file
            file_id = file_entity.get('id')
            entities_in_file = []
            
            for edge in self._knowledge_graph._graph.edges(data=True):
                source, target, edge_data = edge
                if target == file_id and edge_data.get('relation_type') == 'defined_in':
                    entity = self._knowledge_graph.get_entity(source)
                    if entity:
                        entities_in_file.append(entity)
            
            if entities_in_file:
                output += f"## Entities in File ({len(entities_in_file)})\n\n"
                
                # Group by type
                by_type: Dict[str, List] = {}
                for ent in entities_in_file:
                    etype = ent.get('type', 'unknown')
                    if etype not in by_type:
                        by_type[etype] = []
                    by_type[etype].append(ent)
                
                for etype, ents in sorted(by_type.items(), key=lambda x: -len(x[1])):
                    output += f"### {etype} ({len(ents)})\n"
                    for ent in ents[:10]:
                        output += f"- **{ent.get('name')}**"
                        if ent.get('type') == 'fact':
                            fact_type = ent.get('properties', {}).get('fact_type', '')
                            if fact_type:
                                output += f" [{fact_type}]"
                        output += "\n"
                    if len(ents) > 10:
                        output += f"- ... and {len(ents) - 10} more\n"
                    output += "\n"
        
        return output
    
    def list_files(
        self,
        file_pattern: Optional[str] = None,
        file_type: Optional[str] = None,
        limit: int = 50
    ) -> str:
        """
        List all file nodes in the knowledge graph.
        
        File nodes contain metadata about source files and link to all entities
        defined within them via 'defined_in' relationships.
        
        Args:
            file_pattern: Optional glob pattern to filter files
            file_type: Filter by file type (source_file, document_file, config_file, web_file)
            limit: Maximum files to return
        """
        self._log_tool_event(f"Listing files: pattern={file_pattern}, type={file_type}", "list_files")
        
        import re
        
        file_types = {'file', 'source_file', 'document_file', 'config_file', 'web_file'}
        
        # Compile pattern if provided
        file_regex = None
        if file_pattern:
            pattern = file_pattern.replace('.', r'\.').replace('**', '.*').replace('*', '[^/]*').replace('?', '.')
            try:
                file_regex = re.compile(pattern, re.IGNORECASE)
            except re.error:
                pass
        
        files = []
        for node_id, data in self._knowledge_graph._graph.nodes(data=True):
            entity_type = data.get('type', '').lower()
            if entity_type not in file_types:
                continue
            
            # Filter by file_type
            if file_type and entity_type != file_type.lower():
                continue
            
            props = data.get('properties', {})
            full_path = props.get('full_path', data.get('name', ''))
            
            # Filter by pattern
            if file_regex and not file_regex.search(full_path):
                continue
            
            files.append({
                'entity': data,
                'path': full_path,
            })
        
        if not files:
            filters = []
            if file_pattern:
                filters.append(f"pattern={file_pattern}")
            if file_type:
                filters.append(f"type={file_type}")
            filter_str = f" (filters: {', '.join(filters)})" if filters else ""
            return f"No files found{filter_str}"
        
        # Sort by path
        files.sort(key=lambda x: x['path'])
        files = files[:limit]
        
        output = f"# Files ({len(files)})\n\n"
        
        # Group by file type
        by_type: Dict[str, List] = {}
        for f in files:
            ftype = f['entity'].get('type', 'file')
            if ftype not in by_type:
                by_type[ftype] = []
            by_type[ftype].append(f)
        
        for ftype, flist in sorted(by_type.items()):
            output += f"## {ftype} ({len(flist)})\n\n"
            for f in flist:
                entity = f['entity']
                props = entity.get('properties', {})
                path = f['path']
                entity_count = props.get('entity_count', 0)
                fact_count = props.get('fact_count', 0)
                
                output += f"- `{path}` ({entity_count} entities"
                if fact_count:
                    output += f", {fact_count} facts"
                output += ")\n"
            output += "\n"
        
        return output

    def advanced_search(
        self,
        query: Optional[str] = None,
        entity_types: Optional[str] = None,
        layers: Optional[str] = None,
        file_patterns: Optional[str] = None,
        top_k: int = 20,
    ) -> str:
        """
        Advanced search with multiple filter criteria.
        
        All filters use OR logic within each parameter.
        
        Args:
            query: Text search query (optional)
            entity_types: Comma-separated types to include (e.g., "class,function,method")
            layers: Comma-separated layers to include (e.g., "code,service")
            file_patterns: Comma-separated file patterns (e.g., "api/*.py,rpc/*.py")
            top_k: Maximum results
        """
        self._log_tool_event(f"Advanced search: query={query}, types={entity_types}, layers={layers}, files={file_patterns}", "advanced_search")
        
        # Parse comma-separated values
        types_list = [t.strip() for t in entity_types.split(',')] if entity_types else None
        layers_list = [l.strip() for l in layers.split(',')] if layers else None
        files_list = [f.strip() for f in file_patterns.split(',')] if file_patterns else None
        
        results = self._knowledge_graph.search_advanced(
            query=query,
            entity_types=types_list,
            layers=layers_list,
            file_patterns=files_list,
            top_k=top_k,
        )
        
        if not results:
            filters = []
            if entity_types:
                filters.append(f"types={entity_types}")
            if layers:
                filters.append(f"layers={layers}")
            if file_patterns:
                filters.append(f"files={file_patterns}")
            filter_str = f" (filters: {', '.join(filters)})" if filters else ""
            query_str = f" matching '{query}'" if query else ""
            return f"No entities found{query_str}{filter_str}"
        
        output = f"# Advanced Search Results ({len(results)})\n\n"
        
        for i, result in enumerate(results, 1):
            entity = result['entity']
            etype = entity.get('type', 'unknown')
            layer = entity.get('layer', '') or self._knowledge_graph.TYPE_TO_LAYER.get(etype.lower(), '')
            fp = entity.get('file_path', '')
            
            type_str = f"{layer}/{etype}" if layer else etype
            output += f"{i:2}. **{entity.get('name')}** ({type_str})\n"
            if fp:
                output += f"    📍 `{fp}`\n"
            output += "\n"
        
        return output
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Return list of available retrieval tools."""
        return [
            {
                "name": "search_graph",
                "ref": self.search_graph,
                "description": "Search for entities with enhanced token matching. Supports 'chat message' finding 'ChatMessageHandler', file patterns like '**/chat*.py', and layer filtering (code, service, data, product, knowledge).",
                "args_schema": SearchGraphParams,
            },
            {
                "name": "search_facts",
                "ref": self.search_facts,
                "description": "Search semantic facts extracted from code and docs. Filter by fact_type: algorithm, behavior, validation (code) or decision, requirement, definition (text). Returns subject→predicate→object triples with citations.",
                "args_schema": SearchFactsParams,
            },
            {
                "name": "get_entity",
                "ref": self.get_entity,
                "description": "Get detailed information about a specific entity including properties and relations.",
                "args_schema": GetEntityParams,
            },
            {
                "name": "get_entity_content",
                "ref": self.get_entity_content,
                "description": "Retrieve source code for an entity using its citation. Reads from local files or remote toolkit.",
                "args_schema": GetEntityContentParams,
            },
            {
                "name": "search_by_file",
                "ref": self.search_by_file,
                "description": "Search entities by file path pattern. Use '**/chat*.py' to find all chat-related code, 'api/v2/*.py' for API v2 files.",
                "args_schema": SearchByFileParams,
            },
            {
                "name": "advanced_search",
                "ref": self.advanced_search,
                "description": "Advanced multi-criteria search. Combine text query with type/layer/file filters. Types: class,function,method. Layers: code,service,data,product,knowledge.",
                "args_schema": AdvancedSearchParams,
            },
            {
                "name": "impact_analysis",
                "ref": self.impact_analysis,
                "description": "Analyze what entities would be impacted by changes (downstream) or what this entity depends on (upstream).",
                "args_schema": ImpactAnalysisParams,
            },
            {
                "name": "get_related_entities",
                "ref": self.get_related_entities,
                "description": "Get entities related to a specific entity, optionally filtered by relation type.",
                "args_schema": GetRelatedEntitiesParams,
            },
            {
                "name": "get_stats",
                "ref": self.get_stats,
                "description": "Get statistics about the knowledge graph (entity counts, types, sources).",
                "args_schema": GetStatsParams,
            },
            {
                "name": "get_citations",
                "ref": self.get_citations,
                "description": "Get summary of entity citations by file. Shows which files contain which entities.",
                "args_schema": GetCitationsParams,
            },
            {
                "name": "list_entities_by_type",
                "ref": self.list_entities_by_type,
                "description": "List all entities of a specific type (class, function, api_endpoint, etc.). Case-insensitive.",
                "args_schema": ListEntitiesByTypeParams,
            },
            {
                "name": "list_entities_by_layer",
                "ref": self.list_entities_by_layer,
                "description": "List entities by semantic layer: code (classes/functions), service (APIs), data (models), product (features), knowledge (facts), structure (files), documentation, configuration, testing, tooling.",
                "args_schema": ListEntitiesByLayerParams,
            },
            {
                "name": "get_file_info",
                "ref": self.get_file_info,
                "description": "Get detailed info about a file including metadata (lines, size, hash) and all entities defined in it (classes, functions, facts, etc.).",
                "args_schema": GetFileInfoParams,
            },
            {
                "name": "list_files",
                "ref": self.list_files,
                "description": "List all file nodes in the graph. Filter by pattern ('**/*.py') or type (source_file, document_file, config_file). Shows entity counts per file.",
                "args_schema": ListFilesParams,
            },
        ]
