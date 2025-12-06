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
    - Enhanced search with fuzzy matching, token-based search, and file path patterns
    """
    
    # Layer classification based on entity types
    LAYER_TYPE_MAPPING = {
        'code': {
            'class', 'function', 'method', 'module', 'import', 'variable', 
            'constant', 'attribute', 'decorator', 'exception', 'enum',
            'class_reference', 'class_import', 'function_import', 'function_reference',
            'function_call', 'method_call', 'test_function', 'pydanticmodel'
        },
        'service': {
            'api_endpoint', 'rpc_method', 'route', 'service', 'handler',
            'controller', 'middleware', 'event', 'sio', 'rpc'
        },
        'data': {
            'model', 'schema', 'field', 'table', 'database', 'migration',
            'entity', 'pydantic_model', 'dictionary', 'list', 'object'
        },
        'product': {
            'feature', 'capability', 'platform', 'product', 'application',
            'menu', 'ui_element', 'ui_component', 'interface_element'
        },
        'domain': {
            'concept', 'process', 'action', 'use_case', 'workflow',
            'requirement', 'guideline', 'best_practice'
        },
        'documentation': {
            'document', 'guide', 'section', 'subsection', 'tip',
            'example', 'resource', 'reference', 'documentation'
        },
        'configuration': {
            'configuration', 'configuration_option', 'configuration_section',
            'setting', 'credential', 'secret', 'integration'
        },
        'testing': {
            'test', 'test_case', 'test_function', 'fixture', 'mock'
        },
        'tooling': {
            'tool', 'toolkit', 'command', 'node_type', 'node'
        },
        'knowledge': {
            # Facts extracted from code and documentation
            'fact',
            # Code-specific fact types
            'algorithm', 'behavior', 'validation', 'dependency', 'error_handling',
            # Text-specific fact types
            'decision', 'definition', 'date', 'contact',
        },
        'structure': {
            # File-level container nodes
            'file', 'source_file', 'document_file', 'config_file', 'web_file',
            # Directory/package structure
            'directory', 'package',
        }
    }
    
    # Reverse mapping: type -> layer
    TYPE_TO_LAYER = {}
    for layer, types in LAYER_TYPE_MAPPING.items():
        for t in types:
            TYPE_TO_LAYER[t] = layer
    
    def __init__(self):
        """Initialize an empty knowledge graph."""
        if nx is None:
            raise ImportError("networkx is required for KnowledgeGraph. Install with: pip install networkx>=3.0")
        
        self._graph: DiGraph = DiGraph()
        self._entity_index: Dict[str, Set[str]] = defaultdict(set)  # name -> set of node_ids (handles duplicates)
        self._type_index: Dict[str, Set[str]] = defaultdict(set)  # type (lowercase) -> node_ids
        self._file_index: Dict[str, Set[str]] = defaultdict(set)  # file_path -> node_ids
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
        
        # Auto-assign layer based on entity type
        inferred_layer = self.TYPE_TO_LAYER.get(entity_type.lower())
        if inferred_layer:
            node_data['layer'] = inferred_layer
        
        # Store citation in list format from the start
        if citation:
            node_data['citations'] = [citation.to_dict()]
            # Track source document
            if citation.doc_id:
                self._source_doc_index[citation.doc_id].add(entity_id)
            # Track file index
            if citation.file_path:
                self._file_index[citation.file_path].add(entity_id)
        
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
        
        # Update indices - store ALL entities with this name (not just one)
        self._entity_index[name.lower()].add(entity_id)
        self._type_index[entity_type.lower()].add(entity_id)
        
        logger.debug(f"Added entity: {entity_type} '{name}' ({entity_id})")
        return entity_id
    
    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get entity by ID."""
        if self._graph.has_node(entity_id):
            return dict(self._graph.nodes[entity_id])
        return None
    
    def find_entity_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Find entity by name (case-insensitive).
        
        If multiple entities have the same name, returns the first one found.
        Use find_all_entities_by_name to get all matches.
        """
        node_ids = self._entity_index.get(name.lower(), set())
        if node_ids:
            # Return first match
            return self.get_entity(next(iter(node_ids)))
        return None
    
    def find_all_entities_by_name(self, name: str) -> List[Dict[str, Any]]:
        """
        Find all entities with the given name (case-insensitive).
        
        Returns all entities if multiple have the same name but different types.
        """
        node_ids = self._entity_index.get(name.lower(), set())
        return [self.get_entity(nid) for nid in node_ids if nid]
    
    def get_entities_by_type(self, entity_type: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all entities of a specific type (case-insensitive).
        
        Also checks layer-based type groups. For example, searching for 'code'
        will return classes, functions, methods, etc.
        """
        entity_type_lower = entity_type.lower()
        
        # Check if this is a layer name
        if entity_type_lower in self.LAYER_TYPE_MAPPING:
            # Get all types in this layer
            results = []
            for t in self.LAYER_TYPE_MAPPING[entity_type_lower]:
                node_ids = self._type_index.get(t, set())
                for nid in node_ids:
                    entity = self.get_entity(nid)
                    if entity:
                        results.append(entity)
            if limit:
                return results[:limit]
            return results
        
        # Use type index for fast lookup
        node_ids = self._type_index.get(entity_type_lower, set())
        if node_ids:
            results = [self.get_entity(nid) for nid in node_ids if nid]
            if limit:
                return results[:limit]
            return results
        
        # Fallback: linear scan (for types not in index)
        results = [
            dict(data)
            for _, data in self._graph.nodes(data=True)
            if data.get('type', '').lower() == entity_type_lower
        ]
        if limit:
            return results[:limit]
        return results
    
    def get_entities_by_layer(self, layer: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all entities in a specific layer (product, domain, service, code, data, etc.).
        
        Layer is inferred from entity type if not explicitly set on the entity.
        """
        layer_lower = layer.lower()
        
        # Get types that belong to this layer
        layer_types = self.LAYER_TYPE_MAPPING.get(layer_lower, set())
        
        results = []
        for _, data in self._graph.nodes(data=True):
            # Check explicit layer
            if data.get('layer', '').lower() == layer_lower:
                results.append(dict(data))
                continue
            
            # Check if type belongs to this layer
            entity_type = data.get('type', '').lower()
            if entity_type in layer_types:
                results.append(dict(data))
        
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
        
        # Remove from all indices
        entity = self.get_entity(entity_id)
        if entity:
            # Remove from name index
            name = entity.get('name', '').lower()
            if name in self._entity_index:
                self._entity_index[name].discard(entity_id)
                if not self._entity_index[name]:
                    del self._entity_index[name]
            
            # Remove from type index
            entity_type = entity.get('type', '').lower()
            if entity_type in self._type_index:
                self._type_index[entity_type].discard(entity_id)
                if not self._type_index[entity_type]:
                    del self._type_index[entity_type]
            
            # Remove from file index
            file_path = entity.get('file_path', '')
            if file_path in self._file_index:
                self._file_index[file_path].discard(entity_id)
                if not self._file_index[file_path]:
                    del self._file_index[file_path]
            
            # Remove from source doc index
            for citation in entity.get('citations', []):
                if isinstance(citation, dict):
                    doc_id = citation.get('doc_id')
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
    
    def get_relations_by_source(
        self, 
        source_toolkit: str,
        relation_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all relations from a specific source toolkit.
        
        Args:
            source_toolkit: Name of source toolkit (e.g., 'github', 'jira')
            relation_type: Optional filter by relation type
            
        Returns:
            List of relations with their properties
        """
        relations = []
        
        for source, target, data in self._graph.edges(data=True):
            # Check if this relation is from the specified source
            rel_source = data.get('source_toolkit')
            if rel_source == source_toolkit:
                # Filter by relation type if specified
                if relation_type is None or data.get('relation_type') == relation_type:
                    relations.append({
                        'source': source,
                        'target': target,
                        'relation_type': data.get('relation_type'),
                        'source_toolkit': rel_source,
                        'properties': {k: v for k, v in data.items() 
                                     if k not in ('relation_type', 'source_toolkit')}
                    })
        
        return relations
    
    def get_cross_source_relations(self) -> List[Dict[str, Any]]:
        """
        Get relations that connect entities from different sources.
        
        These are particularly valuable for understanding how different
        data sources relate to each other (e.g., Jira ticket references GitHub PR).
        
        Returns:
            List of cross-source relations
        """
        cross_source = []
        
        for source, target, data in self._graph.edges(data=True):
            source_node = self._graph.nodes.get(source, {})
            target_node = self._graph.nodes.get(target, {})
            
            # Get source toolkits from entity citations
            source_citations = source_node.get('citations', [])
            target_citations = target_node.get('citations', [])
            
            if not source_citations or not target_citations:
                continue
            
            # Get unique source toolkits for each entity
            source_toolkits = set()
            target_toolkits = set()
            
            for citation in source_citations:
                if isinstance(citation, dict):
                    toolkit = citation.get('source_toolkit')
                elif hasattr(citation, 'source_toolkit'):
                    toolkit = citation.source_toolkit
                else:
                    toolkit = None
                if toolkit:
                    source_toolkits.add(toolkit)
            
            for citation in target_citations:
                if isinstance(citation, dict):
                    toolkit = citation.get('source_toolkit')
                elif hasattr(citation, 'source_toolkit'):
                    toolkit = citation.source_toolkit
                else:
                    toolkit = None
                if toolkit:
                    target_toolkits.add(toolkit)
            
            # Check if entities come from different sources
            if source_toolkits and target_toolkits and source_toolkits != target_toolkits:
                cross_source.append({
                    'source': source,
                    'target': target,
                    'source_toolkits': list(source_toolkits),
                    'target_toolkits': list(target_toolkits),
                    'relation_type': data.get('relation_type'),
                    'relation_source': data.get('source_toolkit'),
                    'properties': {k: v for k, v in data.items() 
                                 if k not in ('relation_type', 'source_toolkit')}
                })
        
        return cross_source
    
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
    
    def _tokenize(self, text: str) -> Set[str]:
        """Tokenize text into searchable tokens (handles camelCase, snake_case, etc.)."""
        import re
        if not text:
            return set()
        
        # Split on non-alphanumeric
        words = re.split(r'[^a-zA-Z0-9]+', text.lower())
        
        # Also split camelCase
        tokens = set()
        for word in words:
            if word:
                tokens.add(word)
                # Split camelCase: "ChatMessageHandler" -> ["chat", "message", "handler"]
                camel_parts = re.findall(r'[a-z]+|[A-Z][a-z]*|[0-9]+', word)
                tokens.update(p.lower() for p in camel_parts if p)
        
        return tokens
    
    def _calculate_match_score(
        self,
        query_tokens: Set[str],
        query_lower: str,
        name: str,
        entity_type: str,
        description: str,
        file_path: str,
    ) -> tuple:
        """
        Calculate match score for an entity.
        
        Returns (score, match_field) tuple.
        Higher scores mean better matches.
        """
        name_lower = name.lower()
        name_tokens = self._tokenize(name)
        
        # Exact name match (highest priority)
        if query_lower == name_lower:
            return (1.0, 'name_exact')
        
        # Exact substring in name
        if query_lower in name_lower:
            # Prefer matches at word boundaries
            score = 0.85 if name_lower.startswith(query_lower) else 0.75
            return (score, 'name_contains')
        
        # Token overlap in name (for camelCase matching)
        if query_tokens and name_tokens:
            overlap = len(query_tokens & name_tokens)
            if overlap > 0:
                # Score based on percentage of query tokens matched
                score = 0.6 * (overlap / len(query_tokens))
                if overlap == len(query_tokens):  # All query tokens found
                    score = 0.7
                return (score, 'name_tokens')
        
        # Check file path
        if file_path and query_lower in file_path.lower():
            return (0.55, 'file_path')
        
        # Check description
        if description:
            desc_lower = description.lower()
            if query_lower in desc_lower:
                return (0.5, 'description')
            # Token match in description
            desc_tokens = self._tokenize(description)
            if query_tokens and desc_tokens:
                overlap = len(query_tokens & desc_tokens)
                if overlap > 0:
                    score = 0.35 * (overlap / len(query_tokens))
                    return (score, 'description_tokens')
        
        # Check entity type
        if query_lower in entity_type.lower():
            return (0.3, 'type')
        
        return (0.0, None)
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        entity_type: Optional[str] = None,
        layer: Optional[str] = None,
        file_pattern: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search entities with enhanced matching capabilities.
        
        Supports:
        - Exact and partial name matching
        - Token-based matching (handles camelCase, snake_case)
        - Description and property search
        - File path pattern matching
        - Type and layer filtering
        
        Args:
            query: Search query string
            top_k: Maximum results to return
            entity_type: Filter by entity type (case-insensitive)
            layer: Filter by layer (code, service, data, product, etc.)
            file_pattern: Filter by file path pattern (glob-like)
            
        Returns:
            List of matching entities with scores
        """
        import re
        
        results = []
        query_lower = query.lower().strip()
        query_tokens = self._tokenize(query)
        
        # Get layer types for filtering
        layer_types = set()
        if layer:
            layer_types = self.LAYER_TYPE_MAPPING.get(layer.lower(), set())
        
        # Compile file pattern if provided
        file_regex = None
        if file_pattern:
            # Convert glob pattern to regex
            pattern = file_pattern.replace('.', r'\.').replace('*', '.*').replace('?', '.')
            try:
                file_regex = re.compile(pattern, re.IGNORECASE)
            except re.error:
                pass
        
        for node_id, data in self._graph.nodes(data=True):
            # Type filter (case-insensitive)
            data_type = data.get('type', '').lower()
            if entity_type and data_type != entity_type.lower():
                continue
            
            # Layer filter
            if layer:
                entity_layer = data.get('layer', '').lower()
                if entity_layer != layer.lower() and data_type not in layer_types:
                    continue
            
            # File pattern filter
            citations = data.get('citations', [])
            if not citations and 'citation' in data:
                citations = [data['citation']]
            
            file_paths = [c.get('file_path', '') for c in citations if isinstance(c, dict)]
            primary_file = file_paths[0] if file_paths else data.get('file_path', '')
            
            if file_regex and primary_file:
                if not file_regex.search(primary_file):
                    continue
            
            # Calculate match score
            name = data.get('name', '')
            description = data.get('description', '')
            if isinstance(data.get('properties'), dict):
                description = description or data['properties'].get('description', '')
            
            score, match_field = self._calculate_match_score(
                query_tokens, query_lower, name, data_type, description, primary_file
            )
            
            if score > 0:
                results.append({
                    'entity': dict(data),
                    'score': score,
                    'match_field': match_field,
                })
        
        # Sort by score (descending), then by name
        results.sort(key=lambda x: (-x['score'], x['entity'].get('name', '').lower()))
        return results[:top_k]
    
    def search_by_file(self, file_path_pattern: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search entities by file path pattern.
        
        Args:
            file_path_pattern: Glob-like pattern (e.g., "api/*.py", "**/chat*.py")
            limit: Maximum results
            
        Returns:
            List of entities from matching files
        """
        import re
        
        # Convert glob to regex
        pattern = file_path_pattern.replace('.', r'\.').replace('**', '.*').replace('*', '[^/]*').replace('?', '.')
        try:
            file_regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return []
        
        results = []
        for file_path, node_ids in self._file_index.items():
            if file_regex.search(file_path):
                for nid in node_ids:
                    entity = self.get_entity(nid)
                    if entity:
                        results.append(entity)
                        if len(results) >= limit:
                            return results
        
        # Also check entities with file_path attribute (backup)
        if not results:
            for _, data in self._graph.nodes(data=True):
                fp = data.get('file_path', '')
                if fp and file_regex.search(fp):
                    results.append(dict(data))
                    if len(results) >= limit:
                        break
        
        return results
    
    def search_advanced(
        self,
        query: Optional[str] = None,
        entity_types: Optional[List[str]] = None,
        layers: Optional[List[str]] = None,
        file_patterns: Optional[List[str]] = None,
        has_relations: Optional[bool] = None,
        min_citations: Optional[int] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Advanced search with multiple filter criteria.
        
        Args:
            query: Text search query (optional)
            entity_types: List of types to include (OR logic)
            layers: List of layers to include (OR logic)
            file_patterns: List of file patterns to include (OR logic)
            has_relations: If True, only entities with relations; if False, isolated entities
            min_citations: Minimum number of citations required
            top_k: Maximum results
            
        Returns:
            List of matching entities
        """
        import re
        
        # Build type filter set
        type_filter = set()
        if entity_types:
            for t in entity_types:
                type_filter.add(t.lower())
                # Expand layer names to types
                if t.lower() in self.LAYER_TYPE_MAPPING:
                    type_filter.update(self.LAYER_TYPE_MAPPING[t.lower()])
        
        # Build layer filter set
        layer_filter = set()
        if layers:
            for l in layers:
                layer_filter.add(l.lower())
        
        # Build file regex patterns
        file_regexes = []
        if file_patterns:
            for fp in file_patterns:
                pattern = fp.replace('.', r'\.').replace('**', '.*').replace('*', '[^/]*')
                try:
                    file_regexes.append(re.compile(pattern, re.IGNORECASE))
                except re.error:
                    pass
        
        query_tokens = self._tokenize(query) if query else set()
        query_lower = query.lower().strip() if query else ''
        
        results = []
        
        for node_id, data in self._graph.nodes(data=True):
            data_type = data.get('type', '').lower()
            data_layer = data.get('layer', '').lower() or self.TYPE_TO_LAYER.get(data_type, '')
            
            # Type filter
            if type_filter and data_type not in type_filter:
                continue
            
            # Layer filter
            if layer_filter and data_layer not in layer_filter:
                continue
            
            # File pattern filter
            file_path = data.get('file_path', '')
            if file_regexes:
                if not any(rx.search(file_path) for rx in file_regexes):
                    continue
            
            # Relations filter
            if has_relations is not None:
                has_edges = (
                    self._graph.in_degree(node_id) > 0 or 
                    self._graph.out_degree(node_id) > 0
                )
                if has_relations and not has_edges:
                    continue
                if not has_relations and has_edges:
                    continue
            
            # Citations filter
            if min_citations:
                citations = data.get('citations', [])
                if len(citations) < min_citations:
                    continue
            
            # Text search
            score = 1.0
            match_field = 'filter'
            
            if query:
                name = data.get('name', '')
                description = data.get('description', '')
                if isinstance(data.get('properties'), dict):
                    description = description or data['properties'].get('description', '')
                
                score, match_field = self._calculate_match_score(
                    query_tokens, query_lower, name, data_type, description, file_path
                )
                
                if score == 0:
                    continue
            
            results.append({
                'entity': dict(data),
                'score': score,
                'match_field': match_field,
            })
        
        results.sort(key=lambda x: (-x['score'], x['entity'].get('name', '').lower()))
        return results[:top_k]
    
    def get_entities_by_source(self, doc_id: str) -> List[Dict[str, Any]]:
        """Get all entities from a specific source document."""
        node_ids = self._source_doc_index.get(doc_id, set())
        return [self.get_entity(nid) for nid in node_ids if nid]
    
    def get_entities_by_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Get all entities with citations from a specific file."""
        # First try the file index
        node_ids = self._file_index.get(file_path, set())
        if node_ids:
            return [self.get_entity(nid) for nid in node_ids if nid]
        
        # Fallback to linear scan for partial matches
        results = []
        for _, data in self._graph.nodes(data=True):
            # Check file_path attribute
            if data.get('file_path') == file_path:
                results.append(dict(data))
                continue
            
            # Check citations
            for citation in data.get('citations', []):
                if isinstance(citation, dict) and citation.get('file_path') == file_path:
                    results.append(dict(data))
                    break
        
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
        relations_by_source = defaultdict(int)
        
        for _, data in self._graph.nodes(data=True):
            if 'type' in data:
                entity_types[data['type']] += 1
            citation = data.get('citation', {})
            if isinstance(citation, dict) and citation.get('source_toolkit'):
                sources.add(citation['source_toolkit'])
        
        for _, _, data in self._graph.edges(data=True):
            if 'relation_type' in data:
                relation_types[data['relation_type']] += 1
            # Track relations by source
            rel_source = data.get('source_toolkit')
            if rel_source:
                relations_by_source[rel_source] += 1
        
        return {
            'node_count': self._graph.number_of_nodes(),
            'edge_count': self._graph.number_of_edges(),
            'entity_types': dict(entity_types),
            'relation_types': dict(relation_types),
            'source_toolkits': sorted(sources),
            'relations_by_source': dict(relations_by_source),
            'cross_source_relations': len(self.get_cross_source_relations()),
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
        # Use edges="links" explicitly for NetworkX 3.5+ compatibility
        # This ensures consistent format that visualize.py and load_from_json expect
        data = nx.node_link_data(self._graph, edges="links")
        
        # Add index data for persistence
        data['_indices'] = {
            'entity_index': {k: list(v) for k, v in self._entity_index.items()},
            'type_index': {k: list(v) for k, v in self._type_index.items()},
            'file_index': {k: list(v) for k, v in self._file_index.items()},
            'source_doc_index': {k: list(v) for k, v in self._source_doc_index.items()}
        }
        
        # Add schema if discovered
        if self._schema:
            data['_schema'] = self._schema
        
        # Add metadata
        self._metadata['last_saved'] = datetime.now().isoformat()
        self._metadata['version'] = '2.1'  # Enhanced indices version
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
        
        # Entity index - convert to set (handles both old string format and new list format)
        self._entity_index = defaultdict(set)
        for k, v in indices.get('entity_index', {}).items():
            if isinstance(v, list):
                self._entity_index[k] = set(v)
            elif isinstance(v, str):
                self._entity_index[k] = {v}  # Legacy format
        
        # Type index
        self._type_index = defaultdict(set)
        for k, v in indices.get('type_index', {}).items():
            self._type_index[k] = set(v) if isinstance(v, list) else set()
        
        # File index
        self._file_index = defaultdict(set)
        for k, v in indices.get('file_index', {}).items():
            self._file_index[k] = set(v) if isinstance(v, list) else set()
        
        # Source doc index
        self._source_doc_index = defaultdict(set)
        for k, v in indices.get('source_doc_index', {}).items():
            self._source_doc_index[k] = set(v) if isinstance(v, list) else set()
        
        # Restore schema
        self._schema = data.pop('_schema', None)
        
        # Restore metadata
        self._metadata = data.pop('_metadata', {})
        
        # Restore graph - handle both "links" and "edges" keys for compatibility
        # NetworkX 3.5+ defaults to "edges", but we write "links" for visualization compatibility
        if 'edges' in data and 'links' not in data:
            # Data uses new NetworkX 3.5+ default "edges" key - rename to "links" for node_link_graph
            data['links'] = data.pop('edges')
        
        self._graph = nx.node_link_graph(data, edges="links")
        
        # Rebuild missing indices if needed (for legacy graphs)
        if not self._type_index or not self._file_index:
            self._rebuild_indices()
        
        logger.info(f"Loaded graph from {path} ({self._graph.number_of_nodes()} entities, {self._graph.number_of_edges()} relations)")
    
    def _rebuild_indices(self) -> None:
        """Rebuild all indices from graph data (for legacy graph files)."""
        self._entity_index = defaultdict(set)
        self._type_index = defaultdict(set)
        self._file_index = defaultdict(set)
        self._source_doc_index = defaultdict(set)
        
        for node_id, data in self._graph.nodes(data=True):
            # Name index
            name = data.get('name', '').lower()
            if name:
                self._entity_index[name].add(node_id)
            
            # Type index
            entity_type = data.get('type', '').lower()
            if entity_type:
                self._type_index[entity_type].add(node_id)
            
            # File index (from file_path attribute)
            file_path = data.get('file_path', '')
            if file_path:
                self._file_index[file_path].add(node_id)
            
            # Also index from citations
            for citation in data.get('citations', []):
                if isinstance(citation, dict):
                    fp = citation.get('file_path', '')
                    if fp:
                        self._file_index[fp].add(node_id)
                    doc_id = citation.get('doc_id', '')
                    if doc_id:
                        self._source_doc_index[doc_id].add(node_id)
        
        logger.info(f"Rebuilt indices: {len(self._entity_index)} names, {len(self._type_index)} types, {len(self._file_index)} files")
    
    def clear(self) -> None:
        """Clear all data from the graph."""
        self._graph.clear()
        self._entity_index.clear()
        self._type_index.clear()
        self._file_index.clear()
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
