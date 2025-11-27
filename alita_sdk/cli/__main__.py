"""
Entry point for running the Alita CLI as a module.

Usage:
    python -m alita_sdk.cli [command] [options]
"""

# Suppress warnings before any imports
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

from .cli import cli

if __name__ == '__main__':
    cli()
