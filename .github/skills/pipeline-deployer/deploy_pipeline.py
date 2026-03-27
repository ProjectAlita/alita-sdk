#!/usr/bin/env python3
"""
Pipeline Deployment Script

Reads a pipeline YAML file and deploys it to the Elitea backend via REST API.

Usage:
    python deploy_pipeline.py <yaml_file_path> [options]

Environment Variables (from .env):
    TEST_DEPLOYMENT_URL - Backend URL (e.g., https://dev.elitea.ai)
    TEST_API_KEY - Bearer token for authentication
    TEST_PROJECT_ID - Project ID
    TEST_APP - Application ID to update
    TEST_VERSION - (Optional) Version ID to update directly (update mode)

Command-line arguments override environment variables.
.env file: project root .env is used by default; override with --env <path>.

Modes:
    Update mode (default): Updates YAML instructions of an existing version.
    Create-version mode (--name): Creates a new version with the given name.
"""

import os
import sys
import json
import argparse
import requests
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv


def load_environment(args: Optional[Any] = None) -> Dict[str, str]:
    """Load environment variables from .env file, with optional CLI overrides."""
    # Determine which .env file to load:
    # - If --env provided: load that file only
    # - Otherwise: project root .env only (no fallback, no CWD)
    if args and getattr(args, 'env', None):
        env_file = Path(args.env)
        if not env_file.exists():
            print(f"❌ .env file not found: {args.env}")
            sys.exit(1)
        load_dotenv(env_file, override=True)
        print(f"ℹ️  Loaded env from: {env_file}")
    else:
        env_file = Path(__file__).parent.parent.parent.parent / '.env'
        if env_file.exists():
            load_dotenv(env_file, override=True)

    # Build config from env vars first, then override with CLI args
    env = {}
    env['TEST_DEPLOYMENT_URL'] = os.getenv('TEST_DEPLOYMENT_URL', '')
    env['TEST_API_KEY'] = os.getenv('TEST_API_KEY', '')
    env['TEST_PROJECT_ID'] = os.getenv('TEST_PROJECT_ID', '')
    env['TEST_APP'] = os.getenv('TEST_APP', '')
    env['TEST_VERSION'] = os.getenv('TEST_VERSION', '')

    # Override with command-line arguments if provided
    if args:
        if args.url:
            env['TEST_DEPLOYMENT_URL'] = args.url
        if args.api_key:
            env['TEST_API_KEY'] = args.api_key
        if args.project_id:
            env['TEST_PROJECT_ID'] = args.project_id
        if args.app_id:
            env['TEST_APP'] = args.app_id
        if args.version_id:
            env['TEST_VERSION'] = args.version_id

    # Validate required fields
    required_vars = ['TEST_DEPLOYMENT_URL', 'TEST_API_KEY', 'TEST_PROJECT_ID']
    missing = [var for var in required_vars if not env.get(var)]

    # TEST_APP is always needed for the API endpoint URL
    if not env.get('TEST_APP'):
        if not env.get('TEST_VERSION'):
            missing.append('TEST_APP (required for API endpoint)')
        else:
            print(f"⚠️  Warning: TEST_VERSION provided without TEST_APP")
            print(f"   TEST_APP is required for API endpoint construction")
            missing.append('TEST_APP')

    if missing:
        print(f"❌ Missing required configuration: {', '.join(missing)}")
        print(f"   Set via environment variables or command-line arguments")
        sys.exit(1)

    return env


def read_yaml_file(file_path: str) -> str:
    """Read YAML file content."""
    path = Path(file_path)
    
    if not path.exists():
        print(f"❌ File not found: {file_path}")
        sys.exit(1)
    
    if not path.is_file():
        print(f"❌ Not a file: {file_path}")
        sys.exit(1)
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        sys.exit(1)


def get_application_details(
    base_url: str, 
    api_key: str, 
    project_id: str, 
    app_id: str,
    version_name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetch current application details to get version ID and user info.
    
    GET /api/v2/elitea_core/application/prompt_lib/{project_id}/{app_id}[/{version_name}]
    """
    url = f"{base_url}/api/v2/elitea_core/application/prompt_lib/{project_id}/{app_id}"
    if version_name:
        url += f"/{version_name}"
    
    headers = {
        'Authorization': f'Bearer {api_key}'
    }
    
    print(f"🔍 Fetching current application details...")
    print(f"   GET {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Retrieved application: {data.get('name', 'Unknown')}")
            return data
        else:
            print(f"❌ Failed to get application details: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None


def deploy_pipeline(
    base_url: str,
    api_key: str,
    project_id: str,
    app_id: str,
    yaml_content: str,
    app_details: Dict[str, Any],
    version_id: Optional[str] = None
) -> bool:
    """
    Deploy pipeline YAML content to the backend.
    
    PUT /api/v2/elitea_core/application/prompt_lib/{project_id}/{app_id}
    
    If version_id is provided, it's used directly (TEST_APP ignored for version lookup).
    """
    url = f"{base_url}/api/v2/elitea_core/application/prompt_lib/{project_id}/{app_id}"
    
    # If version_id is provided directly, use it (TEST_APP ignored for version lookup)
    if version_id:
        print(f"ℹ️  Using directly provided version ID: {version_id}")
        print(f"   (TEST_APP used only for API endpoint, ignored for version selection)")
        
        # Check if the provided version_id matches the current version_details
        version_details = app_details.get('version_details', {})
        if str(version_details.get('id')) == str(version_id):
            print(f"   Matched to currently loaded version: {version_details.get('name', 'unknown')}")
        else:
            # Need to fetch the specific version's details
            # Find the version name from the versions array
            version_name = None
            for v in app_details.get('versions', []):
                if str(v.get('id')) == str(version_id):
                    version_name = v.get('name')
                    break
            
            if version_name:
                print(f"   Need to fetch details for version '{version_name}'...")
                # Re-fetch application details with the specific version name
                version_specific_details = get_application_details(
                    base_url, api_key, project_id, app_id, version_name
                )
                if version_specific_details:
                    app_details = version_specific_details
                    version_details = app_details.get('version_details', {})
                    print(f"   ✓ Loaded version '{version_name}' details")
                else:
                    print(f"   ❌ Failed to fetch version '{version_name}' details")
                    return False
            else:
                print(f"   ❌ Version ID {version_id} not found in application")
                return False
    else:
        # Use the default/active version from app_details
        version_details = app_details.get('version_details', {})
        version_id = version_details.get('id')
        if not version_id:
            print("❌ No version_details found in application")
            return False
        print(f"ℹ️  Using active version: {version_details.get('name', 'unknown')} (ID: {version_id})")
    
    # Use the full version_details from the response and update instructions
    version_data = version_details.copy()
    version_data['instructions'] = yaml_content
    
    # Construct payload matching browser format
    payload = {
        'name': app_details.get('name'),
        'description': app_details.get('description'),
        'owner_id': app_details.get('owner_id'),
        'webhook_secret': app_details.get('webhook_secret'),
        'version': version_data
    }
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    print(f"\n📤 Deploying pipeline to backend...")
    print(f"   PUT {url}")
    print(f"   Version ID: {version_data.get('id')}")
    print(f"   Version name: {version_data.get('name')}")
    print(f"   YAML size: {len(yaml_content)} bytes")
    
    try:
        response = requests.put(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            print(f"\n✅ Pipeline deployed successfully!")
            print(f"   Status: {response.status_code}")
            try:
                result = response.json()
                print(f"   Response: {json.dumps(result, indent=2)}")
            except:
                print(f"   Response: {response.text}")
            return True
        else:
            print(f"\n❌ Deployment failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ Request failed: {e}")
        return False


def create_version(
    base_url: str,
    api_key: str,
    project_id: str,
    app_id: str,
    version_name: str,
    yaml_content: str,
    app_details: Dict[str, Any],
) -> bool:
    """
    Create a new version for an application.

    POST /api/v2/elitea_core/versions/prompt_lib/{project_id}/{app_id}

    Payload: {name, author_id, tags, instructions}
    """
    url = f"{base_url}/api/v2/elitea_core/versions/prompt_lib/{project_id}/{app_id}"

    # Get author_id from app details (prefer author.id, fall back to owner_id)
    author_id = app_details.get('author', {}).get('id') or app_details.get('owner_id')
    if not author_id:
        print("❌ Could not determine author_id from application details")
        return False

    payload = {
        'name': version_name,
        'author_id': author_id,
        'tags': [],
        'instructions': yaml_content,
    }

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    print(f"\n📤 Creating new version '{version_name}'...")
    print(f"   POST {url}")
    print(f"   Author ID: {author_id}")
    print(f"   YAML size: {len(yaml_content)} bytes")

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code in [200, 201]:
            print(f"\n✅ Version '{version_name}' created successfully!")
            print(f"   Status: {response.status_code}")
            try:
                result = response.json()
                print(f"   Response: {json.dumps(result, indent=2)}")
            except Exception:
                print(f"   Response: {response.text}")
            return True
        else:
            print(f"\n❌ Version creation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ Request failed: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Deploy pipeline YAML to Elitea backend',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Environment Variables:
  TEST_DEPLOYMENT_URL  Backend URL (e.g., https://dev.elitea.ai)
  TEST_API_KEY         Bearer token for authentication
  TEST_PROJECT_ID      Project ID
  TEST_APP             Application ID (always required)
  TEST_VERSION         Version ID (optional, update mode only — skips version lookup)
Examples:
  # Update existing version (default mode)
  python deploy_pipeline.py pipeline.yaml

  # Use a custom .env file
  python deploy_pipeline.py pipeline.yaml --env /path/to/.env

  # Override specific params
  python deploy_pipeline.py pipeline.yaml --project-id 123 --app-id 456

  # Use specific version ID for update
  python deploy_pipeline.py pipeline.yaml --version-id 789

  # Create a new version named 'v2'
  python deploy_pipeline.py pipeline.yaml --name v2
        """
    )
    
    parser.add_argument('yaml_file', help='Path to pipeline YAML file')
    parser.add_argument('--env', help='Path to .env file (default: project root .env)')
    parser.add_argument('--url', help='Backend URL (overrides TEST_DEPLOYMENT_URL)')
    parser.add_argument('--api-key', help='API Bearer token (overrides TEST_API_KEY)')
    parser.add_argument('--project-id', help='Project ID (overrides TEST_PROJECT_ID)')
    parser.add_argument('--app-id', help='Application ID (overrides TEST_APP)')
    parser.add_argument('--version-id', help='Version ID to update (overrides TEST_VERSION)')
    parser.add_argument('--name', help='New version name — triggers create-version mode')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Pipeline Deployment Tool")
    print("=" * 60)
    
    # Load environment with CLI overrides
    env = load_environment(args)
    
    base_url = env['TEST_DEPLOYMENT_URL'].rstrip('/')
    api_key = env['TEST_API_KEY']
    project_id = env['TEST_PROJECT_ID']
    app_id = env.get('TEST_APP', '')
    version_id = env.get('TEST_VERSION', '')
    version_name = args.name or ''
    create_version_mode = bool(version_name)
    yaml_file = args.yaml_file

    print(f"\n📋 Configuration:")
    print(f"   Backend: {base_url}")
    print(f"   Project ID: {project_id}")
    if app_id:
        print(f"   Application ID: {app_id}")
    if create_version_mode:
        print(f"   Mode: Create New Version")
        if version_name:
            print(f"   New Version Name: {version_name}")
    else:
        if version_id:
            print(f"   Version ID: {version_id}")
    print(f"   YAML file: {yaml_file}")
    
    # Read YAML file
    print(f"\n📖 Reading YAML file...")
    yaml_content = read_yaml_file(yaml_file)
    print(f"✓ Loaded {len(yaml_content)} bytes")
    
    # Validate we have app_id for the endpoint
    if not app_id:
        print("❌ Application ID required for API endpoint")
        print("   The endpoint is: POST/PUT /api/v2/.../prompt_lib/{project_id}/{app_id}")
        print("   Set TEST_APP or use --app-id")
        sys.exit(1)

    # Get current application details
    app_details = get_application_details(base_url, api_key, project_id, app_id)
    if not app_details:
        sys.exit(1)

    if create_version_mode:
        # Validate version name
        if not version_name:
            print("❌ Version name required for --create-version mode")
            print("   Set TEST_VERSION_NAME or use --name")
            sys.exit(1)
        # Create new version
        success = create_version(
            base_url,
            api_key,
            project_id,
            app_id,
            version_name,
            yaml_content,
            app_details,
        )
    else:
        # Update existing version
        success = deploy_pipeline(
            base_url,
            api_key,
            project_id,
            app_id,
            yaml_content,
            app_details,
            version_id=version_id if version_id else None
        )
    
    print("\n" + "=" * 60)
    if success:
        print("\u2705 Deployment completed successfully")
        sys.exit(0)
    else:
        print("\u274c Deployment failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
