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

   Optional:
   - `TEST_BRANCH` - Target git branch for post-deploy commit (read by agent, not the deployer script)

3. **Execute Deployment Script**
   Run `deploy_pipeline.py` which:
   - Reads the YAML file
   - Fetches current application details (to get `author_id` etc.)
   - **Update mode**: Makes a PUT request to update the version's instructions
   - **Create-version mode**: Makes a POST request to create a new version
   - Reports success or failure

4. **Post-Deploy Git Commit** (agent-driven, after script succeeds)
   See [Post-Deploy Git Commit Workflow](#post-deploy-git-commit-workflow) below.

5. **Report Results**
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
   # Update existing version (default mode, uses project root .env)
   python deploy_pipeline.py /path/to/pipeline.yaml

   # Use a custom .env file
   python deploy_pipeline.py /path/to/pipeline.yaml --env /path/to/.env

   # Override specific params from CLI
   python deploy_pipeline.py /path/to/pipeline.yaml --project-id 123 --app-id 456

   # Use specific version ID for update (skips version lookup)
   python deploy_pipeline.py /path/to/pipeline.yaml --version-id 789

   # Create a new version named 'v2' (--name triggers create mode)
   python deploy_pipeline.py /path/to/pipeline.yaml --name v2
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
- `TEST_BRANCH` - Git branch for post-deploy commit (optional)

**`.env` file loading**: The script loads the project root `.env` by default. Use `--env <path>` to specify a different file.

**Git commit**: If `TEST_BRANCH` is set (or `--branch` provided), after a successful deployment the script automatically:
1. `git add <yaml_file>`
2. `git commit -m "deployed_{YYYYMMDD_HHMMSS}_{app_id}_{version_id_or_name}"`
3. `git push origin HEAD:<branch>`

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

### Create-Version Mode (`--name`)
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

## Post-Deploy Git Commit Workflow

After `deploy_pipeline.py` exits with code 0, the agent **must** execute the following interactive git workflow. Git commands are run in the terminal — the deployer script itself does not touch git.

> **Key principle**: The YAML file must be committed **only** to the target branch. The current working branch must remain completely untouched (no `git add`, no `git commit` on it). This is achieved with `git worktree`.

### Step 1 — Determine target branch

Read `TEST_BRANCH` from `.env`. If not set, ask the user:
> "Deployment succeeded. Which git branch should the YAML be committed to? (or press Enter to skip git commit)"

If the user skips, end here.

### Step 2 — Build the commit message

Format: `deployed_{YYYYMMDD_HHMMSS}_{app_id}_{version_label}`
- `version_label` = new version name (create mode) or version ID (update mode), falling back to `active`
- Example: `deployed_20260327_143512_2259_v2`

### Step 3 — Resolve paths

```bash
# Get the repository root
REPO_ROOT=$(git rev-parse --show-toplevel)

# Compute relative path of the YAML file inside the repo
# (needed to place the file at the same location in the worktree)
RELATIVE_PATH=$(realpath --relative-to="$REPO_ROOT" <yaml_file_abs_path>)
```

### Step 4 — Show confirmation prompt

Present the following summary and wait for the user's explicit choice **before** touching anything:

```
📝 Ready to commit (current branch will NOT be modified):
   File:           <yaml_file_path>
   Repo path:      <relative_path>
   Target branch:  <branch>
   Commit message: deployed_20260327_143512_2259_v2

Choose an action:
  [1] Commit and push to origin/<branch>
  [2] Commit only (no push)
  [3] Skip (do not commit)
```

### Step 5 — Create a temporary git worktree

A worktree is an isolated checkout of the target branch in a temp directory. The current branch and working tree are **never touched**.

```bash
WORKTREE_DIR=$(mktemp -d /tmp/pipeline-deploy-XXXXXX)
git worktree add "$WORKTREE_DIR" <branch>
```

**If the target branch does not exist yet**, create it first from the remote or as an orphan:
```bash
# If remote branch exists:
git fetch origin <branch>
git worktree add "$WORKTREE_DIR" <branch>

# If branch is brand new (no remote):
git worktree add -b <branch> "$WORKTREE_DIR"
```

**If `git worktree add` fails:**
- Show the full error to the user and **stop**
- Ask: "Would you like me to try to resolve this? (y/n)" — only proceed after **yes**
- Always clean up: `git worktree remove "$WORKTREE_DIR" --force` even on failure

### Step 6 — Copy the file and commit inside the worktree

```bash
# Copy the YAML to the same relative location in the worktree
cp <yaml_file_abs_path> "$WORKTREE_DIR/$RELATIVE_PATH"

# Stage and commit from inside the worktree
cd "$WORKTREE_DIR"
git add "$RELATIVE_PATH"
git commit -m "deployed_..."
```

**If commit fails:**
- Show full stdout + stderr
- If `nothing to commit`: file was unchanged, treat as success
- Otherwise ask: "Would you like me to try to resolve this? (y/n)" — only proceed after **yes**

### Step 7 — Push (only if user chose option 1)

```bash
# Push from inside the worktree — this pushes the target branch, not current
git push origin <branch>
```

**If push fails:**
- Show the full stderr verbatim
- State what was detected (e.g., "Remote branch does not exist", "Authentication error", "Non-fast-forward")
- Ask: "Would you like me to attempt to fix this? (y/n)" — only proceed after **yes**

### Step 8 — Clean up the worktree

**Always run this**, success or failure:
```bash
cd "$REPO_ROOT"
git worktree remove "$WORKTREE_DIR" --force
```

### Step 9 — Report

On success:
```
✅ Committed to branch '<branch>': deployed_20260327_143512_2259_v2
✅ Pushed to origin/<branch>  (or: ℹ️  Push skipped by user choice)
ℹ️  Current branch was not modified.
```

On any unresolved failure, summarise:
- What succeeded (worktree created / file copied / committed / pushed)
- What failed (full error)
- Suggested manual commands the user can run themselves
- Confirm worktree was cleaned up (or provide the cleanup command if it wasn't)

## Notes

- The script fetches the current application details first to get `author_id` and version info
- YAML content is embedded in the `instructions` field as a string
- **Update mode**: Only the `instructions` field is updated; other version settings remain unchanged
- **Create-version mode**: Creates a brand-new version record; `author_id` is auto-detected from app details
- **Git operations** are performed by the agent after the script exits, not by the script itself
- `git worktree` is used so the current branch is **never modified** — the commit lands only on the target branch
- Requires valid authentication token with update/create permissions

## Example Session

**User**: "Push my pipeline to the backend"

**Agent workflow**:
1. Ensure virtual environment is activated (remind user if needed)
2. Identify the pipeline file (ask if not specified)
3. Determine mode: if `--name` is provided → create new version; otherwise update
4. Check for environment variables or prompt user (`--env` for custom .env path)
5. Run `python deploy_pipeline.py <file>` (add `--name <name>` for create mode)
6. If `ModuleNotFoundError` occurs, run `pip install -r requirements.txt` and retry
7. On success: follow [Post-Deploy Git Commit Workflow](#post-deploy-git-commit-workflow)

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| ModuleNotFoundError: No module named 'requests' | Missing dependencies | Activate venv, then run `pip install -r requirements.txt` |
| 401 Unauthorized | Invalid API key | Check `TEST_API_KEY` in `.env` |
| 404 Not Found | Invalid app ID or project | Verify `TEST_APP` and `TEST_PROJECT_ID` |
| 400 Bad Request | Invalid YAML or payload | Check YAML syntax and structure |
| Connection refused | Wrong URL | Verify `TEST_DEPLOYMENT_URL` |
| ❌ Version name required | `--name` not passed in create mode | Provide `--name <version_name>` CLI arg |
| ❌ .env file not found | Wrong `--env` path | Verify path passed to `--env` |
| git commit/push fails | Various (see workflow) | Show error, ask user before attempting fix |

## Files in This Skill

- `SKILL.md` - This documentation
- `deploy_pipeline.py` - Deployment script
- `README.md` - Quick reference guide
