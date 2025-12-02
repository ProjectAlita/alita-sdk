"""
NetworkX-based Knowledge Graph implementation.

Provides lightweight in-memory graph storage with JSON persistence.
Entities contain citations (source file, line numbers) instead of raw content.
Raw data should be retrieved on-demand using filesystem tools.
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional, List, Dict, Set
from collections import defaultdict

try:
    import networkx as nx
    from networkx import DiGraph
except ImportError:
    nx = None

logger = logging.getLogger(__name__)


class Citation:
    """
    Represents a source citation for an entity.
    
    Citations are lightweight references to source files and line ranges.
    The actual content should be retrieved on-demand using filesystem tools.
    """
    
    def __init__(
        self,
        file_path: str,
        line_start: Optional[int] = None,
        line_end: Optional[int] = None,
        source_toolkit: Optional[str] = None,
        doc_id: Optional[str] = None,
        content_hash: Optional[str] = None,
    ):
        self.file_path = file_path
        self.line_start = line_start
        self.line_end = line_end
        self.source_toolkit = source_toolkit
        self.doc_id = doc_id
        self.content_hash = content_hash
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert citation to dictionary."""
        return {
            'file_path': self.file_path,
            'line_start': self.line_start,
            'line_end': self.line_end,
            'source_toolkit': self.source_toolkit,
            'doc_id': self.doc_id,
            'content_hash': self.content_hash,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Citation':
        """Create citation from dictionary."""
        return cls(
            file_path=data.get('file_path', ''),
            line_start=data.get('line_start'),
            line_end=data.get('line_end'),
            source_toolkit=data.get('source_toolkit'),
            doc_id=data.get('doc_id'),
            content_hash=data.get('content_hash'),
        )
    
    def __repr__(self) -> str:
        if self.line_start and self.line_end:
            return f"{self.file_path}:{self.line_start}-{self.line_end}"
        elif self.line_start:
            return f"{self.file_path}:{self.line_start}"
        return self.file_path


class KnowledgeGraph:
    """
    Lightweight NetworkX-based knowledge graph for storing entities and relationships.
    
    Design principles:
    - Graph contains only entity metadata and citations (not raw content)
    - Citations reference source files and line numbers
    - Raw content is retrieved on-demand via filesystem tools
    - Graph file stays small and portable
    
    Features:
    - In-memory property graph using NetworkX
    - JSON persistence via node_link_data format
    - Delta update support with source document tracking
    - Entity deduplication with merge strategies
    - Impact analysis via graph traversal
    """
    
    def __init__(self):
        """Initialize an empty knowledge graph."""
        if nx is None:
            raise ImportError("networkx is required for KnowledgeGraph. Install with: pip install networkx>=3.0")
        
        self._graph: DiGraph = DiGraph()
        self._entity_index: Dict[str, str] = {}  # name -> node_id
        self._source_doc_index: Dict[str, Set[str]] = defaultdict(set)  # source_doc_id -> node_ids
        self._metadata: Dict[str, Any] = {}  # Graph metadata (sources, timestamps)
        self._schema: Optional[Dict[str, Any]] = None  # Discovered entity schema
    
    # ========== Entity Operations ==========
    
    def add_entity(
        self,
        entity_id: str,
        name: str,
        entity_type: str,
        citation: Optional[Citation] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add an entity to the graph with optional citation.
        
        If an entity with this ID already exists, the citation is merged
        into the existing entity's citations list (enabling same-named
        entities from different files to be unified).
        
        Args:
            entity_id: Unique identifier for the entity
            name: Human-readable entity name
            entity_type: Type classification (e.g., 'Class', 'Function', 'Service')
            citation: Source citation (file path, line numbers)
            properties: Additional properties (no raw content, only metadata)
            
        Returns:
            The entity_id (node ID in graph)
        """
        # Check if entity already exists (for merging citations)
        existing = self._graph.nodes.get(entity_id)
        
        if existing:
            # Entity exists - merge the new citation
            if citation:
                new_citation_dict = citation.to_dict()
                existing_citations = existing.get('citations', [])
                
                # Migrate legacy single 'citation' to list
                if 'citation' in existing and existing['citation']:
                    legacy = existing['citation']
                    if legacy not in existing_citations:
                        existing_citations.append(legacy)
                
                # Add new citation if not duplicate
                if new_citation_dict not in existing_citations:
                    existing_citations.append(new_citation_dict)
                
                # Update node with merged citations
                self._graph.nodes[entity_id]['citations'] = existing_citations
                self._graph.nodes[entity_id].pop('citation', None)  # Remove legacy field
                
                # Track source document
                if citation.doc_id:
                    self._source_doc_index[citation.doc_id].add(entity_id)
            
            logger.debug(f"Merged citation into existing entity: {entity_type} '{name}' ({entity_id})")
            return entity_id
        
        # New entity - prepare node data
        node_data = {
            'id': entity_id,
            'name': name,
            'type': entity_type,
        }
        
        # Store citation in list format from the start
        if citation:
            node_data['citations'] = [citation.to_dict()]
            # Track source document
            if citation.doc_id:
                self._source_doc_index[citation.doc_id].add(entity_id)
        
        # Add other properties (excluding any large content)
        if properties:
            # Filter out raw content fields
            excluded_keys = {'content', 'text', 'raw', 'body', 'source_content'}
            for key, value in properties.items():
                if key not in excluded_keys:
                    # Only store if serializable and reasonably sized
                    if isinstance(value, (str, int, float, bool, list, dict)) and \
                       (not isinstance(value, str) or len(value) < 1000):
                        node_data[key] = value
        
        # Add new node
        self._graph.add_node(entity_id, **node_data)
        
        # Update name index
        self._entity_index[name.lower()] = entity_id
        
        logger.debug(f"Added entity: {entity_type} '{name}' ({entity_id})")
        return entity_id
    
    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get entity by ID."""
        if self._graph.has_node(entity_id):
            return dict(self._graph.nodes[entity_id])
        return None
    
    def find_entity_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find entity by name (case-insensitive)."""
        node_id = self._entity_index.get(name.lower())
        if node_id:
            return self.get_entity(node_id)
        return None
    
    def get_entities_by_type(self, entity_type: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all entities of a specific type."""
        results = [
            dict(data)
            for _, data in self._graph.nodes(data=True)
            if data.get('type') == entity_type
        ]
        if limit:
            return results[:limit]
        return results
    
    def get_entities_by_layer(self, layer: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all entities in a specific layer (product, domain, service, code, etc.)."""
        results = [
            dict(data)
            for _, data in self._graph.nodes(data=True)
            if data.get('layer') == layer
        ]
        if limit:
            return results[:limit]
        return results
    
    def get_all_entities(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all entities in the graph."""
        results = [
            {'id': node_id, **dict(data)}
            for node_id, data in self._graph.nodes(data=True)
        ]
        if limit:
            return results[:limit]
        return results
    
    def get_all_entity_types(self) -> List[str]:
        """Get list of all entity types in the graph."""
        types = set()
        for _, data in self._graph.nodes(data=True):
            if 'type' in data:
                types.add(data['type'])
        return sorted(types)
    
    def update_entity(self, entity_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update entity properties.
        
        Args:
            entity_id: Entity to update
            updates: Properties to update (merged with existing)
            
        Returns:
            True if entity exists and was updated
        """
        if not self._graph.has_node(entity_id):
            return False
        
        # Filter out raw content
        excluded_keys = {'content', 'text', 'raw', 'body', 'source_content'}
        filtered_updates = {
            k: v for k, v in updates.items()
            if k not in excluded_keys
        }
        
        current = dict(self._graph.nodes[entity_id])
        current.update(filtered_updates)
        
        for key, value in current.items():
            self._graph.nodes[entity_id][key] = value
        
        return True
    
    def remove_entity(self, entity_id: str) -> bool:
        """Remove entity and its edges from the graph."""
        if not self._graph.has_node(entity_id):
            return False
        
        # Remove from indices
        entity = self.get_entity(entity_id)
        if entity:
            name = entity.get('name', '').lower()
            if name in self._entity_index:
                del self._entity_index[name]
            
            citation_data = entity.get('citation', {})
            if isinstance(citation_data, dict):
                doc_id = citation_data.get('doc_id')
                if doc_id and entity_id in self._source_doc_index.get(doc_id, set()):
                    self._source_doc_index[doc_id].discard(entity_id)
        
        self._graph.remove_node(entity_id)
        return True
    
    # ========== Relation Operations ==========
    
    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Add a directed relation between entities.
        
        Args:
            source_id: Source entity ID
            target_id: Target entity ID
            relation_type: Type of relationship (e.g., 'CALLS', 'IMPORTS', 'INHERITS')
            properties: Additional edge properties
            
        Returns:
            True if relation was added
        """
        if not self._graph.has_node(source_id):
            logger.warning(f"Source entity {source_id} not found")
            return False
        if not self._graph.has_node(target_id):
            logger.warning(f"Target entity {target_id} not found")
            return False
        
        edge_data = {'relation_type': relation_type}
        if properties:
            edge_data.update(properties)
        
        self._graph.add_edge(source_id, target_id, **edge_data)
        logger.debug(f"Added relation: {source_id} --[{relation_type}]--> {target_id}")
        return True
    
    def get_relations(self, entity_id: str, direction: str = 'both') -> List[Dict[str, Any]]:
        """
        Get relations for an entity.
        
        Args:
            entity_id: Entity ID
            direction: 'outgoing', 'incoming', or 'both'
            
        Returns:
            List of relation dicts with source, target, type, properties
        """
        relations = []
        
        if direction in ('outgoing', 'both'):
            for _, target, data in self._graph.out_edges(entity_id, data=True):
                relations.append({
                    'source': entity_id,
                    'target': target,
                    'relation_type': data.get('relation_type'),
                    'properties': {k: v for k, v in data.items() if k != 'relation_type'}
                })
        
        if direction in ('incoming', 'both'):
            for source, _, data in self._graph.in_edges(entity_id, data=True):
                relations.append({
                    'source': source,
                    'target': entity_id,
                    'relation_type': data.get('relation_type'),
                    'properties': {k: v for k, v in data.items() if k != 'relation_type'}
                })
        
        return relations
    
    def remove_relation(self, source_id: str, target_id: str) -> bool:
        """Remove a relation between entities."""
        if self._graph.has_edge(source_id, target_id):
            self._graph.remove_edge(source_id, target_id)
            return True
        return False
    
    # ========== Graph Analysis ==========
    
    def get_neighbors(
        self,
        entity_id: str,
        max_depth: int = 1,
        relation_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get neighboring entities up to a certain depth.
        
        Args:
            entity_id: Starting entity
            max_depth: How many hops to traverse
            relation_types: Filter by relation types
            
        Returns:
            Dict with entities and relations
        """
        if not self._graph.has_node(entity_id):
            return {'entities': [], 'relations': []}
        
        visited = {entity_id}
        entities = [self.get_entity(entity_id)]
        relations = []
        
        current_level = [entity_id]
        
        for _ in range(max_depth):
            next_level = []
            
            for node in current_level:
                # Outgoing edges
                for _, target, data in self._graph.out_edges(node, data=True):
                    rel_type = data.get('relation_type')
                    if relation_types and rel_type not in relation_types:
                        continue
                    
                    relations.append({
                        'source': node,
                        'target': target,
                        'relation_type': rel_type,
                    })
                    
                    if target not in visited:
                        visited.add(target)
                        next_level.append(target)
                        entities.append(self.get_entity(target))
                
                # Incoming edges
                for source, _, data in self._graph.in_edges(node, data=True):
                    rel_type = data.get('relation_type')
                    if relation_types and rel_type not in relation_types:
                        continue
                    
                    relations.append({
                        'source': source,
                        'target': node,
                        'relation_type': rel_type,
                    })
                    
                    if source not in visited:
                        visited.add(source)
                        next_level.append(source)
                        entities.append(self.get_entity(source))
            
            current_level = next_level
        
        return {'entities': entities, 'relations': relations}
    
    def find_path(self, source_id: str, target_id: str) -> Optional[List[str]]:
        """Find shortest path between two entities."""
        if not self._graph.has_node(source_id) or not self._graph.has_node(target_id):
            return None
        
        try:
            path = nx.shortest_path(self._graph, source_id, target_id)
            return path
        except nx.NetworkXNoPath:
            return None
    
    def impact_analysis(
        self,
        entity_id: str,
        direction: str = 'downstream',
        max_depth: int = 3,
    ) -> Dict[str, Any]:
        """
        Analyze impact of changes to an entity.
        
        Args:
            entity_id: Entity to analyze
            direction: 'downstream' (what depends on this) or 'upstream' (what this depends on)
            max_depth: Maximum traversal depth
            
        Returns:
            Dict with impacted entities and paths
        """
        if not self._graph.has_node(entity_id):
            return {'impacted': [], 'paths': []}
        
        impacted = []
        paths = []
        
        # Use BFS for level-by-level analysis
        visited = {entity_id}
        queue = [(entity_id, [entity_id], 0)]
        
        while queue:
            current, path, depth = queue.pop(0)
            
            if depth >= max_depth:
                continue
            
            # Get edges based on direction
            if direction == 'downstream':
                edges = self._graph.in_edges(current, data=True)
            else:  # upstream
                edges = self._graph.out_edges(current, data=True)
            
            for edge in edges:
                if direction == 'downstream':
                    neighbor = edge[0]
                else:
                    neighbor = edge[1]
                
                if neighbor not in visited:
                    visited.add(neighbor)
                    new_path = path + [neighbor]
                    
                    entity = self.get_entity(neighbor)
                    impacted.append({
                        'entity': entity,
                        'depth': depth + 1,
                        'path': new_path,
                    })
                    paths.append(new_path)
                    
                    queue.append((neighbor, new_path, depth + 1))
        
        return {'impacted': impacted, 'paths': paths}
    
    # ========== Search Operations ==========
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        entity_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search entities by name or properties.
        
        Args:
            query: Search query string
            top_k: Maximum results to return
            entity_type: Filter by entity type
            
        Returns:
            List of matching entities with scores
        """
        results = []
        query_lower = query.lower()
        
        for node_id, data in self._graph.nodes(data=True):
            # Type filter
            if entity_type and data.get('type') != entity_type:
                continue
            
            # Name match
            name = data.get('name', '')
            if query_lower in name.lower():
                results.append({
                    'entity': dict(data),
                    'score': 1.0 if query_lower == name.lower() else 0.5,
                    'match_field': 'name',
                })
                continue
            
            # Property match
            for key, value in data.items():
                if key in ('id', 'name', 'type', 'citation'):
                    continue
                if isinstance(value, str) and query_lower in value.lower():
                    results.append({
                        'entity': dict(data),
                        'score': 0.3,
                        'match_field': key,
                    })
                    break
        
        # Sort by score and limit
        results.sort(key=lambda x: -x['score'])
        return results[:top_k]
    
    def get_entities_by_source(self, doc_id: str) -> List[Dict[str, Any]]:
        """Get all entities from a specific source document."""
        node_ids = self._source_doc_index.get(doc_id, set())
        return [self.get_entity(nid) for nid in node_ids if nid]
    
    def get_entities_by_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Get all entities with citations from a specific file."""
        results = []
        for _, data in self._graph.nodes(data=True):
            citation = data.get('citation', {})
            if isinstance(citation, dict) and citation.get('file_path') == file_path:
                results.append(dict(data))
        return results
    
    # ========== Delta Operations ==========
    
    def remove_entities_by_source(self, doc_id: str) -> int:
        """
        Remove all entities from a specific source document.
        Used for delta updates to clean stale entities.
        
        Returns:
            Number of entities removed
        """
        node_ids = list(self._source_doc_index.get(doc_id, set()))
        for node_id in node_ids:
            self.remove_entity(node_id)
        return len(node_ids)
    
    def remove_entities_by_file(self, file_path: str) -> int:
        """
        Remove all entities with citations from a specific file.
        Used for delta updates when a file changes.
        
        Returns:
            Number of entities removed
        """
        to_remove = []
        for node_id, data in self._graph.nodes(data=True):
            citation = data.get('citation', {})
            if isinstance(citation, dict) and citation.get('file_path') == file_path:
                to_remove.append(node_id)
        
        for node_id in to_remove:
            self.remove_entity(node_id)
        
        return len(to_remove)
    
    # ========== Schema Operations ==========
    
    def set_schema(self, schema: Dict[str, Any]) -> None:
        """Store the discovered entity schema."""
        self._schema = schema
    
    def get_schema(self) -> Optional[Dict[str, Any]]:
        """Get the discovered schema."""
        return self._schema
    
    # ========== Statistics ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        entity_types = defaultdict(int)
        relation_types = defaultdict(int)
        sources = set()
        
        for _, data in self._graph.nodes(data=True):
            if 'type' in data:
                entity_types[data['type']] += 1
            citation = data.get('citation', {})
            if isinstance(citation, dict) and citation.get('source_toolkit'):
                sources.add(citation['source_toolkit'])
        
        for _, _, data in self._graph.edges(data=True):
            if 'relation_type' in data:
                relation_types[data['relation_type']] += 1
        
        return {
            'node_count': self._graph.number_of_nodes(),
            'edge_count': self._graph.number_of_edges(),
            'entity_types': dict(entity_types),
            'relation_types': dict(relation_types),
            'source_toolkits': sorted(sources),
            'last_saved': self._metadata.get('last_saved'),
        }
    
    # ========== Persistence ==========
    
    def dump_to_json(self, path: str) -> None:
        """
        Export graph to JSON file using node_link format.
        
        The graph file is lightweight - contains only:
        - Entity metadata and citations (no raw content)
        - Relationships
        - Schema and indices
        
        Args:
            path: File path to write JSON
        """
        data = nx.node_link_data(self._graph)
        
        # Add index data for persistence
        data['_indices'] = {
            'entity_index': self._entity_index,
            'source_doc_index': {k: list(v) for k, v in self._source_doc_index.items()}
        }
        
        # Add schema if discovered
        if self._schema:
            data['_schema'] = self._schema
        
        # Add metadata
        self._metadata['last_saved'] = datetime.now().isoformat()
        self._metadata['version'] = '2.0'  # Citation-based lightweight format
        data['_metadata'] = self._metadata
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Saved graph to {path} ({self._graph.number_of_nodes()} entities, {self._graph.number_of_edges()} relations)")
    
    def load_from_json(self, path: str) -> None:
        """
        Load graph from JSON file.
        
        Args:
            path: File path to read JSON from
            
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Restore indices
        indices = data.pop('_indices', {})
        self._entity_index = indices.get('entity_index', {})
        self._source_doc_index = defaultdict(set)
        for k, v in indices.get('source_doc_index', {}).items():
            self._source_doc_index[k] = set(v)
        
        # Restore schema
        self._schema = data.pop('_schema', None)
        
        # Restore metadata
        self._metadata = data.pop('_metadata', {})
        
        # Restore graph (use edges="links" for networkx 3.6+ compatibility)
        self._graph = nx.node_link_graph(data, edges="links")
        
        logger.info(f"Loaded graph from {path} ({self._graph.number_of_nodes()} entities, {self._graph.number_of_edges()} relations)")
    
    def clear(self) -> None:
        """Clear all data from the graph."""
        self._graph.clear()
        self._entity_index.clear()
        self._source_doc_index.clear()
        self._schema = None
        self._metadata = {}
    
    # ========== Subgraph Operations ==========
    
    def get_subgraph(self, node_ids: List[str]) -> 'KnowledgeGraph':
        """
        Get a subgraph containing only specified nodes and their edges.
        
        Args:
            node_ids: List of node IDs to include
            
        Returns:
            New KnowledgeGraph instance with subgraph
        """
        subgraph = KnowledgeGraph()
        subgraph._graph = self._graph.subgraph(node_ids).copy()
        
        # Rebuild indices for subgraph
        for node_id, data in subgraph._graph.nodes(data=True):
            name = data.get('name', '').lower()
            if name:
                subgraph._entity_index[name] = node_id
            
            citation = data.get('citation', {})
            if isinstance(citation, dict):
                doc_id = citation.get('doc_id')
                if doc_id:
                    subgraph._source_doc_index[doc_id].add(node_id)
        
        return subgraph
    
    def get_connected_component(self, node_id: str) -> List[str]:
        """
        Get all nodes in the same connected component as the given node.
        
        Args:
            node_id: Starting node ID
            
        Returns:
            List of node IDs in the connected component
        """
        if not self._graph.has_node(node_id):
            return []
        
        # For directed graphs, use weakly connected components
        undirected = self._graph.to_undirected()
        component = nx.node_connected_component(undirected, node_id)
        return list(component)
    
    # ========== Citation Helpers ==========
    
    def get_citation(self, entity_id: str) -> Optional[Citation]:
        """Get citation for an entity."""
        entity = self.get_entity(entity_id)
        if entity and 'citation' in entity:
            return Citation.from_dict(entity['citation'])
        return None
    
    def get_citations_for_query(self, query: str, top_k: int = 5) -> List[Citation]:
        """
        Get citations for entities matching a query.
        
        Useful for the LLM to retrieve source content on-demand.
        
        Args:
            query: Search query
            top_k: Maximum citations to return
            
        Returns:
            List of Citation objects
        """
        results = self.search(query, top_k=top_k)
        citations = []
        
        for result in results:
            entity = result['entity']
            if 'citation' in entity:
                citations.append(Citation.from_dict(entity['citation']))
        
        return citations
    
    def export_citations_summary(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Export a summary of all citations grouped by file.
        
        Returns:
            Dict mapping file paths to lists of entity summaries
        """
        by_file: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        for node_id, data in self._graph.nodes(data=True):
            citation = data.get('citation', {})
            if isinstance(citation, dict) and citation.get('file_path'):
                by_file[citation['file_path']].append({
                    'entity_id': node_id,
                    'name': data.get('name'),
                    'type': data.get('type'),
                    'line_start': citation.get('line_start'),
                    'line_end': citation.get('line_end'),
                })
        
        # Sort entities within each file by line number
        for file_path in by_file:
            by_file[file_path].sort(key=lambda x: x.get('line_start') or 0)
        
        return dict(by_file)
