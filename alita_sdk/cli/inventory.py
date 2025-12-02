"""
CLI commands for Inventory Ingestion Pipeline.

Provides command-line interface for running knowledge graph ingestion
from various source toolkits (GitHub, ADO, LocalGit, etc.).

Usage:
    # Ingest using a toolkit config file (preferred)
    alita inventory ingest --toolkit .alita/tools/github.json --graph ./graph.json -w "*.md"
    
    # Ingest from a local git repository
    alita inventory ingest --source localgit --path /path/to/repo --graph ./graph.json
    
    # Use a config file for LLM/embedding/guardrails settings
    alita inventory ingest --toolkit ./github.json -g ./graph.json --config ingestion-config.yml
    
    # Generate config template
    alita inventory init-config
    
    # Show graph stats
    alita inventory stats --graph ./graph.json
    
    # Search the graph
    alita inventory search "PaymentService" --graph ./graph.json
"""

import click
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


@click.group()
def inventory():
    """Inventory knowledge graph commands."""
    pass


@inventory.command('init-config')
@click.option('--output', '-o', default='./ingestion-config.yml', type=click.Path(),
              help='Output path for config template')
def init_config(output: str):
    """
    Generate a configuration template file.
    
    Example:
        alita inventory init-config -o ./my-config.yml
    """
    from alita_sdk.community.inventory import generate_config_template
    
    path = generate_config_template(output)
    click.echo(f"✅ Configuration template created: {path}")
    click.echo("\nEdit this file to configure:")
    click.echo("  - LLM provider and model (openai, azure, anthropic, ollama)")
    click.echo("  - Embeddings for semantic search")
    click.echo("  - Guardrails (rate limits, content filtering, thresholds)")


@inventory.command('ingest')
@click.option('--toolkit', '-t', required=True, type=click.Path(exists=True),
              help='Path to toolkit config JSON (e.g., .alita/tools/github.json)')
@click.option('--graph', '-g', required=True, type=click.Path(),
              help='Path to output graph JSON file')
@click.option('--config', '-c', type=click.Path(exists=True),
              help='Path to YAML/JSON config file for LLM, embeddings, guardrails')
@click.option('--whitelist', '-w', multiple=True,
              help='File patterns to include (e.g., -w "*.py" -w "*.md")')
@click.option('--blacklist', '-x', multiple=True,
              help='File patterns to exclude (e.g., -x "*test*" -x "*vendor*")')
@click.option('--no-relations', is_flag=True,
              help='Skip relation extraction (faster)')
@click.option('--model', '-m', default=None,
              help='LLM model name (overrides config file)')
@click.option('--limit', '-l', type=int, default=None,
              help='Limit number of documents to process (for testing)')
@click.option('--fresh', '-f', is_flag=True,
              help='Start fresh - delete existing graph and create new one')
@click.pass_context
def ingest(ctx, toolkit: str, graph: str, config: Optional[str], 
           whitelist: tuple, blacklist: tuple, no_relations: bool, 
           model: Optional[str], limit: Optional[int], fresh: bool):
    """
    Run ingestion pipeline to build/update a knowledge graph.
    
    All source configuration (type, repository, branch, credentials) comes
    from the toolkit config file.
    
    Examples:
    
        # Ingest markdown files from GitHub repo
        alita inventory ingest -t .alita/tools/github.json -g ./graph.json -w "*.md"
        
        # Ingest with LLM/guardrails config
        alita inventory ingest -t .alita/tools/github.json -g ./graph.json -c ./config.yml
        
        # Ingest Python files, skip relations
        alita inventory ingest -t .alita/tools/localgit.json -g ./graph.json -w "*.py" --no-relations
    """
    # Load toolkit config
    toolkit_config = _load_toolkit_config(toolkit)
    click.echo(f"📦 Loaded toolkit config: {toolkit}")
    
    # Get source type from toolkit
    source_type = toolkit_config.get('type')
    if not source_type:
        raise click.ClickException(f"Toolkit config missing 'type' field: {toolkit}")
    click.echo(f"   Type: {source_type}")
    
    # Get toolkit name (used as source identifier in the graph)
    # Falls back to source_type if toolkit_name not specified
    source_name = toolkit_config.get('toolkit_name') or source_type
    click.echo(f"   Name: {source_name}")
    
    # Get repo/branch from toolkit config
    repo = toolkit_config.get('repository')
    if repo:
        click.echo(f"   Repository: {repo}")
    
    branch = toolkit_config.get('active_branch') or toolkit_config.get('base_branch') or 'main'
    click.echo(f"   Branch: {branch}")
    
    # Get path for local sources
    path = toolkit_config.get('git_root_dir') or toolkit_config.get('path')
    if path:
        click.echo(f"   Path: {path}")
    
    # Validate required fields based on source type
    if source_type in ('github', 'ado') and not repo:
        raise click.ClickException(f"Toolkit config missing 'repository' for source '{source_type}'")
    
    if source_type in ('localgit', 'filesystem') and not path:
        raise click.ClickException(f"Toolkit config missing 'git_root_dir' or 'path' for source '{source_type}'")
    
    # Handle --fresh option: delete existing graph
    if fresh and os.path.exists(graph):
        click.echo(f"🗑️  Fresh mode: deleting existing graph at {graph}")
        os.remove(graph)
    
    click.echo(f"🚀 Starting ingestion from {source_name} ({source_type})...")
    
    # Progress callback
    def progress(message: str, phase: str):
        click.echo(f"  [{phase}] {message}")
    
    try:
        from alita_sdk.community.inventory import IngestionPipeline, IngestionConfig
        
        # Load configuration
        if config:
            click.echo(f"📋 Loading config from {config}")
            if config.endswith('.yml') or config.endswith('.yaml'):
                ingestion_config = IngestionConfig.from_yaml(config)
            else:
                ingestion_config = IngestionConfig.from_json(config)
            
            # Override model if specified on command line
            if model:
                ingestion_config.llm_model = model
            
            # Override graph path
            ingestion_config.graph_path = graph
            
            # Get LLM using the model name and temperature from config
            llm = _get_llm(ctx, ingestion_config.llm_model, ingestion_config.temperature)
            
            pipeline = IngestionPipeline(
                llm=llm,
                graph_path=ingestion_config.graph_path,
                guardrails=ingestion_config.guardrails,
            )
        else:
            # Fall back to environment-based config
            click.echo("📋 Loading config from environment")
            llm = _get_llm(ctx, model)
            pipeline = IngestionPipeline(
                llm=llm,
                graph_path=graph,
            )
        
        # Set progress callback
        pipeline.progress_callback = progress
        
        # Show existing graph status
        graph_stats = pipeline.get_stats()
        if graph_stats['node_count'] > 0:
            click.echo(f"📊 Existing graph: {graph_stats['node_count']} entities, {graph_stats['edge_count']} relations")
            click.echo("   New entities will be ADDED to existing graph")
        
        # Get source toolkit from config and register it
        source_toolkit = _get_source_toolkit(toolkit_config)
        pipeline.register_toolkit(source_name, source_toolkit)
        
        # Run ingestion
        if limit:
            click.echo(f"⚠️  Limiting to {limit} documents (test mode)")
        
        result = pipeline.run(
            source=source_name,
            branch=branch,
            whitelist=list(whitelist) if whitelist else None,
            blacklist=list(blacklist) if blacklist else None,
            extract_relations=not no_relations,
            max_documents=limit,
        )
        
        # Show result
        if result.success:
            click.echo(f"\n✅ Ingestion complete!")
            click.echo(f"   Documents processed: {result.documents_processed}")
            click.echo(f"   Entities extracted: {result.entities_added}")
            click.echo(f"   Relations extracted: {result.relations_added}")
            click.echo(f"   Duration: {result.duration_seconds:.1f}s")
            click.echo(f"   Graph saved to: {graph}")
        else:
            click.echo(f"\n❌ Ingestion failed!")
            for error in result.errors:
                click.echo(f"   Error: {error}")
            sys.exit(1)
            
    except Exception as e:
        logger.exception("Ingestion failed")
        raise click.ClickException(str(e))


@inventory.command('stats')
@click.option('--graph', '-g', required=True, type=click.Path(exists=True),
              help='Path to graph JSON file')
def stats(graph: str):
    """
    Show knowledge graph statistics.
    
    Example:
        alita inventory stats -g ./graph.json
    """
    try:
        from alita_sdk.community.inventory import KnowledgeGraph
        
        kg = KnowledgeGraph()
        kg.load_from_json(graph)
        stats = kg.get_stats()
        
        click.echo(f"\n📊 Knowledge Graph Statistics")
        click.echo(f"   Path: {graph}")
        click.echo(f"\n   Entities: {stats['node_count']}")
        click.echo(f"   Relations: {stats['edge_count']}")
        
        if stats['entity_types']:
            click.echo(f"\n   Entity Types:")
            for etype, count in sorted(stats['entity_types'].items(), key=lambda x: -x[1]):
                click.echo(f"     - {etype}: {count}")
        
        if stats['relation_types']:
            click.echo(f"\n   Relation Types:")
            for rtype, count in sorted(stats['relation_types'].items(), key=lambda x: -x[1]):
                click.echo(f"     - {rtype}: {count}")
        
        if stats['source_toolkits']:
            click.echo(f"\n   Sources: {', '.join(stats['source_toolkits'])}")
        
        if stats['last_saved']:
            click.echo(f"\n   Last updated: {stats['last_saved']}")
        
        click.echo()
        
    except FileNotFoundError:
        raise click.ClickException(f"Graph file not found: {graph}")
    except Exception as e:
        raise click.ClickException(str(e))


@inventory.command('search')
@click.argument('query')
@click.option('--graph', '-g', required=True, type=click.Path(exists=True),
              help='Path to graph JSON file')
@click.option('--type', '-t', 'entity_type', default=None,
              help='Filter by entity type')
@click.option('--limit', '-n', default=10, type=int,
              help='Maximum results (default: 10)')
def search(query: str, graph: str, entity_type: Optional[str], limit: int):
    """
    Search for entities in the knowledge graph.
    
    Example:
        alita inventory search "Payment" -g ./graph.json
        alita inventory search "User" -g ./graph.json --type class
    """
    try:
        from alita_sdk.community.inventory import KnowledgeGraph
        
        kg = KnowledgeGraph()
        kg.load_from_json(graph)
        
        results = kg.search(query, top_k=limit, entity_type=entity_type)
        
        if not results:
            click.echo(f"No entities found matching '{query}'")
            return
        
        click.echo(f"\n🔍 Found {len(results)} entities matching '{query}':\n")
        
        for i, result in enumerate(results, 1):
            entity = result['entity']
            citation = entity.get('citation', {})
            
            click.echo(f"{i}. {entity.get('name')} ({entity.get('type')})")
            
            if citation:
                file_path = citation.get('file_path', 'unknown')
                line_info = ""
                if citation.get('line_start'):
                    line_info = f":{citation['line_start']}"
                    if citation.get('line_end'):
                        line_info += f"-{citation['line_end']}"
                click.echo(f"   📍 {file_path}{line_info}")
            
            # Show description if available
            if entity.get('description'):
                desc = entity['description'][:80]
                if len(entity['description']) > 80:
                    desc += "..."
                click.echo(f"   {desc}")
            
            click.echo()
        
    except FileNotFoundError:
        raise click.ClickException(f"Graph file not found: {graph}")
    except Exception as e:
        raise click.ClickException(str(e))


@inventory.command('entity')
@click.argument('name')
@click.option('--graph', '-g', required=True, type=click.Path(exists=True),
              help='Path to graph JSON file')
@click.option('--relations/--no-relations', default=True,
              help='Include relations (default: yes)')
def entity(name: str, graph: str, relations: bool):
    """
    Get detailed information about an entity.
    
    Example:
        alita inventory entity "PaymentProcessor" -g ./graph.json
    """
    try:
        from alita_sdk.community.inventory import InventoryRetrievalApiWrapper
        
        api = InventoryRetrievalApiWrapper(graph_path=graph)
        result = api.get_entity(name, include_relations=relations)
        
        click.echo(f"\n{result}")
        
    except FileNotFoundError:
        raise click.ClickException(f"Graph file not found: {graph}")
    except Exception as e:
        raise click.ClickException(str(e))


@inventory.command('impact')
@click.argument('name')
@click.option('--graph', '-g', required=True, type=click.Path(exists=True),
              help='Path to graph JSON file')
@click.option('--direction', '-d', type=click.Choice(['upstream', 'downstream']),
              default='downstream', help='Analysis direction (default: downstream)')
@click.option('--depth', default=3, type=int,
              help='Maximum traversal depth (default: 3)')
def impact(name: str, graph: str, direction: str, depth: int):
    """
    Analyze impact of changes to an entity.
    
    Example:
        alita inventory impact "UserService" -g ./graph.json
        alita inventory impact "Database" -g ./graph.json --direction upstream
    """
    try:
        from alita_sdk.community.inventory import InventoryRetrievalApiWrapper
        
        api = InventoryRetrievalApiWrapper(graph_path=graph)
        result = api.impact_analysis(name, direction=direction, max_depth=depth)
        
        click.echo(f"\n{result}")
        
    except FileNotFoundError:
        raise click.ClickException(f"Graph file not found: {graph}")
    except Exception as e:
        raise click.ClickException(str(e))


@inventory.command('visualize')
@click.option('--graph', '-g', required=True, type=click.Path(exists=True),
              help='Path to graph JSON file')
@click.option('--output', '-o', default=None, type=click.Path(),
              help='Output HTML file path (default: graph_visualization.html in same dir)')
@click.option('--open/--no-open', 'open_browser', default=True,
              help='Open in browser after generation (default: yes)')
@click.option('--title', '-t', default=None,
              help='Title for the visualization')
def visualize(graph: str, output: Optional[str], open_browser: bool, title: Optional[str]):
    """
    Generate an interactive visualization of the knowledge graph.
    
    Creates a standalone HTML file with D3.js-powered graph visualization.
    Features include:
    - Force-directed layout
    - Color-coded entity types
    - Node size based on connections
    - Interactive drag, zoom, and pan
    - Search and filter by entity type
    - Click nodes for detailed info
    
    Example:
        alita inventory visualize -g ./graph.json
        alita inventory visualize -g ./graph.json -o my_graph.html
        alita inventory visualize -g ./graph.json --no-open
    """
    try:
        from alita_sdk.community.inventory.visualize import generate_visualization
        from alita_sdk.community.inventory import KnowledgeGraph
        import webbrowser
        import os
        
        # Default output path
        if output is None:
            graph_dir = os.path.dirname(os.path.abspath(graph))
            graph_name = os.path.splitext(os.path.basename(graph))[0]
            output = os.path.join(graph_dir, f"{graph_name}_visualization.html")
        
        # Default title
        if title is None:
            title = os.path.splitext(os.path.basename(graph))[0].replace('_', ' ').title()
        
        click.echo(f"\n🎨 Generating graph visualization...")
        click.echo(f"   Source: {graph}")
        
        # Generate visualization
        html_path = generate_visualization(graph, output, title)
        
        click.echo(f"   Output: {html_path}")
        
        # Show graph stats
        kg = KnowledgeGraph()
        kg.load_from_json(graph)
        stats = kg.get_stats()
        click.echo(f"\n   📊 Graph contains:")
        click.echo(f"      - {stats['node_count']} entities")
        click.echo(f"      - {stats['edge_count']} relations")
        if stats['entity_types']:
            click.echo(f"      - {len(stats['entity_types'])} entity types")
        
        if open_browser:
            click.echo(f"\n   Opening in browser...")
            webbrowser.open(f"file://{os.path.abspath(html_path)}")
        
        click.echo(f"\n✅ Visualization complete!")
        click.echo()
        
    except FileNotFoundError:
        raise click.ClickException(f"Graph file not found: {graph}")
    except ImportError as e:
        raise click.ClickException(f"Visualization module not available: {e}")
    except Exception as e:
        raise click.ClickException(str(e))


@inventory.command('enrich')
@click.option('--graph', '-g', required=True, type=click.Path(exists=True),
              help='Path to graph JSON file')
@click.option('--output', '-o', default=None, type=click.Path(),
              help='Output graph file (default: overwrite input)')
@click.option('--cross-source/--no-cross-source', default=True,
              help='Link same-named entities across sources (default: yes)')
@click.option('--orphans/--no-orphans', default=True,
              help='Connect orphan nodes to related entities (default: yes)')
@click.option('--similarity/--no-similarity', default=False,
              help='Link entities with similar names (default: no)')
@click.option('--dry-run', is_flag=True, default=False,
              help='Show what would be done without saving')
def enrich(graph: str, output: Optional[str], cross_source: bool, orphans: bool, 
           similarity: bool, dry_run: bool):
    """
    Enrich a knowledge graph with additional relationships.
    
    Post-processes the graph to improve connectivity by:
    - Linking same-named entities across sources (SDK class → docs concept)
    - Connecting orphan nodes to semantically related entities
    - Optionally linking entities with very similar names
    
    Example:
        alita inventory enrich -g ./graph.json
        alita inventory enrich -g ./graph.json -o enriched.json
        alita inventory enrich -g ./graph.json --no-orphans
        alita inventory enrich -g ./graph.json --dry-run
    """
    try:
        from alita_sdk.community.inventory.enrichment import GraphEnricher
        
        click.echo(f"\n🔗 Enriching knowledge graph...")
        click.echo(f"   Source: {graph}")
        
        enricher = GraphEnricher(graph)
        
        # Show initial stats
        initial_links = len(enricher.graph_data.get("links", []))
        click.echo(f"   Initial: {len(enricher.nodes_by_id)} nodes, {initial_links} links")
        
        # Run enrichment
        stats = enricher.enrich(
            cross_source=cross_source,
            orphans=orphans,
            similarity=similarity,
        )
        
        click.echo(f"\n   📊 Enrichment results:")
        click.echo(f"      Cross-source links: +{stats['cross_source_links']}")
        click.echo(f"      Orphan connections: +{stats['orphan_links']}")
        if similarity:
            click.echo(f"      Similarity links:   +{stats['similarity_links']}")
        click.echo(f"      Total new links:    +{len(enricher.new_links)}")
        
        if dry_run:
            click.echo(f"\n   🔍 Dry run - no changes saved")
            click.echo(f"\n   Sample new links:")
            for link in enricher.new_links[:10]:
                src = enricher.nodes_by_id.get(link['source'], {})
                tgt = enricher.nodes_by_id.get(link['target'], {})
                click.echo(f"      {src.get('name', '?')[:25]:25} --[{link['relation_type']}]--> {tgt.get('name', '?')[:25]}")
        else:
            output_path = enricher.save(output)
            click.echo(f"\n   💾 Saved to: {output_path}")
        
        click.echo(f"\n✅ Enrichment complete!")
        click.echo()
        
    except FileNotFoundError:
        raise click.ClickException(f"Graph file not found: {graph}")
    except ImportError as e:
        raise click.ClickException(f"Enrichment module not available: {e}")
    except Exception as e:
        raise click.ClickException(str(e))


# ========== Helper Functions ==========

def _load_toolkit_config(toolkit_path: str) -> Dict[str, Any]:
    """
    Load and parse a toolkit config JSON file.
    
    Supports environment variable substitution for values like ${GITHUB_PAT}.
    """
    with open(toolkit_path, 'r') as f:
        config = json.load(f)
    
    # Recursively resolve environment variables
    def resolve_env_vars(obj):
        if isinstance(obj, str):
            # Match ${VAR_NAME} pattern
            pattern = r'\$\{([^}]+)\}'
            matches = re.findall(pattern, obj)
            for var_name in matches:
                env_value = os.environ.get(var_name, '')
                obj = obj.replace(f'${{{var_name}}}', env_value)
            return obj
        elif isinstance(obj, dict):
            return {k: resolve_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [resolve_env_vars(item) for item in obj]
        return obj
    
    return resolve_env_vars(config)


def _get_llm(ctx, model: Optional[str] = None, temperature: float = 0.0):
    """Get LLM instance from Alita client context."""
    from .cli import get_client
    
    # Get Alita client - this will raise ClickException if not configured
    client = get_client(ctx)
    
    # Get model name from parameter or default
    model_name = model or 'gpt-4o-mini'
    
    # Use client.get_llm() which is the actual method
    return client.get_llm(
        model_name=model_name,
        model_config={
            'temperature': temperature,
            'max_tokens': 4096
        }
    )


def _get_source_toolkit(toolkit_config: Dict[str, Any]):
    """
    Get configured source toolkit instance from toolkit config.
    
    Uses the SDK's toolkit factory pattern - all toolkits extend BaseCodeToolApiWrapper
    or BaseVectorStoreToolApiWrapper, which have loader() and chunker() methods.
    
    Args:
        toolkit_config: Toolkit configuration dict with 'type' and settings
        
    Returns:
        API wrapper instance with loader() method
    """
    from alita_sdk.tools import AVAILABLE_TOOLS
    
    source = toolkit_config.get('type')
    if not source:
        raise click.ClickException("Toolkit config missing 'type' field")
    
    # Check if toolkit type is available
    if source not in AVAILABLE_TOOLS:
        raise click.ClickException(
            f"Unknown toolkit type: {source}. "
            f"Available: {', '.join(AVAILABLE_TOOLS.keys())}"
        )
    
    toolkit_info = AVAILABLE_TOOLS[source]
    
    # Get the toolkit class
    if 'toolkit_class' not in toolkit_info:
        raise click.ClickException(
            f"Toolkit '{source}' does not have a toolkit_class registered"
        )
    
    toolkit_class = toolkit_info['toolkit_class']
    
    # Build kwargs from toolkit config - we need to map config to API wrapper params
    kwargs = dict(toolkit_config)
    
    # Remove fields that aren't needed for the API wrapper
    kwargs.pop('type', None)
    kwargs.pop('toolkit_name', None)
    kwargs.pop('selected_tools', None)
    kwargs.pop('excluded_tools', None)
    
    # Handle common config patterns - flatten nested configurations
    config_key = f"{source}_configuration"
    if config_key in kwargs:
        nested_config = kwargs.pop(config_key)
        if isinstance(nested_config, dict):
            kwargs.update(nested_config)
    
    # Handle ADO-specific config pattern
    if 'ado_configuration' in kwargs:
        ado_config = kwargs.pop('ado_configuration')
        if isinstance(ado_config, dict):
            kwargs.update(ado_config)
    
    # Expand environment variables in string values (e.g., ${GITHUB_PAT})
    def expand_env_vars(value):
        """Recursively expand environment variables in values."""
        if isinstance(value, str):
            import re
            # Match ${VAR} or $VAR patterns
            pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'
            def replace(match):
                var_name = match.group(1) or match.group(2)
                return os.environ.get(var_name, match.group(0))
            return re.sub(pattern, replace, value)
        elif isinstance(value, dict):
            return {k: expand_env_vars(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [expand_env_vars(v) for v in value]
        return value
    
    kwargs = expand_env_vars(kwargs)
    
    # Map common field names to API wrapper expected names
    # GitHub: personal_access_token -> github_access_token
    if 'personal_access_token' in kwargs and source == 'github':
        kwargs['github_access_token'] = kwargs.pop('personal_access_token')
    
    # GitHub: repository -> github_repository
    if 'repository' in kwargs and source == 'github':
        kwargs['github_repository'] = kwargs.pop('repository')
    
    # Ensure active_branch has a default
    if 'active_branch' not in kwargs:
        kwargs['active_branch'] = kwargs.get('base_branch', 'main')
    
    # Get the API wrapper class from the toolkit
    # Introspect toolkit to find the API wrapper class it uses
    try:
        # Try to get the API wrapper class from the toolkit's module
        import importlib
        module_path = f"alita_sdk.tools.{source}.api_wrapper"
        try:
            wrapper_module = importlib.import_module(module_path)
        except ImportError:
            # Try alternate path for nested modules
            module_path = f"alita_sdk.tools.{source.replace('_', '.')}.api_wrapper"
            wrapper_module = importlib.import_module(module_path)
        
        # Find the API wrapper class - look for class containing ApiWrapper/APIWrapper
        api_wrapper_class = None
        for name in dir(wrapper_module):
            obj = getattr(wrapper_module, name)
            if (isinstance(obj, type) and 
                ('ApiWrapper' in name or 'APIWrapper' in name) and 
                name not in ('BaseCodeToolApiWrapper', 'BaseVectorStoreToolApiWrapper', 'BaseToolApiWrapper')):
                api_wrapper_class = obj
                break
        
        if not api_wrapper_class:
            raise click.ClickException(
                f"Could not find API wrapper class in {module_path}"
            )
        
        # Instantiate the API wrapper directly
        api_wrapper = api_wrapper_class(**kwargs)
        
        # Verify it has loader method
        if not hasattr(api_wrapper, 'loader'):
            raise click.ClickException(
                f"API wrapper '{api_wrapper_class.__name__}' has no loader() method"
            )
        
        return api_wrapper
        
    except ImportError as e:
        logger.exception(f"Failed to import API wrapper for {source}")
        raise click.ClickException(f"Failed to import {source} API wrapper: {e}")
    except Exception as e:
        logger.exception(f"Failed to instantiate toolkit {source}")
        raise click.ClickException(f"Failed to create {source} toolkit: {e}")
