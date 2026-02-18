# Categorize Toolkit

This procedure determines whether a toolkit directory is a user-facing toolkit (requires test coverage), a framework utility (no tests needed), or a container directory (holds multiple toolkits).

## Purpose

Accurately classify toolkits to calculate meaningful coverage metrics. Framework utilities should not be included in coverage calculations since they are infrastructure, not user-facing features.

## Toolkit Categories

### 1. User-Facing Toolkits

**Definition**: Toolkits that expose tools for users to interact with external services or perform specific tasks.

**Characteristics**:
- ✅ Has wrapper file (`api_wrapper.py` or similar)
- ✅ Contains `get_available_tools()` method
- ✅ Has `toolkit_config_schema()` static method
- ✅ Provides business functionality (not infrastructure)
- ✅ Users directly invoke these tools
- ✅ Requires test coverage

**Examples by Domain**:

| Domain | Toolkits |
|--------|----------|
| **Version Control** | github, gitlab, gitlab_org, bitbucket, localgit, ado |
| **Issue Tracking** | jira, advanced_jira_mining, rally |
| **Documentation** | confluence, sharepoint |
| **Test Management** | xray, qtest, testrail, testio, zephyr, zephyr_enterprise, zephyr_essential, zephyr_scale, zephyr_squad, report_portal |
| **API Tools** | postman, openapi, custom_open_api |
| **Communication** | slack, gmail, yagmail |
| **CRM/ITSM** | salesforce, servicenow, keycloak, carrier |
| **Cloud Infrastructure** | aws (from cloud/), azure (from cloud/), gcp (from cloud/), k8s (from cloud/) |
| **Data & Analytics** | sql, pandas, elastic, bigquery (from google/), delta_lake (from aws/) |
| **Design** | figma |
| **Search** | azure_search (from azure_ai/) |
| **Other** | ocr, pptx, memory, google_places |

### 2. Framework Utilities

**Definition**: Infrastructure components that support toolkit development but don't expose user-facing tools.

**Characteristics**:
- ❌ No `get_available_tools()` method (or returns empty)
- ❌ Provides base classes or utilities
- ❌ Not directly invoked by users
- ❌ No test coverage required

**Complete List**:

| Utility | Location | Purpose |
|---------|----------|----------|
| **base** | `tools/base/` | BaseAction class, BaseTool, BaseToolkit |
| **browser** | `tools/browser/` | Browser automation support (currently empty) |
| **chunkers** | `tools/chunkers/` | Document chunking strategies (markdown, code, JSON) |
| **llm** | `tools/llm/` | LLM integration utilities |
| **utils** | `tools/utils/` | Decorators, helpers, common functions |
| **vector_adapters** | `tools/vector_adapters/` | Vector store adapters (pgvector, etc.) |
| **code** | `tools/code/` | Code analysis base classes (linter, sonar inherit from this) |

### 3. Container Directories

**Definition**: Directories that organize multiple related toolkits but don't contain tools themselves.

**Characteristics**:
- 📁 Contains subdirectories with actual toolkits
- ❌ No wrapper file at this level
- ➡️ Each subdirectory should be analyzed separately

**Known Containers**:

| Container | Sub-Toolkits | Notes |
|-----------|--------------|-------|
| `cloud/` | aws, azure, gcp, k8s | Cloud provider toolkits |
| `ado/` | repos, work_item, test_plan, wiki | Azure DevOps components |
| `aws/` | delta_lake | AWS-specific tools |
| `azure_ai/` | search | Azure AI services |
| `google/` | bigquery | Google Cloud services |

## Decision Process

Use this flowchart to categorize any toolkit directory:

```
[Start: Toolkit Directory]
       |
       v
1. Is it in the Framework Utilities list?
       |
       ├─ YES → [Framework Utility] (No tests required)
       └─ NO → Continue
       |
       v
2. Does it have subdirectories with toolkits?
       |
       ├─ YES → [Container Directory] (Analyze each subdirectory)
       └─ NO → Continue
       |
       v
3. Does it have a wrapper file?
   (api_wrapper.py, *_wrapper.py, *_client.py)
       |
       ├─ NO → [Framework Utility or Empty]
       └─ YES → Continue
       |
       v
4. Does wrapper have get_available_tools()?
       |
       ├─ NO → [Framework Utility]
       └─ YES → Continue
       |
       v
5. Does get_available_tools() return tools?
       |
       ├─ NO (empty) → [Framework Utility]
       └─ YES → [User-Facing Toolkit] (Requires tests)
```

## Step-by-Step Procedure

### Step 1: Check Against Known Lists

**Check if toolkit is a known framework utility**:
- Look up toolkit name in Framework Utilities table above
- If found → Classify as Framework Utility, DONE

**Check if toolkit is a known container**:
- Look up directory in Container Directories table above
- If found → Classify as Container, analyze subdirectories

### Step 2: Inspect Directory Structure

List contents of `alita_sdk/tools/{toolkit}/`:

```
Case A: Has subdirectories (cloud/, ado/, google/, etc.)
  → Container Directory
  → Recursively categorize each subdirectory

Case B: Has wrapper file (api_wrapper.py, etc.)
  → Continue to Step 3

Case C: Only has __init__.py and utility files
  → Likely Framework Utility
```

### Step 3: Analyze Wrapper File

If wrapper file exists:

1. Open the wrapper file
2. Search for `def get_available_tools(self):`
3. Examine the return value:

```python
# User-Facing (has tools)
def get_available_tools(self):
    return [
        {"name": "tool1", ...},
        {"name": "tool2", ...},
    ]

# Framework Utility (empty or no method)
def get_available_tools(self):
    return []  # or method doesn't exist
```

### Step 4: Check for Configuration Schema

User-facing toolkits typically have:

```python
@staticmethod
def toolkit_config_schema() -> BaseModel:
    return create_model(...)
```

If this method exists → Likely user-facing

### Step 5: Make Final Classification

Based on evidence:

- **User-Facing**: Has tools, config schema, clear functionality
- **Framework Utility**: No tools, infrastructure code, utility functions
- **Container**: Has subdirectories, no wrapper at this level

## Expected Output

Provide classification in this format:

```json
{
  "toolkit": "github",
  "category": "user-facing",
  "domain": "Version Control",
  "location": "alita_sdk/tools/github/",
  "reason": "Has api_wrapper.py with 15 tools in get_available_tools()",
  "requires_tests": true,
  "wrapper_file": "api_wrapper.py",
  "has_config_schema": true
}
```

**For Framework Utility**:
```json
{
  "toolkit": "chunkers",
  "category": "framework-utility",
  "location": "alita_sdk/tools/chunkers/",
  "reason": "Provides document chunking utilities, no user-facing tools",
  "requires_tests": false,
  "purpose": "Document chunking strategies for vector indexing"
}
```

**For Container**:
```json
{
  "toolkit": "cloud",
  "category": "container",
  "location": "alita_sdk/tools/cloud/",
  "reason": "Container directory for cloud provider toolkits",
  "sub_toolkits": ["aws", "azure", "gcp", "k8s"],
  "action": "Analyze each sub-toolkit separately"
}
```

## Special Cases

### Case 1: Empty or Placeholder Toolkits

**Example**: `browser/` directory

```
tools/browser/
├── __init__.py    # Empty or minimal
└── (no other files)
```

**Classification**: Framework Utility (placeholder for future development)

### Case 2: Nested Toolkits

**Example**: `cloud/aws/` or `ado/repos/`

**Path**: `alita_sdk/tools/cloud/aws/`

**Classification**: User-Facing (treat as independent toolkit)

**Naming for tests**: Use full path context (e.g., `cloud_aws` or just `aws`)

### Case 3: Multi-Component Toolkits

**Example**: ADO has multiple components (repos, work_item, test_plan, wiki)

**Approach**:
- Each component is a separate user-facing toolkit
- Create separate test suites: `ado_repos`, `ado_work_item`, etc.
- Or create unified `ado_toolkit` suite testing all components

### Case 4: Deprecated Toolkits

**Indicators**:
- Comments in code mentioning "deprecated"
- Empty `get_available_tools()` method
- No recent commits

**Classification**: Framework Utility (exclude from coverage)

## Validation Checklist

- [ ] Checked against known framework utilities list
- [ ] Inspected directory structure
- [ ] Looked for wrapper file
- [ ] Checked for `get_available_tools()` method
- [ ] Verified if method returns tools (not empty)
- [ ] Checked for `toolkit_config_schema()` method
- [ ] Considered special cases (container, deprecated, etc.)
- [ ] Made clear classification with reasoning

## Troubleshooting

**Problem**: Toolkit has wrapper but no `get_available_tools()`  
**Solution**: Likely framework utility or incomplete implementation

**Problem**: Container has wrapper file  
**Solution**: Not a pure container, might be toolkit with sub-components

**Problem**: Unclear if tools are user-facing  
**Solution**: Check if tools appear in platform UI or documentation

**Problem**: New toolkit not in any list  
**Solution**: Use decision flowchart, default to user-facing if it has active tools

## Impact on Coverage Calculation

**User-Facing Toolkits**:
- ✅ Include in total toolkit count
- ✅ Include in coverage percentage
- ✅ Track which have tests
- ✅ Calculate per-toolkit coverage

**Framework Utilities**:
- ❌ Exclude from toolkit count
- ❌ Exclude from coverage calculation
- ℹ️ Document separately in report
- ℹ️ Note their purpose

**Containers**:
- ❌ Don't count container itself
- ✅ Count each sub-toolkit individually
- ℹ️ Note relationship in report

## Related Procedures

- [count-tools.md](./count-tools.md) - Count tools (only for user-facing toolkits)
- [count-tests.md](./count-tests.md) - Count tests (only for user-facing toolkits)
- [skill.md](./skill.md) - Main coverage calculator skill
