# Read File

## Objective

Verify that the `read_file` tool correctly retrieves the content of a specific file from the Azure DevOps repository.

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
| **Tool** | `read_file` | ADO repos tool to execute for reading file content |
| **File Path** | `README.md` | Path to the file to read |

## Config

path: .github\ai_native\testcases\ado\configs\ado-config.json
generateTestData : false

## Pre-requisites

- Azure DevOps organization and project exist and are accessible
- Valid Azure DevOps personal access token with read permissions
- Repository with ID specified in config exists
- Repository contains a README.md file in the root directory

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `read_file` tool to retrieve the content of README.md from the repository.

**Expectation:** The tool runs without errors and returns the file content.

### Step 2: Verify the Output

Verify that the output contains the expected file content.

**Expectation:** The output contains the content of the README.md file from the repository.
