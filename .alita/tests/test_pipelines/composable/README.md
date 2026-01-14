# Shared Composable Pipelines

This directory contains reusable composable pipelines that can be used across multiple test suites.

## Available Composables

### rca_on_failure.yaml

Root Cause Analysis pipeline with SDK code search capabilities.

**Purpose**: Analyzes test failures with deep code inspection using GitHub toolkit to search and read SDK source code. This enables accurate root cause identification by examining actual implementation.

**Features**:
- Analyzes test failure details
- Searches SDK codebase for relevant code
- Reads source files to understand implementation
- Categorizes failures (tool_error, assertion_failed, timeout, etc.)
- Provides severity assessment
- Suggests fixes with file/line references
- High confidence analysis based on code inspection

**Future Enhancement**: Can run failing tools with different params via code node for deeper insights.

**Prerequisites**:
- SDK analysis toolkit must be created in setup
- Toolkit must have access to alita-sdk repository
- GitHub credentials configured

**Configuration in pipeline.yaml**:

```yaml
setup:
  # Create SDK analysis toolkit
  - name: Setup GitHub Configuration
    type: configuration
    config:
      config_type: github
      alita_title: ${GITHUB_SECRET_NAME:github}
      data:
        access_token: ${GIT_TOOL_ACCESS_TOKEN}
        base_url: "https://api.github.com"

  - name: Create SDK Analysis Toolkit
    type: toolkit
    action: create_or_update
    config:
      config_file: ../configs/git-config.json
      toolkit_type: github
      overrides:
        github_configuration:
          private: true
          alita_title: ${GITHUB_SECRET_NAME:github}
        repository: ${SDK_REPO:ProjectAlita/alita-sdk}
        active_branch: ${SDK_BRANCH:main}
        base_branch: ${SDK_BRANCH:main}
      toolkit_name: sdk-analysis  # Short, reusable name
    save_to_env:
      - key: SDK_TOOLKIT_ID
        value: $.id
      - key: SDK_TOOLKIT_NAME
        value: $.name

composable_pipelines:
  - file: ../composable/rca_on_failure.yaml
    env:
      SUITE_NAME: your_suite_name
      RCA_MODEL: ${RCA_MODEL:gpt-4o-mini}
      SDK_TOOLKIT_ID: ${SDK_TOOLKIT_ID}
      SDK_TOOLKIT_NAME: ${SDK_TOOLKIT_NAME:sdk-analysis}
    save_to_env:
      - key: RCA_PIPELINE_ID
        value: $.id
      - key: RCA_PIPELINE_VERSION_ID
        value: $.versions.0.id
```

## Using RCA in Hooks

Add the RCA hook to your pipeline.yaml:

```yaml
hooks:
  post_test:
    - name: rca_on_failure
      pipeline_id: ${RCA_PIPELINE_ID}
      condition: "result.get('test_passed') is False"
      input_mapping:
        test_name: "result.get('pipeline_name', 'Unknown')"
        test_description: "result.get('description', '')"
        test_results: "result"
        tool_result: "result.get('output', {})"
        toolkit_name: "'your_toolkit_name'"
      output_mapping:
        "result['rca']": "rca_result"
        "result['rca_summary']": "rca_summary"
```

## RCA Output Format

When a test fails, RCA analysis is added to the test result:

```json
{
  "test_passed": false,
  "error": "...",
  "rca": {
    "root_cause": "Clear explanation of what caused the failure",
    "category": "assertion_failed",
    "severity": "medium",
    "suggested_fix": ["Step 1...", "Step 2..."],
    "code_references": ["path/to/file.py:123"],
    "additional_context": "Insights from code analysis...",
    "confidence": "high",
    "test_name": "Test Name"
  },
  "rca_summary": "[MEDIUM] assertion_failed: Brief summary... (see: file.py:123)"
}
```

## How RCA Works

1. **Failure Detection**: Post-test hook triggers when `test_passed` is False
2. **Input Mapping**: Test result fields mapped to RCA pipeline inputs
3. **Code Search**: RCA uses GitHub toolkit to search SDK codebase for relevant code
4. **Source Analysis**: Reads implementation files to understand the failure context
5. **Root Cause Analysis**: LLM analyzes failure with code context and generates structured output
6. **Output Formatting**: Results formatted and added to test result via output mapping

## Example Suites

All test suites use this unified RCA approach:

- **github_toolkit**: Tests GitHub toolkit with RCA analyzing toolkit code
- **state_retrieval**: Tests state management with RCA analyzing SDK state handling
- **structured_output**: Tests LLM outputs with RCA analyzing SDK output parsing

## Creating Custom Composables

To create a new composable pipeline:

1. Create a new `.yaml` file in this directory
2. Use environment variable substitution for customization (e.g., `${SUITE_NAME}`)
3. Define clear input_schema and output_schema
4. Document in this README
5. Reference from suite pipeline.yaml files

Example structure:

```yaml
name: "MyComposable-${SUITE_NAME}"
description: "..."

input_schema:
  # Define what this accepts

output_schema:
  # Define what this returns

entry_point: main_node
nodes:
  # Pipeline logic
```

## Best Practices

- **Consistent Naming**: Use descriptive names with suite name variable
- **Environment Variables**: Use `${VAR:default}` pattern for flexibility
- **Input Schema**: Document required vs optional inputs
- **Output Schema**: Define clear output structure for mapping
- **Toolkit Access**: Ensure required toolkits are linked during seeding
- **Error Handling**: Handle missing or malformed inputs gracefully
