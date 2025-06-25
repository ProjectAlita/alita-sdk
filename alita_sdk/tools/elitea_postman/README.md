# Elitea Postman Toolkit

A comprehensive Python toolkit for interacting with the Postman API, migrated from the original TypeScript/JavaScript implementation. This toolkit provides full-featured API management capabilities including collection analysis, CRUD operations, and quality assessment.

## Features

### Analysis and Read-only Operations
- **Get Collections**: Retrieve all accessible Postman collections
- **Get Collection**: Fetch specific collection details
- **Get Folder**: Access folders from collections by path (supports nested paths)
- **Get Folder Requests**: Detailed information about requests in folders
- **Search Requests**: Search across collections with flexible criteria
- **Analyze Collection**: Comprehensive API quality and best practices analysis
- **Analyze Folder**: Detailed folder-level analysis
- **Get Improvement Suggestions**: AI-powered recommendations for API improvements

### Collection Management
- **Create Collection**: Create new Postman collections with metadata
- **Update Collection**: Modify collection properties, variables, and authentication
- **Delete Collection**: Permanently remove collections
- **Duplicate Collection**: Create collection copies with new names

### Folder Management
- **Create Folder**: Add new folders to collections with optional nesting
- **Update Folder**: Modify folder properties and authentication
- **Delete Folder**: Remove folders and all contents
- **Move Folder**: Relocate folders within collection hierarchy

### Request Management
- **Create Request**: Add new API requests with full configuration
- **Update Request**: Modify existing requests (method, URL, headers, body, tests)
- **Delete Request**: Remove requests permanently
- **Duplicate Request**: Create request copies with customization
- **Move Request**: Relocate requests between folders

## Configuration

The toolkit requires the following configuration parameters:

```python
{
    "api_key": "your_postman_api_key",  # Required: Postman API key
    "base_url": "https://api.getpostman.com",  # Optional: API base URL
    "collection_id": "collection_id_here",  # Optional: Default collection ID
    "workspace_id": "workspace_id_here"  # Optional: Default workspace ID
}
```

## Analysis Features

### Collection Analysis
The toolkit provides comprehensive analysis including:

- **Quality Score**: Overall collection quality (0-100)
- **Security Assessment**: Authentication and credential security analysis
- **Performance Evaluation**: Request optimization and efficiency metrics
- **Documentation Quality**: Description and example completeness
- **Best Practices Compliance**: Industry standard adherence
- **Issue Detection**: Automated identification of problems with severity levels

### Request Analysis
Individual request analysis covers:

- **Authentication Status**: Presence and type of authentication
- **Documentation Quality**: Description and example availability
- **Test Coverage**: Test script comprehensiveness
- **Security Issues**: Credential exposure and security vulnerabilities
- **Performance Issues**: Large payloads, excessive headers
- **Variable Usage**: Environment variable utilization
- **Naming Conventions**: Consistency and descriptiveness
- **Error Handling**: Test script error coverage

### Folder Analysis
Folder-level analysis includes:

- **Structure Quality**: Organization and hierarchy assessment
- **Naming Consistency**: Consistent naming pattern usage
- **Authentication Consistency**: Uniform auth approach across requests
- **Request Distribution**: Balanced folder organization
- **Documentation Standards**: Folder and request description quality

## Usage Examples

### Basic Usage
```python
from alita_sdk.tools.elitea_postman import PostmanToolkit

# Configure toolkit
toolkit = PostmanToolkit.get_toolkit(
    api_key="your_api_key",
    collection_id="your_collection_id",
    selected_tools=["get_collections", "analyze_collection", "create_request"]
)

# Get available tools
tools = toolkit.get_tools()
```

### Analyzing a Collection
```python
# Analyze collection quality
analysis = api_wrapper.analyze_collection(collection_id="collection_id_here")

# Get improvement suggestions
improvements = api_wrapper.get_improvement_suggestions(collection_id="collection_id_here")
```

### Managing Requests
```python
# Create a new request
api_wrapper.create_request(
    collection_id="collection_id",
    folder_path="API/Users",
    name="Get User Profile",
    method="GET",
    url="{{base_url}}/api/users/{{user_id}}",
    description="Retrieve user profile information",
    headers=[
        {"key": "Authorization", "value": "Bearer {{token}}"},
        {"key": "Accept", "value": "application/json"}
    ],
    tests="pm.test('Status code is 200', function () { pm.response.to.have.status(200); });"
)

# Update an existing request
api_wrapper.update_request(
    collection_id="collection_id",
    request_path="API/Users/Get User Profile",
    description="Updated description with more details",
    headers=[
        {"key": "Authorization", "value": "Bearer {{token}}"},
        {"key": "Accept", "value": "application/json"},
        {"key": "Content-Type", "value": "application/json"}
    ]
)
```

### Searching and Organization
```python
# Search for requests
results = api_wrapper.search_requests(
    collection_id="collection_id",
    query="authentication",
    search_in="all",
    method="POST"
)

# Move request to different folder
api_wrapper.move_request(
    collection_id="collection_id",
    source_path="Old Folder/Login Request",
    target_path="Authentication/Auth Requests"
)
```

## Quality Analysis Output

The analysis features provide detailed reports including:

### Collection Analysis Report
```json
{
  "collection_id": "12345",
  "collection_name": "My API Collection",
  "total_requests": 45,
  "score": 78,
  "overall_security_score": 85,
  "overall_performance_score": 72,
  "overall_documentation_score": 65,
  "issues": [
    {
      "type": "warning",
      "severity": "high",
      "message": "Request contains hardcoded URL",
      "location": "Users/Get Profile",
      "suggestion": "Replace hardcoded URLs with environment variables"
    }
  ],
  "recommendations": [
    "Add test scripts to validate responses (12 instances)",
    "Use environment variables for URLs (8 instances)",
    "Add request descriptions (15 instances)"
  ]
}
```

### Request Analysis Details
```json
{
  "name": "Create User",
  "method": "POST",
  "url": "{{base_url}}/api/users",
  "has_auth": true,
  "has_description": true,
  "has_tests": true,
  "security_score": 90,
  "performance_score": 85,
  "test_coverage": "comprehensive",
  "documentation_quality": "good",
  "issues": []
}
```

## Error Handling

The toolkit includes comprehensive error handling with detailed error messages and suggestions:

- **API Connection Errors**: Network and authentication issues
- **Invalid Parameters**: Missing or malformed request parameters
- **Resource Not Found**: Non-existent collections, folders, or requests
- **Permission Errors**: Insufficient API permissions
- **Rate Limiting**: Postman API rate limit handling

## Migration from TypeScript

This Python implementation provides 1:1 feature parity with the original TypeScript version, including:

- All API endpoints and operations
- Complete analysis engine with identical algorithms
- Same configuration and parameter structure
- Equivalent error handling and response formats
- Compatible tool naming and descriptions

## Dependencies

- `requests`: HTTP client for API communication
- `pydantic`: Data validation and settings management
- `langchain_core`: Base toolkit and tool interfaces

## Installation

Install the required dependencies:

```bash
pip install requests pydantic langchain_core
```

The toolkit is integrated into the Alita SDK and available through the standard toolkit loading mechanism.

## Architecture

The toolkit follows the established Alita SDK patterns:

- **`__init__.py`**: Toolkit configuration and registration
- **`api_wrapper.py`**: Core API implementation and business logic  
- **`tool.py`**: Langchain tool action wrapper
- **`types.py`**: Type definitions and data structures

This structure ensures consistency with other Alita SDK toolkits and provides a familiar development experience.
