"""
Postman collection analysis utilities.

This module contains all the analysis logic for Postman collections, folders, and requests
that is separate from the API interaction logic.
"""

import json
import re
from typing import Any, Dict, List, Optional


class PostmanAnalyzer:
    """Analyzer for Postman collections, folders, and requests."""

    def perform_collection_analysis(self, collection: Dict) -> Dict:
        """Perform comprehensive analysis of a collection."""
        collection_data = collection['collection']
        folders = self.analyze_folders(collection_data.get('item', []))
        total_requests = self.count_requests(collection_data.get('item', []))
        issues = self.identify_collection_issues(collection_data)
        score = self.calculate_quality_score(collection_data, folders, issues)
        recommendations = self.generate_recommendations(issues)

        return {
            "collection_id": collection_data['info'].get('_postman_id', ''),
            "collection_name": collection_data['info'].get('name', ''),
            "total_requests": total_requests,
            "folders": folders,
            "issues": issues,
            "recommendations": recommendations,
            "score": score,
            "overall_security_score": self.calculate_overall_security_score(folders),
            "overall_performance_score": self.calculate_overall_performance_score(folders),
            "overall_documentation_score": self.calculate_overall_documentation_score(folders)
        }

    def analyze_folders(self, items: List[Dict], base_path: str = "") -> List[Dict]:
        """Analyze all folders in a collection."""
        folders = []

        for item in items:
            if item.get('item') is not None:  # This is a folder
                folder_path = f"{base_path}/{item['name']}" if base_path else item['name']
                analysis = self.perform_folder_analysis(item, folder_path)
                folders.append(analysis)

                # Recursively analyze subfolders
                subfolders = self.analyze_folders(item['item'], folder_path)
                folders.extend(subfolders)

        return folders

    def perform_folder_analysis(self, folder: Dict, path: str) -> Dict:
        """Perform analysis of a specific folder."""
        requests = self.analyze_requests(folder.get('item', []))
        request_count = self.count_requests(folder.get('item', []))
        issues = self.identify_folder_issues(folder, requests)

        return {
            "name": folder['name'],
            "path": path,
            "request_count": request_count,
            "requests": requests,
            "issues": issues,
            "has_consistent_naming": self.check_consistent_naming(folder.get('item', [])),
            "has_proper_structure": bool(folder.get('description') and folder.get('item')),
            "auth_consistency": self.check_auth_consistency(requests),
            "avg_documentation_quality": self.calculate_avg_documentation_quality(requests),
            "avg_security_score": self.calculate_avg_security_score(requests),
            "avg_performance_score": self.calculate_avg_performance_score(requests)
        }

    def analyze_requests(self, items: List[Dict]) -> List[Dict]:
        """Analyze requests within a folder."""
        requests = []

        for item in items:
            if item.get('request'):  # This is a request
                analysis = self.perform_request_analysis(item)
                requests.append(analysis)

        return requests

    def perform_request_analysis(self, item: Dict) -> Dict:
        """Perform comprehensive analysis of a specific request."""
        request = item['request']
        issues = []

        # Basic checks
        has_auth = bool(request.get('auth') or self.has_auth_in_headers(request))
        has_description = bool(item.get('description') or request.get('description'))
        has_tests = bool([e for e in item.get('event', []) if e.get('listen') == 'test'])
        has_examples = bool(item.get('response', []))

        # Enhanced analysis
        url = request.get('url', '')
        if isinstance(url, dict):
            url = url.get('raw', '')

        has_hardcoded_url = self.detect_hardcoded_url(url)
        has_hardcoded_data = self.detect_hardcoded_data(request)
        has_proper_headers = self.validate_headers(request)
        has_variables = self.detect_variable_usage(request)
        has_error_handling = self.detect_error_handling(item)
        follows_naming_convention = self.validate_naming_convention(item['name'])
        has_security_issues = self.detect_security_issues(request)
        has_performance_issues = self.detect_performance_issues(request)

        # Calculate scores
        security_score = self.calculate_security_score(request, has_auth, has_security_issues)
        performance_score = self.calculate_performance_score(request, has_performance_issues)

        # Generate issues
        self.generate_request_issues(issues, item, {
            'has_description': has_description,
            'has_auth': has_auth,
            'has_tests': has_tests,
            'has_hardcoded_url': has_hardcoded_url,
            'has_hardcoded_data': has_hardcoded_data,
            'has_proper_headers': has_proper_headers,
            'has_security_issues': has_security_issues,
            'follows_naming_convention': follows_naming_convention
        })

        return {
            "name": item['name'],
            "method": request.get('method'),
            "url": url,
            "has_auth": has_auth,
            "has_description": has_description,
            "has_tests": has_tests,
            "has_examples": has_examples,
            "issues": issues,
            "has_hardcoded_url": has_hardcoded_url,
            "has_hardcoded_data": has_hardcoded_data,
            "has_proper_headers": has_proper_headers,
            "has_variables": has_variables,
            "has_error_handling": has_error_handling,
            "follows_naming_convention": follows_naming_convention,
            "has_security_issues": has_security_issues,
            "has_performance_issues": has_performance_issues,
            "auth_type": request.get('auth', {}).get('type'),
            "response_examples": len(item.get('response', [])),
            "test_coverage": self.assess_test_coverage(item),
            "documentation_quality": self.assess_documentation_quality(item),
            "security_score": security_score,
            "performance_score": performance_score
        }

    def extract_requests_from_items(self, items: List[Dict], include_details: bool = False) -> List[Dict]:
        """Extract requests from items recursively."""
        requests = []

        for item in items:
            if item.get('request'):
                # This is a request
                request_data = {
                    "name": item.get('name'),
                    "method": item['request'].get('method'),
                    "url": item['request'].get('url')
                }

                if include_details:
                    request_data.update({
                        "description": item.get('description'),
                        "headers": item['request'].get('header', []),
                        "body": item['request'].get('body'),
                        "auth": item['request'].get('auth'),
                        "tests": [e for e in item.get('event', []) if e.get('listen') == 'test'],
                        "pre_request_scripts": [e for e in item.get('event', []) if e.get('listen') == 'prerequest']
                    })

                requests.append(request_data)
            elif item.get('item'):
                # This is a folder, recurse
                requests.extend(self.extract_requests_from_items(
                    item['item'], include_details))

        return requests

    def search_requests_in_items(self, items: List[Dict], query: str, search_in: str, method: str = None) -> List[Dict]:
        """Search for requests in items recursively."""
        results = []
        query_lower = query.lower()

        for item in items:
            if item.get('request'):
                # This is a request
                request = item['request']
                matches = False

                # Check method filter first
                if method and request.get('method', '').upper() != method.upper():
                    continue

                # Check search criteria
                if search_in == 'all' or search_in == 'name':
                    if query_lower in item.get('name', '').lower():
                        matches = True

                if search_in == 'all' or search_in == 'url':
                    url = request.get('url', '')
                    if isinstance(url, dict):
                        url = url.get('raw', '')
                    if query_lower in url.lower():
                        matches = True

                if search_in == 'all' or search_in == 'description':
                    description = item.get('description', '') or request.get('description', '')
                    if query_lower in description.lower():
                        matches = True

                if matches:
                    results.append({
                        "name": item.get('name'),
                        "method": request.get('method'),
                        "url": request.get('url'),
                        "description": item.get('description') or request.get('description'),
                        "path": self.get_item_path(items, item)
                    })

            elif item.get('item'):
                # This is a folder, recurse
                results.extend(self.search_requests_in_items(
                    item['item'], query, search_in, method))

        return results

    def get_item_path(self, root_items: List[Dict], target_item: Dict, current_path: str = "") -> str:
        """Get the path of an item within the collection structure."""
        for item in root_items:
            item_path = f"{current_path}/{item['name']}" if current_path else item['name']

            if item == target_item:
                return item_path

            if item.get('item'):
                result = self.get_item_path(
                    item['item'], target_item, item_path)
                if result:
                    return result

        return ""

    def get_script_content(self, events: List[Dict], script_type: str) -> str:
        """Get script content from event list."""
        for event in events:
            if event.get("listen") == script_type and event.get("script"):
                script_exec = event["script"].get("exec", [])
                if isinstance(script_exec, list):
                    return "\n".join(script_exec)
                return str(script_exec)
        return ""

    # =================================================================
    # UTILITY METHODS
    # =================================================================

    def count_requests(self, items: List[Dict]) -> int:
        """Count total requests in items."""
        count = 0
        for item in items:
            if item.get('request'):
                count += 1
            elif item.get('item'):
                count += self.count_requests(item['item'])
        return count

    def has_auth_in_headers(self, request: Dict) -> bool:
        """Check if request has authentication in headers."""
        headers = request.get('header', [])
        auth_headers = ['authorization', 'x-api-key', 'x-auth-token']
        return any(h.get('key', '').lower() in auth_headers for h in headers)

    def detect_hardcoded_url(self, url: str) -> bool:
        """Detect hardcoded URLs that should use variables."""
        hardcoded_patterns = [
            r'^https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',  # IP addresses
            r'^https?://localhost',  # localhost
            r'^https?://[a-zA-Z0-9.-]+\.(com|org|net|io|dev)',  # Direct domains
            r'api\.example\.com',  # Example domains
            r'staging\.|dev\.|test\.'  # Environment-specific
        ]
        return any(re.search(pattern, url) for pattern in hardcoded_patterns) and '{{' not in url

    def detect_hardcoded_data(self, request: Dict) -> bool:
        """Detect hardcoded data in request body and headers."""
        # Check headers
        headers = request.get('header', [])
        has_hardcoded_headers = any(
            ('token' in h.get('key', '').lower() or
             'key' in h.get('key', '').lower() or
             'secret' in h.get('key', '').lower()) and
            '{{' not in h.get('value', '')
            for h in headers
        )

        # Check body
        has_hardcoded_body = False
        body = request.get('body', {})
        if body.get('raw'):
            try:
                body_data = json.loads(body['raw'])
                has_hardcoded_body = self.contains_hardcoded_values(body_data)
            except json.JSONDecodeError:
                # If not JSON, check for common patterns
                has_hardcoded_body = re.search(
                    r'("api_key"|"token"|"password"):\s*"[^{]', body['raw']) is not None

        return has_hardcoded_headers or has_hardcoded_body

    def contains_hardcoded_values(self, obj: Any) -> bool:
        """Check if object contains hardcoded values that should be variables."""
        if not isinstance(obj, dict):
            return False

        for key, value in obj.items():
            if isinstance(value, str):
                # Check for sensitive keys
                if key.lower() in ['token', 'key', 'secret', 'password', 'api_key', 'client_id', 'client_secret']:
                    if '{{' not in value:
                        return True
                # Check for email patterns, URLs
                if re.search(r'@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', value) or value.startswith('http'):
                    if '{{' not in value:
                        return True
            elif isinstance(value, dict):
                if self.contains_hardcoded_values(value):
                    return True

        return False

    def validate_headers(self, request: Dict) -> bool:
        """Validate request headers."""
        headers = request.get('header', [])
        header_names = [h.get('key', '').lower() for h in headers]
        method = request.get('method', '').upper()

        # Check for essential headers
        if method in ['POST', 'PUT', 'PATCH'] and request.get('body'):
            if 'content-type' not in header_names:
                return False

        if method in ['GET', 'POST', 'PUT', 'PATCH']:
            if 'accept' not in header_names:
                return False

        return True

    def detect_variable_usage(self, request: Dict) -> bool:
        """Detect variable usage in request."""
        url = request.get('url', '')
        if isinstance(url, dict):
            url = url.get('raw', '')

        has_url_variables = '{{' in url
        has_header_variables = any('{{' in h.get('value', '') for h in request.get('header', []))

        has_body_variables = False
        body = request.get('body', {})
        if body.get('raw'):
            has_body_variables = '{{' in body['raw']

        return has_url_variables or has_header_variables or has_body_variables

    def detect_error_handling(self, item: Dict) -> bool:
        """Detect error handling in tests."""
        test_scripts = [e for e in item.get('event', []) if e.get('listen') == 'test']

        for script in test_scripts:
            script_code = '\n'.join(script.get('script', {}).get('exec', []))
            if ('4' in script_code or '5' in script_code or
                    'error' in script_code.lower() or 'fail' in script_code.lower()):
                return True

        return False

    def validate_naming_convention(self, name: str) -> bool:
        """Validate naming convention."""
        has_consistent_case = re.match(r'^[a-zA-Z][a-zA-Z0-9\s\-_]*$', name) is not None
        has_descriptive_name = len(name) > 3 and 'test' not in name.lower() and 'temp' not in name.lower()
        return has_consistent_case and has_descriptive_name

    def detect_security_issues(self, request: Dict) -> bool:
        """Detect security issues."""
        url = request.get('url', '')
        if isinstance(url, dict):
            url = url.get('raw', '')

        # Check for exposed credentials in URL
        if re.search(r'[?&](token|key|password|secret)=([^&\s]+)', url):
            return True

        # Check for weak authentication
        auth = request.get('auth', {})
        if auth.get('type') == 'basic' and not url.startswith('https'):
            return True

        # Check headers for exposed credentials
        headers = request.get('header', [])
        return any('secret' in h.get('key', '').lower() or 'password' in h.get('key', '').lower()
                   for h in headers)

    def detect_performance_issues(self, request: Dict) -> bool:
        """Detect performance issues."""
        # Large request body
        body = request.get('body', {})
        if body.get('raw') and len(body['raw']) > 10000:
            return True

        # Too many headers
        if len(request.get('header', [])) > 20:
            return True

        # Too many query parameters
        url = request.get('url', '')
        if isinstance(url, dict):
            url = url.get('raw', '')

        query_params = url.split('?')[1] if '?' in url else ''
        if query_params and len(query_params.split('&')) > 15:
            return True

        return False

    # =================================================================
    # SCORING METHODS
    # =================================================================

    def calculate_security_score(self, request: Dict, has_auth: bool, has_security_issues: bool) -> int:
        """Calculate security score."""
        score = 100
        method = request.get('method', '').upper()

        if not has_auth and method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            score -= 40

        if has_security_issues:
            score -= 30

        url = request.get('url', '')
        if isinstance(url, dict):
            url = url.get('raw', '')

        if url.startswith('http://'):
            score -= 20

        auth = request.get('auth', {})
        if auth.get('type') == 'basic':
            score -= 10

        return max(0, score)

    def calculate_performance_score(self, request: Dict, has_performance_issues: bool) -> int:
        """Calculate performance score."""
        score = 100

        if has_performance_issues:
            score -= 50

        headers = request.get('header', [])
        header_names = [h.get('key', '').lower() for h in headers]

        if 'cache-control' not in header_names:
            score -= 10

        if 'accept-encoding' not in header_names:
            score -= 10

        return max(0, score)

    def assess_test_coverage(self, item: Dict) -> str:
        """Assess test coverage."""
        test_scripts = [e for e in item.get('event', []) if e.get('listen') == 'test']

        if not test_scripts:
            return 'none'

        all_test_code = '\n'.join([
            '\n'.join(script.get('script', {}).get('exec', []))
            for script in test_scripts
        ])

        checks = [
            'pm.response.code' in all_test_code or 'status' in all_test_code,
            'responseTime' in all_test_code,
            'pm.response.json' in all_test_code or 'body' in all_test_code,
            '4' in all_test_code or '5' in all_test_code
        ]

        check_count = sum(checks)

        if check_count >= 3:
            return 'comprehensive'
        elif check_count >= 1:
            return 'basic'

        return 'none'

    def assess_documentation_quality(self, item: Dict) -> str:
        """Assess documentation quality."""
        description = item.get('description', '') or item.get('request', {}).get('description', '')

        if not description:
            return 'none'

        description_lower = description.lower()
        quality_factors = [
            'parameter' in description_lower,
            'response' in description_lower,
            'example' in description_lower,
            'auth' in description_lower,
            'error' in description_lower
        ]

        factor_count = sum(quality_factors)

        if factor_count >= 4:
            return 'excellent'
        elif factor_count >= 2:
            return 'good'
        elif factor_count >= 1 or len(description) > 50:
            return 'minimal'

        return 'none'

    def check_consistent_naming(self, items: List[Dict]) -> bool:
        """Check if items have consistent naming."""
        if len(items) <= 1:
            return True

        naming_patterns = []
        for item in items:
            name = item.get('name', '').lower()
            if re.match(r'^[a-z][a-z0-9]*(_[a-z0-9]+)*$', name):
                naming_patterns.append('snake_case')
            elif re.match(r'^[a-z][a-zA-Z0-9]*$', name):
                naming_patterns.append('camelCase')
            elif re.match(r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$', name):
                naming_patterns.append('kebab-case')
            else:
                naming_patterns.append('mixed')

        unique_patterns = set(naming_patterns)
        return len(unique_patterns) == 1 and 'mixed' not in unique_patterns

    def check_auth_consistency(self, requests: List[Dict]) -> str:
        """Check authentication consistency across requests."""
        if not requests:
            return 'none'

        auth_types = set(req.get('auth_type') or 'none' for req in requests)

        if len(auth_types) == 1:
            return 'none' if 'none' in auth_types else 'consistent'

        return 'mixed'

    def calculate_avg_documentation_quality(self, requests: List[Dict]) -> int:
        """Calculate average documentation quality score."""
        if not requests:
            return 0

        quality_scores = {
            'excellent': 100,
            'good': 75,
            'minimal': 50,
            'none': 0
        }

        scores = [quality_scores.get(req.get('documentation_quality', 'none'), 0) for req in requests]
        return round(sum(scores) / len(scores))

    def calculate_avg_security_score(self, requests: List[Dict]) -> int:
        """Calculate average security score."""
        if not requests:
            return 0

        scores = [req.get('security_score', 0) for req in requests]
        return round(sum(scores) / len(scores))

    def calculate_avg_performance_score(self, requests: List[Dict]) -> int:
        """Calculate average performance score."""
        if not requests:
            return 0

        scores = [req.get('performance_score', 0) for req in requests]
        return round(sum(scores) / len(scores))

    def calculate_quality_score(self, collection_data: Dict, folders: List[Dict], issues: List[Dict]) -> int:
        """Calculate quality score (0-100)."""
        score = 100

        # Deduct points for issues
        for issue in issues:
            severity = issue.get('severity', 'low')
            if severity == 'high':
                score -= 10
            elif severity == 'medium':
                score -= 5
            elif severity == 'low':
                score -= 2

        # Deduct points for folder and request issues
        for folder in folders:
            for issue in folder.get('issues', []):
                severity = issue.get('severity', 'low')
                if severity == 'high':
                    score -= 5
                elif severity == 'medium':
                    score -= 3
                elif severity == 'low':
                    score -= 1

            for request in folder.get('requests', []):
                for issue in request.get('issues', []):
                    severity = issue.get('severity', 'low')
                    if severity == 'high':
                        score -= 3
                    elif severity == 'medium':
                        score -= 2
                    elif severity == 'low':
                        score -= 1

        return max(0, min(100, score))

    def calculate_overall_security_score(self, folders: List[Dict]) -> int:
        """Calculate overall security score."""
        if not folders:
            return 0

        scores = []
        for folder in folders:
            avg_score = folder.get('avg_security_score', 0)
            if avg_score > 0:
                scores.append(avg_score)

        return round(sum(scores) / len(scores)) if scores else 0

    def calculate_overall_performance_score(self, folders: List[Dict]) -> int:
        """Calculate overall performance score."""
        if not folders:
            return 0

        scores = []
        for folder in folders:
            avg_score = folder.get('avg_performance_score', 0)
            if avg_score > 0:
                scores.append(avg_score)

        return round(sum(scores) / len(scores)) if scores else 0

    def calculate_overall_documentation_score(self, folders: List[Dict]) -> int:
        """Calculate overall documentation score."""
        if not folders:
            return 0

        scores = []
        for folder in folders:
            avg_score = folder.get('avg_documentation_quality', 0)
            if avg_score > 0:
                scores.append(avg_score)

        return round(sum(scores) / len(scores)) if scores else 0

    # =================================================================
    # ISSUE IDENTIFICATION METHODS
    # =================================================================

    def identify_collection_issues(self, collection_data: Dict) -> List[Dict]:
        """Identify collection-level issues."""
        issues = []

        if not collection_data.get('info', {}).get('description'):
            issues.append({
                'type': 'warning',
                'severity': 'medium',
                'message': 'Collection lacks description',
                'location': 'Collection root',
                'suggestion': 'Add a description explaining the purpose of this collection'
            })

        if not collection_data.get('auth'):
            issues.append({
                'type': 'info',
                'severity': 'low',
                'message': 'Collection lacks default authentication',
                'location': 'Collection root',
                'suggestion': 'Consider setting up collection-level authentication'
            })

        return issues

    def identify_folder_issues(self, folder: Dict, requests: List[Dict]) -> List[Dict]:
        """Identify folder-level issues."""
        issues = []

        if not folder.get('description'):
            issues.append({
                'type': 'warning',
                'severity': 'low',
                'message': 'Folder lacks description',
                'location': folder['name'],
                'suggestion': 'Add a description explaining the purpose of this folder'
            })

        if not requests and (not folder.get('item') or len(folder['item']) == 0):
            issues.append({
                'type': 'warning',
                'severity': 'medium',
                'message': 'Empty folder',
                'location': folder['name'],
                'suggestion': 'Consider removing empty folders or adding requests'
            })

        return issues

    def generate_request_issues(self, issues: List[Dict], item: Dict, analysis: Dict):
        """Generate request-specific issues."""
        if not analysis['has_description']:
            issues.append({
                'type': 'warning',
                'severity': 'medium',
                'message': 'Request lacks description',
                'location': item['name'],
                'suggestion': 'Add a clear description explaining what this request does'
            })

        if not analysis['has_auth'] and item['request']['method'] in ['POST', 'PUT', 'PATCH', 'DELETE']:
            issues.append({
                'type': 'warning',
                'severity': 'high',
                'message': 'Sensitive operation without authentication',
                'location': item['name'],
                'suggestion': 'Add authentication for this request'
            })

        if not analysis['has_tests']:
            issues.append({
                'type': 'info',
                'severity': 'high',
                'message': 'Request lacks test scripts',
                'location': item['name'],
                'suggestion': 'Add test scripts to validate response'
            })

        if analysis['has_hardcoded_url']:
            issues.append({
                'type': 'warning',
                'severity': 'high',
                'message': 'Request contains hardcoded URL',
                'location': item['name'],
                'suggestion': 'Replace hardcoded URLs with environment variables'
            })

        if analysis['has_security_issues']:
            issues.append({
                'type': 'error',
                'severity': 'high',
                'message': 'Security vulnerabilities detected',
                'location': item['name'],
                'suggestion': 'Address security issues such as exposed credentials'
            })

    # =================================================================
    # IMPROVEMENT GENERATION METHODS
    # =================================================================

    def generate_recommendations(self, issues: List[Dict]) -> List[str]:
        """Generate recommendations based on issues."""
        recommendations = []
        suggestion_counts = {}

        # Count similar suggestions
        for issue in issues:
            suggestion = issue.get('suggestion', '')
            if suggestion:
                suggestion_counts[suggestion] = suggestion_counts.get(suggestion, 0) + 1

        # Generate recommendations from most common suggestions
        sorted_suggestions = sorted(
            suggestion_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        for suggestion, count in sorted_suggestions:
            if count > 1:
                recommendations.append(f"{suggestion} ({count} instances)")
            else:
                recommendations.append(suggestion)

        return recommendations

    def generate_improvements(self, analysis: Dict) -> List[Dict]:
        """Generate improvement suggestions with enhanced analysis."""
        improvements = []

        # Collection-level improvements
        if analysis['score'] < 80:
            improvements.append({
                'id': 'collection-quality',
                'title': 'Improve Overall Collection Quality',
                'description': f"Collection quality score is {analysis['score']}/100. Focus on addressing high-priority issues.",
                'priority': 'high',
                'category': 'quality',
                'impact': 'high'
            })

        if analysis['overall_security_score'] < 70:
            improvements.append({
                'id': 'security-enhancement',
                'title': 'Enhance Security Practices',
                'description': f"Security score is {analysis['overall_security_score']}/100. Review authentication and data handling.",
                'priority': 'high',
                'category': 'security',
                'impact': 'high'
            })

        if analysis['overall_documentation_score'] < 60:
            improvements.append({
                'id': 'documentation-improvement',
                'title': 'Improve Documentation',
                'description': f"Documentation score is {analysis['overall_documentation_score']}/100. Add descriptions and examples.",
                'priority': 'medium',
                'category': 'documentation',
                'impact': 'medium'
            })

        # Add specific improvements based on common issues
        issue_counts = {}
        for folder in analysis.get('folders', []):
            for request in folder.get('requests', []):
                for issue in request.get('issues', []):
                    issue_type = issue.get('message', '')
                    issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1

        # Generate improvements for most common issues
        if issue_counts.get('Request lacks test scripts', 0) > 3:
            improvements.append({
                'id': 'add-test-scripts',
                'title': 'Add Test Scripts to Requests',
                'description': f"Found {issue_counts['Request lacks test scripts']} requests without test scripts.",
                'priority': 'medium',
                'category': 'testing',
                'impact': 'medium'
            })

        if issue_counts.get('Request contains hardcoded URL', 0) > 2:
            improvements.append({
                'id': 'use-environment-variables',
                'title': 'Use Environment Variables',
                'description': f"Found {issue_counts['Request contains hardcoded URL']} requests with hardcoded URLs.",
                'priority': 'high',
                'category': 'maintainability',
                'impact': 'high'
            })

        return improvements

    def generate_folder_improvements(self, analysis: Dict) -> List[Dict]:
        """Generate improvement suggestions for a specific folder."""
        improvements = []

        # Folder-level improvements
        if analysis.get('avg_security_score', 0) < 70:
            improvements.append({
                'id': 'folder-security',
                'title': 'Improve Folder Security',
                'description': f"Folder security score is {analysis.get('avg_security_score', 0)}/100. Review authentication and data handling.",
                'priority': 'high',
                'category': 'security',
                'impact': 'high'
            })

        if analysis.get('avg_documentation_quality', 0) < 60:
            improvements.append({
                'id': 'folder-documentation',
                'title': 'Improve Folder Documentation',
                'description': f"Documentation quality is {analysis.get('avg_documentation_quality', 0)}/100. Add descriptions and examples.",
                'priority': 'medium',
                'category': 'documentation',
                'impact': 'medium'
            })

        if not analysis.get('has_consistent_naming', True):
            improvements.append({
                'id': 'folder-naming-consistency',
                'title': 'Improve Naming Consistency',
                'description': "Folder contains inconsistent naming patterns. Consider standardizing request names.",
                'priority': 'low',
                'category': 'organization',
                'impact': 'low'
            })

        if not analysis.get('auth_consistency', True):
            improvements.append({
                'id': 'folder-auth-consistency',
                'title': 'Standardize Authentication',
                'description': "Inconsistent authentication methods across requests in this folder.",
                'priority': 'medium',
                'category': 'security',
                'impact': 'medium'
            })

        # Count specific issues in requests
        issue_counts = {}
        for request in analysis.get('requests', []):
            for issue in request.get('issues', []):
                issue_type = issue.get('message', '')
                issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1

        # Generate improvements for common issues in this folder
        if issue_counts.get('Request lacks test scripts', 0) > 0:
            improvements.append({
                'id': 'folder-add-tests',
                'title': 'Add Test Scripts',
                'description': f"Found {issue_counts['Request lacks test scripts']} requests in this folder without test scripts.",
                'priority': 'medium',
                'category': 'testing',
                'impact': 'medium'
            })

        return improvements

    def generate_request_improvements(self, analysis: Dict) -> List[Dict]:
        """Generate improvement suggestions for a specific request."""
        improvements = []

        # Request-level improvements based on analysis
        if analysis.get('security_score', 100) < 70:
            improvements.append({
                'id': 'request-security',
                'title': 'Improve Request Security',
                'description': f"Security score is {analysis.get('security_score', 0)}/100. Review authentication and data handling.",
                'priority': 'high',
                'category': 'security',
                'impact': 'high'
            })

        if analysis.get('performance_score', 100) < 70:
            improvements.append({
                'id': 'request-performance',
                'title': 'Optimize Request Performance',
                'description': f"Performance score is {analysis.get('performance_score', 0)}/100. Review request structure and size.",
                'priority': 'medium',
                'category': 'performance',
                'impact': 'medium'
            })

        if not analysis.get('has_description', True):
            improvements.append({
                'id': 'request-add-description',
                'title': 'Add Request Description',
                'description': "Request lacks a description. Add documentation to explain its purpose.",
                'priority': 'low',
                'category': 'documentation',
                'impact': 'low'
            })

        if not analysis.get('has_auth', True):
            improvements.append({
                'id': 'request-add-auth',
                'title': 'Add Authentication',
                'description': "Request lacks authentication. Consider adding appropriate auth method.",
                'priority': 'high',
                'category': 'security',
                'impact': 'high'
            })

        if not analysis.get('has_tests', True):
            improvements.append({
                'id': 'request-add-tests',
                'title': 'Add Test Scripts',
                'description': "Request lacks test scripts. Add tests to validate responses.",
                'priority': 'medium',
                'category': 'testing',
                'impact': 'medium'
            })

        if analysis.get('has_hardcoded_url', False):
            improvements.append({
                'id': 'request-use-variables',
                'title': 'Use Environment Variables',
                'description': "Request contains hardcoded URLs. Use environment variables for better maintainability.",
                'priority': 'high',
                'category': 'maintainability',
                'impact': 'high'
            })

        if analysis.get('has_hardcoded_data', False):
            improvements.append({
                'id': 'request-parameterize-data',
                'title': 'Parameterize Request Data',
                'description': "Request contains hardcoded data. Consider using variables or dynamic values.",
                'priority': 'medium',
                'category': 'maintainability',
                'impact': 'medium'
            })

        if not analysis.get('has_proper_headers', True):
            improvements.append({
                'id': 'request-fix-headers',
                'title': 'Fix Request Headers',
                'description': "Request headers may be missing or incorrect. Review and add appropriate headers.",
                'priority': 'medium',
                'category': 'correctness',
                'impact': 'medium'
            })

        if not analysis.get('follows_naming_convention', True):
            improvements.append({
                'id': 'request-naming-convention',
                'title': 'Follow Naming Convention',
                'description': "Request name doesn't follow standard conventions. Consider renaming for consistency.",
                'priority': 'low',
                'category': 'organization',
                'impact': 'low'
            })

        return improvements

    # =================================================================
    # FINDER METHODS
    # =================================================================

    def find_folders_by_path(self, items: List[Dict], path: str) -> List[Dict]:
        """Find folders by path (supports nested paths like 'API/Users')."""
        path_parts = [part.strip() for part in path.split('/') if part.strip()]
        if not path_parts:
            return items

        results = []

        def find_in_items(current_items: List[Dict], current_path: List[str], depth: int = 0):
            if depth >= len(current_path):
                results.extend(current_items)
                return

            target_name = current_path[depth]
            for item in current_items:
                if (item.get('name', '').lower() == target_name.lower() or
                        target_name.lower() in item.get('name', '').lower()) and item.get('item'):
                    if depth == len(current_path) - 1:
                        # This is the target folder
                        results.append(item)
                    else:
                        # Continue searching in subfolders
                        find_in_items(item['item'], current_path, depth + 1)

        find_in_items(items, path_parts)
        return results

    def find_request_by_path(self, items: List[Dict], request_path: str) -> Optional[Dict]:
        """Find a request by its path."""
        path_parts = [part.strip() for part in request_path.split('/') if part.strip()]
        if not path_parts:
            return None

        current_items = items

        # Navigate through folders to the request
        for i, part in enumerate(path_parts):
            found = False
            for item in current_items:
                if item.get('name', '').lower() == part.lower():
                    if i == len(path_parts) - 1:
                        # This should be the request
                        if item.get('request'):
                            return item
                        else:
                            return None
                    else:
                        # This should be a folder
                        if item.get('item'):
                            current_items = item['item']
                            found = True
                            break
                        else:
                            return None

            if not found:
                return None

        return None

    def remove_folder_by_path(self, items: List[Dict], folder_path: str) -> bool:
        """Remove a folder by its path."""
        path_parts = [part.strip() for part in folder_path.split('/') if part.strip()]
        if not path_parts:
            return False

        if len(path_parts) == 1:
            # Remove from current level
            for i, item in enumerate(items):
                if item.get('name', '').lower() == path_parts[0].lower() and item.get('item') is not None:
                    del items[i]
                    return True
            return False
        else:
            # Navigate to parent folder
            parent_path = '/'.join(path_parts[:-1])
            parent_folders = self.find_folders_by_path(items, parent_path)
            if parent_folders:
                return self.remove_folder_by_path(parent_folders[0]['item'], path_parts[-1])
            return False

    def remove_request_by_path(self, items: List[Dict], request_path: str) -> bool:
        """Remove a request by its path."""
        path_parts = [part.strip() for part in request_path.split('/') if part.strip()]
        if not path_parts:
            return False

        if len(path_parts) == 1:
            # Remove from current level
            for i, item in enumerate(items):
                if item.get('name', '').lower() == path_parts[0].lower() and item.get('request'):
                    del items[i]
                    return True
            return False
        else:
            # Navigate to parent folder
            parent_path = '/'.join(path_parts[:-1])
            parent_folders = self.find_folders_by_path(items, parent_path)
            if parent_folders:
                return self.remove_request_by_path(parent_folders[0]['item'], path_parts[-1])
            return False

    def remove_item_ids(self, items: List[Dict]):
        """Remove IDs from items recursively for duplication."""
        for item in items:
            if 'id' in item:
                del item['id']
            if item.get('item'):
                self.remove_item_ids(item['item'])
