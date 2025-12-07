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


# ============================================================================
# TYPE NORMALIZATION FOR ENRICHMENT
# ============================================================================

# Comprehensive type consolidation map
# Maps many ad-hoc LLM types to a smaller set of canonical types
# NOTE: All keys should be lowercase - normalize_type() lowercases input first
TYPE_NORMALIZATION_MAP = {
    # ==========================================================================
    # IDENTITY MAPPINGS - Types that MUST be preserved as-is
    # ==========================================================================
    "fact": "fact",
    "source_file": "source_file",
    "feature": "feature",
    "module": "module",
    "constant": "constant",
    "rule": "rule",
    "parameter": "parameter",
    "error_handling": "error_handling",
    "todo": "todo",
    "property": "property",
    "configuration": "configuration",
    "process": "process",
    "integration": "integration",
    "interface": "interface",
    "user_story": "user_story",
    "test": "test",
    "variable": "variable",
    "function": "function",
    
    # ==========================================================================
    # CODE STRUCTURE FAMILY → map to preserved types
    # ==========================================================================
    "named": "export",
    "default": "export",
    "business_rule": "rule",
    "domain_concept": "concept",
    "business_concept": "concept",
    "integration_point": "integration",
    "user_interface_element": "interface",
    "user_interface_component": "interface",
    "user_interaction": "interface",
    "user_action": "interface",
    "api_contract": "rest_api",
    "technical_debt": "todo",
    "test_scenario": "test",
    "test_case": "test",
    "tooltype": "tool",
    
    # ==========================================================================
    # TOOL & TOOLKIT FAMILY → tool, toolkit
    # ==========================================================================
    "tool": "tool",
    "tools": "tool",
    "tool_used": "tool",
    "tool_example": "tool",
    "tool_category": "tool",
    "internal_tool": "tool",
    "documentationtool": "tool",
    "toolkit": "toolkit",
    "toolkits": "toolkit",
    "toolkit_type": "toolkit",
    
    # ==========================================================================
    # FEATURE & CAPABILITY FAMILY → feature
    # ==========================================================================
    "features": "feature",
    "functionality": "feature",
    "capability": "feature",
    "benefit": "feature",
    "characteristic": "feature",
    
    # ==========================================================================
    # PROCESS & WORKFLOW FAMILY → process
    # ==========================================================================
    "processes": "process",
    "procedure": "process",
    "workflow": "workflow",
    "flow": "process",
    "pipeline": "process",
    
    # ==========================================================================
    # CONCEPT & ENTITY FAMILY → concept
    # ==========================================================================
    "concept": "concept",
    "concepts": "concept",
    "entity": "entity",
    "entities": "entity",
    "entity_type": "entity",
    "entitytype": "entity",
    "domain_entity": "entity",
    "domain": "concept",
    "topic": "concept",
    "term": "concept",
    "glossary_term": "concept",
    "key_concept": "concept",
    
    # ==========================================================================
    # CONFIGURATION FAMILY → configuration
    # ==========================================================================
    "config": "configuration",
    "configuration_section": "configuration",
    "configuration_field": "configuration",
    "configuration_option": "configuration",
    "configuration_file": "configuration",
    "configurationfile": "configuration",
    "configurationchange": "configuration",
    "configuration_command": "configuration",
    "setting": "configuration",
    "environment": "configuration",
    
    # ==========================================================================
    # DOCUMENTATION & GUIDE FAMILY → documentation
    # ==========================================================================
    "documentation": "documentation",
    "documentation_section": "documentation",
    "documentation_template": "documentation",
    "guide": "documentation",
    "guideline": "documentation",
    "instruction": "documentation",
    "tip": "documentation",
    "note": "documentation",
    "faq": "documentation",
    "overview": "documentation",
    "summary": "documentation",
    "best_practice": "documentation",
    
    # ==========================================================================
    # SECTION & STRUCTURE FAMILY → section
    # ==========================================================================
    "section": "section",
    "sections": "section",
    "interface_section": "section",
    "navigation_structure": "section",
    "navigation_group": "section",
    "navigation": "section",
    
    # ==========================================================================
    # COMPONENT & UI FAMILY → component
    # ==========================================================================
    "component": "component",
    "components": "component",
    "ui_component": "component",
    "ui_element": "component",
    "ui_layout": "component",
    "interface_element": "component",
    "button": "component",
    "menu": "component",
    "tab": "component",
    "panel": "component",
    "editor": "component",
    "view": "component",
    
    # ==========================================================================
    # ISSUE & PROBLEM FAMILY → issue
    # ==========================================================================
    "issue": "issue",
    "issues": "issue",
    "issue_type": "issue",
    "issuetype": "issue",
    "known_issue": "issue",
    "fixed_issue": "issue",
    "limitation": "issue",
    "challenge": "issue",
    "problem": "issue",
    "error_message": "issue",
    "troubleshooting": "issue",
    "compatibilityissue": "issue",
    
    # ==========================================================================
    # ACTION & COMMAND FAMILY → action
    # ==========================================================================
    "action": "action",
    "actions": "action",
    "command": "action",
    "operation": "action",
    "task": "action",
    "trigger": "action",
    "automation_rule": "action",
    
    # ==========================================================================
    # PARAMETER & FIELD FAMILY → parameter
    # ==========================================================================
    "parameters": "parameter",
    "field": "parameter",
    "field_identifier": "parameter",
    "placeholder": "parameter",
    "value": "parameter",
    "label": "parameter",
    "tag": "parameter",
    
    # ==========================================================================
    # CREDENTIAL & AUTH FAMILY → credential
    # ==========================================================================
    "credential": "credential",
    "credential_type": "credential",
    "secret": "credential",
    "token": "credential",
    "api_key": "credential",
    "api_token": "credential",
    "key": "credential",
    "authentication": "credential",
    "authentication_method": "credential",
    "permission": "credential",
    "access_control": "credential",
    "access_requirement": "credential",
    
    # ==========================================================================
    # RESOURCE & FILE FAMILY → resource
    # ==========================================================================
    "resource": "resource",
    "resources": "resource",
    "file": "resource",
    "file_type": "resource",
    "file_format": "resource",
    "file_path": "resource",
    "folder": "resource",
    "artifact": "resource",
    "artifact_type": "resource",
    "document": "resource",
    "template": "resource",
    "script": "resource",
    
    # ==========================================================================
    # PLATFORM & SOFTWARE FAMILY → platform
    # ==========================================================================
    "platform": "platform",
    "platforms": "platform",
    "software": "platform",
    "softwareversion": "platform",
    "application": "platform",
    "app": "platform",
    "system": "platform",
    "framework": "platform",
    "library": "platform",
    "technology": "platform",
    "product": "platform",
    
    # ==========================================================================
    # SERVICE & API FAMILY → Keep distinct types for different communication patterns
    # ==========================================================================
    "service": "service",
    "services": "service",
    "microservice": "service",
    "web_service": "service",
    "server": "service",
    "client": "service",
    "hostingservice": "service",
    
    # REST API (do NOT normalize to generic 'service')
    "rest api": "rest_api",
    "rest_api": "rest_api",
    "restapi": "rest_api",
    "rest": "rest_api",
    "api": "rest_api",
    "openapi": "rest_api",
    "swagger": "rest_api",
    "rest endpoint": "rest_endpoint",
    "rest_endpoint": "rest_endpoint",
    "endpoint": "rest_endpoint",
    "api_endpoint": "rest_endpoint",
    "http_endpoint": "rest_endpoint",
    "rest_resource": "rest_resource",
    
    # GraphQL (do NOT normalize to 'service')
    "graphql api": "graphql_api",
    "graphql_api": "graphql_api",
    "graphql": "graphql_api",
    "graphql_schema": "graphql_api",
    "graphql query": "graphql_query",
    "graphql_query": "graphql_query",
    "query": "graphql_query",
    "graphql mutation": "graphql_mutation",
    "graphql_mutation": "graphql_mutation",
    "mutation": "graphql_mutation",
    "graphql subscription": "graphql_subscription",
    "graphql_subscription": "graphql_subscription",
    "subscription": "graphql_subscription",
    "graphql type": "graphql_type",
    "graphql_type": "graphql_type",
    
    # gRPC (do NOT normalize to 'service')
    "grpc service": "grpc_service",
    "grpc_service": "grpc_service",
    "grpc": "grpc_service",
    "grpc method": "grpc_method",
    "grpc_method": "grpc_method",
    "rpc_method": "grpc_method",
    "protobuf_message": "protobuf_message",
    "protobuf": "protobuf_message",
    "proto_message": "protobuf_message",
    "protocol buffer": "protobuf_message",
    
    # Event-Driven Architecture (do NOT normalize to 'service')
    "event bus": "event_bus",
    "event_bus": "event_bus",
    "message_broker": "event_bus",
    "message_queue": "event_bus",
    "kafka": "event_bus",
    "rabbitmq": "event_bus",
    "event type": "event_type",
    "event_type": "event_type",
    "event": "event_type",
    "message_type": "event_type",
    "event producer": "event_producer",
    "event_producer": "event_producer",
    "publisher": "event_producer",
    "event consumer": "event_consumer",
    "event_consumer": "event_consumer",
    "subscriber": "event_consumer",
    "listener": "event_consumer",
    "event handler": "event_handler",
    "event_handler": "event_handler",
    "message_handler": "event_handler",
    "handler": "event_handler",
    
    # ==========================================================================
    # INTEGRATION & CONNECTION FAMILY → integration
    # ==========================================================================
    "integrations": "integration",
    "connection": "integration",
    "connection_type": "integration",
    "connector": "integration",
    "adapter": "integration",
    "datasource": "integration",
    "database": "integration",
    
    # ==========================================================================
    # EXAMPLE & USE CASE FAMILY → example
    # ==========================================================================
    "example": "example",
    "examples": "example",
    "example_type": "example",
    "example_request": "example",
    "use_case": "example",
    "use_case_category": "example",
    "code_sample": "example",
    "sample_prompt": "example",
    
    # ==========================================================================
    # NODE & GRAPH FAMILY → node
    # ==========================================================================
    "node": "node",
    "nodetype": "node",
    "node_type": "node",
    "execution_node": "node",
    "iteration_node": "node",
    "interaction_node": "node",
    "utilitynode": "node",
    
    # ==========================================================================
    # STEP & PROCEDURE FAMILY → step
    # ==========================================================================
    "step": "step",
    "steps": "step",
    "number_of_step": "step",
    "prerequisite": "step",
    
    # ==========================================================================
    # STATUS & STATE FAMILY → status
    # ==========================================================================
    "status": "status",
    "state": "status",
    "state_type": "status",
    "mode": "status",
    "session_mode": "status",
    
    # ==========================================================================
    # PROJECT & WORKSPACE FAMILY → project
    # ==========================================================================
    "project": "project",
    "workspace": "project",
    "project_scope": "project",
    "repository": "project",
    "space": "project",
    
    # ==========================================================================
    # ROLE & USER FAMILY → role
    # ==========================================================================
    "role": "role",
    "user_role": "role",
    "team": "role",
    "person": "role",
    "audience": "role",
    "stakeholder": "role",
    "owner": "role",
    
    # ==========================================================================
    # AGENT FAMILY → agent
    # ==========================================================================
    "agent": "agent",
    "agents": "agent",
    "agent_type": "agent",
    "agent_configuration": "agent",
    "ai_agent": "agent",
    "public_agent": "agent",
    
    # ==========================================================================
    # DATA & TYPE FAMILY → data_type
    # ==========================================================================
    "data_type": "data_type",
    "datatype": "data_type",
    "data_structure": "data_type",
    "schema": "data_type",
    "format": "data_type",
    "content_type": "data_type",
    "collection": "data_type",
    "collectiontype": "data_type",
    "list": "data_type",
    "table": "data_type",
    
    # ==========================================================================
    # RELEASE & VERSION FAMILY → release
    # ==========================================================================
    "release": "release",
    "version": "release",
    "change": "release",
    "feature_change": "release",
    "migration": "release",
    "deployment": "release",
    "fix": "release",
    
    # ==========================================================================
    # REFERENCE & LINK FAMILY → reference
    # ==========================================================================
    "reference": "reference",
    "related_page": "reference",
    "url": "reference",
    "webpage": "reference",
    "website": "reference",
    "page": "reference",
    "link": "reference",
    
    # ==========================================================================
    # RULE & POLICY FAMILY → rule
    # ==========================================================================
    "rules": "rule",
    "policy": "rule",
    "formatting_rule": "rule",
    "directive": "rule",
    "requirement": "rule",
    "specification": "rule",
    
    # ==========================================================================
    # MCP FAMILY → mcp_server
    # ==========================================================================
    "mcp server": "mcp_server",
    "mcp_server": "mcp_server",
    "mcp tool": "mcp_tool", 
    "mcp_tool": "mcp_tool",
    "mcp resource": "mcp_resource",
    "mcp_resource": "mcp_resource",
    "mcp_type": "mcp_server",
    "transport": "mcp_server",
    
    # ==========================================================================
    # MISCELLANEOUS → map to closest canonical type
    # ==========================================================================
    "method": "method",
    "model": "concept",
    "category": "concept",
    "metric": "parameter",
    "identifier": "parameter",
    "port": "parameter",
    "protocol": "service",
    "security": "credential",
    "support": "documentation",
    "community": "documentation",
    "contact": "reference",
    "contactmethod": "reference",
    "contact_information": "reference",
    "contactinfo": "reference",
    "building_block": "component",
    "container": "component",
    "instance": "entity",
    "object": "entity",
    "sourcetype": "data_type",
    "input_mapping_type": "data_type",
    "control_flow_feature": "feature",
    "export_option": "action",
    "export_format": "data_type",
    "conversion": "action",
    "customization": "configuration",
    "viewing_option": "configuration",
    "review_outcome": "status",
    "goal": "feature",
    "engagement": "action",
    "output": "data_type",
    "effect": "action",
    "solution": "documentation",
    "cause": "issue",
    "indicator": "status",
    "date": "parameter",
    "screenshot": "resource",
    "open_question": "issue",
    "static_site_generator": "platform",
    "theme": "configuration",
    "theme_convention": "rule",
    "file_naming_convention": "rule",
    "metadata_guideline": "rule",
    "linking_guideline": "rule",
    "media_guideline": "rule",
    "accessibility_guideline": "rule",
    "page_type": "section",
    "document_category": "section",
    "prompt": "example",
    "chat": "feature",
    "ide": "platform",
    "tagging": "action",
    "account": "credential",
    "installation_command": "action",
    "usage": "documentation",
    "mechanism": "concept",
    "ai_component": "component",
    "communication_method": "integration",
    "dns_record": "configuration",
    "tone": "rule",
    "voice": "rule",
    
    # ==========================================================================
    # FACT & KNOWLEDGE FAMILY → fact (semantic facts extracted by LLM)
    # ==========================================================================
    "facts": "fact",
    "algorithm": "fact",
    "behavior": "fact",
    "validation": "fact",
    "decision": "fact",
    "definition": "fact",
    
    # ==========================================================================
    # FILE & STRUCTURE FAMILY → file types (container nodes for entities)
    # ==========================================================================
    "document_file": "document_file",
    "config_file": "config_file",
    "web_file": "web_file",
    "directory": "directory",
    "package": "package",
}

# Types that should NEVER be normalized - they pass through as-is
PRESERVED_TYPES = {
    "fact", "source_file", "feature", "module", "constant", "rule",
    "parameter", "error_handling", "todo", "property", "configuration",
    "process", "integration", "interface", "user_story", "test",
    "export", "rest_api", "concept", "component", "workflow",
    "document_file", "config_file", "web_file", "directory", "package",
    "variable", "function",  # Code entities - preserve for impact analysis
}

def normalize_type(entity_type: str) -> str:
    """
    Normalize entity type to canonical lowercase form.
    
    Aggressively consolidates types to a small set of ~25 canonical types:
    - feature, tool, toolkit, process, concept, entity
    - section, component, issue, action, parameter, credential
    - resource, platform, service, integration, example, node
    - step, status, project, role, agent, data_type, release
    - reference, rule, documentation, configuration, mcp_server
    
    Args:
        entity_type: Raw entity type
        
    Returns:
        Canonical lowercase entity type
    """
    if not entity_type:
        return "concept"  # Default to concept for unknown
    
    # Normalize to lowercase first - all checks are case-insensitive
    normalized = entity_type.lower().strip().replace(" ", "_").replace("-", "_")
    
    # First: check if type should be preserved as-is (25+ canonical types)
    if normalized in PRESERVED_TYPES:
        return normalized
    
    # Check explicit mapping (all keys are lowercase now)
    if normalized in TYPE_NORMALIZATION_MAP:
        return TYPE_NORMALIZATION_MAP[normalized]
    
    # Handle plural forms
    if normalized.endswith('s') and not normalized.endswith('ss') and len(normalized) > 3:
        singular = normalized[:-1]
        if singular in PRESERVED_TYPES:
            return singular
        if singular in TYPE_NORMALIZATION_MAP:
            return TYPE_NORMALIZATION_MAP[singular]
    
    # Fallback heuristics based on common suffixes/patterns
    if '_type' in normalized or normalized.endswith('type'):
        return "data_type"
    if '_section' in normalized or normalized.endswith('section'):
        return "section"
    if '_field' in normalized or normalized.endswith('field'):
        return "parameter"
    if '_node' in normalized or normalized.endswith('node'):
        return "node"
    if '_issue' in normalized or normalized.endswith('issue'):
        return "issue"
    if '_guide' in normalized or normalized.endswith('guide'):
        return "documentation"
    if '_config' in normalized or normalized.endswith('config'):
        return "configuration"
    if '_tool' in normalized or normalized.endswith('tool'):
        return "tool"
    if '_service' in normalized or normalized.endswith('service'):
        return "service"
    
    # If still unknown, map to concept (generic catch-all)
    return "concept"

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
    
    # Service layer - specific communication patterns have higher priority than generic
    "service": 90,
    
    # REST API types
    "rest_api": 89,
    "rest_endpoint": 88,
    "rest_resource": 87,
    
    # GraphQL types
    "graphql_api": 89,
    "graphql_mutation": 88,
    "graphql_query": 87,
    "graphql_subscription": 86,
    "graphql_type": 85,
    
    # gRPC types
    "grpc_service": 89,
    "grpc_method": 88,
    "protobuf_message": 87,
    
    # Event-driven types
    "event_bus": 89,
    "event_type": 88,
    "event_producer": 87,
    "event_consumer": 87,
    "event_handler": 86,
    
    # Generic fallbacks (lower priority)
    "integration": 84,
    "payload": 83,
    
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
    "tool",                  # Tools belong to specific toolkits
    "property",              # Properties belong to specific entities
    "properties",            # Same as above
    "parameter",             # Parameters belong to specific functions/methods
    "argument",              # Arguments belong to specific functions
    "field",                 # Fields belong to specific tables/forms
    "column",                # Columns belong to specific tables
    "attribute",             # Attributes belong to specific entities
    "option",                # Options belong to specific settings
    "setting",               # Settings may have same name in different contexts
    "step",                  # Steps belong to specific workflows/processes
    "test_step",             # Test steps belong to specific test cases
    "ui_field",              # UI fields belong to specific screens
    "method",                # Methods belong to specific classes
    
    # API types - same name can exist in different API contexts
    "rest_endpoint",         # /users endpoint in API A != /users in API B
    "rest_resource",         # Same resource name in different REST APIs
    "graphql_query",         # Same query name in different GraphQL schemas
    "graphql_mutation",      # Same mutation name in different GraphQL schemas
    "graphql_subscription",  # Same subscription in different GraphQL schemas
    "graphql_type",          # Same type name in different GraphQL schemas
    "grpc_method",           # Same method name in different gRPC services
    "protobuf_message",      # Same message name in different proto files
    "event_type",            # Same event name in different event busses
    "event_handler",         # Same handler name in different services
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
    
    def normalize_entity_types(self):
        """
        Normalize all entity types in the graph to canonical lowercase forms.
        
        This fixes inconsistencies like Tool/tool/Tools all becoming 'tool'.
        Should be run before other enrichment steps.
        """
        logger.info("Normalizing entity types...")
        types_normalized = 0
        type_changes: Dict[str, str] = {}  # original -> normalized
        
        for node in self.graph_data.get("nodes", []):
            original_type = node.get("type", "")
            normalized = normalize_type(original_type)
            
            if normalized != original_type:
                if original_type not in type_changes:
                    type_changes[original_type] = normalized
                node["type"] = normalized
                types_normalized += 1
        
        # Log what was changed
        if type_changes:
            logger.info(f"Normalized {types_normalized} entity types:")
            for orig, norm in sorted(type_changes.items()):
                logger.debug(f"  {orig} -> {norm}")
        
        self.stats["types_normalized"] = types_normalized
        self.stats["type_changes"] = len(type_changes)
        
        # Rebuild indices after type normalization
        self.nodes_by_id.clear()
        self.nodes_by_name.clear()
        for node in self.graph_data.get("nodes", []):
            self.nodes_by_id[node["id"]] = node
            name_key = self._normalize_name(node.get("name", ""))
            self.nodes_by_name[name_key].append(node)
        
        logger.info(f"Normalized {len(type_changes)} distinct type variations")
    
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
        
        # Tool/Toolkit relationships - highest priority
        if type1 == "toolkit" and type2 == "tool":
            return "contains"
        if type2 == "toolkit" and type1 == "tool":
            return "part_of"
        if type1 == "mcp_server" and type2 == "mcp_tool":
            return "provides"
        if type2 == "mcp_server" and type1 == "mcp_tool":
            return "provided_by"
        
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
            ({"toolkit"}, {"feature", "capability", "function"}, "provides"),
            ({"tool"}, {"feature", "capability", "function"}, "implements"),
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
    
    def enrich_toolkit_tool_links(self):
        """
        Create explicit links between toolkits and their tools.
        
        This method specifically handles the toolkit → tool relationship by:
        1. Finding all toolkit and tool entities
        2. Matching tools to toolkits based on:
           - Same file path (tools defined in toolkit's documentation)
           - Toolkit name appearing in tool's parent_toolkit property
           - Tool name containing toolkit name prefix
        """
        logger.info("Linking tools to toolkits...")
        
        nodes = self.graph_data.get("nodes", [])
        links_created = 0
        
        # Index toolkits and tools
        toolkits = [n for n in nodes if n.get("type", "").lower() == "toolkit"]
        tools = [n for n in nodes if n.get("type", "").lower() == "tool"]
        
        # Index toolkits by file_path and name
        toolkit_by_file: Dict[str, List[Dict]] = defaultdict(list)
        toolkit_by_name: Dict[str, Dict] = {}
        
        for tk in toolkits:
            file_path = tk.get("file_path", "")
            if file_path:
                toolkit_by_file[file_path].append(tk)
            name = tk.get("name", "").lower()
            if name:
                toolkit_by_name[name] = tk
                # Also index by common variations
                # e.g., "GitHub Toolkit" → "github", "github toolkit"
                short_name = name.replace(" toolkit", "").replace("_toolkit", "")
                toolkit_by_name[short_name] = tk
        
        for tool in tools:
            tool_id = tool["id"]
            tool_file = tool.get("file_path", "")
            tool_name = tool.get("name", "").lower()
            tool_props = tool.get("properties", {})
            parent_toolkit = tool_props.get("parent_toolkit", "").lower()
            
            matched_toolkit = None
            match_reason = ""
            
            # Strategy 1: Match by parent_toolkit property
            if parent_toolkit:
                for tk_name, tk in toolkit_by_name.items():
                    if tk_name in parent_toolkit or parent_toolkit in tk_name:
                        matched_toolkit = tk
                        match_reason = f"parent_toolkit:{parent_toolkit}"
                        break
            
            # Strategy 2: Match by same file path
            if not matched_toolkit and tool_file:
                if tool_file in toolkit_by_file:
                    # Pick first matching toolkit in same file
                    matched_toolkit = toolkit_by_file[tool_file][0]
                    match_reason = f"same_file:{tool_file}"
            
            # Strategy 3: Match by tool name containing toolkit name
            if not matched_toolkit:
                for tk_name, tk in toolkit_by_name.items():
                    if tk_name in tool_name:
                        matched_toolkit = tk
                        match_reason = f"name_match:{tk_name}"
                        break
            
            # Create link if matched
            if matched_toolkit:
                pair = tuple(sorted([matched_toolkit["id"], tool_id]))
                if pair not in self.existing_links:
                    if self._add_link(
                        matched_toolkit["id"],
                        tool_id,
                        "contains",
                        f"toolkit_tool:{match_reason}"
                    ):
                        links_created += 1
        
        self.stats["toolkit_tool_links"] = links_created
        logger.info(f"Created {links_created} toolkit → tool links")
    
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

    def validate_low_confidence_relationships(
        self,
        confidence_threshold: float = 0.7,
        llm: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Validate and re-evaluate relationships with confidence below threshold.
        
        This method routes low-confidence relationships through additional validation:
        1. Gather context from both source and target entities
        2. Check if relationship makes semantic sense given entity types
        3. Optionally use LLM to validate ambiguous relationships
        
        Args:
            confidence_threshold: Relationships below this are candidates for validation
            llm: Optional LLM for re-evaluation (if None, uses heuristics only)
            
        Returns:
            Dictionary with validation stats:
            - validated: Number of relationships confirmed
            - rejected: Number of relationships removed
            - upgraded: Number of relationships with increased confidence
            - downgraded: Number of relationships with decreased confidence
        """
        logger.info(f"Validating low-confidence relationships (threshold={confidence_threshold})...")
        
        stats = {
            "candidates": 0,
            "validated": 0,
            "rejected": 0,
            "upgraded": 0,
            "downgraded": 0,
        }
        
        links_to_keep = []
        links_to_remove = []
        
        for link in self.graph_data.get("links", []):
            confidence = link.get("confidence", 1.0)
            
            # Skip high-confidence links
            if confidence >= confidence_threshold:
                links_to_keep.append(link)
                continue
            
            # Skip parser-extracted relationships (already validated by code structure)
            if link.get("source") == "parser":
                links_to_keep.append(link)
                continue
            
            stats["candidates"] += 1
            
            # Get source and target entities
            source_id = link.get("source")
            target_id = link.get("target")
            source_node = self.nodes_by_id.get(source_id)
            target_node = self.nodes_by_id.get(target_id)
            
            if not source_node or not target_node:
                # Invalid link - remove
                stats["rejected"] += 1
                links_to_remove.append(link)
                continue
            
            # Validate using heuristics
            validation_result = self._validate_relationship_heuristic(
                source_node, target_node, link
            )
            
            if validation_result["action"] == "keep":
                # Update confidence if suggested
                if "new_confidence" in validation_result:
                    link["confidence"] = validation_result["new_confidence"]
                    link["validation_reason"] = validation_result.get("reason", "heuristic")
                    if validation_result["new_confidence"] > confidence:
                        stats["upgraded"] += 1
                    elif validation_result["new_confidence"] < confidence:
                        stats["downgraded"] += 1
                stats["validated"] += 1
                links_to_keep.append(link)
                
            elif validation_result["action"] == "remove":
                stats["rejected"] += 1
                links_to_remove.append(link)
                logger.debug(
                    f"Removing low-confidence relationship: {source_node.get('name')} "
                    f"--[{link.get('relation_type')}]--> {target_node.get('name')} "
                    f"(reason: {validation_result.get('reason', 'unknown')})"
                )
                
            elif validation_result["action"] == "llm_validate" and llm:
                # Use LLM for ambiguous cases
                llm_result = self._validate_relationship_with_llm(
                    source_node, target_node, link, llm
                )
                if llm_result["valid"]:
                    link["confidence"] = llm_result.get("confidence", confidence)
                    link["validation_reason"] = "llm_validated"
                    stats["validated"] += 1
                    links_to_keep.append(link)
                else:
                    stats["rejected"] += 1
                    links_to_remove.append(link)
            else:
                # Default: keep with same confidence
                links_to_keep.append(link)
                stats["validated"] += 1
        
        # Update links
        self.graph_data["links"] = links_to_keep
        
        # Log removed links for analysis
        if links_to_remove:
            logger.info(f"Removed {len(links_to_remove)} invalid low-confidence relationships")
        
        self.stats["low_confidence_validation"] = stats
        logger.info(
            f"Low-confidence validation: {stats['candidates']} candidates, "
            f"{stats['validated']} validated, {stats['rejected']} rejected, "
            f"{stats['upgraded']} upgraded, {stats['downgraded']} downgraded"
        )
        
        return stats
    
    def _validate_relationship_heuristic(
        self,
        source_node: Dict,
        target_node: Dict,
        link: Dict
    ) -> Dict[str, Any]:
        """
        Validate a relationship using heuristic rules.
        
        Returns:
            Dict with 'action' (keep/remove/llm_validate) and optional 'new_confidence'
        """
        source_type = source_node.get("type", "").lower()
        target_type = target_node.get("type", "").lower()
        relation_type = link.get("relation_type", "").lower()
        confidence = link.get("confidence", 0.5)
        
        # Rule 1: Invalid type combinations for specific relationships
        invalid_combinations = {
            # imports should be between code entities
            "imports": {
                "invalid_source": {"feature", "concept", "documentation", "requirement"},
                "invalid_target": {"feature", "concept", "documentation", "requirement"},
            },
            # implements should have code as source
            "implements": {
                "invalid_source": {"documentation", "concept", "glossary_term"},
            },
            # contains should have container as source
            "contains": {
                "invalid_source": {"constant", "variable", "field", "property"},
            },
            # tests should have test as source
            "tests": {
                "invalid_source": {"class", "function", "method", "module"},
            },
        }
        
        if relation_type in invalid_combinations:
            rules = invalid_combinations[relation_type]
            if source_type in rules.get("invalid_source", set()):
                return {"action": "remove", "reason": f"invalid_source_type:{source_type}"}
            if target_type in rules.get("invalid_target", set()):
                return {"action": "remove", "reason": f"invalid_target_type:{target_type}"}
        
        # Rule 2: Boost confidence for semantically valid combinations
        valid_combinations = {
            ("class", "interface", "implements"): 0.9,
            ("method", "function", "calls"): 0.85,
            ("test_case", "function", "tests"): 0.9,
            ("test_case", "class", "tests"): 0.9,
            ("documentation", "class", "documents"): 0.85,
            ("documentation", "function", "documents"): 0.85,
            ("ticket", "feature", "implements"): 0.8,
            ("feature", "requirement", "implements"): 0.85,
            ("toolkit", "tool", "contains"): 0.95,
            ("module", "class", "contains"): 0.9,
            ("class", "method", "contains"): 0.95,
        }
        
        combo_key = (source_type, target_type, relation_type)
        if combo_key in valid_combinations:
            suggested_confidence = valid_combinations[combo_key]
            return {
                "action": "keep",
                "new_confidence": max(confidence, suggested_confidence),
                "reason": f"valid_combination:{combo_key}"
            }
        
        # Rule 3: Check name overlap for related_to relationships
        if relation_type == "related_to":
            source_words = self._tokenize_name(source_node.get("name", ""))
            target_words = self._tokenize_name(target_node.get("name", ""))
            
            if source_words and target_words:
                overlap = len(source_words & target_words)
                if overlap >= 2:
                    # Good overlap - boost confidence
                    return {
                        "action": "keep",
                        "new_confidence": min(confidence + 0.2, 0.9),
                        "reason": f"name_overlap:{overlap}"
                    }
                elif overlap == 0 and confidence < 0.5:
                    # No overlap and low confidence - consider removal
                    return {"action": "llm_validate", "reason": "no_name_overlap"}
        
        # Rule 4: Very low confidence with no semantic support
        if confidence < 0.4:
            # Check if there's any semantic basis
            source_name = source_node.get("name", "").lower()
            target_name = target_node.get("name", "").lower()
            
            if (source_name not in target_name and 
                target_name not in source_name and
                self._word_overlap_score(source_name, target_name) < 0.3):
                return {"action": "remove", "reason": "very_low_confidence_no_semantic_support"}
        
        # Default: keep with same confidence
        return {"action": "keep", "reason": "default"}
    
    def _validate_relationship_with_llm(
        self,
        source_node: Dict,
        target_node: Dict,
        link: Dict,
        llm: Any
    ) -> Dict[str, Any]:
        """
        Use LLM to validate an ambiguous relationship.
        
        Args:
            source_node: Source entity
            target_node: Target entity
            link: The relationship to validate
            llm: LLM instance for validation
            
        Returns:
            Dict with 'valid' (bool) and 'confidence' (float)
        """
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser
        
        prompt_template = """Validate if the following relationship makes semantic sense.

Source Entity:
- Name: {source_name}
- Type: {source_type}
- Description: {source_desc}

Relationship: {relation_type}

Target Entity:
- Name: {target_name}
- Type: {target_type}
- Description: {target_desc}

Question: Does it make sense that "{source_name}" {relation_type} "{target_name}"?

Respond with ONLY a JSON object:
{{"valid": true/false, "confidence": 0.0-1.0, "reason": "<brief explanation>"}}
"""
        
        try:
            prompt = ChatPromptTemplate.from_template(prompt_template)
            parser = JsonOutputParser()
            chain = prompt | llm | parser
            
            result = chain.invoke({
                "source_name": source_node.get("name", ""),
                "source_type": source_node.get("type", ""),
                "source_desc": source_node.get("description", "No description"),
                "relation_type": link.get("relation_type", "related_to"),
                "target_name": target_node.get("name", ""),
                "target_type": target_node.get("type", ""),
                "target_desc": target_node.get("description", "No description"),
            })
            
            return {
                "valid": result.get("valid", False),
                "confidence": result.get("confidence", 0.5),
                "reason": result.get("reason", "llm_validated")
            }
            
        except Exception as e:
            logger.warning(f"LLM validation failed: {e}")
            # On LLM failure, keep the relationship
            return {"valid": True, "confidence": link.get("confidence", 0.5)}

    def enrich(
        self,
        normalize_types: bool = True,  # Normalize entity types first
        deduplicate: bool = False,  # Disabled by default - can lose semantic meaning
        cross_source: bool = True,
        semantic_links: bool = True,
        toolkit_tools: bool = True,  # Link tools to their toolkits
        orphans: bool = True,
        similarity: bool = False,  # Disabled by default - can create too many links
        validate_low_confidence: bool = True,  # Validate relationships with confidence < 0.7
        confidence_threshold: float = 0.7,  # Threshold for low-confidence validation
        min_similarity: float = 0.9,
        exact_match_only: bool = True,
        llm: Optional[Any] = None,  # Optional LLM for relationship validation
    ):
        """
        Run all enrichment steps.
        
        The recommended order is:
        0. Normalize entity types (Tool/tool/Tools → tool)
        1. Deduplicate entities (DISABLED by default - use with caution)
        2. Link tools to toolkits (explicit toolkit → tool relationships)
        3. Create cross-source links (code ↔ docs)
        4. Create semantic links (shared concepts) - LINKS related entities
        5. Connect orphans
        6. Similarity links (optional)
        7. Validate low-confidence relationships
        
        Args:
            normalize_types: Normalize entity types to canonical forms
            deduplicate: Merge entities with exact same name (DISABLED by default)
            cross_source: Link same-named entities across sources
            semantic_links: Link entities sharing significant words
            toolkit_tools: Create explicit toolkit → tool relationships
            orphans: Connect orphan nodes to related entities
            similarity: Link highly similar entity names
            validate_low_confidence: Validate relationships below confidence_threshold
            confidence_threshold: Threshold for low-confidence validation (default: 0.7)
            min_similarity: Threshold for similarity matching
            exact_match_only: Only merge exact name matches if dedup enabled
            llm: Optional LLM instance for validating ambiguous relationships
        """
        # Step 0: Normalize entity types (Tool/tool/Tools → tool)
        if normalize_types:
            self.normalize_entity_types()
        
        # Step 1: Deduplication (DISABLED by default - can lose semantic meaning)
        if deduplicate:
            self.deduplicate_entities(require_exact_match=exact_match_only)
        
        # Step 2: Link tools to their toolkits (high priority - structural)
        if toolkit_tools:
            self.enrich_toolkit_tool_links()
        
        # Step 3: Cross-source linking
        if cross_source:
            self.enrich_cross_source_links()
        
        # Step 4: Semantic cross-linking (LINKS related entities, doesn't merge)
        if semantic_links:
            self.enrich_semantic_links()
        
        # Step 5: Orphan connections
        if orphans:
            self.enrich_orphan_nodes()
        
        # Step 6: High similarity links (optional)
        if similarity:
            self.enrich_similarity_links(min_similarity)
        
        # Step 7: Validate low-confidence relationships
        if validate_low_confidence:
            self.validate_low_confidence_relationships(
                confidence_threshold=confidence_threshold,
                llm=llm
            )
        
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
    deduplicate: bool = False,  # Disabled by default
    cross_source: bool = True,
    semantic_links: bool = True,
    toolkit_tools: bool = True,
    orphans: bool = True,
    similarity: bool = False,
    validate_low_confidence: bool = True,
    confidence_threshold: float = 0.7,
    llm: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Convenience function to enrich a graph file.
    
    Args:
        graph_path: Path to input graph JSON
        output_path: Path to output (default: overwrite input)
        deduplicate: Merge same/similar entities (disabled by default)
        cross_source: Create cross-source links
        semantic_links: Create semantic cross-links
        toolkit_tools: Link tools to their toolkits
        orphans: Connect orphan nodes
        similarity: Create similarity links
        validate_low_confidence: Validate relationships below confidence_threshold
        confidence_threshold: Threshold for low-confidence validation (default: 0.7)
        llm: Optional LLM instance for validating ambiguous relationships
        
    Returns:
        Enrichment statistics
    """
    enricher = GraphEnricher(graph_path)
    stats = enricher.enrich(
        deduplicate=deduplicate,
        cross_source=cross_source,
        semantic_links=semantic_links,
        toolkit_tools=toolkit_tools,
        orphans=orphans,
        similarity=similarity,
        validate_low_confidence=validate_low_confidence,
        confidence_threshold=confidence_threshold,
        llm=llm,
    )
    enricher.save(output_path)
    return stats
