"""
Toolkit testing commands for Alita CLI.

Provides commands to list, inspect, and test toolkits directly from the command line.
"""

import click
import json
import logging
from typing import Optional, Dict, Any

from .cli import get_client
from .toolkit_loader import load_toolkit_config

logger = logging.getLogger(__name__)


@click.group()
def toolkit():
    """Toolkit testing commands."""
    pass


@toolkit.command('list')
@click.option('--failed', is_flag=True, help='Show failed imports')
@click.pass_context
def toolkit_list(ctx, failed: bool):
    """List all available toolkits."""
    formatter = ctx.obj['formatter']
    
    try:
        # Import toolkit registry
        from alita_sdk.tools import AVAILABLE_TOOLS, AVAILABLE_TOOLKITS, FAILED_IMPORTS
        
        if failed:
            # Show failed imports
            if FAILED_IMPORTS:
                click.echo("\nFailed toolkit imports:\n")
                for name, error in FAILED_IMPORTS.items():
                    click.echo(f"  - {name}: {error}")
                click.echo(f"\nTotal failed: {len(FAILED_IMPORTS)}")
            else:
                click.echo("\nNo failed imports")
            return
        
        # Build toolkit list
        toolkits = []
        for name, toolkit_dict in AVAILABLE_TOOLS.items():
            toolkit_class_name = None
            if 'toolkit_class' in toolkit_dict:
                toolkit_class_name = toolkit_dict['toolkit_class'].__name__
            
            toolkits.append({
                'name': name,
                'class_name': toolkit_class_name,
                'has_get_tools': 'get_tools' in toolkit_dict
            })
        
        # Format and display
        output = formatter.format_toolkit_list(toolkits)
        click.echo(output)
        
    except Exception as e:
        logger.exception("Failed to list toolkits")
        click.echo(formatter.format_error(str(e)), err=True)
        raise click.Abort()


@toolkit.command('schema')
@click.argument('toolkit_name')
@click.pass_context
def toolkit_schema(ctx, toolkit_name: str):
    """
    Show configuration schema for a toolkit.
    
    TOOLKIT_NAME: Name of the toolkit (e.g., 'jira', 'github', 'confluence')
    """
    formatter = ctx.obj['formatter']
    
    try:
        # Import toolkit registry
        from alita_sdk.tools import AVAILABLE_TOOLKITS
        
        # Find toolkit class
        toolkit_class = None
        for name, cls in AVAILABLE_TOOLKITS.items():
            if name.lower().replace('toolkit', '').replace('alita', '').strip() == toolkit_name.lower():
                toolkit_class = cls
                break
        
        if not toolkit_class:
            # Try direct match
            for name, cls in AVAILABLE_TOOLKITS.items():
                if toolkit_name.lower() in name.lower():
                    toolkit_class = cls
                    break
        
        if not toolkit_class:
            available = [name.lower().replace('toolkit', '').replace('alita', '').strip() 
                        for name in AVAILABLE_TOOLKITS.keys()]
            raise click.ClickException(
                f"Toolkit '{toolkit_name}' not found.\n"
                f"Available toolkits: {', '.join(sorted(set(available)))}"
            )
        
        # Get schema
        schema_model = toolkit_class.toolkit_config_schema()
        schema = schema_model.model_json_schema()
        
        # Format and display
        if formatter.__class__.__name__ == 'JSONFormatter':
            output = formatter.format_toolkit_schema(toolkit_name, schema)
        else:
            output = formatter.format_toolkit_schema(toolkit_name, schema)
        
        click.echo(output)
        
    except click.ClickException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get schema for toolkit '{toolkit_name}'")
        click.echo(formatter.format_error(str(e)), err=True)
        raise click.Abort()


@toolkit.command('test')
@click.argument('toolkit_type')
@click.option('--tool', required=True, help='Tool name to execute')
@click.option('--config', 'config_file', type=click.File('r'), 
              help='Toolkit configuration JSON file')
@click.option('--params', type=click.File('r'), 
              help='Tool parameters JSON file')
@click.option('--param', multiple=True, 
              help='Tool parameter as key=value (can be used multiple times)')
@click.option('--llm-model', default='gpt-4o-mini', 
              help='LLM model to use (default: gpt-4o-mini)')
@click.option('--temperature', default=0.1, type=float,
              help='LLM temperature (default: 0.1)')
@click.option('--max-tokens', default=1000, type=int,
              help='LLM max tokens (default: 1000)')
@click.pass_context
def toolkit_test(ctx, toolkit_type: str, tool: str, config_file, params, 
                param, llm_model: str, temperature: float, max_tokens: int):
    """Test a specific tool from a toolkit.
    
    TOOLKIT_TYPE: Type of toolkit (e.g., 'jira', 'github', 'confluence')
    
    \b
    Examples:
      alita toolkit test jira --tool get_issue --config jira.json --params params.json
      alita toolkit test jira --tool get_issue --config jira.json --param issue_key=PROJ-123
      alita -o json toolkit test github --tool get_issue --config github.json
    """
    formatter = ctx.obj['formatter']
    client = get_client(ctx)
    
    try:
        # Load toolkit configuration
        toolkit_config = {}
        if config_file:
            toolkit_config = load_toolkit_config(config_file.name)
            logger.debug(f"Loaded toolkit config from {config_file.name}")
        
        # Add the tool to selected_tools in the config
        if 'selected_tools' not in toolkit_config:
            toolkit_config['selected_tools'] = []
        if tool not in toolkit_config['selected_tools']:
            toolkit_config['selected_tools'].append(tool)
        
        # Load tool parameters
        tool_params = {}
        if params:
            tool_params = json.load(params)
            logger.debug(f"Loaded tool params from {params.name}")
        
        # Parse inline parameters
        if param:
            for param_pair in param:
                if '=' not in param_pair:
                    raise click.ClickException(
                        f"Invalid parameter format: '{param_pair}'. "
                        "Use --param key=value"
                    )
                key, value = param_pair.split('=', 1)
                
                # Try to parse as JSON for complex values
                try:
                    tool_params[key] = json.loads(value)
                except json.JSONDecodeError:
                    tool_params[key] = value
            
            logger.debug(f"Parsed {len(param)} inline parameters")
        
        # Prepare full toolkit configuration
        full_config = {
            'toolkit_name': toolkit_type,
            'type': toolkit_type,
            'settings': toolkit_config
        }
        
        # LLM configuration
        llm_config = {
            'temperature': temperature,
            'max_tokens': max_tokens,
        }
        
        # Execute test
        logger.info(f"Testing tool '{tool}' from toolkit '{toolkit_type}'")
        result = client.test_toolkit_tool(
            toolkit_config=full_config,
            tool_name=tool,
            tool_params=tool_params,
            llm_model=llm_model,
            llm_config=llm_config
        )
        
        # Format and display result
        output = formatter.format_toolkit_result(result)
        click.echo(output)
        
        # Exit with error code if test failed
        if not result.get('success', False):
            raise click.Abort()
        
    except click.ClickException:
        raise
    except Exception as e:
        logger.exception("Failed to execute toolkit test")
        click.echo(formatter.format_error(str(e)), err=True)
        raise click.Abort()


@toolkit.command('tools')
@click.argument('toolkit_type')
@click.option('--config', 'config_file', type=click.File('r'),
              help='Toolkit configuration JSON file (required for some toolkits)')
@click.pass_context
def toolkit_tools(ctx, toolkit_type: str, config_file):
    """
    List available tools for a specific toolkit.
    
    TOOLKIT_TYPE: Type of toolkit (e.g., 'jira', 'github', 'confluence')
    
    Some toolkits require configuration to determine available tools.
    Use --config to provide configuration if needed.
    """
    formatter = ctx.obj['formatter']
    client = get_client(ctx)
    
    try:
        # Load toolkit configuration if provided
        toolkit_config = {}
        if config_file:
            toolkit_config = load_toolkit_config(config_file.name)
        
        # Import and instantiate toolkit
        from alita_sdk.tools import AVAILABLE_TOOLS
        
        if toolkit_type not in AVAILABLE_TOOLS:
            raise click.ClickException(
                f"Toolkit '{toolkit_type}' not found. "
                f"Use 'alita-cli toolkit list' to see available toolkits."
            )
        
        toolkit_entry = AVAILABLE_TOOLS[toolkit_type]
        
        if 'toolkit_class' not in toolkit_entry:
            raise click.ClickException(
                f"Toolkit '{toolkit_type}' does not support tool listing"
            )
        
        # Get toolkit class and instantiate
        toolkit_class = toolkit_entry['toolkit_class']
        
        # Create minimal configuration
        full_config = {
            'toolkit_name': toolkit_type,
            'type': toolkit_type,
            'settings': toolkit_config
        }
        
        # Try to get available tools via API wrapper
        try:
            # Instantiate API wrapper if possible
            api_wrapper_class = None
            
            # Find API wrapper class by inspecting toolkit
            import inspect
            for name, obj in inspect.getmembers(toolkit_class):
                if inspect.isclass(obj) and 'ApiWrapper' in obj.__name__:
                    api_wrapper_class = obj
                    break
            
            if api_wrapper_class:
                try:
                    api_wrapper = api_wrapper_class(**toolkit_config)
                    available_tools = api_wrapper.get_available_tools()
                    
                    # Format tools list
                    click.echo(f"\nAvailable tools for {toolkit_type}:\n")
                    for tool_info in available_tools:
                        tool_name = tool_info.get('name', 'unknown')
                        description = tool_info.get('description', '')
                        click.echo(f"  - {tool_name}")
                        if description:
                            click.echo(f"      {description}")
                    
                    click.echo(f"\nTotal: {len(available_tools)} tools")
                    return
                    
                except Exception as e:
                    logger.debug(f"Could not instantiate API wrapper: {e}")
            
            # Fallback: show general info
            click.echo(f"\n{toolkit_type} toolkit is available")
            click.echo("Use 'alita-cli toolkit schema {toolkit_type}' to see configuration options")
            
        except Exception as e:
            logger.exception("Failed to list tools")
            raise click.ClickException(str(e))
        
    except click.ClickException:
        raise
    except Exception as e:
        logger.exception("Failed to list toolkit tools")
        click.echo(formatter.format_error(str(e)), err=True)
        raise click.Abort()
