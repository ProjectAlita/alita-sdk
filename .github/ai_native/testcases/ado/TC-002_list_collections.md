# List Collections

## Objective

Verify that the `list_collections` tool correctly retrieves a list of project collections from the Azure DevOps organization.

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
| **Tool** | `list_collections` | ADO repos tool to execute for listing collections |

## Config

path: .github\ai_native\testcases\ado\configs\ado-config.json
generateTestData : false

## Pre-requisites

- Azure DevOps organization exists and is accessible
- Valid Azure DevOps personal access token with read permissions
- Organization contains at least one project collection

## Test Steps & Expectations

### Step 1: Execute the Tool

Execute the `list_collections` tool to retrieve project collections from the organization.

**Expectation:** The tool runs without errors and returns a list of collections.

### Step 2: Verify the Output

Verify that the output contains the expected collections.

**Expectation:** The output contains a list of collection names available in the organization.
