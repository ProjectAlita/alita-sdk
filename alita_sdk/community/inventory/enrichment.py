"""
Knowledge Graph Enrichment Utilities.

Post-processing tools to improve graph connectivity by:
1. Soft entity deduplication (merging same/similar entities with different types)
2. Linking semantically similar entities across sources
3. Creating cross-reference relationships (implements, documents, etc.)
4. Connecting orphan nodes to parent concepts

Usage:
    from alita_sdk.community.inventory.enrichment import GraphEnricher
    
    enricher = GraphEnricher(graph_path="./graph.json")
    enricher.enrich()
    enricher.save()
"""

import json
import logging
import re
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# Relationship types for cross-source linking
CROSS_SOURCE_RELATIONS = {
    # (source_type, target_type): relation_type
    ("class", "concept"): "implements",
    ("module", "concept"): "implements", 
    ("function", "concept"): "implements",
    ("method", "concept"): "implements",
    ("class", "entity"): "implements",
    ("module", "feature"): "implements",
    ("command", "feature"): "provides",
    ("toolkit", "toolkit_type"): "is_type_of",
    ("source_toolkit", "toolkit_type"): "is_type_of",
    ("SourceToolkit", "toolkit_type"): "is_type_of",
    ("import", "module"): "imports",
    ("import", "class"): "imports",
}

# Types that represent code vs documentation
CODE_TYPES = {
    "class", "module", "function", "method", "variable", "constant",
    "import", "attribute", "property", "command", "command_group",
    "SourceToolkit", "source_toolkit", "toolkit"
}

DOC_TYPES = {
    "concept", "entity", "feature", "Feature", "guide", "section",
    "step", "process", "guideline", "tutorial", "example", "overview",
    "toolkit_type", "platform", "software", "integration"
}

# Type priority for deduplication - higher priority types are preferred
# When merging entities with different types, the higher priority type wins
TYPE_PRIORITY = {
    # Code layer - highest priority (most specific)
    "class": 100,
    "function": 99,
    "method": 98,
    "module": 97,
    "interface": 96,
    "constant": 95,
    "variable": 94,
    "configuration": 93,
    
    # Service layer
    "service": 90,
    "api": 89,
    "endpoint": 88,
    "integration": 87,
    "payload": 86,
    
    # Data layer
    "database": 85,
    "table": 84,
    "column": 83,
    "constraint": 82,
    "index": 81,
    "migration": 80,
    "enum": 79,
    
    # Product layer
    "feature": 75,
    "epic": 74,
    "user_story": 73,
    "screen": 72,
    "ux_flow": 71,
    "ui_component": 70,
    "ui_field": 69,
    
    # Domain layer
    "domain_entity": 65,
    "attribute": 64,
    "business_rule": 63,
    "business_event": 62,
    "glossary_term": 61,
    "workflow": 60,
    
    # Testing layer
    "test_suite": 55,
    "test_case": 54,
    "test_step": 53,
    "assertion": 52,
    "test_data": 51,
    "defect": 50,
    "incident": 49,
    
    # Delivery layer
    "release": 45,
    "sprint": 44,
    "commit": 43,
    "pull_request": 42,
    "ticket": 41,
    "deployment": 40,
    
    # Organization layer
    "team": 35,
    "owner": 34,
    "stakeholder": 33,
    "repository": 32,
    "documentation": 31,
    
    # Toolkits (specific types)
    "toolkit": 28,
    "source_toolkit": 27,
    "SourceToolkit": 26,
    "command": 25,
    "command_group": 24,
    
    # Generic types - lowest priority
    "concept": 15,
    "entity": 14,
    "component": 13,
    "object": 12,
    "item": 11,
    "element": 10,
    "thing": 5,
    "unknown": 1,
}

# Types that should NOT be merged even with same name
# These represent fundamentally different concepts
NON_MERGEABLE_TYPES = {
    # Don't merge tests with the things they test
    ("test_case", "function"),
    ("test_case", "class"),
    ("test_case", "endpoint"),
    ("test_suite", "module"),
    
    # Don't merge documentation with code
    ("documentation", "module"),
    ("documentation", "class"),
    
    # Don't merge defects with features
    ("defect", "feature"),
    ("incident", "feature"),
    
    # Don't merge owners with owned items
    ("owner", "module"),
    ("owner", "service"),
    ("team", "repository"),
}

# Types that should NEVER be deduplicated even with exact same name
# These are context-dependent - same name in different files means different things
# e.g., "Get Tests" tool in Xray toolkit != "Get Tests" tool in Zephyr toolkit
NEVER_DEDUPLICATE_TYPES = {
    "tool",           # Tools belong to specific toolkits
    "property",       # Properties belong to specific entities
    "properties",     # Same as above
    "parameter",      # Parameters belong to specific functions/methods
    "argument",       # Arguments belong to specific functions
    "field",          # Fields belong to specific tables/forms
    "column",         # Columns belong to specific tables
    "attribute",      # Attributes belong to specific entities
    "option",         # Options belong to specific settings
    "setting",        # Settings may have same name in different contexts
    "step",           # Steps belong to specific workflows/processes
    "test_step",      # Test steps belong to specific test cases
    "ui_field",       # UI fields belong to specific screens
    "endpoint",       # Endpoints may have same path in different APIs
    "method",         # Methods belong to specific classes
}


class GraphEnricher:
    """
    Enriches a knowledge graph with cross-source relationships.
    """
    
    def __init__(self, graph_path: str):
        """
        Initialize enricher with a graph file.
        
        Args:
            graph_path: Path to the graph JSON file
        """
        self.graph_path = Path(graph_path)
        self.graph_data: Dict[str, Any] = {}
        self.nodes_by_id: Dict[str, Dict] = {}
        self.nodes_by_name: Dict[str, List[Dict]] = defaultdict(list)
        self.existing_links: Set[Tuple[str, str]] = set()
        self.new_links: List[Dict] = []
        self.id_mapping: Dict[str, str] = {}  # old_id -> new_id for merged nodes
        self.merged_nodes: List[Dict] = []  # Track merged node info
        self.stats = {
            "cross_source_links": 0,
            "orphan_links": 0,
            "similarity_links": 0,
            "entities_merged": 0,
            "merge_groups": 0,
        }
        
        self._load_graph()
    
    def _load_graph(self):
        """Load graph from JSON file."""
        with open(self.graph_path) as f:
            self.graph_data = json.load(f)
        
        # Build indices
        for node in self.graph_data.get("nodes", []):
            self.nodes_by_id[node["id"]] = node
            name_key = self._normalize_name(node.get("name", ""))
            self.nodes_by_name[name_key].append(node)
        
        # Track existing links
        for link in self.graph_data.get("links", []):
            self.existing_links.add((link["source"], link["target"]))
            self.existing_links.add((link["target"], link["source"]))  # bidirectional check
        
        logger.info(f"Loaded graph: {len(self.nodes_by_id)} nodes, {len(self.existing_links)//2} links")
    
    def _normalize_name(self, name: str) -> str:
        """Normalize entity name for matching."""
        # Convert to lowercase, replace separators with spaces
        name = name.lower().strip()
        name = re.sub(r'[_\-\.]+', ' ', name)
        name = re.sub(r'\s+', ' ', name)
        return name
    
    def _tokenize_name(self, name: str) -> Set[str]:
        """Tokenize name into significant words."""
        normalized = self._normalize_name(name)
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'of', 'to', 'in', 'for', 'on', 'with', 'by', 'is', 'it'}
        words = set(normalized.split())
        return words - stop_words
    
    def _get_source(self, node: Dict) -> str:
        """Determine source category for a node."""
        citations = node.get("citations", [])
        if node.get("citation"):
            citations = [node["citation"]]
        
        if not citations:
            return "unknown"
        
        fp = citations[0].get("file_path", "")
        if "alita-sdk" in fp or "alita_sdk" in fp:
            return "sdk"
        elif "elitea_core" in fp:
            return "core"
        elif "AlitaUI" in fp:
            return "ui"
        elif "docs/" in fp or fp.endswith(".md"):
            return "docs"
        else:
            return "other"
    
    def _is_code_type(self, entity_type: str) -> bool:
        """Check if entity type represents code."""
        return entity_type.lower() in {t.lower() for t in CODE_TYPES}
    
    def _is_doc_type(self, entity_type: str) -> bool:
        """Check if entity type represents documentation."""
        return entity_type.lower() in {t.lower() for t in DOC_TYPES}
    
    def _get_type_priority(self, entity_type: str) -> int:
        """Get priority score for entity type."""
        return TYPE_PRIORITY.get(entity_type.lower(), TYPE_PRIORITY.get(entity_type, 0))
    
    def _are_types_mergeable(self, type1: str, type2: str) -> bool:
        """Check if two entity types can be merged."""
        t1, t2 = type1.lower(), type2.lower()
        pair1 = (t1, t2)
        pair2 = (t2, t1)
        return pair1 not in NON_MERGEABLE_TYPES and pair2 not in NON_MERGEABLE_TYPES
    
    def _generate_merged_id(self, name: str, entity_type: str) -> str:
        """Generate a consistent ID for merged entity."""
        normalized = self._normalize_name(name)
        key = f"{entity_type}:{normalized}"
        return hashlib.md5(key.encode()).hexdigest()[:16]
    
    def _add_link(self, source_id: str, target_id: str, relation_type: str, reason: str):
        """Add a new link if it doesn't exist."""
        # Apply ID mapping for merged nodes
        source_id = self.id_mapping.get(source_id, source_id)
        target_id = self.id_mapping.get(target_id, target_id)
        
        if source_id == target_id:
            return False
        if (source_id, target_id) in self.existing_links:
            return False
        
        self.new_links.append({
            "source": source_id,
            "target": target_id,
            "relation_type": relation_type,
            "enrichment_reason": reason,
        })
        self.existing_links.add((source_id, target_id))
        self.existing_links.add((target_id, source_id))
        return True
    
    def _similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity ratio."""
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
    
    def _word_overlap_score(self, name1: str, name2: str) -> float:
        """Calculate word overlap score between two names."""
        words1 = self._tokenize_name(name1)
        words2 = self._tokenize_name(name2)
        if not words1 or not words2:
            return 0.0
        overlap = len(words1 & words2)
        return overlap / max(len(words1), len(words2))
    
    def deduplicate_entities(self, 
                            name_similarity_threshold: float = 0.95,
                            require_exact_match: bool = True) -> int:
        """
        Soft entity deduplication - merge entities that represent the same concept.
        
        CONSERVATIVE APPROACH: Only merges entities with EXACT same name (after normalization).
        This prevents incorrectly merging related but distinct concepts like:
        - "Artifact Toolkit" vs "Artifact Toolkit Guide" 
        - "Feature X" vs "Configure Feature X"
        
        Entities with different names but similar concepts should be LINKED, not merged.
        
        When merging, it:
        - Selects the best type based on TYPE_PRIORITY
        - Consolidates all citations from merged entities
        - Preserves all properties/attributes
        - Updates all links to point to the merged entity
        
        Args:
            name_similarity_threshold: Min similarity for fuzzy matching (only if require_exact_match=False)
            require_exact_match: If True (default), only merge exact name matches
            
        Returns:
            Number of entities merged
        """
        logger.info("Starting soft entity deduplication (exact match only)...")
        
        nodes = self.graph_data.get("nodes", [])
        if not nodes:
            return 0
        
        # Group entities by normalized name for exact matches
        name_groups: Dict[str, List[Dict]] = defaultdict(list)
        for node in nodes:
            name_key = self._normalize_name(node.get("name", ""))
            if len(name_key) >= 2:  # Skip very short names
                name_groups[name_key].append(node)
        
        # Find merge candidates - ONLY exact name matches
        merge_groups: List[List[Dict]] = []
        processed_ids: Set[str] = set()
        
        for name_key, group_nodes in name_groups.items():
            if len(group_nodes) < 2:
                continue
            
            # Skip types that should NEVER be deduplicated (context-dependent)
            # e.g., "Get Tests" tool in Xray != "Get Tests" tool in Zephyr
            group_nodes = [
                n for n in group_nodes 
                if n.get("type", "").lower() not in NEVER_DEDUPLICATE_TYPES
            ]
            if len(group_nodes) < 2:
                continue
            
            # Filter to only mergeable types within exact name matches
            mergeable_groups: List[List[Dict]] = []
            for node in group_nodes:
                if node["id"] in processed_ids:
                    continue
                
                # Try to add to existing group if types are compatible
                added = False
                for mg in mergeable_groups:
                    if all(self._are_types_mergeable(node.get("type", ""), m.get("type", "")) for m in mg):
                        mg.append(node)
                        added = True
                        break
                
                if not added:
                    mergeable_groups.append([node])
            
            # Add groups with multiple nodes
            for mg in mergeable_groups:
                if len(mg) >= 2:
                    merge_groups.append(mg)
                    for node in mg:
                        processed_ids.add(node["id"])
        
        # Optional: Phase 2 - Very high similarity fuzzy matches (disabled by default)
        if not require_exact_match:
            remaining_nodes = [n for n in nodes if n["id"] not in processed_ids]
            
            for i, node1 in enumerate(remaining_nodes):
                if node1["id"] in processed_ids:
                    continue
                
                name1 = self._normalize_name(node1.get("name", ""))
                if len(name1) < 3:
                    continue
                
                candidates = [node1]
                
                for node2 in remaining_nodes[i+1:]:
                    if node2["id"] in processed_ids:
                        continue
                    
                    name2 = self._normalize_name(node2.get("name", ""))
                    if len(name2) < 3:
                        continue
                    
                    # Check if types are mergeable
                    if not self._are_types_mergeable(node1.get("type", ""), node2.get("type", "")):
                        continue
                    
                    # Only merge on VERY high similarity (almost identical names)
                    str_sim = self._similarity(name1, name2)
                    if str_sim >= name_similarity_threshold:
                        candidates.append(node2)
                
                if len(candidates) >= 2:
                    merge_groups.append(candidates)
                    for node in candidates:
                        processed_ids.add(node["id"])
        
        # Execute merges
        logger.info(f"Found {len(merge_groups)} merge groups")
        
        nodes_to_remove: Set[str] = set()
        nodes_to_add: List[Dict] = []
        
        for group in merge_groups:
            merged = self._merge_entity_group(group)
            if merged:
                nodes_to_add.append(merged["new_node"])
                nodes_to_remove.update(merged["removed_ids"])
                self.merged_nodes.append(merged)
                self.stats["entities_merged"] += len(merged["removed_ids"])
        
        self.stats["merge_groups"] = len(merge_groups)
        
        # Update nodes list
        self.graph_data["nodes"] = [n for n in nodes if n["id"] not in nodes_to_remove]
        self.graph_data["nodes"].extend(nodes_to_add)
        
        # Update links to use new IDs
        self._update_links_after_merge()
        
        # Rebuild indices
        self._rebuild_indices()
        
        logger.info(f"Deduplication complete: {self.stats['entities_merged']} entities merged into {self.stats['merge_groups']} groups")
        
        return self.stats["entities_merged"]
    
    def _merge_entity_group(self, group: List[Dict]) -> Optional[Dict]:
        """
        Merge a group of entities into a single entity.
        
        Returns merge info dict or None if merge failed.
        """
        if len(group) < 2:
            return None
        
        # Select best type based on priority
        best_node = max(group, key=lambda n: self._get_type_priority(n.get("type", "")))
        best_type = best_node.get("type", "entity")
        
        # Use the name from the highest priority node
        best_name = best_node.get("name", "")
        
        # Generate merged ID
        new_id = self._generate_merged_id(best_name, best_type)
        
        # Collect all citations
        all_citations = []
        all_sources = set()
        for node in group:
            if "citations" in node:
                all_citations.extend(node["citations"])
            if "citation" in node:
                all_citations.append(node["citation"])
            all_sources.add(self._get_source(node))
        
        # Remove duplicate citations
        seen_citations = set()
        unique_citations = []
        for cit in all_citations:
            cit_key = (cit.get("file_path", ""), cit.get("chunk_index", 0))
            if cit_key not in seen_citations:
                seen_citations.add(cit_key)
                unique_citations.append(cit)
        
        # Collect all properties
        all_properties = {}
        for node in group:
            if "properties" in node:
                all_properties.update(node["properties"])
        
        # Collect all types as alternative_types
        all_types = list(set(n.get("type", "") for n in group if n.get("type")))
        all_types = [t for t in all_types if t != best_type]
        
        # Create merged node
        merged_node = {
            "id": new_id,
            "name": best_name,
            "type": best_type,
            "citations": unique_citations,
            "sources": list(all_sources),
            "merged_from": [n["id"] for n in group],
            "alternative_types": all_types,
        }
        
        if all_properties:
            merged_node["properties"] = all_properties
        
        # Add description from best node
        if "description" in best_node:
            merged_node["description"] = best_node["description"]
        else:
            # Try to get description from any node
            for node in group:
                if "description" in node:
                    merged_node["description"] = node["description"]
                    break
        
        # Map old IDs to new ID
        removed_ids = []
        for node in group:
            old_id = node["id"]
            self.id_mapping[old_id] = new_id
            removed_ids.append(old_id)
        
        return {
            "new_node": merged_node,
            "removed_ids": removed_ids,
            "merged_types": [n.get("type", "") for n in group],
        }
    
    def _update_links_after_merge(self):
        """Update all links to use merged node IDs."""
        updated_links = []
        seen_links = set()
        
        for link in self.graph_data.get("links", []):
            source = self.id_mapping.get(link["source"], link["source"])
            target = self.id_mapping.get(link["target"], link["target"])
            
            # Skip self-links and duplicates
            if source == target:
                continue
            
            link_key = (source, target, link.get("relation_type", ""))
            if link_key in seen_links:
                continue
            seen_links.add(link_key)
            
            updated_link = link.copy()
            updated_link["source"] = source
            updated_link["target"] = target
            updated_links.append(updated_link)
        
        self.graph_data["links"] = updated_links
    
    def _rebuild_indices(self):
        """Rebuild internal indices after modifications."""
        self.nodes_by_id.clear()
        self.nodes_by_name.clear()
        self.existing_links.clear()
        
        for node in self.graph_data.get("nodes", []):
            self.nodes_by_id[node["id"]] = node
            name_key = self._normalize_name(node.get("name", ""))
            self.nodes_by_name[name_key].append(node)
        
        for link in self.graph_data.get("links", []):
            self.existing_links.add((link["source"], link["target"]))
            self.existing_links.add((link["target"], link["source"]))
    
    def enrich_cross_source_links(self, min_similarity: float = 0.85):
        """
        Create links between entities with similar names across different sources.
        
        For example, link SDK class "Toolkit" to docs concept "Toolkit".
        """
        logger.info("Creating cross-source links...")
        
        for name_key, nodes in self.nodes_by_name.items():
            if len(nodes) < 2:
                continue
            
            # Group by source
            by_source: Dict[str, List[Dict]] = defaultdict(list)
            for node in nodes:
                source = self._get_source(node)
                by_source[source].append(node)
            
            if len(by_source) < 2:
                continue  # All from same source
            
            # Link code entities to doc entities
            code_nodes = []
            doc_nodes = []
            
            for source, source_nodes in by_source.items():
                for node in source_nodes:
                    if self._is_code_type(node.get("type", "")):
                        code_nodes.append(node)
                    elif self._is_doc_type(node.get("type", "")):
                        doc_nodes.append(node)
            
            # Create cross-links
            for code_node in code_nodes:
                for doc_node in doc_nodes:
                    code_type = code_node.get("type", "").lower()
                    doc_type = doc_node.get("type", "").lower()
                    
                    # Determine relationship type
                    rel_type = CROSS_SOURCE_RELATIONS.get(
                        (code_type, doc_type),
                        "related_to"
                    )
                    
                    if self._add_link(
                        code_node["id"],
                        doc_node["id"],
                        rel_type,
                        f"cross_source:{name_key}"
                    ):
                        self.stats["cross_source_links"] += 1
        
        logger.info(f"Created {self.stats['cross_source_links']} cross-source links")
    
    def enrich_semantic_links(self, 
                              min_word_overlap: float = 0.5,
                              max_links_per_entity: int = 5):
        """
        Create semantic links between entities based on shared concepts.
        
        This enhanced cross-linking finds relationships by:
        1. Shared significant words in entity names
        2. Similar context (source/type combinations)
        3. Hierarchical relationships (parent-child by naming)
        
        Args:
            min_word_overlap: Minimum word overlap ratio
            max_links_per_entity: Maximum new links per entity
        """
        logger.info("Creating semantic cross-links...")
        
        nodes = self.graph_data.get("nodes", [])
        links_created = 0
        
        # Build word index for efficient lookup
        word_to_nodes: Dict[str, List[Dict]] = defaultdict(list)
        for node in nodes:
            words = self._tokenize_name(node.get("name", ""))
            for word in words:
                if len(word) >= 3:  # Skip very short words
                    word_to_nodes[word].append(node)
        
        # Find semantic relationships
        processed_pairs: Set[Tuple[str, str]] = set()
        entity_link_count: Dict[str, int] = defaultdict(int)
        
        for node in nodes:
            if entity_link_count[node["id"]] >= max_links_per_entity:
                continue
            
            node_words = self._tokenize_name(node.get("name", ""))
            if not node_words:
                continue
            
            # Find candidate nodes sharing words
            candidates: Dict[str, float] = {}
            for word in node_words:
                for other in word_to_nodes.get(word, []):
                    if other["id"] == node["id"]:
                        continue
                    
                    pair = tuple(sorted([node["id"], other["id"]]))
                    if pair in processed_pairs:
                        continue
                    if pair in self.existing_links:
                        continue
                    
                    other_words = self._tokenize_name(other.get("name", ""))
                    if not other_words:
                        continue
                    
                    # Calculate overlap
                    overlap = len(node_words & other_words)
                    overlap_ratio = overlap / max(len(node_words), len(other_words))
                    
                    if overlap_ratio >= min_word_overlap:
                        if other["id"] not in candidates:
                            candidates[other["id"]] = overlap_ratio
                        else:
                            candidates[other["id"]] = max(candidates[other["id"]], overlap_ratio)
            
            # Create links to top candidates
            sorted_candidates = sorted(candidates.items(), key=lambda x: x[1], reverse=True)
            
            for other_id, overlap in sorted_candidates[:max_links_per_entity]:
                if entity_link_count[node["id"]] >= max_links_per_entity:
                    break
                if entity_link_count[other_id] >= max_links_per_entity:
                    continue
                
                pair = tuple(sorted([node["id"], other_id]))
                processed_pairs.add(pair)
                
                other_node = self.nodes_by_id.get(other_id)
                if not other_node:
                    continue
                
                # Determine relationship type
                rel_type = self._infer_relationship_type(node, other_node)
                
                if self._add_link(
                    node["id"],
                    other_id,
                    rel_type,
                    f"semantic_overlap:{overlap:.2f}"
                ):
                    links_created += 1
                    entity_link_count[node["id"]] += 1
                    entity_link_count[other_id] += 1
        
        self.stats["semantic_links"] = links_created
        logger.info(f"Created {links_created} semantic cross-links")
        return links_created
    
    def _infer_relationship_type(self, node1: Dict, node2: Dict) -> str:
        """Infer the best relationship type between two entities."""
        type1 = node1.get("type", "").lower()
        type2 = node2.get("type", "").lower()
        name1 = self._normalize_name(node1.get("name", ""))
        name2 = self._normalize_name(node2.get("name", ""))
        
        # Check for hierarchical relationship (one name contains the other)
        if name1 in name2 or name2 in name1:
            if len(name1) < len(name2):
                return "part_of"
            else:
                return "contains"
        
        # Check for type-based relationships
        type_pairs = [
            ({"class", "function", "method", "module"}, {"feature", "concept"}, "implements"),
            ({"endpoint", "api"}, {"service"}, "part_of"),
            ({"test_case", "test_suite"}, {"feature", "function", "class"}, "tests"),
            ({"defect", "incident"}, {"feature", "component"}, "affects"),
            ({"ticket"}, {"feature", "epic", "user_story"}, "implements"),
            ({"documentation"}, {"feature", "api", "class"}, "documents"),
        ]
        
        for types_a, types_b, rel in type_pairs:
            if (type1 in types_a and type2 in types_b) or (type2 in types_a and type1 in types_b):
                return rel
        
        # Check cross-source relation map
        if (type1, type2) in CROSS_SOURCE_RELATIONS:
            return CROSS_SOURCE_RELATIONS[(type1, type2)]
        if (type2, type1) in CROSS_SOURCE_RELATIONS:
            return CROSS_SOURCE_RELATIONS[(type2, type1)]
        
        return "related_to"
    
    def enrich_orphan_nodes(self, max_links_per_orphan: int = 3):
        """
        Connect orphan nodes to related entities based on name similarity.
        """
        logger.info("Connecting orphan nodes...")
        
        # Find orphans
        connected = set()
        for link in self.graph_data.get("links", []):
            connected.add(link["source"])
            connected.add(link["target"])
        for link in self.new_links:
            connected.add(link["source"])
            connected.add(link["target"])
        
        orphans = [
            node for node in self.graph_data.get("nodes", [])
            if node["id"] not in connected
        ]
        
        logger.info(f"Found {len(orphans)} orphan nodes")
        
        # For each orphan, find potential parents
        for orphan in orphans:
            orphan_name = self._normalize_name(orphan.get("name", ""))
            orphan_words = set(orphan_name.split())
            
            candidates = []
            
            for node in self.graph_data.get("nodes", []):
                if node["id"] == orphan["id"]:
                    continue
                if node["id"] not in connected:
                    continue  # Don't link orphans to orphans
                
                node_name = self._normalize_name(node.get("name", ""))
                node_words = set(node_name.split())
                
                # Check word overlap
                overlap = len(orphan_words & node_words)
                if overlap > 0:
                    # Calculate similarity score
                    sim = self._similarity(orphan_name, node_name)
                    word_score = overlap / max(len(orphan_words), 1)
                    score = (sim + word_score) / 2
                    
                    if score > 0.3:  # Minimum threshold
                        candidates.append((node, score))
            
            # Sort by score and take top matches
            candidates.sort(key=lambda x: x[1], reverse=True)
            
            for node, score in candidates[:max_links_per_orphan]:
                if self._add_link(
                    orphan["id"],
                    node["id"],
                    "related_to",
                    f"orphan_link:score={score:.2f}"
                ):
                    self.stats["orphan_links"] += 1
        
        logger.info(f"Created {self.stats['orphan_links']} orphan links")
    
    def enrich_similarity_links(self, min_similarity: float = 0.9):
        """
        Create links between entities with very similar names.
        
        This catches variations like "Create Toolkit" and "Toolkit Creation".
        """
        logger.info(f"Creating similarity links (threshold={min_similarity})...")
        
        nodes = self.graph_data.get("nodes", [])
        processed = set()
        
        for i, node1 in enumerate(nodes):
            name1 = self._normalize_name(node1.get("name", ""))
            if len(name1) < 3:
                continue
            
            for j, node2 in enumerate(nodes[i+1:], i+1):
                pair = (node1["id"], node2["id"])
                if pair in processed:
                    continue
                processed.add(pair)
                
                name2 = self._normalize_name(node2.get("name", ""))
                if len(name2) < 3:
                    continue
                
                # Calculate similarity
                sim = self._similarity(name1, name2)
                
                if sim >= min_similarity:
                    if self._add_link(
                        node1["id"],
                        node2["id"],
                        "similar_to",
                        f"similarity:{sim:.2f}"
                    ):
                        self.stats["similarity_links"] += 1
        
        logger.info(f"Created {self.stats['similarity_links']} similarity links")
    
    def enrich(
        self,
        deduplicate: bool = False,  # Disabled by default - can lose semantic meaning
        cross_source: bool = True,
        semantic_links: bool = True,
        orphans: bool = True,
        similarity: bool = False,  # Disabled by default - can create too many links
        min_similarity: float = 0.9,
        exact_match_only: bool = True,
    ):
        """
        Run all enrichment steps.
        
        The recommended order is:
        1. Deduplicate entities (DISABLED by default - use with caution)
        2. Create cross-source links (code ↔ docs)
        3. Create semantic links (shared concepts) - LINKS related entities
        4. Connect orphans
        5. Similarity links (optional)
        
        Args:
            deduplicate: Merge entities with exact same name (DISABLED by default)
            cross_source: Link same-named entities across sources
            semantic_links: Link entities sharing significant words
            orphans: Connect orphan nodes to related entities
            similarity: Link highly similar entity names
            min_similarity: Threshold for similarity matching
            exact_match_only: Only merge exact name matches if dedup enabled
        """
        # Step 1: Deduplication (DISABLED by default - can lose semantic meaning)
        if deduplicate:
            self.deduplicate_entities(require_exact_match=exact_match_only)
        
        # Step 2: Cross-source linking
        if cross_source:
            self.enrich_cross_source_links()
        
        # Step 3: Semantic cross-linking (LINKS related entities, doesn't merge)
        if semantic_links:
            self.enrich_semantic_links()
        
        # Step 4: Orphan connections
        if orphans:
            self.enrich_orphan_nodes()
        
        # Step 5: High similarity links (optional)
        if similarity:
            self.enrich_similarity_links(min_similarity)
        
        logger.info(f"Enrichment complete: {len(self.new_links)} new links added")
        return self.stats
    
    def save(self, output_path: Optional[str] = None):
        """
        Save enriched graph.
        
        Args:
            output_path: Optional output path. If None, overwrites input file.
        """
        output = Path(output_path) if output_path else self.graph_path
        
        # Merge new links
        all_links = self.graph_data.get("links", []) + self.new_links
        self.graph_data["links"] = all_links
        
        # Add enrichment metadata
        if "metadata" not in self.graph_data:
            self.graph_data["metadata"] = {}
        self.graph_data["metadata"]["enrichment_stats"] = self.stats
        
        with open(output, "w") as f:
            json.dump(self.graph_data, f, indent=2)
        
        logger.info(f"Saved enriched graph to {output}")
        return str(output)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get enrichment statistics."""
        return {
            **self.stats,
            "total_new_links": len(self.new_links),
            "original_nodes": len(self.nodes_by_id) + self.stats.get("entities_merged", 0),
            "final_nodes": len(self.nodes_by_id),
            "original_links": len(self.graph_data.get("links", [])) - len(self.new_links),
            "final_links": len(self.graph_data.get("links", [])),
        }


def enrich_graph(
    graph_path: str,
    output_path: Optional[str] = None,
    deduplicate: bool = True,
    cross_source: bool = True,
    semantic_links: bool = True,
    orphans: bool = True,
    similarity: bool = False,
) -> Dict[str, Any]:
    """
    Convenience function to enrich a graph file.
    
    Args:
        graph_path: Path to input graph JSON
        output_path: Path to output (default: overwrite input)
        deduplicate: Merge same/similar entities
        cross_source: Create cross-source links
        semantic_links: Create semantic cross-links
        orphans: Connect orphan nodes
        similarity: Create similarity links
        
    Returns:
        Enrichment statistics
    """
    enricher = GraphEnricher(graph_path)
    stats = enricher.enrich(
        deduplicate=deduplicate,
        cross_source=cross_source,
        semantic_links=semantic_links,
        orphans=orphans,
        similarity=similarity,
    )
    enricher.save(output_path)
    return stats
