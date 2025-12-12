# List Files

## Objective

Verify that the `list_files` tool correctly retrieves a list of files from the Azure DevOps repository.

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
| **Tool** | `list_files` | ADO repos tool to execute for listing files |

## Config

path: .alita\tool_configs\ado-config.json
generateTestData : false

## Pre-requisites

- Azure DevOps organization and project exist and are accessible
- Valid Azure DevOps personal access token with read permissions
- Repository with ID specified in config exists
- Repository contains files in the root directory

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `list_files` tool to retrieve files from the repository root directory.

**Expectation:** The tool runs without errors and returns a list of files.

### Step 2: Verify the Output

Verify that the output contains the expected files.

**Expectation:** The output is `['/ElitePipeline.yml', '/README.md']`.
