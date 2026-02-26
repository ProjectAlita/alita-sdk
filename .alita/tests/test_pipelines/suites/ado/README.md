# Azure DevOps (ADO) Toolkit Test Suite

This directory contains a comprehensive test suite for validating Azure DevOps toolkit functionality through the Alita SDK, covering Repos, Wiki, and Work Items components.

## Directory Structure

```
ado/
├── pipeline.yaml          # Main suite configuration
├── tests/                 # Test case files (41 tests)
│   ├── test_case_01_list_files.yaml
│   ├── test_case_06_get_work_items.yaml
│   ├── test_case_32_search_work_items.yaml  # Work Items tests start here
│   └── ...
├── configs/               # Suite-specific configurations (optional)
└── README.md
```

## Overview

This test suite validates Azure DevOps operations across three major components:
- **ADO Repos** (Tests 01-26): Repository operations, branches, files, pull requests, commits
- **ADO Wiki** (Tests 27-31): Wiki operations, page management
- **ADO Work Items** (Tests 32-41): Work item CRUD, linking, comments, field definitions

## Test Coverage

### ADO Repos Component (Tests 01-26)
**Coverage: 15/15 tools (100%)**

| Test ID | Test Case | Tool | Description |
|---------|-----------|------|-------------|
| ADO01 | List Files | `list_files` | List files in directory |
| ADO02 | List Open PRs | `list_open_pull_requests` | Get open pull requests |
| ADO03 | Read File | `read_file` | Read file content |
| ADO04 | List Branches | `list_branches_in_repo` | List repository branches |
| ADO05 | Get Wiki Page | `get_wiki_page` | Get wiki page with image processing |
| ADO06 | Get Work Items | `get_work_items` | Get work items for PR |
| ADO07 | Comment on PR | `comment_on_pull_request` | Add PR comment |
| ADO08 | Create PR | `create_pull_request` | Create pull request |
| ADO09 | Get Commits | `get_commits` | Get commit history |
| ADO10-11 | Set Active Branch | `set_active_branch` | Change active branch |
| ADO12-13 | Get Pull Request | `get_pull_request` | Get PR details |
| ADO14-15 | List PR Files | `list_pull_request_files` | List files in PR |
| ADO16-17 | Create Branch | `create_branch` | Create new branch |
| ADO18-19 | Create File | `create_file` | Create file in repo |
| ADO20-21 | Update File | `update_file` | Update file content |
| ADO22-23 | Delete File | `delete_file` | Delete file from repo |
| ADO24 | List Files Subdirectory | `list_files` | List files in subdirectory |
| ADO25 | Read File Line Range | `read_file` | Read specific line range |
| ADO26 | List Branches with Details | `list_branches_in_repo` | List branches with metadata |

### ADO Wiki Component (Tests 27-31)
**Coverage: 8/8 tools (100%)**

| Test ID | Test Case | Tool | Description |
|---------|-----------|------|-------------|
| ADO27 | Get Wiki | `get_wiki` | Get wiki details |
| ADO28 | Modify Wiki Page | `modify_wiki_page` | Update wiki page content |
| ADO29 | Rename Wiki Page | `rename_wiki_page` | Rename wiki page |
| ADO30 | Delete Page by Path | `delete_page_by_path` | Delete wiki page by path |
| ADO31 | Delete Page by ID | `delete_page_by_id` | Delete wiki page by ID |

### ADO Work Items Component (Tests 32-41) ⭐ NEW
**Coverage: 10/10 tools (100%)**

| Test ID | Test Case | Tool | Description |
|---------|-----------|------|-------------|
| ADO32 | Search Work Items | `search_work_items` | Query work items using WIQL |
| ADO33 | Create Work Item | `create_work_item` | Create new work item (Task) |
| ADO34 | Get Work Item | `get_work_item` | Retrieve work item by ID |
| ADO35 | Update Work Item | `update_work_item` | Update work item fields |
| ADO36 | Get Work Item Type Fields | `get_work_item_type_fields` | Get field definitions for work item type |
| ADO37 | Get Relation Types | `get_relation_types` | Get available work item link types |
| ADO38 | Link Work Items | `link_work_items` | Create link between two work items |
| ADO39 | Get Comments | `get_comments` | Get comments from work item |
| ADO40 | Link Work Items to Wiki | `link_work_items_to_wiki_page` | Link work items to wiki page |
| ADO41 | Unlink Work Items from Wiki | `unlink_work_items_from_wiki_page` | Remove work item links from wiki |

## Prerequisites

### 1. Azure DevOps Project Setup

You need an Azure DevOps project with:
- **Organization and Project** - Valid ADO organization URL and project name
- **Personal Access Token (PAT)** - Token with appropriate permissions:
  - Work Items: Read, Write
  - Code: Read, Write
  - Wiki: Read, Write
  - Pull Requests: Read, Write

### 2. Test Data Requirements

For work item tests (ADO32-41), you need:
- **Test Work Item** - An existing work item ID for read/update operations
- **Source & Target Work Items** - Two work item IDs for linking tests (ADO38)
- **Wiki** - A wiki created in the project for wiki linking tests (ADO40-41)
  - Wiki name (e.g., "ProjectWiki")
  - Test wiki page path (e.g., "/TestPage")

### 3. Environment Variables

Create a [.env](.alita/tests/test_pipelines/.env) file or set the following environment variables:

**Required for All Tests:**
```bash
# ADO Connection
ADO_ORG=your-org-name                          # Organization name (not full URL)
ADO_PROJECT=your-project-name                  # Project name
ADO_TOKEN=your-personal-access-token           # PAT with appropriate permissions

# Toolkit Configuration
ADO_BOARDS_TOOLKIT_ID=1                        # Toolkit ID after setup
ADO_BOARDS_TOOLKIT_NAME=ado                    # Toolkit reference name
ADO_REPOS_TOOLKIT_ID=1                         # Repos toolkit ID
ADO_REPOS_TOOLKIT_NAME=ado-repos               # Repos toolkit reference name

# Repository
ADO_REPOSITORY_ID=your-repo-id                 # Repository ID or name

# LLM Configuration
DEFAULT_LLM_MODEL=gpt-4o                       # LLM model for validation nodes
```

**Required for Work Item Tests (ADO32-41):**
```bash
# Work Item Test Data
ADO_TEST_WORK_ITEM_ID=68                       # Existing work item ID for read/update tests (e.g., Task #68)
ADO_SOURCE_WORK_ITEM_ID=68                     # Source work item ID for linking test
ADO_TARGET_WORK_ITEM_ID=69                     # Target work item ID for linking test (e.g., Issue #69)

# Wiki Configuration (for ADO40-41)
ADO_WIKI_NAME=TestProject.wiki                 # Wiki identifier/name
```

**Note**: Work items in the test project are in "To Do" state. The test queries have been updated to search for `State = 'To Do'` instead of `State = 'Active'`.

**TestProject Configuration:**
- **Area Path**: `TestProject` (default project area)
- **Iteration Path**: `TestProject` (default project iteration)
- **Valid States**: `To Do`, `Doing`, `Done` (from the project's workflow)
- **Work Item Types**: `Task`, `Issue`, `User Story`, `Epic`, `Feature`

**Example .env file:**
```bash
# Azure DevOps Configuration
ADO_ORG=mycompany
ADO_PROJECT=MyProject
ADO_TOKEN=abcdef1234567890

# Toolkit IDs
ADO_BOARDS_TOOLKIT_ID=1
ADO_BOARDS_TOOLKIT_NAME=ado
ADO_REPOS_TOOLKIT_ID=2
ADO_REPOS_TOOLKIT_NAME=ado-repos

# Repository
ADO_REPOSITORY_ID=my-repo

# Work Item Test Data
ADO_TEST_WORK_ITEM_ID=123
ADO_SOURCE_WORK_ITEM_ID=123
ADO_TARGET_WORK_ITEM_ID=456
ADO_WIKI_NAME=MyProject.wiki

# LLM
DEFAULT_LLM_MODEL=gpt-4o
```

## Configuration Files

### ado-config.json (Work Items Toolkit)
Located at `.alita/tests/test_pipelines/configs/ado-config.json`:

```json
{
  "type": "ado_boards",
  "toolkit_name": "ado",
  "id": 1,
  "ado_configuration": {
    "alita_title": "ado",
    "private": false,
    "organization_url": "https://dev.azure.com/${ADO_ORG}",
    "project": "${ADO_PROJECT}",
    "token": "${ADO_TOKEN}"
  },
  "selected_tools": [
    "search_work_items",
    "create_work_item",
    "update_work_item",
    "delete_work_item",
    "get_work_item",
    "link_work_items",
    "get_relation_types",
    "get_comments",
    "link_work_items_to_wiki_page",
    "unlink_work_items_from_wiki_page",
    "get_work_item_type_fields"
  ]
}
```

### ado-repos-config.json (Repos Toolkit)
For repository operations (ADO01-26).

### ado-wiki-config.json (Wiki Toolkit)
For wiki operations (ADO27-31).

## Running Tests

### Run All ADO Tests
```bash
cd .alita/tests/test_pipelines
./run_all_suites.sh ado
```

### Run Specific Test
```bash
# Run work item search test
./run_test.sh suites/ado ADO32

# Run all work item tests (32-42) using wildcards (MUST wrap with * for substring match)
./run_test.sh --all -w suites/ado --pattern "*ADO3[2-9]*" --pattern "*ADO4[0-2]*"

# Or use multiple specific patterns (substring matching - no wildcards needed)
./run_test.sh --all suites/ado --pattern ADO32 --pattern ADO33 --pattern ADO34 \
  --pattern ADO35 --pattern ADO36 --pattern ADO37 --pattern ADO38 \
  --pattern ADO39 --pattern ADO40 --pattern ADO41 --pattern ADO42

# Simpler: Match by prefix (substring matching - matches 30-39, 40-49)
./run_test.sh --all suites/ado --pattern ADO3 --pattern ADO4

# Run in local mode (no backend)
./run_test.sh --local suites/ado ADO32
```

### Run Work Item Tests Only
```bash
# Using wildcards (most precise - matches ONLY 32-42)
./run_test.sh --all -w suites/ado --pattern "*ADO3[2-9]*" --pattern "*ADO4[0-2]*"

# Using substring matching (simpler but broader - matches all 30-39, 40-49)
./run_test.sh --all suites/ado --pattern ADO3 --pattern ADO4

# Or match by filename prefix
./run_test.sh --all suites/ado --pattern "test_case_3" --pattern "test_case_4"
```

### Setup and Run
```bash
# Full workflow: setup, seed, run, cleanup
./run_test.sh --setup --seed --cleanup suites/ado ADO32
```

## Test Workflow

### Work Item Test Flow (ADO32-42)

1. **ADO36** - Get Work Item Type Fields
   - Discover required fields for work item creation
   - Validates field schema retrieval

2. **ADO33** - Create Work Item
   - Creates a test Task work item
   - Returns work item ID

3. **ADO34** - Get Work Item
   - Retrieves created work item by ID
   - Validates field retrieval

4. **ADO35** - Update Work Item
   - Updates work item fields
   - Validates update operation

5. **ADO32** - Search Work Items
   - Searches using WIQL query
   - Validates query execution

6. **ADO37** - Get Relation Types
   - Gets available link types
   - Validates relation type schema

7. **ADO38** - Link Work Items
   - Links two work items
   - Validates link creation

8. **ADO39** - Get Comments
   - Retrieves work item comments
   - Validates comment retrieval

9. **ADO40** - Link Work Items to Wiki Page
   - Links work items to wiki page
   - Validates wiki page linking

10. **ADO41** - Unlink Work Items from Wiki Page
    - Removes wiki page links
    - Validates link removal

11. **ADO42** - Delete Work Item
    - Deletes a work item by ID
    - Validates deletion operation

## Troubleshooting

### Common Issues

**Authentication Errors**
- Verify `ADO_TOKEN` is valid and not expired
- Ensure PAT has required permissions (Work Items: Read/Write)
- Check organization URL format: `https://dev.azure.com/org-name`

**Work Item Not Found (ADO34, ADO35)**
- Ensure `ADO_TEST_WORK_ITEM_ID` points to an existing work item
- Verify work item is in the correct project
- Check token has access to the work item

**Linking Test Failures (ADO38)**
- Ensure both `ADO_SOURCE_WORK_ITEM_ID` and `ADO_TARGET_WORK_ITEM_ID` exist
- Verify work items are in the same project
- Check that link type is valid (use ADO37 to list available types)

**Wiki Linking Failures (ADO40, ADO41)**
- Verify `ADO_WIKI_NAME` matches actual wiki identifier
- Ensure wiki page exists at specified path
- Check wiki permissions in PAT

### Debug Mode

Run tests with verbose output:
```bash
./run_test.sh -v suites/ado ADO32
```

Run in local mode to see detailed logs:
```bash
./run_test.sh --local -v suites/ado ADO32
```

## Test Results

After running tests, view results:
- **Console Output** - Test pass/fail status
- **HTML Report** - Generated at `test_output/report.html`
- **JSON Results** - Raw results at `test_output/results.json`

## Notes

- **Test Order** - Work item tests (ADO32-41) can run independently except:
  - ADO38 (Link Work Items) requires two existing work items
  - ADO40-41 (Wiki linking) require an existing wiki and work items
  
- **Destructive Operations** - Tests ADO30-31 delete wiki pages; ensure test pages are expendable

- **Rate Limiting** - Azure DevOps APIs have rate limits; if tests fail with 429 errors, wait and retry

- **Token Security** - Never commit `.env` files with actual tokens to version control

## Coverage Statistics

| Component | Tools Tested | Coverage | Test Count |
|-----------|--------------|----------|------------|
| **ADO Repos** | 15/15 | 100% | 26 |
| **ADO Wiki** | 8/8 | 100% | 5 |
| **ADO Work Items** | 11/11 | 100% ⭐ | 11 |
| **Total** | **34/34** | **100%** | **42** |

---

**Overall ADO Toolkit Coverage: 100% (34/34 tools) ✅**

Work Item component tests added: February 12, 2026
Delete work item tool added: February 12, 2026
