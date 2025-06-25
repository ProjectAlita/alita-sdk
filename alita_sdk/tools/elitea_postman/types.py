"""
Type definitions for Postman API wrapper.
"""

from typing import Dict, List, Optional, Any, Union


class PostmanConfig:
    """Configuration for Postman API client."""

    def __init__(self, api_key: str, base_url: str = "https://api.getpostman.com",
                 collection_id: Optional[str] = None, workspace_id: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        self.collection_id = collection_id
        self.workspace_id = workspace_id


class PostmanCollection:
    """Represents a Postman collection."""

    def __init__(self, collection: Dict[str, Any]):
        self.collection = collection


class PostmanItem:
    """Represents a Postman item (folder or request)."""

    def __init__(self, name: str, item: Optional[List['PostmanItem']] = None,
                 request: Optional['PostmanRequest'] = None, **kwargs):
        self.name = name
        self.item = item or []
        self.request = request
        self.id = kwargs.get('id')
        self.description = kwargs.get('description')
        self.response = kwargs.get('response', [])
        self.event = kwargs.get('event', [])
        self.auth = kwargs.get('auth')


class PostmanRequest:
    """Represents a Postman request."""

    def __init__(self, method: str, url: Union[str, Dict], header: List[Dict] = None, **kwargs):
        self.method = method
        self.url = url
        self.header = header or []
        self.body = kwargs.get('body')
        self.auth = kwargs.get('auth')
        self.description = kwargs.get('description')


class PostmanUrl:
    """Represents a Postman URL."""

    def __init__(self, raw: str, **kwargs):
        self.raw = raw
        self.protocol = kwargs.get('protocol')
        self.host = kwargs.get('host')
        self.port = kwargs.get('port')
        self.path = kwargs.get('path')
        self.query = kwargs.get('query', [])
        self.hash = kwargs.get('hash')
        self.variable = kwargs.get('variable', [])


class PostmanHeader:
    """Represents a Postman header."""

    def __init__(self, key: str, value: str, **kwargs):
        self.key = key
        self.value = value
        self.description = kwargs.get('description')
        self.disabled = kwargs.get('disabled', False)


class PostmanVariable:
    """Represents a Postman variable."""

    def __init__(self, key: str, value: str, **kwargs):
        self.key = key
        self.value = value
        self.type = kwargs.get('type', 'string')
        self.description = kwargs.get('description')


class PostmanAuth:
    """Represents Postman authentication."""

    def __init__(self, auth_type: str, **kwargs):
        self.type = auth_type
        self.bearer = kwargs.get('bearer', [])
        self.basic = kwargs.get('basic', [])
        self.apikey = kwargs.get('apikey', [])
        self.oauth1 = kwargs.get('oauth1', [])
        self.oauth2 = kwargs.get('oauth2', [])


class PostmanEvent:
    """Represents a Postman event (pre-request script or test)."""

    def __init__(self, listen: str, script: Dict):
        self.listen = listen  # 'prerequest' or 'test'
        self.script = script


class PostmanScript:
    """Represents a Postman script."""

    def __init__(self, exec_list: List[str], script_type: str = "text/javascript"):
        self.exec = exec_list
        self.type = script_type


class PostmanResponse:
    """Represents a Postman response example."""

    def __init__(self, name: str, original_request: PostmanRequest, **kwargs):
        self.name = name
        self.original_request = original_request
        self.status = kwargs.get('status')
        self.code = kwargs.get('code')
        self.header = kwargs.get('header', [])
        self.body = kwargs.get('body')


class PostmanRequestBody:
    """Represents a Postman request body."""

    def __init__(self, mode: str, **kwargs):
        self.mode = mode  # 'raw', 'urlencoded', 'formdata', 'file', 'graphql', 'binary'
        self.raw = kwargs.get('raw')
        self.urlencoded = kwargs.get('urlencoded', [])
        self.formdata = kwargs.get('formdata', [])
        self.file = kwargs.get('file')
        self.binary = kwargs.get('binary')
        self.graphql = kwargs.get('graphql')
        self.options = kwargs.get('options')


class ApiIssue:
    """Represents an API issue found during analysis."""

    def __init__(self, issue_type: str, severity: str, message: str, location: str, suggestion: Optional[str] = None):
        self.type = issue_type  # 'error', 'warning', 'info'
        self.severity = severity  # 'high', 'medium', 'low'
        self.message = message
        self.location = location
        self.suggestion = suggestion


class ApiImprovement:
    """Represents an API improvement suggestion."""

    def __init__(self, improvement_id: str, title: str, description: str, priority: str, category: str, impact: str):
        self.id = improvement_id
        self.title = title
        self.description = description
        self.priority = priority  # 'high', 'medium', 'low'
        # 'security', 'performance', 'documentation', 'testing', etc.
        self.category = category
        self.impact = impact  # 'high', 'medium', 'low'


class RequestAnalysis:
    """Represents analysis results for a single request."""

    def __init__(self, name: str, method: str, url: str, **kwargs):
        self.name = name
        self.method = method
        self.url = url

        # Basic analysis
        self.has_auth = kwargs.get('has_auth', False)
        self.has_description = kwargs.get('has_description', False)
        self.has_tests = kwargs.get('has_tests', False)
        self.has_examples = kwargs.get('has_examples', False)

        # Enhanced analysis
        self.has_hardcoded_url = kwargs.get('has_hardcoded_url', False)
        self.has_hardcoded_data = kwargs.get('has_hardcoded_data', False)
        self.has_proper_headers = kwargs.get('has_proper_headers', True)
        self.has_variables = kwargs.get('has_variables', False)
        self.has_error_handling = kwargs.get('has_error_handling', False)
        self.follows_naming_convention = kwargs.get(
            'follows_naming_convention', True)
        self.has_security_issues = kwargs.get('has_security_issues', False)
        self.has_performance_issues = kwargs.get(
            'has_performance_issues', False)

        # Metadata
        self.auth_type = kwargs.get('auth_type')
        self.response_examples = kwargs.get('response_examples', 0)
        # 'none', 'basic', 'comprehensive'
        self.test_coverage = kwargs.get('test_coverage', 'none')
        # 'none', 'minimal', 'good', 'excellent'
        self.documentation_quality = kwargs.get(
            'documentation_quality', 'none')

        # Scores
        self.security_score = kwargs.get('security_score', 0)
        self.performance_score = kwargs.get('performance_score', 0)

        # Issues
        self.issues = kwargs.get('issues', [])


class FolderAnalysis:
    """Represents analysis results for a folder."""

    def __init__(self, name: str, path: str, request_count: int, requests: List[RequestAnalysis], **kwargs):
        self.name = name
        self.path = path
        self.request_count = request_count
        self.requests = requests

        # Analysis results
        self.has_consistent_naming = kwargs.get('has_consistent_naming', True)
        self.has_proper_structure = kwargs.get('has_proper_structure', True)
        self.auth_consistency = kwargs.get(
            'auth_consistency', 'none')  # 'consistent', 'mixed', 'none'

        # Average scores
        self.avg_documentation_quality = kwargs.get(
            'avg_documentation_quality', 0)
        self.avg_security_score = kwargs.get('avg_security_score', 0)
        self.avg_performance_score = kwargs.get('avg_performance_score', 0)

        # Issues and improvements
        self.issues = kwargs.get('issues', [])
        self.improvements = kwargs.get('improvements', [])
        self.subfolders = kwargs.get('subfolders', [])


class ApiAnalysis:
    """Represents comprehensive analysis results for a collection."""

    def __init__(self, collection_id: str, collection_name: str, total_requests: int,
                 folders: List[FolderAnalysis], **kwargs):
        self.collection_id = collection_id
        self.collection_name = collection_name
        self.total_requests = total_requests
        self.folders = folders

        # Analysis results
        self.issues = kwargs.get('issues', [])
        self.recommendations = kwargs.get('recommendations', [])
        self.score = kwargs.get('score', 0)

        # Overall scores
        self.overall_security_score = kwargs.get('overall_security_score', 0)
        self.overall_performance_score = kwargs.get(
            'overall_performance_score', 0)
        self.overall_documentation_score = kwargs.get(
            'overall_documentation_score', 0)
        self.compliance_score = kwargs.get('compliance_score', 0)

        # Enhanced analysis
        self.improvement_analysis = kwargs.get('improvement_analysis', {})
        self.best_practices_compliance = kwargs.get(
            'best_practices_compliance', {})
        self.variable_usage_analysis = kwargs.get(
            'variable_usage_analysis', {})
        self.authentication_analysis = kwargs.get(
            'authentication_analysis', {})
