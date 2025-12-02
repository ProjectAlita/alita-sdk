"""
Knowledge Graph Enrichment Utilities.

Post-processing tools to improve graph connectivity by:
1. Linking semantically similar entities across sources
2. Creating cross-reference relationships (implements, documents, etc.)
3. Connecting orphan nodes to parent concepts

Usage:
    from alita_sdk.community.inventory.enrichment import GraphEnricher
    
    enricher = GraphEnricher(graph_path="./graph.json")
    enricher.enrich()
    enricher.save()
"""

import json
import logging
import re
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
        self.stats = {
            "cross_source_links": 0,
            "orphan_links": 0,
            "similarity_links": 0,
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
    
    def _add_link(self, source_id: str, target_id: str, relation_type: str, reason: str):
        """Add a new link if it doesn't exist."""
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
        cross_source: bool = True,
        orphans: bool = True,
        similarity: bool = False,  # Disabled by default - can create too many links
        min_similarity: float = 0.9
    ):
        """
        Run all enrichment steps.
        
        Args:
            cross_source: Link same-named entities across sources
            orphans: Connect orphan nodes to related entities
            similarity: Link highly similar entity names
            min_similarity: Threshold for similarity matching
        """
        if cross_source:
            self.enrich_cross_source_links()
        
        if orphans:
            self.enrich_orphan_nodes()
        
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
            "original_nodes": len(self.nodes_by_id),
            "original_links": len(self.graph_data.get("links", [])) - len(self.new_links),
        }


def enrich_graph(
    graph_path: str,
    output_path: Optional[str] = None,
    cross_source: bool = True,
    orphans: bool = True,
    similarity: bool = False,
) -> Dict[str, Any]:
    """
    Convenience function to enrich a graph file.
    
    Args:
        graph_path: Path to input graph JSON
        output_path: Path to output (default: overwrite input)
        cross_source: Create cross-source links
        orphans: Connect orphan nodes
        similarity: Create similarity links
        
    Returns:
        Enrichment statistics
    """
    enricher = GraphEnricher(graph_path)
    stats = enricher.enrich(
        cross_source=cross_source,
        orphans=orphans,
        similarity=similarity,
    )
    enricher.save(output_path)
    return stats
