---
name: pipeline-deployer
description: Deploy pipeline YAML files to remote Elitea backend via API. Use when user wants to push/update/deploy local pipeline YAML to server, sync agent configuration, or upload pipeline changes.
---

# Pipeline Deployer

**Purpose**: Read local pipeline YAML files and push them to the Elitea backend via REST API.

## When to Use This Skill

Use this skill when the user wants to:
- Push a local pipeline YAML file to the remote server
- Update an existing pipeline/agent configuration
- Deploy pipeline changes after local edits
- Sync local agent definitions with the backend
- Create a new version of an existing application

## Workflow

1. **Gather Information**
   - Pipeline/agent YAML file path
   - Application ID (always required for the API endpoint)
   - Mode is determined automatically:
     - `--name <name>` provided → **create new version** with that name
     - No `--name` → **update** existing version (active or specified by `TEST_VERSION`)
   - Environment variables (or prompt user to provide)

2. **Validate Environment Variables**
   Required for both modes:
   - `TEST_DEPLOYMENT_URL` - Backend URL (e.g., https://dev.elitea.ai)
   - `TEST_API_KEY` - Bearer token for authentication
   - `TEST_PROJECT_ID` - Project ID
   - `TEST_APP` - Application ID

3. **Execute Deployment Script**
   Run `deploy_pipeline.py` which:
   - Reads the YAML file
   - Fetches current application details (to get `author_id` etc.)
   - **Update mode**: Makes a PUT request to update the version's instructions
   - **Create-version mode**: Makes a POST request to create a new version
   - Reports success or failure

4. **Report Results**
   Show the user:
   - HTTP status code
   - Response data
   - Any errors encountered

## Prerequisites

**ALWAYS activate the project virtual environment before executing any Python scripts no matter if it is already activated before:**

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

All Python commands in this skill assume the virtual environment is active.

## Script Usage

**Basic workflow:**

1. **Activate virtual environment** (see Prerequisites above)

2. **Run the deployment script:**
   ```bash
   # Update existing version (default mode)
   python deploy_pipeline.py /path/to/pipeline.yaml

   # Override with command-line arguments
   python deploy_pipeline.py /path/to/pipeline.yaml --project-id 123 --app-id 456

   # Use specific version ID for update (skips version lookup)
   python deploy_pipeline.py /path/to/pipeline.yaml --version-id 789

   # Create a new version named 'v2' (--name triggers create mode)
   python deploy_pipeline.py /path/to/pipeline.yaml --name v2

   # Create a new version with all params from CLI
   python deploy_pipeline.py /path/to/pipeline.yaml --name v2 --app-id 2259 --project-id 121
   ```

3. **If you see `ModuleNotFoundError`**, install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   Then re-run the deployment script.

**Environment Variables** (can be overridden by CLI args):
- `TEST_DEPLOYMENT_URL` - Backend URL (required)
- `TEST_API_KEY` - Bearer token (required)
- `TEST_PROJECT_ID` - Project ID (required)
- `TEST_APP` - Application ID (required)
- `TEST_VERSION` - Version ID (optional, update mode only — skips version lookup)

**Mode selection**: Pass `--name <version_name>` to create a new version. Omit `--name` to update.

**Important:** `TEST_APP` is always required. `--name` is the only flag needed to switch to create-version mode.

## API Endpoints

### Update Mode (default)
```
PUT {TEST_DEPLOYMENT_URL}/api/v2/elitea_core/application/prompt_lib/{TEST_PROJECT_ID}/{TEST_APP}
```

**Payload Structure:**
```json
{
  "name": "<app name>",
  "description": "<app description>",
  "owner_id": <owner_id>,
  "version": {
    "id": <version_id>,
    "instructions": "<yaml_content>",
    "agent_type": "pipeline"
  }
}
```

### Create-Version Mode (`--create-version`)
```
POST {TEST_DEPLOYMENT_URL}/api/v2/elitea_core/versions/prompt_lib/{TEST_PROJECT_ID}/{TEST_APP}
```

**Payload Structure:**
```json
{
  "name": "<version_name>",
  "author_id": <author_id>,
  "tags": [],
  "instructions": "<yaml_content>"
}
```

`author_id` is automatically extracted from the fetched application details (`author.id`).

**Headers (both modes):**
```
Authorization: Bearer {TEST_API_KEY}
Content-Type: application/json
```

## Notes

- The script fetches the current application details first to get `author_id` and version info
- YAML content is embedded in the `instructions` field as a string
- **Update mode**: Only the `instructions` field is updated; other version settings remain unchanged
- **Create-version mode**: Creates a brand-new version record; `author_id` is auto-detected from app details
- Requires valid authentication token with update/create permissions

## Example Session

**User**: "Push my pipeline to the backend"

**Agent workflow**:
1. Ensure virtual environment is activated (remind user if needed)
2. Identify the pipeline file (ask if not specified)
3. Determine mode: if `--name` is provided → create new version; otherwise update
4. Check for environment variables or prompt user
5. Run `python deploy_pipeline.py <file>` (add `--name <name>` for create mode)
6. If `ModuleNotFoundError` occurs, run `pip install -r requirements.txt` and retry
7. Report: "✓ Pipeline deployed successfully" or "✓ Version 'v2' created successfully"

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| ModuleNotFoundError: No module named 'requests' | Missing dependencies | Activate venv, then run `pip install -r requirements.txt` |
| 401 Unauthorized | Invalid API key | Check `TEST_API_KEY` in `.env` |
| 404 Not Found | Invalid app ID or project | Verify `TEST_APP` and `TEST_PROJECT_ID` |
| 400 Bad Request | Invalid YAML or payload | Check YAML syntax and structure |
| Connection refused | Wrong URL | Verify `TEST_DEPLOYMENT_URL` |
| ❌ Version name required | `--name` not passed in create mode | Provide `--name <version_name>` CLI arg |

## Files in This Skill

- `SKILL.md` - This documentation
- `deploy_pipeline.py` - Deployment script
- `README.md` - Quick reference guide
