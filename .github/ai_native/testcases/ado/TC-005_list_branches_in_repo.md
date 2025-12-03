# List Branches in Repository

## Objective

Verify that the `list_branches_in_repo` tool correctly retrieves a list of branches from the Azure DevOps repository.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Organization URL** | `${ADO_ORGANIZATION_URL}` | Azure DevOps organization URL |
| **Project** | `${ADO_PROJECT}` | Azure DevOps project name |
| **Repository ID** | `${ADO_REPOSITORY_ID}` | Azure DevOps repository ID |
| **Token** | `${ADO_TOKEN}` | Azure DevOps personal access token |
| **Base Branch** | `main` | Base branch name |
| **Active Branch** | `main` | Active branch name |
| **Tool** | `list_branches_in_repo` | ADO repos tool to execute for listing branches |

## Config

path: .github\ai_native\testcases\ado\configs\ado-config.json
generateTestData : false

## Pre-requisites

- Azure DevOps organization and project exist and are accessible
- Valid Azure DevOps personal access token with read permissions
- Repository with ID specified in config exists
- Repository contains at least one branch (e.g., main)

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `list_branches_in_repo` tool to retrieve branches from the repository.

**Expectation:** The tool runs without errors and returns a list of branches.

### Step 2: Verify the Output

Verify that the output contains the expected branches.

**Expectation:** The output contains a list of branch names including at least the main branch.
