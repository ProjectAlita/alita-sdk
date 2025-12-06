"""
Main CLI application for Alita SDK.

Provides command-line interface for testing agents and toolkits,
using the same .env authentication as SDK tests and Streamlit interface.
"""

# Suppress warnings FIRST before any other imports
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

import click
import logging
import sys
from typing import Optional

from .config import get_config
from .formatting import get_formatter

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.group()
@click.option('--env-file', default='.env', help='Path to .env file')
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose/info logging (shows timing)')
@click.option('--output', type=click.Choice(['text', 'json']), default='text', 
              help='Output format')
@click.pass_context
def cli(ctx, env_file: str, debug: bool, verbose: bool, output: str):
    """
    Alita SDK CLI - Test agents and toolkits from the command line.
    
    Credentials are loaded from .env file with variables:
    - DEPLOYMENT_URL: Alita deployment URL
    - PROJECT_ID: Project ID
    - API_KEY: API authentication key
    
    Example .env file:
    
        DEPLOYMENT_URL=https://api.elitea.ai
        PROJECT_ID=123
        API_KEY=your_api_key_here
    """
    ctx.ensure_object(dict)
    
    # Enable debug logging if requested
    if debug:
        logging.getLogger('alita_sdk').setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    elif verbose:
        # Verbose mode shows INFO level (timing info)
        logging.getLogger('alita_sdk').setLevel(logging.INFO)
        logger.setLevel(logging.INFO)
        logger.info("Verbose logging enabled")
    
    # Load configuration
    config = get_config(env_file=env_file)
    ctx.obj['config'] = config
    ctx.obj['formatter'] = get_formatter(output)
    ctx.obj['debug'] = debug
    ctx.obj['verbose'] = verbose
    
    # Check if configuration is valid (but don't fail yet - some commands don't need it)
    if not config.is_configured():
        missing = config.get_missing_config()
        ctx.obj['config_error'] = f"Missing required configuration: {', '.join(missing)}"
        logger.debug(f"Configuration incomplete: {missing}")
    else:
        ctx.obj['config_error'] = None
        logger.debug(f"Configuration loaded from {env_file}")


def get_client(ctx):
    """
    Get configured AlitaClient from context.
    
    Raises click.ClickException if configuration is invalid.
    """
    if ctx.obj.get('config_error'):
        raise click.ClickException(
            f"{ctx.obj['config_error']}\n\n"
            "Please ensure your .env file contains:\n"
            "  DEPLOYMENT_URL=https://api.elitea.ai\n"
            "  PROJECT_ID=123\n"
            "  API_KEY=your_api_key_here"
        )
    
    # Import here to avoid loading SDK if not needed
    from alita_sdk.runtime.clients.client import AlitaClient
    
    config = ctx.obj['config']
    
    try:
        client = AlitaClient(
            base_url=config.deployment_url,
            project_id=config.project_id,
            auth_token=config.api_key
        )
        logger.debug(f"AlitaClient initialized for project {config.project_id}")
        return client
    except Exception as e:
        raise click.ClickException(f"Failed to initialize AlitaClient: {str(e)}")


@cli.command()
@click.pass_context
def config(ctx):
    """Show current configuration (credentials masked)."""
    config_obj = ctx.obj['config']
    formatter = ctx.obj['formatter']
    
    if formatter.__class__.__name__ == 'JSONFormatter':
        click.echo(formatter._dump(config_obj.to_dict()))
    else:
        click.echo("\nCurrent configuration:\n")
        for key, value in config_obj.to_dict().items():
            click.echo(f"  {key}: {value}")
        
        if not config_obj.is_configured():
            missing = config_obj.get_missing_config()
            click.echo(f"\n⚠ Missing: {', '.join(missing)}")
        else:
            click.echo("\n✓ Configuration is complete")


# Import subcommands
from . import toolkit
from . import agents
from . import inventory

# Register subcommands
cli.add_command(toolkit.toolkit)
cli.add_command(agents.agent)
cli.add_command(inventory.inventory)

# Add top-level 'chat' command as alias to 'agent chat'
cli.add_command(agents.agent_chat, name='chat')


def main():
    """Entry point for CLI."""
    # Suppress warnings at entry point
    warnings.filterwarnings('ignore', category=DeprecationWarning)
    warnings.filterwarnings('ignore', category=UserWarning)
    warnings.filterwarnings('ignore', message='Unverified HTTPS request')
    
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\n\nInterrupted by user", err=True)
        sys.exit(130)
    except Exception as e:
        logger.exception("Unexpected error")
        click.echo(f"\nError: {str(e)}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
