# Pipeline Deployer Skill

Quick reference for deploying pipeline YAML files to Elitea backend.

## Prerequisites

**ALWAYS activate the project virtual environment first:**

```bash
# Linux / macOS
source .venv/bin/activate

# Windows (Git Bash)
source .venv/Scripts/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (CMD)
.venv\Scripts\activate.bat
```

## Quick Start

```bash
# 1. Activate virtual environment (see Prerequisites above)

# 2. Set up environment variables in .env
TEST_DEPLOYMENT_URL=https://dev.elitea.ai
TEST_API_KEY=your_api_key_here
TEST_PROJECT_ID=123
TEST_APP=456
TEST_VERSION=789  # Optional

# 3. Run deployment (using env vars)
python deploy_pipeline.py /path/to/pipeline.yaml

# Or override with CLI arguments
python deploy_pipeline.py /path/to/pipeline.yaml --project-id 123 --app-id 456

# Use specific version ID
python deploy_pipeline.py /path/to/pipeline.yaml --version-id 789

# 4. If you see ModuleNotFoundError, install dependencies:
pip install -r requirements.txt
# Then re-run the deployment command
```

## Environment Variables

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `TEST_DEPLOYMENT_URL` | Backend URL | `https://dev.elitea.ai` | Yes |
| `TEST_API_KEY` | Bearer token | `your_api_key` | Yes |
| `TEST_PROJECT_ID` | Project ID | `123` | Yes |
| `TEST_APP` | Application ID (for API endpoint) | `456` | Yes |
| `TEST_VERSION` | Version ID (optional) | `789` | No |

**Note:** `TEST_APP` is always required for the API endpoint URL. If both are provided:
- `TEST_VERSION` is used for version data
- `TEST_APP` is used only for the endpoint (ignored for version lookup)

## Script Behavior

**Prerequisites:** Virtual environment must be activated.

1. Parses command-line arguments
2. Loads environment variables from `.env` (CLI args override env vars)
3. Reads the specified YAML file
4. Fetches current application details (GET request)
5. Determines version to update:
   - If `TEST_VERSION` provided: uses it directly (ignores app version lookup)
   - If only `TEST_APP` provided: looks up "base" version or first version
6. Constructs update payload with new YAML content
7. Sends PUT request to update the application
8. Reports success or failure

**Note:** If the script fails with `ModuleNotFoundError`, run `pip install -r requirements.txt`, then re-run.

## Command-Line Arguments

All environment variables can be overridden via CLI:

```bash
python deploy_pipeline.py <yaml_file> [options]

Options:
  --url URL              Backend URL (overrides TEST_DEPLOYMENT_URL)
  --api-key KEY          API Bearer token (overrides TEST_API_KEY)
  --project-id ID        Project ID (overrides TEST_PROJECT_ID)
  --app-id ID            Application ID (overrides TEST_APP)
  --version-id ID        Version ID (overrides TEST_VERSION)
  -h, --help             Show help message
```

## Exit Codes

- `0` - Success
- `1` - Failure (missing env vars, file not found, API error, etc.)

## API Endpoint

```
PUT /api/v2/elitea_core/applications/prompt_lib/{project_id}/{app_id}
```

## Dependencies

```bash
pip install requests python-dotenv
```

## Example Output

```
============================================================
Pipeline Deployment Tool
============================================================

📋 Configuration:
   Backend: https://dev.elitea.ai
   Project ID: 123
   Application ID: 456
   YAML file: my_pipeline.yaml

📖 Reading YAML file...
✓ Loaded 2048 bytes

🔍 Fetching current application details...
   GET https://dev.elitea.ai/api/v2/elitea_core/applications/prompt_lib/123/456
✓ Retrieved application: My Pipeline

📤 Deploying pipeline to backend...
   PUT https://dev.elitea.ai/api/v2/elitea_core/applications/prompt_lib/123/456
   Version ID: 789
   YAML size: 2048 bytes

✅ Pipeline deployed successfully!
   Status: 201

============================================================
✅ Deployment completed successfully
```

## Troubleshooting

**ModuleNotFoundError: No module named 'requests' (or similar)?**
- Ensure virtual environment is activated (see Prerequisites)
- Run `pip install -r requirements.txt`
- Re-run the deployment command

**Missing environment variables?**
- Create `.env` file in project root or `.alita/.env`
- Or export variables: `export TEST_API_KEY=...`

**File not found?**
- Use absolute path: `/full/path/to/pipeline.yaml`
- Or relative path from current directory

**401 Unauthorized?**
- Check your `TEST_API_KEY` is valid
- Verify token hasn't expired

**404 Not Found?**
- Verify `TEST_PROJECT_ID` and `TEST_APP` are correct
- Ensure the application exists

**400 Bad Request?**
- Check YAML syntax is valid
- Validate pipeline structure follows Elitea schema
