"""
LLM-based extractors for document classification, schema discovery,
entity extraction, and relation extraction.

Supports comprehensive entity types across multiple layers:
- Product Layer: Features, Epics, User Stories, Screens, UX Flows
- Domain Layer: Business Objects, Rules, Glossary Terms
- Service Layer: APIs, Endpoints, Services, Methods
- Code Layer: Modules, Classes, Functions
- Data Layer: Tables, Columns, Constraints
- Testing Layer: Test Cases, Test Suites, Defects
- Delivery Layer: Releases, Commits, Tickets
- Organization Layer: Teams, Owners, Repositories
"""

import json
import logging
import hashlib
from typing import Any, Optional, List, Dict

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

logger = logging.getLogger(__name__)


# ============================================================================
# COMPREHENSIVE ENTITY & RELATIONSHIP TAXONOMY
# ============================================================================

ENTITY_TAXONOMY = {
    "product_layer": {
        "description": "Product and UX artifacts",
        "types": [
            {"name": "epic", "description": "Large feature grouping or initiative", "properties": ["name", "description", "acceptance_criteria", "priority"]},
            {"name": "feature", "description": "Product capability or functionality", "properties": ["name", "description", "acceptance_criteria", "related_screens"]},
            {"name": "user_story", "description": "User requirement in story format", "properties": ["name", "description", "persona", "acceptance_criteria", "story_points"]},
            {"name": "screen", "description": "UI page, screen, or view", "properties": ["name", "description", "url_path", "parent_screen"]},
            {"name": "ux_flow", "description": "User journey or navigation flow", "properties": ["name", "description", "start_screen", "end_screen", "steps"]},
            {"name": "ui_component", "description": "Reusable UI element (form, button, modal)", "properties": ["name", "description", "component_type", "parent_screen"]},
            {"name": "ui_field", "description": "Input field, dropdown, or display element", "properties": ["name", "field_type", "validation_rules", "api_mapping", "db_mapping"]},
        ]
    },
    "domain_layer": {
        "description": "Business domain concepts",
        "types": [
            {"name": "domain_entity", "description": "Core business object (Customer, Order, Product)", "properties": ["name", "description", "attributes", "lifecycle_states"]},
            {"name": "attribute", "description": "Property of a domain entity", "properties": ["name", "data_type", "constraints", "parent_entity"]},
            {"name": "business_rule", "description": "Business logic or constraint", "properties": ["name", "description", "trigger_event", "conditions", "actions", "exceptions"]},
            {"name": "business_event", "description": "Domain event that triggers actions", "properties": ["name", "description", "trigger", "payload", "handlers"]},
            {"name": "glossary_term", "description": "Domain vocabulary definition", "properties": ["name", "definition", "synonyms", "related_terms"]},
            {"name": "workflow", "description": "Business process or workflow", "properties": ["name", "description", "steps", "triggers", "outcomes"]},
        ]
    },
    "service_layer": {
        "description": "APIs and services",
        "types": [
            {"name": "service", "description": "Software service or microservice", "properties": ["name", "description", "tech_stack", "owner_team"]},
            {"name": "api", "description": "API specification or contract", "properties": ["name", "description", "version", "auth_schema", "base_url"]},
            {"name": "endpoint", "description": "API endpoint", "properties": ["name", "method", "path", "request_schema", "response_schema", "auth_required"]},
            {"name": "payload", "description": "API request/response payload structure", "properties": ["name", "schema_type", "fields", "required_fields"]},
            {"name": "integration", "description": "External system integration", "properties": ["name", "description", "protocol", "external_system", "direction"]},
        ]
    },
    "code_layer": {
        "description": "Source code artifacts",
        "types": [
            {"name": "module", "description": "Code module or package", "properties": ["name", "path", "language", "description"]},
            {"name": "class", "description": "Class or type definition", "properties": ["name", "description", "parent_class", "interfaces", "methods"]},
            {"name": "function", "description": "Function or method", "properties": ["name", "signature", "description", "parameters", "return_type"]},
            {"name": "interface", "description": "Interface or protocol definition", "properties": ["name", "description", "methods"]},
            {"name": "constant", "description": "Configuration constant or enum value", "properties": ["name", "value", "description"]},
            {"name": "configuration", "description": "Configuration setting", "properties": ["name", "value", "environment", "description"]},
        ]
    },
    "data_layer": {
        "description": "Database and data artifacts",
        "types": [
            {"name": "database", "description": "Database or data store", "properties": ["name", "type", "description"]},
            {"name": "table", "description": "Database table or collection", "properties": ["name", "description", "primary_key", "indexes"]},
            {"name": "column", "description": "Table column or field", "properties": ["name", "data_type", "nullable", "default_value", "constraints", "parent_table"]},
            {"name": "constraint", "description": "Database constraint (FK, unique, check)", "properties": ["name", "constraint_type", "definition", "parent_table"]},
            {"name": "index", "description": "Database index", "properties": ["name", "columns", "unique", "parent_table"]},
            {"name": "migration", "description": "Database migration script", "properties": ["name", "version", "description", "changes"]},
            {"name": "enum", "description": "Enumeration or lookup values", "properties": ["name", "values", "description"]},
        ]
    },
    "testing_layer": {
        "description": "Testing artifacts",
        "types": [
            {"name": "test_suite", "description": "Collection of related test cases", "properties": ["name", "description", "test_type", "coverage_area"]},
            {"name": "test_case", "description": "Individual test case", "properties": ["name", "description", "preconditions", "steps", "expected_result", "priority", "automated"]},
            {"name": "test_step", "description": "Step within a test case", "properties": ["name", "action", "expected_result", "test_data"]},
            {"name": "assertion", "description": "Test assertion or verification", "properties": ["name", "condition", "expected_value"]},
            {"name": "test_data", "description": "Test data set or fixture", "properties": ["name", "description", "data_format", "scope"]},
            {"name": "defect", "description": "Bug or defect report", "properties": ["name", "description", "severity", "status", "steps_to_reproduce", "affected_version"]},
            {"name": "incident", "description": "Production incident", "properties": ["name", "description", "severity", "impact", "root_cause", "resolution"]},
        ]
    },
    "delivery_layer": {
        "description": "Delivery and release artifacts",
        "types": [
            {"name": "release", "description": "Software release or version", "properties": ["name", "version", "release_date", "changes", "status"]},
            {"name": "sprint", "description": "Development sprint or iteration", "properties": ["name", "start_date", "end_date", "goals"]},
            {"name": "commit", "description": "Source code commit", "properties": ["name", "hash", "message", "author", "files_changed"]},
            {"name": "pull_request", "description": "Code review request", "properties": ["name", "description", "source_branch", "target_branch", "status", "reviewers"]},
            {"name": "ticket", "description": "Work item or task ticket", "properties": ["name", "description", "type", "status", "priority", "assignee"]},
            {"name": "deployment", "description": "Deployment to environment", "properties": ["name", "environment", "version", "timestamp", "status"]},
        ]
    },
    "organization_layer": {
        "description": "People and organizational artifacts",
        "types": [
            {"name": "team", "description": "Development team or squad", "properties": ["name", "description", "members", "responsibilities"]},
            {"name": "owner", "description": "Feature or component owner", "properties": ["name", "email", "role", "owned_components"]},
            {"name": "stakeholder", "description": "Business stakeholder", "properties": ["name", "role", "interests", "contact"]},
            {"name": "repository", "description": "Code repository", "properties": ["name", "url", "description", "language", "owner_team"]},
            {"name": "documentation", "description": "Documentation page or article", "properties": ["name", "url", "description", "doc_type", "last_updated"]},
        ]
    },
    "tooling_layer": {
        "description": "Tools and integration toolkits",
        "types": [
            {"name": "toolkit", "description": "Integration toolkit or connector (e.g., Jira Toolkit, GitHub Toolkit)", "properties": ["name", "description", "tools", "configuration_fields", "authentication"]},
            {"name": "tool", "description": "Individual tool or capability within a toolkit", "properties": ["name", "description", "parameters", "return_type", "parent_toolkit"]},
            {"name": "mcp_server", "description": "MCP (Model Context Protocol) server", "properties": ["name", "description", "transport", "tools", "resources"]},
            {"name": "mcp_tool", "description": "Tool exposed by an MCP server", "properties": ["name", "description", "input_schema", "parent_server"]},
            {"name": "mcp_resource", "description": "Resource exposed by an MCP server", "properties": ["name", "uri", "description", "mime_type"]},
            {"name": "connector", "description": "External system connector or adapter", "properties": ["name", "description", "target_system", "auth_type", "capabilities"]},
        ]
    },
}

RELATIONSHIP_TAXONOMY = {
    "structural": {
        "description": "Structural relationships",
        "types": [
            {"name": "contains", "description": "Parent contains child", "examples": ["module contains class", "screen contains ui_component", "toolkit contains tool"]},
            {"name": "extends", "description": "Inherits or extends", "examples": ["class extends parent_class", "epic contains feature"]},
            {"name": "implements", "description": "Implements interface or requirement", "examples": ["class implements interface", "function implements user_story"]},
            {"name": "imports", "description": "Import or include dependency", "examples": ["module imports module"]},
            {"name": "part_of", "description": "Part of larger whole", "examples": ["column part_of table", "step part_of test_case", "tool part_of toolkit"]},
            {"name": "provides", "description": "Provides capability or resource", "examples": ["toolkit provides tool", "mcp_server provides mcp_tool", "service provides api"]},
        ]
    },
    "behavioral": {
        "description": "Behavioral and runtime relationships",
        "types": [
            {"name": "calls", "description": "Invokes or calls", "examples": ["function calls function", "service calls api"]},
            {"name": "triggers", "description": "Triggers event or action", "examples": ["business_rule triggers workflow", "event triggers handler"]},
            {"name": "depends_on", "description": "Runtime dependency", "examples": ["service depends_on service", "feature depends_on feature"]},
            {"name": "uses", "description": "Uses or references", "examples": ["endpoint uses payload", "test_case uses test_data"]},
        ]
    },
    "data_lineage": {
        "description": "Data flow relationships",
        "types": [
            {"name": "stores_in", "description": "Data stored in", "examples": ["ui_field stores_in column", "endpoint stores_in table"]},
            {"name": "reads_from", "description": "Reads data from", "examples": ["endpoint reads_from table", "screen reads_from api"]},
            {"name": "transforms", "description": "Transforms data", "examples": ["function transforms payload"]},
            {"name": "maps_to", "description": "Data mapping", "examples": ["ui_field maps_to column", "attribute maps_to column"]},
        ]
    },
    "ui_product": {
        "description": "UI and product relationships",
        "types": [
            {"name": "shown_on", "description": "Displayed on screen/UI", "examples": ["ui_field shown_on screen", "domain_entity shown_on screen"]},
            {"name": "navigates_to", "description": "Navigation link", "examples": ["screen navigates_to screen", "button navigates_to screen"]},
            {"name": "validates", "description": "Validates input", "examples": ["business_rule validates ui_field"]},
        ]
    },
    "testing": {
        "description": "Testing relationships",
        "types": [
            {"name": "tests", "description": "Tests functionality", "examples": ["test_case tests feature", "test_case tests endpoint"]},
            {"name": "validates", "description": "Validates rule or requirement", "examples": ["test_case validates business_rule"]},
            {"name": "covers", "description": "Test coverage", "examples": ["test_suite covers feature", "test_case covers user_story"]},
            {"name": "reproduces", "description": "Reproduces defect", "examples": ["test_case reproduces defect"]},
        ]
    },
    "ownership": {
        "description": "Ownership and responsibility",
        "types": [
            {"name": "owned_by", "description": "Owned by team/person", "examples": ["service owned_by team", "feature owned_by owner"]},
            {"name": "maintained_by", "description": "Maintained by", "examples": ["repository maintained_by team"]},
            {"name": "reviewed_by", "description": "Reviewed by", "examples": ["pull_request reviewed_by owner"]},
            {"name": "assigned_to", "description": "Assigned to person", "examples": ["ticket assigned_to owner", "defect assigned_to owner"]},
        ]
    },
    "temporal": {
        "description": "Temporal and versioning relationships",
        "types": [
            {"name": "introduced_in", "description": "Introduced in release", "examples": ["feature introduced_in release", "api introduced_in release"]},
            {"name": "removed_in", "description": "Removed in release", "examples": ["endpoint removed_in release"]},
            {"name": "modified_in", "description": "Modified in release", "examples": ["table modified_in migration"]},
            {"name": "supersedes", "description": "Replaces previous version", "examples": ["api supersedes api", "release supersedes release"]},
            {"name": "blocks", "description": "Blocks progress", "examples": ["defect blocks feature", "ticket blocks ticket"]},
        ]
    },
    "semantic": {
        "description": "Semantic and conflict relationships",
        "types": [
            {"name": "related_to", "description": "General relationship", "examples": ["feature related_to feature", "ticket related_to defect"]},
            {"name": "duplicates", "description": "Duplicate of another", "examples": ["defect duplicates defect", "glossary_term duplicates glossary_term"]},
            {"name": "contradicts", "description": "Conflicts with", "examples": ["requirement contradicts requirement", "business_rule contradicts business_rule"]},
            {"name": "references", "description": "References document", "examples": ["ticket references documentation", "test_case references user_story"]},
            {"name": "synonym_of", "description": "Synonym relationship", "examples": ["glossary_term synonym_of glossary_term"]},
        ]
    },
}


def get_entity_types_for_doc_type(doc_type: str) -> List[Dict[str, Any]]:
    """Get relevant entity types for a document type."""
    mapping = {
        "code": ["code_layer", "service_layer"],
        "api_spec": ["service_layer", "data_layer"],
        "requirements": ["product_layer", "domain_layer"],
        "architecture": ["service_layer", "data_layer", "organization_layer"],
        "config": ["code_layer", "data_layer"],
        "database": ["data_layer"],
        "test": ["testing_layer", "product_layer"],
        "documentation": ["organization_layer", "domain_layer", "product_layer"],
        "ticket": ["delivery_layer", "testing_layer", "product_layer"],
        "commit": ["delivery_layer", "code_layer"],
    }
    
    layers = mapping.get(doc_type, list(ENTITY_TAXONOMY.keys()))
    types = []
    for layer in layers:
        if layer in ENTITY_TAXONOMY:
            types.extend(ENTITY_TAXONOMY[layer]["types"])
    return types


def get_all_entity_types() -> List[Dict[str, Any]]:
    """Get all entity types from taxonomy."""
    types = []
    for layer_data in ENTITY_TAXONOMY.values():
        types.extend(layer_data["types"])
    return types


def get_all_relationship_types() -> List[Dict[str, Any]]:
    """Get all relationship types from taxonomy."""
    types = []
    for category_data in RELATIONSHIP_TAXONOMY.values():
        types.extend(category_data["types"])
    return types


# ============================================================================
# PROMPTS
# ============================================================================

DOCUMENT_CLASSIFIER_PROMPT = """Analyze the following document chunk and classify it into one of these document types:
- code: Source code files (Python, JavaScript, Java, etc.)
- api_spec: API specifications (OpenAPI, Swagger, GraphQL schemas)
- requirements: Requirements documents, user stories, specs
- architecture: Architecture documentation, design documents
- config: Configuration files (YAML, JSON config, env files)
- database: Database schemas, migrations, SQL
- test: Test files, test cases
- documentation: General documentation, READMEs, guides
- ticket: Issue tickets, bug reports, feature requests (Jira, GitHub issues)
- commit: Git commits, changelogs
- ui: UI component definitions, screen layouts, UX flows
- other: Anything that doesn't fit the above

Document content:
---
{content}
---

Metadata:
{metadata}

Respond with ONLY a JSON object:
{{"doc_type": "<type>", "confidence": <0.0-1.0>}}
"""


SCHEMA_DISCOVERY_PROMPT = """Analyze the following document samples to discover entity types and relationship types for a comprehensive knowledge graph.

## Entity Layers to Consider

### Product Layer (UI/UX artifacts)
- Epic, Feature, User Story (product requirements)
- Screen, Page, View (UI containers)
- UX Flow, Journey (navigation flows)
- UI Component, Field (interactive elements with validation rules)

### Domain Layer (Business concepts)
- Domain Entity (Customer, Order, Product - core business objects)
- Attribute (properties of domain entities)
- Business Rule (conditions, triggers, exceptions)
- Business Event (domain events that trigger actions)
- Glossary Term (vocabulary definitions, synonyms)

### Service Layer (APIs and integrations)
- Service, Microservice
- API, Endpoint (with method, path, auth)
- Payload, Schema (request/response structures)
- Integration (external system connections)

### Code Layer (Implementation)
- Module, Package
- Class, Interface
- Function, Method
- Configuration, Constant

### Data Layer (Storage)
- Database, Table, Collection
- Column, Field (with type, constraints, nullable)
- Constraint, Index, Enum
- Migration Script

### Testing Layer
- Test Suite, Test Case (with preconditions, steps, expected results)
- Test Data, Fixture
- Defect, Bug (with severity, reproduction steps)
- Incident (production issues)

### Delivery Layer
- Release, Version
- Sprint, Iteration
- Commit, Pull Request
- Ticket, Task

### Organization Layer
- Team, Squad (ownership)
- Owner, SME (subject matter experts)
- Repository (code location)
- Documentation (wiki, guides)

## Relationship Categories

- Structural: contains, extends, implements, imports, part_of
- Behavioral: calls, triggers, depends_on, uses
- Data Lineage: stores_in, reads_from, maps_to, transforms
- UI/Product: shown_on, navigates_to, validates
- Testing: tests, validates, covers, reproduces
- Ownership: owned_by, maintained_by, assigned_to, reviewed_by
- Temporal: introduced_in, removed_in, modified_in, supersedes, blocks
- Semantic: related_to, duplicates, contradicts, references, synonym_of

---

Document samples:
---
{samples}
---

Based on these samples, identify which entity types and relationships are most relevant.
Group by layer and include properties that would be valuable to extract.

Respond with ONLY a JSON object:
{{
  "entity_types": [
    {{"name": "<type_name>", "layer": "<layer_name>", "description": "<description>", "properties": ["<prop1>", "<prop2>"]}}
  ],
  "relation_types": [
    {{"name": "<relation_name>", "category": "<category>", "description": "<description>", "source_types": ["<entity_type>"], "target_types": ["<entity_type>"]}}
  ]
}}
"""


ENTITY_EXTRACTION_PROMPT = """Extract entities from the following document for a knowledge graph.

{schema_section}

Document content (with line numbers):
---
{content}
---

Source file: {file_path}
Source toolkit: {source_toolkit}

Extract all relevant entities. For each entity provide:
- A unique ID (use existing identifiers when available, like class names, function names, ticket IDs)
- The entity type
- The line range where this entity is defined or described (provide enough context - at least 3-5 lines minimum, never a single line)
- Properties including at minimum: name, description

IMPORTANT: line_start and line_end should capture the full context of the entity definition, not just a single mention.
If an entity is mentioned on one line but defined or described across multiple lines, use the broader range.
Single-line references (line_start == line_end) are discouraged - expand to include surrounding context.

Respond with ONLY a JSON array:
[
  {{
    "id": "<unique_id>",
    "type": "<entity_type>",
    "name": "<entity_name>",
    "line_start": <start_line_number>,
    "line_end": <end_line_number>,
    "properties": {{
      "description": "<brief_description>",
      ...
    }}
  }}
]
"""


RELATION_EXTRACTION_PROMPT = """Extract relationships between the entities listed below based on the document content.

## Document content:
---
{content}
---

## Available Entities (ID -> Name):
{entities_list}

{schema_section}

## Instructions:
1. Look for relationships mentioned or implied in the document
2. For source_id and target_id, you MUST use EXACTLY the ID shown before the arrow (->)
3. Common relationship types: contains, references, depends_on, implements, extends, uses, part_of, describes, follows, requires, configures

## Output Format:
Respond with ONLY a JSON array. Use the EXACT entity IDs from the list above:
[
  {{
    "source_id": "<exact-id-from-list>",
    "relation_type": "<relationship_type>",
    "target_id": "<exact-id-from-list>",
    "confidence": <0.0-1.0>
  }}
]

If no relationships are found, return an empty array: []

EXAMPLE: If entities are "Migration Guide (407b9c0c2048)" and "Before State (bc4612fc3d87)",
a valid relation would be: {{"source_id": "407b9c0c2048", "relation_type": "describes", "target_id": "bc4612fc3d87", "confidence": 0.9}}
"""


DEDUPLICATION_PROMPT = """Analyze these entity candidates and identify which ones refer to the same real-world entity.

Entity candidates:
{entities_json}

Group entities that refer to the same thing. Consider:
- Same names with different casing
- Abbreviations vs full names
- Partial matches that clearly refer to the same entity

Respond with ONLY a JSON object mapping representative ID to list of duplicate IDs:
{{
  "<canonical_id>": ["<duplicate_id_1>", "<duplicate_id_2>"]
}}
"""


class DocumentClassifier:
    """Classifies documents by type using LLM."""
    
    def __init__(self, llm: Any):
        self.llm = llm
        self.prompt = ChatPromptTemplate.from_template(DOCUMENT_CLASSIFIER_PROMPT)
        self.parser = JsonOutputParser()
    
    def classify(self, document: Document) -> str:
        """Classify a single document."""
        try:
            content = document.page_content[:3000]  # Limit content size
            metadata = json.dumps(document.metadata, default=str)[:500]
            
            chain = self.prompt | self.llm | self.parser
            result = chain.invoke({
                "content": content,
                "metadata": metadata
            })
            
            return result.get('doc_type', 'other')
        except Exception as e:
            logger.warning(f"Classification failed: {e}")
            return 'other'
    
    def classify_batch(self, documents: List[Document]) -> List[str]:
        """Classify multiple documents."""
        return [self.classify(doc) for doc in documents]


class EntitySchemaDiscoverer:
    """Discovers entity and relation schemas from document samples using LLM."""
    
    def __init__(self, llm: Any):
        self.llm = llm
        self.prompt = ChatPromptTemplate.from_template(SCHEMA_DISCOVERY_PROMPT)
        self.parser = JsonOutputParser()
    
    def discover(self, documents: List[Document]) -> Dict[str, Any]:
        """
        Discover entity and relation types from document samples.
        
        Args:
            documents: Sample documents to analyze
            
        Returns:
            Schema dictionary with entity_types and relation_types
        """
        try:
            # Build samples string
            samples_parts = []
            for i, doc in enumerate(documents[:20]):  # Limit samples
                content = doc.page_content[:500]
                doc_type = doc.metadata.get('doc_type', 'unknown')
                source = doc.metadata.get('source_toolkit', 'unknown')
                samples_parts.append(f"[Sample {i+1} - {doc_type} from {source}]\n{content}\n")
            
            samples = "\n---\n".join(samples_parts)
            
            chain = self.prompt | self.llm | self.parser
            result = chain.invoke({"samples": samples})
            
            # Validate structure
            if 'entity_types' not in result:
                result['entity_types'] = []
            if 'relation_types' not in result:
                result['relation_types'] = []
            
            return result
        except Exception as e:
            logger.error(f"Schema discovery failed: {e}")
            return self._default_schema()
    
    def _default_schema(self) -> Dict[str, Any]:
        """Return a default schema as fallback."""
        return {
            "entity_types": [
                {"name": "service", "description": "A software service or microservice", "properties": ["name", "description"]},
                {"name": "module", "description": "A code module or package", "properties": ["name", "path"]},
                {"name": "function", "description": "A function or method", "properties": ["name", "signature"]},
                {"name": "api", "description": "An API endpoint", "properties": ["name", "path", "method"]},
                {"name": "feature", "description": "A product feature", "properties": ["name", "description"]},
                {"name": "requirement", "description": "A requirement or user story", "properties": ["name", "description"]},
            ],
            "relation_types": [
                {"name": "depends_on", "description": "Dependency relationship", "source_types": ["*"], "target_types": ["*"]},
                {"name": "calls", "description": "Function/API call", "source_types": ["function", "service"], "target_types": ["function", "api"]},
                {"name": "implements", "description": "Implementation relationship", "source_types": ["module", "function"], "target_types": ["feature", "requirement"]},
                {"name": "contains", "description": "Containment relationship", "source_types": ["service", "module"], "target_types": ["module", "function"]},
            ]
        }


class EntityExtractor:
    """Extracts entities from documents using LLM."""
    
    def __init__(self, llm: Any, embedding: Optional[Any] = None, max_retries: int = 3, retry_delay: float = 2.0):
        self.llm = llm
        self.embedding = embedding
        self.prompt = ChatPromptTemplate.from_template(ENTITY_EXTRACTION_PROMPT)
        self.parser = JsonOutputParser()
        self._entity_cache: Dict[str, Dict] = {}
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    def extract(
        self,
        document: Document,
        schema: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract entities from a single document with retry logic.
        
        Args:
            document: Document to extract from
            schema: Optional schema to guide extraction
            
        Returns:
            List of extracted entities with line numbers for citations
        """
        import time
        
        file_path = document.metadata.get('file_path', document.metadata.get('source', 'unknown'))
        source_toolkit = document.metadata.get('source_toolkit', 'filesystem')
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                content = document.page_content
                
                # Add line numbers to content for better extraction
                lines = content.split('\n')
                numbered_content = '\n'.join(
                    f"{i+1:4d} | {line}" 
                    for i, line in enumerate(lines[:200])  # Limit lines
                )
                
                # Build schema section
                schema_section = ""
                if schema and schema.get('entity_types'):
                    types_str = ", ".join([et['name'] for et in schema['entity_types']])
                    schema_section = f"Entity types to extract: {types_str}\n"
                    for et in schema['entity_types']:
                        schema_section += f"- {et['name']}: {et.get('description', '')}\n"
                
                chain = self.prompt | self.llm | self.parser
                result = chain.invoke({
                    "content": numbered_content,
                    "file_path": file_path,
                    "source_toolkit": source_toolkit,
                    "schema_section": schema_section
                })
                
                if not isinstance(result, list):
                    result = [result] if result else []
                
                # Track total lines in document for boundary checks
                total_lines = len(lines)
                
                # Add source tracking and normalize structure
                for entity in result:
                    entity['source_toolkit'] = source_toolkit
                    entity['file_path'] = file_path
                    
                    # Ensure name is at top level
                    if 'name' not in entity and 'properties' in entity:
                        entity['name'] = entity['properties'].get('name', entity.get('id', 'unnamed'))
                    
                    # Expand small line ranges to provide meaningful context
                    # Minimum span should be 3 lines
                    line_start = entity.get('line_start', 1)
                    line_end = entity.get('line_end', line_start)
                    span = line_end - line_start
                    
                    if span < 2:  # Less than 3 lines of context
                        # Expand range symmetrically around the center
                        center = (line_start + line_end) // 2
                        # Add 2 lines on each side (for 5 line minimum)
                        new_start = max(1, center - 2)
                        new_end = min(total_lines, center + 2)
                        entity['line_start'] = new_start
                        entity['line_end'] = new_end
                
                return result
                
            except Exception as e:
                last_error = e
                attempt_num = attempt + 1
                
                if attempt_num < self.max_retries:
                    # Calculate delay with exponential backoff
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Entity extraction failed for '{file_path}' (attempt {attempt_num}/{self.max_retries}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Entity extraction failed for '{file_path}' after {self.max_retries} attempts: {e}"
                    )
        
        # All retries exhausted - raise exception to signal failure
        raise RuntimeError(
            f"Entity extraction failed for '{file_path}' after {self.max_retries} attempts: {last_error}"
        )
    
    def extract_batch(
        self,
        documents: List[Document],
        schema: Optional[Dict[str, Any]] = None,
        skip_on_error: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Extract entities from multiple documents with deduplication.
        
        Args:
            documents: List of documents to extract from
            schema: Optional schema to guide extraction
            skip_on_error: If True, skip documents that fail extraction after retries.
                          If False (default), raise exception on first failure.
        
        Returns:
            List of extracted entities
        """
        all_entities = []
        failed_docs = []
        
        for doc in documents:
            try:
                entities = self.extract(doc, schema)
                all_entities.extend(entities)
            except RuntimeError as e:
                file_path = doc.metadata.get('file_path', doc.metadata.get('source', 'unknown'))
                if skip_on_error:
                    logger.warning(f"Skipping document '{file_path}' due to extraction failure: {e}")
                    failed_docs.append(file_path)
                else:
                    raise
        
        if failed_docs:
            logger.warning(f"Skipped {len(failed_docs)} documents due to extraction failures: {failed_docs[:5]}{'...' if len(failed_docs) > 5 else ''}")
        
        # Deduplicate
        deduped = self._deduplicate_entities(all_entities)
        
        return deduped
    
    def _deduplicate_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate entities using simple heuristics.
        
        For more complex deduplication, LLM-based approach can be used.
        """
        seen = {}  # (type, normalized_name) -> entity
        deduped = []
        
        for entity in entities:
            etype = entity.get('type', 'unknown')
            name = entity.get('properties', {}).get('name', entity.get('id', ''))
            
            # Normalize name
            normalized = name.lower().strip().replace('_', ' ').replace('-', ' ')
            key = (etype, normalized)
            
            if key in seen:
                # Merge properties
                existing = seen[key]
                for prop_key, prop_value in entity.get('properties', {}).items():
                    if prop_key not in existing.get('properties', {}):
                        existing.setdefault('properties', {})[prop_key] = prop_value
            else:
                seen[key] = entity
                deduped.append(entity)
        
        return deduped


class RelationExtractor:
    """Extracts relationships between entities using LLM."""
    
    def __init__(self, llm: Any, max_retries: int = 3, retry_delay: float = 2.0):
        self.llm = llm
        self.prompt = ChatPromptTemplate.from_template(RELATION_EXTRACTION_PROMPT)
        self.parser = JsonOutputParser()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    def extract(
        self,
        document: Document,
        entities: List[Dict[str, Any]],
        schema: Optional[Dict[str, Any]] = None,
        confidence_threshold: float = 0.5,
        all_entities: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract relationships from a document given known entities with retry logic.
        
        Args:
            document: Document to analyze
            entities: Entities known to be in this document (for LLM context)
            schema: Optional schema to guide extraction
            confidence_threshold: Minimum confidence to include
            all_entities: All entities in graph (for ID resolution across sources)
            
        Returns:
            List of extracted relations
        """
        import time
        
        if not entities:
            return []
        
        # Use all_entities for ID resolution if provided, otherwise just doc entities
        entities_for_lookup = all_entities if all_entities else entities
        
        file_path = document.metadata.get('file_path', document.metadata.get('source', 'unknown'))
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                content = document.page_content[:4000]
                
                # Filter entities from this document
                doc_id = document.metadata.get('source')
                doc_entities = [e for e in entities if e.get('source_doc_id') == doc_id]
                
                if not doc_entities:
                    doc_entities = entities[:20]  # Fall back to first N entities
                
                # Format entities with ID first for clarity: "ID -> Name (type)"
                entities_list = "\n".join([
                    f"- {e.get('id')} -> {e.get('name', 'unnamed')} ({e.get('type', 'unknown')})"
                    for e in doc_entities[:30]
                ])
                
                # Build schema section
                schema_section = ""
                if schema and schema.get('relation_types'):
                    types_str = ", ".join([rt['name'] for rt in schema['relation_types']])
                    schema_section = f"## Relationship types: {types_str}\n"
                    for rt in schema['relation_types']:
                        schema_section += f"- {rt['name']}: {rt.get('description', '')}\n"
                
                chain = self.prompt | self.llm | self.parser
                result = chain.invoke({
                    "content": content,
                    "entities_list": entities_list,
                    "schema_section": schema_section
                })
                
                if not isinstance(result, list):
                    result = [result] if result else []
                
                # Build lookup tables from ALL entities (enables cross-source resolution)
                # LLMs often use names instead of hex IDs, so we map both
                id_lookup = {}
                name_to_id = {}  # For fuzzy matching fallback
                
                for e in entities_for_lookup:
                    entity_id = e.get('id', '')
                    entity_name = e.get('name', '')
                    entity_type = e.get('type', '')
                    
                    if not entity_id:
                        continue
                    
                    # Direct ID match
                    id_lookup[entity_id] = entity_id
                    id_lookup[entity_id.lower()] = entity_id
                    
                    # Name-based lookups (what LLM often returns)
                    if entity_name:
                        # Exact name
                        id_lookup[entity_name] = entity_id
                        id_lookup[entity_name.lower()] = entity_id
                        # snake_case version
                        snake_name = entity_name.lower().replace(' ', '_').replace('-', '_').replace(':', '_')
                        id_lookup[snake_name] = entity_id
                        # Remove articles/filler words for matching
                        short_snake = snake_name.replace('_a_', '_').replace('_an_', '_').replace('_the_', '_').replace('_your_', '_').replace('_my_', '_')
                        id_lookup[short_snake] = entity_id
                        # type:name format
                        type_name = f"{entity_type}:{snake_name}"
                        id_lookup[type_name] = entity_id
                        id_lookup[type_name.lower()] = entity_id
                        # Store for fuzzy matching with word sets
                        words = set(snake_name.split('_'))
                        name_to_id[snake_name] = (entity_id, words)
                
                def resolve_id(ref: str) -> Optional[str]:
                    """Resolve an entity reference to its actual ID."""
                    if not ref:
                        return None
                    # Direct lookup
                    if ref in id_lookup:
                        return id_lookup[ref]
                    ref_lower = ref.lower()
                    if ref_lower in id_lookup:
                        return id_lookup[ref_lower]
                    # Snake case the reference
                    ref_snake = ref_lower.replace(' ', '_').replace('-', '_').replace(':', '_')
                    if ref_snake in id_lookup:
                        return id_lookup[ref_snake]
                    
                    # Fuzzy matching: substring or word overlap
                    ref_words = set(ref_snake.split('_'))
                    best_match = None
                    best_score = 0
                    
                    for name, (eid, name_words) in name_to_id.items():
                        # Substring match
                        if ref_snake in name or name in ref_snake:
                            return eid
                        
                        # Word overlap score
                        overlap = len(ref_words & name_words)
                        if overlap >= 2 and overlap > best_score:
                            # At least 2 words must match
                            best_score = overlap
                            best_match = eid
                    
                    return best_match
                
                # Resolve relations to actual entity IDs
                resolved = []
                logger.info(f"Relation extraction got {len(result)} raw relations from LLM")
                logger.info(f"ID lookup has {len(id_lookup)} entries, name_to_id has {len(name_to_id)} entries")
                
                for r in result:
                    source = r.get('source_id', '')
                    target = r.get('target_id', '')
                    
                    # Try to resolve source and target
                    resolved_source = resolve_id(source)
                    resolved_target = resolve_id(target)
                    
                    logger.debug(f"Resolving: {source} -> {resolved_source}, {target} -> {resolved_target}")
                    
                    if resolved_source and resolved_target:
                        r['source_id'] = resolved_source
                        r['target_id'] = resolved_target
                        resolved.append(r)
                    else:
                        logger.warning(f"Could not resolve relation: {source} ({resolved_source}) -> {target} ({resolved_target})")
                
                logger.info(f"Resolved {len(resolved)} relations successfully")
                
                # Filter by confidence
                filtered = [
                    r for r in resolved 
                    if r.get('confidence', 0) >= confidence_threshold
                ]
                
                return filtered
                
            except Exception as e:
                last_error = e
                attempt_num = attempt + 1
                
                if attempt_num < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Relation extraction failed for '{file_path}' (attempt {attempt_num}/{self.max_retries}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.warning(
                        f"Relation extraction failed for '{file_path}' after {self.max_retries} attempts: {e}. Skipping."
                    )
        
        # Return empty list on failure (relations are optional)
        return []
    
    def extract_batch(
        self,
        documents: List[Document],
        entities: List[Dict[str, Any]],
        schema: Optional[Dict[str, Any]] = None,
        confidence_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Extract relations from multiple documents."""
        all_relations = []
        
        for doc in documents:
            relations = self.extract(
                doc, 
                entities, 
                schema=schema,
                confidence_threshold=confidence_threshold
            )
            all_relations.extend(relations)
        
        # Deduplicate relations
        return self._deduplicate_relations(all_relations)
    
    def _deduplicate_relations(self, relations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate relations by source-type-target key."""
        seen = {}
        deduped = []
        
        for rel in relations:
            key = (
                rel.get('source_id'),
                rel.get('relation_type'),
                rel.get('target_id')
            )
            
            if key not in seen:
                seen[key] = rel
                deduped.append(rel)
            else:
                # Keep higher confidence
                if rel.get('confidence', 0) > seen[key].get('confidence', 0):
                    seen[key] = rel
                    # Update in deduped list
                    for i, r in enumerate(deduped):
                        if (r.get('source_id'), r.get('relation_type'), r.get('target_id')) == key:
                            deduped[i] = rel
                            break
        
        return deduped


class EntityDeduplicator:
    """LLM-based entity deduplication for complex cases."""
    
    def __init__(self, llm: Any):
        self.llm = llm
        self.prompt = ChatPromptTemplate.from_template(DEDUPLICATION_PROMPT)
        self.parser = JsonOutputParser()
    
    def find_duplicates(self, entities: List[Dict[str, Any]], batch_size: int = 50) -> Dict[str, List[str]]:
        """
        Find duplicate entities using LLM.
        
        Args:
            entities: List of entity candidates
            batch_size: Number of entities to process at once
            
        Returns:
            Mapping of canonical ID to list of duplicate IDs
        """
        all_duplicates = {}
        
        # Process in batches
        for i in range(0, len(entities), batch_size):
            batch = entities[i:i + batch_size]
            
            try:
                entities_json = json.dumps(batch, indent=2, default=str)
                
                chain = self.prompt | self.llm | self.parser
                result = chain.invoke({"entities_json": entities_json})
                
                all_duplicates.update(result)
            except Exception as e:
                logger.warning(f"Deduplication batch failed: {e}")
        
        return all_duplicates
    
    def merge_duplicates(
        self,
        entities: List[Dict[str, Any]],
        duplicates: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:
        """
        Merge duplicate entities based on duplicate mapping.
        
        Args:
            entities: Original entity list
            duplicates: Mapping from canonical ID to duplicate IDs
            
        Returns:
            Merged entity list
        """
        # Build ID to entity mapping
        id_to_entity = {e.get('id'): e for e in entities}
        
        # Build set of IDs to skip (duplicates)
        skip_ids = set()
        for dup_list in duplicates.values():
            skip_ids.update(dup_list)
        
        merged = []
        for entity in entities:
            entity_id = entity.get('id')
            
            if entity_id in skip_ids:
                continue
            
            # If this is a canonical entity, merge properties from duplicates
            if entity_id in duplicates:
                for dup_id in duplicates[entity_id]:
                    if dup_id in id_to_entity:
                        dup = id_to_entity[dup_id]
                        # Merge properties
                        for key, value in dup.get('properties', {}).items():
                            if key not in entity.get('properties', {}):
                                entity.setdefault('properties', {})[key] = value
            
            merged.append(entity)
        
        return merged
