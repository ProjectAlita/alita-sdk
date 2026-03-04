"""
Shared Alita API clients and helpers for copy/link scripts.

Provides ENV_URLS, extract_list(), and AlitaAPI (apps, tools, configs, linking).
"""

from __future__ import annotations

import logging
import requests

log = logging.getLogger(__name__)

ENV_URLS: dict[str, str] = {
    "dev":   "https://dev.elitea.ai",
    "stage": "https://stage.elitea.ai",
    "next":  "https://next.elitea.ai",
}


def extract_list(data: dict | list) -> list:
    """Unwrap items from various API response wrapper formats."""
    if isinstance(data, list):
        return data
    for key in ("rows", "items", "data", "results", "applications"):
        val = data.get(key) if isinstance(data, dict) else None
        if isinstance(val, list):
            return val
    return []


class AlitaAPI:
    """Alita REST API: apps, tools, configs, and linking."""

    def __init__(self, base_url: str, project_id: int, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.project_id = project_id
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        })

    def _apps_url(self) -> str:
        return f"{self.base_url}/api/v2/elitea_core/applications/prompt_lib/{self.project_id}"

    def _app_url(self, app_id: int) -> str:
        return f"{self.base_url}/api/v2/elitea_core/application/prompt_lib/{self.project_id}/{app_id}"

    def _tools_url(self) -> str:
        return f"{self.base_url}/api/v2/elitea_core/tools/prompt_lib/{self.project_id}"

    def _tool_url(self, tool_id: int) -> str:
        return f"{self.base_url}/api/v2/elitea_core/tool/prompt_lib/{self.project_id}/{tool_id}"

    def _application_relation_url(self, app_id: int, version_id: int) -> str:
        return f"{self.base_url}/api/v2/elitea_core/application_relation/prompt_lib/{self.project_id}/{app_id}/{version_id}"

    def _configs_url(self) -> str:
        return f"{self.base_url}/api/v2/configurations/configurations/{self.project_id}"

    def _config_url(self, config_id: int) -> str:
        return f"{self.base_url}/api/v2/configurations/configuration/{self.project_id}/{config_id}"

    def list_apps(self) -> list[dict]:
        params = {"sort_by": "created_at", "sort_order": "desc", "limit": 100}
        resp = self.session.get(self._apps_url(), params=params, timeout=30)
        if resp.status_code != 200:
            log.warning("list_apps: GET %s -> %d", self._apps_url(), resp.status_code)
            return []
        return extract_list(resp.json())

    def get_app_details(self, app_id: int) -> dict | None:
        resp = self.session.get(self._app_url(app_id), timeout=30)
        if resp.status_code != 200:
            return None
        return resp.json()

    def create_app(self, payload: dict) -> dict:
        resp = self.session.post(self._apps_url(), json=payload, timeout=30)
        if resp.status_code == 201:
            return {"success": True, "data": resp.json()}
        return {"success": False, "status_code": resp.status_code, "error": resp.text}

    def delete_app(self, app_id: int) -> dict:
        resp = self.session.delete(self._app_url(app_id), timeout=30)
        if resp.status_code in (200, 204):
            return {"success": True}
        return {"success": False, "status_code": resp.status_code, "error": resp.text}

    def list_toolkits(self) -> list[dict]:
        params = {"limit": 100}
        resp = self.session.get(self._tools_url(), params=params, timeout=30)
        if resp.status_code != 200:
            log.warning("list_toolkits: GET %s -> %d", self._tools_url(), resp.status_code)
            return []
        return resp.json().get("rows") or []

    def list_mcp(self) -> list[dict]:
        """List MCP toolkits (same tools endpoint with mcp=true)."""
        params = {"sort_by": "created_at", "sort_order": "desc", "mcp": True, "limit": 100}
        resp = self.session.get(self._tools_url(), params=params, timeout=30)
        if resp.status_code != 200:
            log.warning("list_mcp: GET %s -> %d", self._tools_url(), resp.status_code)
            return []
        return resp.json().get("rows") or []

    def create_tool(self, payload: dict) -> dict:
        """Can be toolkit or mcp"""
        resp = self.session.post(self._tools_url(), json=payload, timeout=30)
        if resp.status_code in (200, 201):
            return {"success": True, "data": resp.json()}
        return {"success": False, "status_code": resp.status_code, "error": resp.text}

    def delete_tool(self, tool_id: int) -> dict:
        """Can be toolkit or mcp"""
        resp = self.session.delete(self._tool_url(tool_id), timeout=30)
        if resp.status_code in (200, 204):
            return {"success": True}
        return {"success": False, "status_code": resp.status_code, "error": resp.text}

    def list_configs(self) -> list[dict]:
        """Excluding shared configs"""
        params = {"limit": 100, "sort_order": "asc", "sort_by": "label"}
        resp = self.session.get(self._configs_url(), params=params, timeout=30)
        if resp.status_code != 200:
            log.warning("list_configs: GET %s -> %d", self._configs_url(), resp.status_code)
            return []
        return resp.json().get("items") or []

    def create_config(self, payload: dict) -> dict:
        resp = self.session.post(self._configs_url(), json=payload, timeout=30)
        if resp.status_code in (200, 201):
            return {"success": True, "data": resp.json()}
        return {"success": False, "status_code": resp.status_code, "error": resp.text}

    def delete_config(self, config_id: int) -> dict:
        resp = self.session.delete(self._config_url(config_id), timeout=30)
        if resp.status_code in (200, 204):
            return {"success": True}
        return {"success": False, "status_code": resp.status_code, "error": resp.text}

    def link_tool(self, tool_id: int, app_id: int, version_id: int) -> dict:
        """Can be toolkit or mcp"""
        payload = {
            "entity_id": app_id,
            "entity_version_id": version_id,
            "entity_type": "agent",
            "has_relation": True,
        }
        resp = self.session.patch(self._tool_url(tool_id), json=payload, timeout=30)
        if resp.status_code in (200, 201):
            return {"success": True, "data": resp.json()}
        return {"success": False, "status_code": resp.status_code, "error": resp.text}

    def link_app(
        self,
        parent_app_id: int,
        parent_version_id: int,
        nested_app_id: int,
        nested_version_id: int,
    ) -> dict:
        payload = {
            "application_id": parent_app_id,
            "version_id": parent_version_id,
            "has_relation": True,
        }
        resp = self.session.patch(
            self._application_relation_url(nested_app_id, nested_version_id),
            json=payload,
            timeout=30,
        )
        if resp.status_code in (200, 201):
            return {"success": True, "data": resp.json()}
        return {"success": False, "status_code": resp.status_code, "error": resp.text}
