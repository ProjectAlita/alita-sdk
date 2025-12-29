import json
import logging
import re
from urllib.parse import urlencode
from typing import Annotated, Any, Callable, Optional
import copy

import yaml
from langchain_core.tools import ToolException
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PrivateAttr, create_model
from requests_openapi import Client, Operation

from ..elitea_base import BaseToolApiWrapper
from ..utils import clean_string


def _coerce_empty_string_to_none(v: Any) -> Any:
    """Convert empty strings to None for optional fields.
	
	This handles UI/pipeline inputs where empty fields are sent as '' instead of null.
	"""
    if v == '':
        return None
    return v


def _coerce_headers_value(v: Any) -> Optional[dict]:
    """Convert headers value to dict, handling empty strings and JSON strings.
	
	This handles UI/pipeline inputs where:
	- Empty fields are sent as '' instead of null
	- Dict values may be sent as JSON strings like '{}'
	"""
    if v is None or v == '':
        return None
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            # Intentionally ignore JSON decode errors - fall back to returning
            # the original value which will be validated later in _execute
            pass
    # Return as-is, will be validated later in _execute
    return v


logger = logging.getLogger(__name__)


# Base class for dynamically created parameter models
# Supports populate_by_name so both alias (original param name) and field name (sanitized) work
class _BaseParamsModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


def _sanitize_param_name(name: str) -> str:
    """Sanitize OpenAPI parameter names for use as Python/Pydantic identifiers.

	Pydantic's create_model requires valid Python identifiers as field names.
	This function handles:
	- Dots in names (e.g., 'searchCriteria.minTime' -> 'searchCriteria_minTime')
	- Dollar sign prefix (e.g., '$top' -> 'dollar_top')
	- Other special characters

	Returns the sanitized name suitable for use as a Pydantic field name.
	"""
    if not name:
        return name

    sanitized = name
    # Replace dots with underscores
    sanitized = sanitized.replace('.', '_')
    # Handle $ prefix (common in OData APIs like Azure DevOps)
    if sanitized.startswith('$'):
        sanitized = 'dollar_' + sanitized[1:]
    # Replace any remaining invalid characters with underscores
    # Python identifiers: [a-zA-Z_][a-zA-Z0-9_]*
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', sanitized)
    # Ensure it doesn't start with a digit
    if sanitized and sanitized[0].isdigit():
        sanitized = '_' + sanitized

    return sanitized


def _raise_openapi_tool_exception(
        *,
        code: str,
        message: str,
        operation_id: Optional[str] = None,
        url: Optional[str] = None,
        retryable: Optional[bool] = None,
        missing_inputs: Optional[list[str]] = None,
        http_status: Optional[int] = None,
        http_body_preview: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
) -> None:
    payload: dict[str, Any] = {
        "tool": "openapi",
        "code": code,
        "message": message,
    }
    if operation_id:
        payload["operation_id"] = operation_id
    if url:
        payload["url"] = url
    if retryable is not None:
        payload["retryable"] = bool(retryable)
    if missing_inputs:
        payload["missing_inputs"] = list(missing_inputs)
    if http_status is not None:
        payload["http_status"] = int(http_status)
    if http_body_preview:
        payload["http_body_preview"] = str(http_body_preview)
    if details:
        payload["details"] = details

    try:
        details_json = json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception:
        details_json = str(payload)

    raise ToolException(f"{message}\n\nToolError:\n{details_json}")


def _truncate(text: Any, max_len: int) -> str:
    if text is None:
        return ""
    s = str(text)
    if len(s) <= max_len:
        return s
    return s[:max_len] + "…"


def _is_retryable_http_status(status_code: Optional[int]) -> bool:
    if status_code is None:
        return False
    return int(status_code) in (408, 425, 429, 500, 502, 503, 504)


def _resolve_server_variables(url: str, variables: Optional[dict]) -> tuple[str, list[str]]:
    """
    Substitute server variables in URL with their default values.
    
    Per OpenAPI 3.x spec, server URLs can contain variables like:
    https://dev.azure.com/{organization}/{project}
    
    The variables object provides default values:
    {
        "organization": {"default": "MyOrg"},
        "project": {"default": "MyProject"}
    }
    
    Args:
        url: Server URL potentially containing {variable} placeholders
        variables: Dict of variable definitions with 'default' values
    
    Returns:
        Tuple of (resolved_url, list of variable names that could not be resolved)
    """
    if not url:
        return url, []
    
    result = url
    missing_defaults: list[str] = []
    
    if variables and isinstance(variables, dict):
        for var_name, var_def in variables.items():
            placeholder = '{' + str(var_name) + '}'
            if placeholder not in result:
                continue  # Variable not used in URL
            
            if not isinstance(var_def, dict):
                missing_defaults.append(var_name)
                continue
            
            default_value = var_def.get('default')
            if default_value is not None:
                result = result.replace(placeholder, str(default_value))
            else:
                # Variable defined but no default provided
                missing_defaults.append(var_name)
    
    # Check for any remaining {variable} placeholders that weren't in the variables dict
    # This catches cases where the URL has placeholders but no variables definition
    remaining_placeholders = re.findall(r'\{([^}]+)\}', result)
    for placeholder_name in remaining_placeholders:
        if placeholder_name not in missing_defaults:
            missing_defaults.append(placeholder_name)
    
    return result, missing_defaults


def _get_base_url_from_spec(spec: dict) -> str:
    """
    Extract base URL from OpenAPI spec's servers array.
    
    Handles server variables by substituting their default values.
    For example:
        url: "https://dev.azure.com/{organization}/{project}"
        variables:
            organization: {default: "MyOrg"}
            project: {default: "MyProject"}
    
    Returns: "https://dev.azure.com/MyOrg/MyProject"
    
    Note: Unresolved variables are logged but not raised here - this function
    is used for display/debugging purposes. The main validation happens in
    _resolve_server_variables_in_spec() during initialization.
    """
    servers = spec.get("servers") if isinstance(spec, dict) else None
    if isinstance(servers, list) and servers:
        first = servers[0]
        if isinstance(first, dict) and isinstance(first.get("url"), str):
            url = first["url"].strip()
            variables = first.get("variables")
            resolved_url, _ = _resolve_server_variables(url, variables)
            return resolved_url
    return ""


def _is_absolute_url(url: str) -> bool:
    return isinstance(url, str) and (url.startswith("http://") or url.startswith("https://"))


def _resolve_server_variables_in_spec(spec: dict) -> dict:
    """
    Resolve server variables in the OpenAPI spec by substituting their default values.
    
    This modifies the spec's servers[].url to replace {variable} placeholders with
    the default values from servers[].variables. This is necessary because the
    requests_openapi library doesn't handle server variables - it uses the raw URL.
    
    Example transformation:
        url: "https://dev.azure.com/{organization}/{project}"
        variables:
            organization: {default: "MyOrg"}
            project: {default: "MyProject"}
    
    Becomes:
        url: "https://dev.azure.com/MyOrg/MyProject"
    
    Args:
        spec: OpenAPI specification dict
    
    Returns:
        The same spec dict with server URLs resolved (modified in place)
    
    Raises:
        ToolException: If server URL contains variables without default values.
            Per OpenAPI spec, variables without defaults must be provided by the client,
            but this toolkit doesn't support runtime server variable input.
    """
    if not isinstance(spec, dict):
        return spec
    
    servers = spec.get("servers")
    if not isinstance(servers, list):
        return spec
    
    for i, server in enumerate(servers):
        if not isinstance(server, dict):
            continue
        url = server.get("url")
        if not isinstance(url, str):
            continue
        variables = server.get("variables")
        
        resolved_url, missing_vars = _resolve_server_variables(url, variables)
        
        if missing_vars:
            # Build example snippets showing how to fix the spec
            # Generate variable examples based on actual missing variable names
            yaml_vars = '\n'.join(f'      {v}:\n        default: "your_{v}_value"' for v in missing_vars)
            json_vars = ', '.join(f'"{v}": {{"default": "your_{v}_value"}}' for v in missing_vars)
            
            var_list = ', '.join(f'"{v}"' for v in missing_vars)
            _raise_openapi_tool_exception(
                code="unresolved_server_variables",
                message=(
                    f"Server URL contains variables without default values: {var_list}.\n\n"
                    f"The OpenAPI spec defines server URL:\n"
                    f"  {url}\n\n"
                    f"These variables must have default values. Update your OpenAPI spec as follows:\n\n"
                    f"YAML format:\n"
                    f"  servers:\n"
                    f"    - url: \"{url}\"\n"
                    f"      variables:\n"
                    f"{yaml_vars}\n\n"
                    f"JSON format:\n"
                    f"  {{\n"
                    f"    \"servers\": [{{\n"
                    f"      \"url\": \"{url}\",\n"
                    f"      \"variables\": {{ {json_vars} }}\n"
                    f"    }}]\n"
                    f"  }}"
                ),
                details={
                    "server_url": url,
                    "missing_variables": missing_vars,
                    "server_index": i,
                },
            )
        
        if resolved_url != url:
            server["url"] = resolved_url
            logger.debug(f"Resolved server URL: '{url}' -> '{resolved_url}'")
    
    return spec


def _apply_base_url_override(spec: dict, base_url_override: str) -> dict:
    """Normalize server URL when OpenAPI spec uses relative servers.

	Some public specs (including Petstore) use relative server URLs like "/api/v3".
	To execute requests against a real host, we can provide a base URL override like
	"https://petstore3.swagger.io" and convert the first server URL to an absolute URL.
	"""
    if not isinstance(spec, dict):
        return spec
    if not isinstance(base_url_override, str) or not base_url_override.strip():
        return spec
    base_url_override = base_url_override.strip().rstrip("/")

    servers = spec.get("servers")
    if not isinstance(servers, list) or not servers:
        spec["servers"] = [{"url": base_url_override}]
        return spec

    first = servers[0]
    if not isinstance(first, dict):
        return spec
    server_url = first.get("url")
    if not isinstance(server_url, str):
        return spec
    server_url = server_url.strip()
    if not server_url:
        first["url"] = base_url_override
        return spec
    if _is_absolute_url(server_url):
        return spec

    # Relative server URL ("/api/v3" or "api/v3") -> join with base host.
    if not server_url.startswith("/"):
        server_url = "/" + server_url
    first["url"] = base_url_override + server_url
    return spec


def _join_base_and_path(base_url: str, path: str) -> str:
    base = (base_url or "").rstrip("/")
    p = (path or "")
    if not p.startswith("/"):
        p = "/" + p
    if not base:
        return p
    return base + p


# Maximum length for generated operationIds (tool names)
_MAX_OPERATION_ID_LENGTH = 64

# Map HTTP methods to semantic action names for better readability
_METHOD_TO_ACTION = {
    'get': 'get',
    'post': 'create',
    'put': 'update',
    'patch': 'update',
    'delete': 'delete',
    'head': 'head',
    'options': 'options',
    'trace': 'trace',
}


def _generate_operation_id(method: str, path: str) -> str:
    """
    Generate an operationId from HTTP method and path when not provided in spec.
    
    Follows a pattern that produces readable, unique identifiers:
    - Format: {action}_{path_segments}
    - HTTP methods are mapped to semantic actions (POST→create, PUT/PATCH→update)
    - Path parameters ({id}) become "by_{param}"
    - Segments are joined with underscores
    - Result is snake_case
    - Truncated to _MAX_OPERATION_ID_LENGTH characters
    
    Examples:
        GET /users -> get_users
        GET /users/{id} -> get_users_by_id
        POST /users -> create_users
        PUT /users/{id} -> update_users_by_id
        PATCH /users/{id} -> update_users_by_id
        DELETE /api/v1/items/{itemId} -> delete_api_v1_items_by_itemId
    
    Args:
        method: HTTP method (GET, POST, etc.)
        path: URL path (e.g., /users/{id})
    
    Returns:
        Generated operationId string
    """
    # Map HTTP method to semantic action
    action = _METHOD_TO_ACTION.get(method.lower(), method.lower())
    
    # Split path and process segments
    segments = [s for s in path.split('/') if s]
    processed_segments = []
    
    for segment in segments:
        # Check if it's a path parameter like {id} or {userId}
        if segment.startswith('{') and segment.endswith('}'):
            param_name = segment[1:-1]  # Remove braces
            processed_segments.append(f'by_{param_name}')
        else:
            # Regular segment - keep as is (already suitable for identifier)
            # Replace any non-alphanumeric chars with underscore
            clean_segment = re.sub(r'[^a-zA-Z0-9]', '_', segment)
            if clean_segment:
                processed_segments.append(clean_segment)
    
    # Join: action_segment1_segment2_...
    if processed_segments:
        operation_id = f"{action}_{'_'.join(processed_segments)}"
    else:
        # Edge case: root path "/"
        operation_id = f"{action}_root"
    
    # Ensure valid Python identifier (no leading digits)
    if operation_id[0].isdigit():
        operation_id = '_' + operation_id
    
    # Truncate if too long
    if len(operation_id) > _MAX_OPERATION_ID_LENGTH:
        # Start with a hard cut at the max length
        truncated = operation_id[:_MAX_OPERATION_ID_LENGTH]
        # Prefer truncating at a word boundary (underscore) if possible
        last_underscore = truncated.rfind('_')
        if last_underscore > 0:
            truncated = truncated[:last_underscore]
        # Ensure we don't end with an underscore after truncation
        truncated = truncated.rstrip('_')
        operation_id = truncated
    
    return operation_id


def _ensure_operation_ids(spec: dict) -> dict:
    """
    Ensure all operations in the spec have operationIds.
    
    For operations missing operationId, generates one from method+path.
    Handles deduplication by appending _2, _3, etc. for collisions.
    
    Args:
        spec: Parsed OpenAPI specification dict
    
    Returns:
        The same spec dict with operationIds injected where missing
    """
    paths = spec.get('paths')
    if not isinstance(paths, dict):
        return spec
    
    # Track all operationIds (existing + generated) to handle collisions
    used_operation_ids: set[str] = set()
    
    # First pass: collect existing operationIds
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                continue
            # Skip non-operation keys like 'parameters', 'summary', etc.
            if method.lower() not in ('get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace'):
                continue
            existing_id = operation.get('operationId')
            if existing_id:
                used_operation_ids.add(str(existing_id))
    
    # Second pass: generate missing operationIds
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                continue
            # Skip non-operation keys
            if method.lower() not in ('get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace'):
                continue
            
            if operation.get('operationId'):
                continue  # Already has operationId
            
            # Generate operationId
            base_id = _generate_operation_id(method, path)
            
            # Handle collisions by appending suffix
            final_id = base_id
            counter = 2
            while final_id in used_operation_ids:
                suffix = f'_{counter}'
                # Ensure we don't exceed max length with suffix
                max_base_len = _MAX_OPERATION_ID_LENGTH - len(suffix)
                truncated_base = base_id[:max_base_len]
                final_id = f'{truncated_base}{suffix}'
                counter += 1
            
            operation['operationId'] = final_id
            used_operation_ids.add(final_id)
            logger.debug(f"Generated operationId '{final_id}' for {method.upper()} {path}")
    
    return spec


def _parse_openapi_spec(spec: str | dict) -> dict:
    if isinstance(spec, dict):
        return spec
    if not isinstance(spec, str) or not spec.strip():
        _raise_openapi_tool_exception(code="missing_spec", message="OpenAPI spec is required")

    try:
        parsed = json.loads(spec)
    except json.JSONDecodeError:
        try:
            parsed = yaml.safe_load(spec)
        except yaml.YAMLError as e:
            _raise_openapi_tool_exception(
                code="invalid_spec",
                message=f"Failed to parse OpenAPI spec as JSON or YAML: {e}",
                details={"error": str(e)},
            )

    if not isinstance(parsed, dict):
        _raise_openapi_tool_exception(code="invalid_spec", message="OpenAPI spec must parse to an object")
    return parsed


def _guess_python_type(openapi_schema: dict | None) -> type:
    schema_type = (openapi_schema or {}).get("type")
    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return bool
    # arrays/objects are left as string for now (simple start)
    return str


def _schema_type_hint(openapi_schema: dict | None) -> str:
    if not isinstance(openapi_schema, dict):
        return ""
    type_ = openapi_schema.get("type")
    fmt = openapi_schema.get("format")
    if not type_:
        return ""
    if fmt:
        return f"{type_} ({fmt})"
    return str(type_)


def _extract_request_body_example(spec: Optional[dict], op_raw: dict) -> Optional[str]:
    request_body = op_raw.get("requestBody") or {}
    content = request_body.get("content") or {}
    for media_type in ("application/json", "application/*+json"):
        mt = content.get(media_type)
        if not isinstance(mt, dict):
            continue

        if "example" in mt:
            try:
                return json.dumps(mt["example"], indent=2)
            except Exception:
                return str(mt["example"])

        examples = mt.get("examples")
        if isinstance(examples, dict) and examples:
            first = next(iter(examples.values()))
            if isinstance(first, dict) and "value" in first:
                try:
                    return json.dumps(first["value"], indent=2)
                except Exception:
                    return str(first["value"])

        schema = mt.get("schema")
        if isinstance(schema, dict) and "example" in schema:
            try:
                return json.dumps(schema["example"], indent=2)
            except Exception:
                return str(schema["example"])

        # No explicit example found; fall back to schema-based template.
        if isinstance(schema, dict):
            template_obj = _schema_to_template_json(
                spec=spec,
                schema=schema,
                max_depth=3,
                max_properties=20,
            )
            if template_obj is not None:
                try:
                    return json.dumps(template_obj, indent=2)
                except Exception:
                    return str(template_obj)
    return None


def _schema_to_template_json(
        spec: Any,
        schema: dict,
        max_depth: int,
        max_properties: int,
) -> Any:
    """Build a schema-shaped JSON template from an OpenAPI/JSONSchema fragment.

	This is a best-effort helper intended for LLM prompting. It avoids infinite recursion
	(via depth and $ref cycle checks) and prefers enum/default/example when available.
	"""
    visited_refs: set[str] = set()
    return _schema_node_to_value(
        spec=spec if isinstance(spec, dict) else None,
        node=schema,
        depth=0,
        max_depth=max_depth,
        max_properties=max_properties,
        visited_refs=visited_refs,
    )


def _schema_node_to_value(
        spec: Optional[dict],
        node: Any,
        depth: int,
        max_depth: int,
        max_properties: int,
        visited_refs: set[str],
) -> Any:
    if depth > max_depth:
        return "<...>"

    if not isinstance(node, dict):
        return "<value>"

    # Prefer explicit example/default/enum at this node.
    if "example" in node:
        return node.get("example")
    if "default" in node:
        return node.get("default")
    if isinstance(node.get("enum"), list) and node.get("enum"):
        return node.get("enum")[0]

    ref = node.get("$ref")
    if isinstance(ref, str):
        if ref in visited_refs:
            return "<ref-cycle>"
        visited_refs.add(ref)
        resolved = _resolve_ref(spec, ref)
        if resolved is None:
            return "<ref>"
        return _schema_node_to_value(
            spec=spec,
            node=resolved,
            depth=depth + 1,
            max_depth=max_depth,
            max_properties=max_properties,
            visited_refs=visited_refs,
        )

    # Combinators
    for key in ("oneOf", "anyOf"):
        if isinstance(node.get(key), list) and node.get(key):
            return _schema_node_to_value(
                spec=spec,
                node=node.get(key)[0],
                depth=depth + 1,
                max_depth=max_depth,
                max_properties=max_properties,
                visited_refs=visited_refs,
            )

    if isinstance(node.get("allOf"), list) and node.get("allOf"):
        # Best-effort merge for objects.
        merged: dict = {"type": "object", "properties": {}, "required": []}
        for part in node.get("allOf"):
            part_resolved = _schema_node_to_value(
                spec=spec,
                node=part,
                depth=depth + 1,
                max_depth=max_depth,
                max_properties=max_properties,
                visited_refs=visited_refs,
            )
            # If a part produced an object template, merge keys.
            if isinstance(part_resolved, dict):
                for k, v in part_resolved.items():
                    merged.setdefault(k, v)
        return merged

    type_ = node.get("type")
    fmt = node.get("format")

    if type_ == "object" or (type_ is None and ("properties" in node or "additionalProperties" in node)):
        props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
        required = node.get("required") if isinstance(node.get("required"), list) else []

        out: dict[str, Any] = {}
        # Prefer required fields, then a small subset of optional fields for guidance.
        keys: list[str] = []
        for k in required:
            if isinstance(k, str) and k in props:
                keys.append(k)
        if not keys:
            keys = list(props.keys())[: min(3, len(props))]
        else:
            optional = [k for k in props.keys() if k not in keys]
            keys.extend(optional[: max(0, min(3, len(optional)))])

        keys = keys[:max_properties]
        for k in keys:
            out[k] = _schema_node_to_value(
                spec=spec,
                node=props.get(k),
                depth=depth + 1,
                max_depth=max_depth,
                max_properties=max_properties,
                visited_refs=visited_refs,
            )
        return out

    if type_ == "array":
        items = node.get("items")
        return [
            _schema_node_to_value(
                spec=spec,
                node=items,
                depth=depth + 1,
                max_depth=max_depth,
                max_properties=max_properties,
                visited_refs=visited_refs,
            )
        ]

    if type_ == "integer":
        return 0
    if type_ == "number":
        return 0.0
    if type_ == "boolean":
        return False
    if type_ == "string":
        if fmt == "date-time":
            return "2025-01-01T00:00:00Z"
        if fmt == "date":
            return "2025-01-01"
        if fmt == "uuid":
            return "00000000-0000-0000-0000-000000000000"
        return "<string>"

    # Unknown: return a placeholder
    return "<value>"


def _resolve_ref(spec: Optional[dict], ref: str) -> Optional[dict]:
    if not spec or not isinstance(ref, str):
        return None
    if not ref.startswith("#/"):
        return None
    # Only local refs supported for now.
    parts = ref.lstrip("#/").split("/")
    cur: Any = spec
    for part in parts:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    if isinstance(cur, dict):
        return cur
    return None


def _normalize_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except Exception:
            return value.decode("utf-8", errors="replace")
    return str(value)


class OpenApiApiWrapper(BaseToolApiWrapper):
    """Builds callable tool functions for OpenAPI operations and executes them."""

    spec: dict = Field(description="Parsed OpenAPI spec")
    base_headers: dict[str, str] = Field(default_factory=dict)

    _client: Client = PrivateAttr()
    _op_meta: dict[str, dict] = PrivateAttr(default_factory=dict)
    _tool_defs: list[dict[str, Any]] = PrivateAttr(default_factory=list)
    _tool_ref_by_name: dict[str, Callable[..., str]] = PrivateAttr(default_factory=dict)
    # Mapping: operation_id -> {sanitized_field_name: original_param_name}
    # Needed because LangChain passes kwargs using Pydantic field names (sanitized),
    # but the API expects original parameter names
    _param_name_mapping: dict[str, dict[str, str]] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        # Resolve server variables in spec URLs before loading
        # This handles specs like Azure DevOps that use {organization}/{project} placeholders
        _resolve_server_variables_in_spec(self.spec)
        
        # Build meta from raw spec (method/path/examples)
        op_meta: dict[str, dict] = {}
        paths = self.spec.get("paths") or {}
        if isinstance(paths, dict):
            for path, path_item in paths.items():
                if not isinstance(path_item, dict):
                    continue
                for method, op_raw in path_item.items():
                    if not isinstance(op_raw, dict):
                        continue
                    operation_id = op_raw.get("operationId")
                    if not operation_id:
                        continue
                    op_meta[str(operation_id)] = {
                        "method": str(method).upper(),
                        "path": str(path),
                        "raw": op_raw,
                    }

        client = Client()
        client.load_spec(self.spec)
        if self.base_headers:
            client.requestor.headers.update({str(k): str(v) for k, v in self.base_headers.items()})

        self._client = client
        self._op_meta = op_meta

        # Build tool definitions once.
        self._tool_defs = self._build_tool_defs()
        self._tool_ref_by_name = {t["name"]: t["ref"] for t in self._tool_defs if "ref" in t}

    def _build_tool_defs(self) -> list[dict[str, Any]]:
        tool_defs: list[dict[str, Any]] = []
        for operation_id, op in getattr(self._client, "operations", {}).items():
            if not isinstance(op, Operation):
                continue
            op_id = str(operation_id)
            meta = self._op_meta.get(op_id, {})
            op_raw = meta.get("raw") if isinstance(meta.get("raw"), dict) else {}

            method = meta.get("method")
            path = meta.get("path")

            title_line = ""
            if method and path:
                title_line = f"{method} {path}"

            summary = op.spec.summary or ""
            description = op.spec.description or ""
            tool_desc_parts = [p for p in [title_line, summary, description] if p]

            has_request_body = bool(op.spec.requestBody)
            usage_lines: list[str] = ["How to call:"]
            usage_lines.append("- Provide path/query parameters as named arguments.")
            if has_request_body:
                usage_lines.append("- For JSON request bodies, pass `body_json` as a JSON string.")
            usage_lines.append(
                "- Use `headers` only for per-call extra headers; base/toolkit headers (including auth) are already applied."
            )
            tool_desc_parts.append("\n".join(usage_lines))

            args_schema = self._create_args_schema(op_id, op, op_raw)
            ref = self._make_operation_callable(op_id)

            tool_defs.append(
                {
                    "name": op_id,
                    "description": "\n".join(tool_desc_parts).strip(),
                    "args_schema": args_schema,
                    "ref": ref,
                }
            )
        return tool_defs

    def _make_operation_callable(self, operation_id: str) -> Callable[..., str]:
        def _call_operation(*args: Any, **kwargs: Any) -> str:
            return self._execute(operation_id, *args, **kwargs)

        return _call_operation

    def _create_args_schema(self, operation_id: str, op: Operation, op_raw: dict) -> type[BaseModel]:
        fields: dict[str, tuple[Any, Any]] = {}
        # Track sanitized -> original name mapping for this operation
        name_mapping: dict[str, str] = {}

        # Parameters
        raw_params = op_raw.get("parameters") or []
        raw_param_map: dict[tuple[str, str], dict] = {}
        if isinstance(raw_params, list):
            for p in raw_params:
                if isinstance(p, dict) and p.get("name") and p.get("in"):
                    raw_param_map[(str(p.get("name")), str(p.get("in")))] = p

        for param in op.spec.parameters or []:
            param_name = str(param.name)
            # Sanitize parameter name for Pydantic field (handles dots, $ prefix, etc.)
            sanitized_name = _sanitize_param_name(param_name)
            # Track if we need alias (original name differs from sanitized)
            needs_alias = sanitized_name != param_name
            if needs_alias:
                # Store mapping for restoring original names in _execute
                name_mapping[sanitized_name] = param_name
                logger.debug(
                    f"Using alias for parameter '{param_name}' (field name: '{sanitized_name}') for operation '{operation_id}'")

            param_in_obj = getattr(param, "param_in", None)
            # requests_openapi uses an enum-like value for `param_in`.
            # For prompt quality and stable matching against raw spec, normalize to e.g. "query".
            if hasattr(param_in_obj, "value"):
                param_in = str(getattr(param_in_obj, "value"))
            else:
                param_in = str(param_in_obj)
            raw_param = raw_param_map.get((param_name, param_in), {})

            required = bool(raw_param.get("required", False))
            schema = raw_param.get("schema") if isinstance(raw_param.get("schema"), dict) else None
            py_type = _guess_python_type(schema)

            example = raw_param.get("example")
            if example is None and isinstance(schema, dict):
                example = schema.get("example")

            default = getattr(param.param_schema, "default", None)
            # Build description
            desc = (param.description or "").strip()
            desc = f"({param_in}) {desc}".strip()
            type_hint = _schema_type_hint(schema)
            if type_hint:
                desc = f"{desc}\nType: {type_hint}".strip()
            if required:
                desc = f"{desc}\nRequired: true".strip()
            if example is not None:
                desc = f"{desc}\nExample: {example}".strip()
            if default is not None:
                desc = f"{desc}\nDefault: {default}".strip()

            # Build Field kwargs - use alias if name was sanitized so schema shows original name
            field_kwargs = {"description": desc}
            if needs_alias:
                # Use alias so JSON schema shows original param name (e.g., "$top", "searchCriteria.status")
                # and Pydantic accepts input using original name
                field_kwargs["alias"] = param_name

            # Required fields have no default. Use sanitized name for field.
            if required:
                fields[sanitized_name] = (py_type, Field(**field_kwargs))
            else:
                field_kwargs["default"] = default
                fields[sanitized_name] = (Optional[py_type], Field(**field_kwargs))

        # Additional headers not modeled in spec
        # Use Annotated with BeforeValidator to coerce empty strings and JSON strings to dict
        fields["headers"] = (
            Annotated[Optional[dict], BeforeValidator(_coerce_headers_value)],
            Field(
                default_factory=dict,
                description=(
                    "Additional HTTP headers to include in this request. "
                    "These are merged with the toolkit/base headers (including auth headers). "
                    "Only add headers if the API requires them. "
                    "Provide a JSON object/dict. Example: {\"X-Trace-Id\": \"123\"}"
                ),
            ),
        )

        # Request body
        request_body = op_raw.get("requestBody") if isinstance(op_raw.get("requestBody"), dict) else None
        body_required = bool((request_body or {}).get("required", False))
        body_example = _extract_request_body_example(self.spec, op_raw)
        body_desc = (
            "Request body (JSON) as a string. The tool will parse it with json.loads and send as the request JSON body."
        )
        if body_example:
            body_desc = f"{body_desc}\nExample JSON:\n{body_example}"
        if op.spec.requestBody:
            if body_required:
                fields["body_json"] = (str, Field(description=body_desc))
            else:
                # Use BeforeValidator to coerce empty strings to None for optional body_json
                fields["body_json"] = (
                    Annotated[Optional[str], BeforeValidator(_coerce_empty_string_to_none)],
                    Field(default=None, description=body_desc),
                )

        model_name = f"OpenApi_{clean_string(operation_id, max_length=40) or 'Operation'}_Params"

        # Store the mapping for this operation (needed to restore original names in _execute)
        if name_mapping:
            self._param_name_mapping[operation_id] = name_mapping

        return create_model(
            model_name,
            __base__=_BaseParamsModel,
            # Use BeforeValidator to coerce empty strings to None for optional regexp
            regexp=(
                Annotated[Optional[str], BeforeValidator(_coerce_empty_string_to_none)],
                Field(
                    description="Regular expression to remove from the final output (optional)",
                    default=None,
                ),
            ),
            **fields,
        )

    def get_available_tools(self, selected_tools: Optional[list[str]] = None) -> list[dict[str, Any]]:
        if not selected_tools:
            return list(self._tool_defs)
        selected_set = {t for t in selected_tools if isinstance(t, str) and t}
        return [t for t in self._tool_defs if t.get("name") in selected_set]

    def run(self, mode: str, *args: Any, **kwargs: Any) -> str:
        try:
            ref = self._tool_ref_by_name[mode]
        except KeyError:
            _raise_openapi_tool_exception(
                code="unknown_operation",
                message=f"Unknown operation: {mode}",
                details={"known_operations": sorted(list(self._tool_ref_by_name.keys()))[:200]},
            )
        return ref(*args, **kwargs)

    def _get_required_inputs_from_raw_spec(self, operation_id: str) -> dict[str, Any]:
        meta = self._op_meta.get(str(operation_id), {})
        op_raw = meta.get("raw") if isinstance(meta, dict) and isinstance(meta.get("raw"), dict) else {}

        required_path: list[str] = []
        required_query: list[str] = []
        raw_params = op_raw.get("parameters")
        if isinstance(raw_params, list):
            for p in raw_params:
                if not isinstance(p, dict):
                    continue
                name = p.get("name")
                where = p.get("in")
                required = bool(p.get("required", False))
                if not required or not isinstance(name, str) or not isinstance(where, str):
                    continue
                if where == "path":
                    required_path.append(name)
                elif where == "query":
                    required_query.append(name)

        req_body = False
        rb = op_raw.get("requestBody")
        if isinstance(rb, dict):
            req_body = bool(rb.get("required", False))

        return {
            "required_path": required_path,
            "required_query": required_query,
            "required_body": req_body,
        }

    def get_operation_request_url(self, operation_id: str, params: dict[str, Any]) -> str:
        """Best-effort resolved URL for debugging/prompt-quality inspection.

		This does not execute the request.
		"""
        meta = self._op_meta.get(str(operation_id), {})
        path = meta.get("path") if isinstance(meta, dict) else None
        if not isinstance(path, str):
            return ""
        base_url = _get_base_url_from_spec(self.spec)
        url = _join_base_and_path(base_url, path)

        # Substitute {pathParams}
        for k, v in (params or {}).items():
            placeholder = "{" + str(k) + "}"
            if placeholder in url:
                url = url.replace(placeholder, str(v))

        # Add query params if present.
        query: dict[str, Any] = {}
        try:
            op = self._client.operations[str(operation_id)]
            if isinstance(op, Operation):
                for p in op.spec.parameters or []:
                    p_in_obj = getattr(p, "param_in", None)
                    p_in = str(getattr(p_in_obj, "value", p_in_obj))
                    if p_in != "query":
                        continue
                    name = str(p.name)
                    if name in (params or {}) and (params or {}).get(name) is not None:
                        query[name] = (params or {})[name]
        except Exception:
            query = {}

        if query:
            url = url + "?" + urlencode(query, doseq=True)
        return url

    def _execute(self, operation_id: str, *args: Any, **kwargs: Any) -> str:
        # Extract special fields (already coerced by BeforeValidator at validation time)
        regexp = kwargs.pop("regexp", None)
        extra_headers = kwargs.pop("headers", None)

        # Restore original parameter names from sanitized field names
        # LangChain passes kwargs using Pydantic field names (sanitized like 'dollar_top'),
        # but the API expects original parameter names (like '$top')
        name_mapping = self._param_name_mapping.get(operation_id, {})
        if name_mapping:
            restored_kwargs: dict[str, Any] = {}
            for key, value in kwargs.items():
                original_name = name_mapping.get(key, key)
                restored_kwargs[original_name] = value
            kwargs = restored_kwargs

        # Validate headers type (should be dict or None after BeforeValidator coercion)
        if extra_headers is not None and not isinstance(extra_headers, dict):
            _raise_openapi_tool_exception(
                code="invalid_headers",
                message="'headers' must be a dict or valid JSON object string",
                operation_id=str(operation_id),
                details={"provided_type": str(type(extra_headers)), "provided_value": str(extra_headers)[:100]},
            )

        # Handle body_json (already coerced to None for empty strings by BeforeValidator)
        body_json = kwargs.pop("body_json", None)
        if body_json is not None:
            if isinstance(body_json, str):
                try:
                    kwargs["json"] = json.loads(body_json)
                except Exception as e:
                    _raise_openapi_tool_exception(
                        code="invalid_json_body",
                        message=f"Invalid JSON body: {e}",
                        operation_id=str(operation_id),
                        details={"hint": "Ensure body_json is valid JSON (double quotes, no trailing commas)."},
                    )
            else:
                kwargs["json"] = body_json

        # Backward compatible: accept `json` as a string too.
        if "json" in kwargs and isinstance(kwargs.get("json"), str):
            try:
                kwargs["json"] = json.loads(kwargs["json"])
            except Exception as e:
                _raise_openapi_tool_exception(
                    code="invalid_json_body",
                    message=f"Invalid JSON body: {e}",
                    operation_id=str(operation_id),
                    details={"hint": "If you pass `json` as a string, it must be valid JSON."},
                )

        try:
            op = self._client.operations[operation_id]
        except Exception:
            _raise_openapi_tool_exception(
                code="operation_not_found",
                message=f"Operation '{operation_id}' not found in OpenAPI spec",
                operation_id=str(operation_id),
            )
        if not isinstance(op, Operation):
            _raise_openapi_tool_exception(
                code="invalid_operation",
                message=f"Operation '{operation_id}' is not a valid OpenAPI operation",
                operation_id=str(operation_id),
            )

        # Best-effort URL reconstruction for error context.
        debug_url = ""
        try:
            debug_url = self.get_operation_request_url(operation_id, dict(kwargs))
        except Exception:
            debug_url = ""

        # Preflight required input checks (helps LLM recover without needing spec knowledge).
        missing: list[str] = []
        required_info = self._get_required_inputs_from_raw_spec(str(operation_id))
        for name in required_info.get("required_path", []) or []:
            if name not in kwargs or kwargs.get(name) is None:
                missing.append(name)
        for name in required_info.get("required_query", []) or []:
            if name not in kwargs or kwargs.get(name) is None:
                missing.append(name)
        if bool(required_info.get("required_body")) and kwargs.get("json") is None:
            missing.append("body_json")

        # Also check for unresolved {param} placeholders in the path.
        meta = self._op_meta.get(str(operation_id), {})
        path = meta.get("path") if isinstance(meta, dict) else None
        if isinstance(path, str):
            for placeholder in re.findall(r"\{([^}]+)\}", path):
                if placeholder and (placeholder not in kwargs or kwargs.get(placeholder) is None):
                    missing.append(str(placeholder))

        if missing:
            _raise_openapi_tool_exception(
                code="missing_required_inputs",
                message=f"Missing required inputs for operation '{operation_id}': {', '.join(sorted(set(missing)))}",
                operation_id=str(operation_id),
                url=debug_url or None,
                retryable=True,
                missing_inputs=sorted(set(missing)),
                details={"hint": "Provide the missing fields and retry the same operation."},
            )

        # Preflight base URL check: requests_openapi needs an absolute server URL to execute HTTP.
        base_url = _get_base_url_from_spec(self.spec)
        if not base_url or not _is_absolute_url(base_url):
            servers = self.spec.get("servers") if isinstance(self.spec, dict) else None
            server_url = None
            if isinstance(servers, list) and servers and isinstance(servers[0], dict):
                server_url = servers[0].get("url")

            _raise_openapi_tool_exception(
                code="missing_base_url",
                message=(
                    "Cannot execute HTTP request because the OpenAPI spec does not contain an absolute server URL. "
                    "Provide `base_url_override`/`base_url` in the toolkit settings (e.g. 'https://host') "
                    "or update `servers[0].url` to an absolute URL (https://...)."
                ),
                operation_id=str(operation_id),
                url=debug_url or None,
                retryable=False,
                details={
                    "servers_0_url": server_url,
                    "computed_base_url": base_url,
                    "hint": "If servers[0].url is relative like '/api/v3', set base_url_override to the host (e.g. 'https://petstore3.swagger.io').",
                },
            )

        # Apply per-call extra headers (best-effort) without permanently mutating global headers.
        old_headers = dict(getattr(self._client.requestor, "headers", {}) or {})
        try:
            if extra_headers:
                self._client.requestor.headers.update({str(k): str(v) for k, v in extra_headers.items()})
            response = op(*args, **kwargs)
        except Exception as e:
            _raise_openapi_tool_exception(
                code="request_failed",
                message=f"OpenAPI request failed for operation '{operation_id}': {e}",
                operation_id=str(operation_id),
                url=debug_url or None,
                retryable=True,
                details={"exception": repr(e)},
            )
        finally:
            try:
                self._client.requestor.headers.clear()
                self._client.requestor.headers.update(old_headers)
            except Exception:
                pass

        # If this looks like a requests.Response, raise on HTTP errors with actionable context.
        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int) and status_code >= 400:
            body_preview = ""
            for attr in ("text", "content", "data"):
                if hasattr(response, attr):
                    body_preview = _normalize_output(getattr(response, attr))
                    break
            body_preview = _truncate(body_preview, 2000)
            retryable = _is_retryable_http_status(status_code)

            hint = ""
            if status_code in (401, 403):
                hint = "Authentication/authorization failed. Verify toolkit authentication settings / base headers."
            elif status_code == 404:
                hint = "Resource not found. Check path parameters and identifiers."
            elif status_code == 400:
                hint = "Bad request. Check required parameters and request body schema."
            elif status_code == 415:
                hint = "Unsupported media type. The API may require Content-Type headers."
            elif status_code == 429:
                hint = "Rate limited. Retry after a short delay."

            _raise_openapi_tool_exception(
                code="http_error",
                message=f"OpenAPI request failed with HTTP {status_code} for operation '{operation_id}'",
                operation_id=str(operation_id),
                url=debug_url or None,
                retryable=retryable,
                http_status=status_code,
                http_body_preview=body_preview,
                details={"hint": hint} if hint else None,
            )

        output = None
        for attr in ("content", "data", "text"):
            if hasattr(response, attr):
                output = getattr(response, attr)
                break
        if output is None:
            output = response

        output_str = _normalize_output(output)

        if regexp:
            try:
                output_str = re.sub(rf"{regexp}", "", output_str)
            except Exception as e:
                logger.debug(f"Failed to apply regexp filter: {e}")

        return output_str


def build_wrapper(
        openapi_spec: str | dict,
        base_headers: Optional[dict[str, str]] = None,
        base_url_override: Optional[str] = None,
) -> OpenApiApiWrapper:
    parsed = _parse_openapi_spec(openapi_spec)
    # Avoid mutating caller-owned spec dict.
    spec = copy.deepcopy(parsed)
    if base_url_override:
        spec = _apply_base_url_override(spec, base_url_override)
    # Ensure all operations have operationIds (generate from method+path if missing)
    spec = _ensure_operation_ids(spec)
    return OpenApiApiWrapper(spec=spec, base_headers=base_headers or {})
