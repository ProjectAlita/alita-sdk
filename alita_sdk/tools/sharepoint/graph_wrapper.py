"""SharePoint Microsoft Graph API wrapper — **delegated access only**.

This wrapper is instantiated exclusively when an OAuth *token* **and** *scopes*
are provided (i.e. a delegated user-context token obtained via the Azure AD
OAuth flow).  It communicates directly with
``https://graph.microsoft.com/v1.0`` using plain ``requests`` calls — the
*office365-rest-python-client* library is **not** used here.

Required OAuth scopes (delegated):
    ``Sites.ReadWrite.All``, ``Files.ReadWrite.All``, ``Lists.ReadWrite.All``
    (read-only variants also work for non-mutating operations)
"""
from __future__ import annotations

import base64
import logging
import re
from typing import Optional, List
from urllib.parse import quote

import requests
from langchain_core.tools import ToolException

from .base_wrapper import BaseSharepointWrapper

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_SMALL_FILE_THRESHOLD = 4 * 1024 * 1024   # 4 MB — simple PUT
_CHUNK_SIZE = 5 * 1024 * 1024             # 5 MB chunks for resumable upload


class SharepointGraphWrapper(BaseSharepointWrapper):
    """Graph-API-backed SharePoint wrapper for **delegated (user) access**.

    Args:
        site_url: Full SharePoint site URL, e.g.
                  ``https://contoso.sharepoint.com/sites/MyTeam``.
        token: Plain-text OAuth bearer token (delegated, user-context).
        scopes: List of OAuth scopes that were granted for this token.
                Stored for informational purposes; not used at runtime.
        alita: Optional Alita client for artifact resolution.
        llm: Optional LLM instance forwarded to the content parser.
    """

    def __init__(self, site_url: str, token: str, scopes: List[str],
                 alita=None, llm=None):
        self.site_url = site_url.rstrip('/')
        self._token = token
        self._scopes = scopes
        self.alita = alita
        self.llm = llm
        # Lazily resolved and cached
        self.__site_id: Optional[str] = None
        self.__drive_id: Optional[str] = None

    # ------------------------------------------------------------------ #
    #  Low-level HTTP helpers                                              #
    # ------------------------------------------------------------------ #

    def _auth_headers(self, content_type: str = "application/json") -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "Content-Type": content_type,
        }

    def _get(self, url: str, params: Optional[dict] = None) -> dict:
        resp = requests.get(url, headers=self._auth_headers(), params=params, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def _post(self, url: str, payload: dict) -> dict:
        resp = requests.post(url, headers=self._auth_headers(), json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def _delete(self, url: str) -> None:
        resp = requests.delete(url, headers=self._auth_headers(), timeout=30)
        resp.raise_for_status()

    # ------------------------------------------------------------------ #
    #  Site / Drive resolution (lazily cached)                            #
    # ------------------------------------------------------------------ #

    def _resolve_site_id(self) -> str:
        """Resolve and cache the Graph *site-id* for :attr:`site_url`."""
        if self.__site_id:
            return self.__site_id
        match = re.match(r'https?://([^/]+)(/.+)?', self.site_url)
        if not match:
            raise ToolException(f"Invalid site_url: {self.site_url}")
        hostname = match.group(1)
        site_path = (match.group(2) or '').strip('/')
        url = f"{_GRAPH_BASE}/sites/{hostname}:/{site_path}"
        data = self._get(url)
        self.__site_id = data['id']
        return self.__site_id

    def _resolve_drive_id(self) -> str:
        """Return the id of the site's default document library drive."""
        if self.__drive_id:
            return self.__drive_id
        data = self._get(f"{_GRAPH_BASE}/sites/{self._resolve_site_id()}/drive")
        self.__drive_id = data['id']
        return self.__drive_id

    def _resolve_list_id(self, list_title: str) -> str:
        """Resolve list display-name → Graph list id (case-insensitive)."""
        data = self._get(
            f"{_GRAPH_BASE}/sites/{self._resolve_site_id()}/lists",
            params={"$select": "id,displayName,name"})
        for lst in data.get('value', []):
            display = lst.get('displayName', lst.get('name', ''))
            if display.lower() == list_title.lower():
                return lst['id']
        raise ToolException(f"List '{list_title}' not found on site.")

    # ------------------------------------------------------------------ #
    #  Lists                                                               #
    # ------------------------------------------------------------------ #

    def read_list(self, list_title: str, limit: int = 1000):
        """Reads a specified List in sharepoint site. Number of list items is limited by limit (default is 1000)."""
        try:
            list_id = self._resolve_list_id(list_title)
            url = (f"{_GRAPH_BASE}/sites/{self._resolve_site_id()}/lists/"
                   f"{list_id}/items")
            params = {"$top": min(limit, 999), "$expand": "fields"}
            items: list = []
            next_link: Optional[str] = None
            while True:
                data = self._get(
                    next_link or url,
                    params=params if not next_link else None)
                for item in data.get('value', []):
                    items.append(item.get('fields', {}))
                    if len(items) >= limit:
                        return items
                next_link = data.get('@odata.nextLink')
                if not next_link:
                    break
            logging.info("%d items loaded from Graph API.", len(items))
            return items
        except ToolException:
            raise
        except Exception as e:
            logging.error("Graph read_list failed: %s", e)
            return ToolException(f"Cannot read list '{list_title}': {e}")

    def get_lists(self):
        """Returns all SharePoint lists available on the site with their titles, IDs, and descriptions."""
        try:
            data = self._get(
                f"{_GRAPH_BASE}/sites/{self._resolve_site_id()}/lists",
                params={"$select": "id,displayName,description,list,createdDateTime"})
            result = []
            for lst in data.get('value', []):
                list_info = lst.get('list', {})
                if list_info.get('hidden', False):
                    continue
                result.append({
                    'Title': lst.get('displayName', ''),
                    'Id': lst.get('id', ''),
                    'Description': lst.get('description', ''),
                    'ItemCount': list_info.get('itemCount', 0),
                    'BaseTemplate': list_info.get('template', ''),
                })
            return result
        except ToolException:
            raise
        except Exception as e:
            logging.error("Graph get_lists failed: %s", e)
            return ToolException(f"Cannot retrieve lists: {e}")

    def get_list_columns(self, list_title: str):
        """Get all columns (fields) in a SharePoint list with their metadata.

        Returns array of column objects with:
        - name: Internal field name
        - displayName: User-friendly name
        - columnType: text, number, boolean, dateTime, choice
        - required: Whether field is mandatory
        - choice: For choice fields, includes array of valid values

        Lookup columns are excluded from results.
        Use this tool before create_list_item() to discover available fields and validate inputs.
        """
        try:
            list_id = self._resolve_list_id(list_title)
            data = self._get(
                f"{_GRAPH_BASE}/sites/{self._resolve_site_id()}/lists/{list_id}/columns")
            result = []
            for col in data.get('value', []):
                if col.get('hidden', False) or col.get('readOnly', False):
                    continue
                if 'lookup' in col:
                    continue

                col_type = 'text'
                if 'text' in col:
                    col_type = 'text'
                elif 'number' in col or 'currency' in col:
                    col_type = 'number'
                elif 'boolean' in col:
                    col_type = 'boolean'
                elif 'dateTime' in col:
                    col_type = 'dateTime'
                elif 'choice' in col:
                    col_type = 'choice'

                column_info = {
                    'name': col.get('name', ''),
                    'displayName': col.get('displayName', col.get('name', '')),
                    'columnType': col_type,
                    'required': col.get('required', False),
                }
                if col_type == 'choice':
                    choices = col.get('choice', {}).get('choices', [])
                    if choices:
                        column_info['choice'] = {'choices': choices}
                result.append(column_info)
            return result
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Get list columns failed: {e}") from e

    def create_list_item(self, list_title: str, fields: dict):
        """Create a new item in a SharePoint list."""
        if not list_title:
            raise ToolException("list_title is required")
        if not fields or not isinstance(fields, dict):
            raise ToolException("fields must be a non-empty dictionary")
        try:
            list_id = self._resolve_list_id(list_title)
            url = (f"{_GRAPH_BASE}/sites/{self._resolve_site_id()}/lists/"
                   f"{list_id}/items")
            data = self._post(url, {"fields": fields})
            return {
                'id': data.get('id', ''),
                'fields': data.get('fields', {}),
                'webUrl': data.get('webUrl', ''),
            }
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Create list item failed: {e}") from e

    # ------------------------------------------------------------------ #
    #  Files                                                               #
    # ------------------------------------------------------------------ #

    def get_files_list(self, folder_name: Optional[str] = None,
                       limit_files: int = 100,
                       form_name: Optional[str] = None):
        """
        If folder name is specified, lists all files in this folder under Shared Documents path.
        If folder name is empty, lists all files under root catalog (Shared Documents).
        Number of files is limited by limit_files (default is 100).

        If form_name is specified, only files from specified form will be returned.
        Note:
            * URL anatomy: https://epam.sharepoint.com/sites/{some_site}/{form_name}/Forms/AllItems.aspx
            * Example of folders syntax: `{form_name} / Hello / inner-folder` - 1st folder is commonly form_name
        """
        try:
            drive_id = self._resolve_drive_id()
            if folder_name:
                encoded = quote(folder_name.strip('/'), safe='/')
                url = f"{_GRAPH_BASE}/drives/{drive_id}/root:/{encoded}:/children"
            else:
                url = f"{_GRAPH_BASE}/drives/{drive_id}/root/children"

            params = {
                "$top": min(limit_files, 999),
                "$select": ("id,name,file,folder,webUrl,createdDateTime,"
                             "lastModifiedDateTime,parentReference,size"),
            }
            result: list = []
            next_link: Optional[str] = None
            while len(result) < limit_files:
                data = self._get(
                    next_link or url,
                    params=params if not next_link else None)
                for item in data.get('value', []):
                    if 'file' not in item:
                        continue   # skip sub-folders
                    if form_name:
                        parent_path = (item.get('parentReference', {})
                                       .get('path', ''))
                        if form_name.lower() not in parent_path.lower():
                            continue
                    parent_path = item.get('parentReference', {}).get('path', '')
                    result.append({
                        'Name': item.get('name', ''),
                        'Path': f"{parent_path}/{item.get('name', '')}",
                        'Created': item.get('createdDateTime', ''),
                        'Modified': item.get('lastModifiedDateTime', ''),
                        'Link': item.get('webUrl', ''),
                        'id': item.get('id', ''),
                    })
                    if len(result) >= limit_files:
                        break
                next_link = data.get('@odata.nextLink')
                if not next_link:
                    break

            return result if result else ToolException(
                "Can not get files or folder is empty. "
                "Please, double check folder name and read permissions.")
        except ToolException:
            raise
        except Exception as e:
            logging.error("Graph get_files_list failed: %s", e)
            return ToolException(
                f"Can not get files. Please, double check folder name and "
                f"read permissions: {e}")

    def read_file(self, path: str, is_capture_image: bool = False,
                  page_number: Optional[int] = None, sheet_name: Optional[str] = None,
                  excel_by_sheets: bool = False):
        """Reads file located at the specified server-relative path."""
        from ..utils.content_parser import parse_file_content
        try:
            file_bytes = self.load_file_content_in_bytes(path)
            file_name = path.split('/')[-1]
            return parse_file_content(
                file_name=file_name,
                file_content=file_bytes,
                is_capture_image=is_capture_image,
                page_number=page_number,
                sheet_name=sheet_name,
                excel_by_sheets=excel_by_sheets,
                llm=self.llm,
            )
        except ToolException:
            raise
        except Exception as e:
            logging.error("Graph read_file failed (%s): %s", path, e)
            return ToolException(
                f"File not found. Please, check file name and path: {e}")

    def load_file_content_in_bytes(self, path: str) -> bytes:
        drive_id = self._resolve_drive_id()
        # Strip server-relative prefix so we get a drive-relative path
        # e.g. "/sites/MySite/Shared Documents/folder/file.txt" → "folder/file.txt"
        # We resolve the drive root path to strip it
        drive_data = self._get(f"{_GRAPH_BASE}/drives/{drive_id}/root")
        drive_root = drive_data.get('parentReference', {}).get('path', '')
        drive_name = drive_data.get('name', '')
        # Build drive-root prefix to strip (e.g. "/drives/<id>/root:/Shared Documents")
        relative = path.strip('/')
        # Try to match the drive path prefix from the site segments
        site_path = re.sub(r'^https?://[^/]+', '', self.site_url).strip('/')
        prefix_candidates = [
            f"{site_path}/{drive_name}",
            drive_name,
        ]
        for prefix in prefix_candidates:
            if relative.startswith(prefix):
                relative = relative[len(prefix):].lstrip('/')
                break

        encoded = quote(relative, safe='/')
        url = f"{_GRAPH_BASE}/drives/{drive_id}/root:/{encoded}:/content"
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=120,
            allow_redirects=True)
        resp.raise_for_status()
        return resp.content

    def upload_file(self, folder_path: str, filepath: Optional[str] = None,
                    filedata: Optional[str] = None, filename: Optional[str] = None,
                    replace: bool = True):
        """Upload file to SharePoint document library.

        Supports both artifact-based and direct content uploads. Files ≤4 MB use simple
        PUT, larger files use chunked upload sessions (5 MB chunks).

        Args:
            folder_path: Server-relative folder path
                         (e.g., '/sites/MySite/Shared Documents/folder')
            filepath: File path in format /{bucket}/{filename} from artifact storage
                      (mutually exclusive with filedata)
            filedata: String content to upload as a file
                      (mutually exclusive with filepath)
            filename: Target filename. Required with filedata, optional with filepath
            replace: If True, overwrite existing file. If False, raise error on conflict

        Returns:
            dict with {id, webUrl, path, size, mime_type}
        """
        from ..utils import get_file_bytes_from_artifact, detect_mime_type

        if not filepath and not filedata:
            raise ToolException("Either filepath or filedata must be provided")
        if filepath and filedata:
            raise ToolException("Cannot specify both filepath and filedata")
        if filedata and not filename:
            raise ToolException("filename is required when using filedata")

        if filepath:
            file_bytes, artifact_filename = get_file_bytes_from_artifact(self.alita, filepath)
            actual_filename = filename or artifact_filename
        else:
            file_bytes = filedata.encode('utf-8')
            actual_filename = filename

        mime_type = detect_mime_type(file_bytes, actual_filename)
        drive_id = self._resolve_drive_id()

        # Build a drive-relative item path from folder_path + filename
        site_path = re.sub(r'^https?://[^/]+', '', self.site_url).strip('/')
        folder_clean = folder_path.strip('/')
        # Strip site prefix if present
        if folder_clean.startswith(site_path):
            folder_clean = folder_clean[len(site_path):].lstrip('/')

        item_path = f"{folder_clean}/{actual_filename}".strip('/')
        safe_item_path = quote(item_path, safe='/')
        conflict = "replace" if replace else "fail"

        try:
            if len(file_bytes) <= _SMALL_FILE_THRESHOLD:
                # Simple PUT for small files
                url = (f"{_GRAPH_BASE}/drives/{drive_id}/root:/"
                       f"{safe_item_path}:/content"
                       f"?@microsoft.graph.conflictBehavior={conflict}")
                resp = requests.put(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Content-Type": mime_type,
                    },
                    data=file_bytes,
                    timeout=120)
                resp.raise_for_status()
                result = resp.json()
            else:
                # Resumable upload session for large files
                session_url = (f"{_GRAPH_BASE}/drives/{drive_id}/root:/"
                               f"{safe_item_path}:/createUploadSession")
                session = self._post(session_url, {
                    "item": {"@microsoft.graph.conflictBehavior": conflict}
                })
                upload_url = session.get('uploadUrl')
                if not upload_url:
                    raise RuntimeError("No uploadUrl returned in upload session response")

                total = len(file_bytes)
                offset = 0
                result = {}
                while offset < total:
                    chunk = file_bytes[offset: offset + _CHUNK_SIZE]
                    end = offset + len(chunk) - 1
                    chunk_resp = requests.put(
                        upload_url,
                        headers={
                            "Authorization": f"Bearer {self._token}",
                            "Content-Length": str(len(chunk)),
                            "Content-Range": f"bytes {offset}-{end}/{total}",
                            "Content-Type": "application/octet-stream",
                        },
                        data=chunk,
                        timeout=120)
                    chunk_resp.raise_for_status()
                    if chunk_resp.status_code in (200, 201):
                        result = chunk_resp.json()
                    offset += len(chunk)

            logging.info("Uploaded '%s' to '%s' via Graph API", actual_filename, folder_path)
            return {
                'id': result.get('id', ''),
                'webUrl': result.get('webUrl', ''),
                'path': (result.get('parentReference', {}).get('path', '')
                         + '/' + result.get('name', actual_filename)),
                'size': result.get('size', len(file_bytes)),
                'mime_type': result.get('file', {}).get('mimeType', mime_type),
            }
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Upload failed: {e}") from None

    def add_attachment_to_list_item(self, list_title: str, item_id: int,
                                    filepath: Optional[str] = None,
                                    filedata: Optional[str] = None,
                                    filename: Optional[str] = None,
                                    replace: bool = True):
        """Add attachment to SharePoint list item."""
        from ..utils import get_file_bytes_from_artifact

        if not filepath and not filedata:
            raise ToolException("Either filepath or filedata must be provided")
        if filepath and filedata:
            raise ToolException("Cannot specify both filepath and filedata")
        if filedata and not filename:
            raise ToolException("filename is required when using filedata")

        if filepath:
            file_bytes, artifact_filename = get_file_bytes_from_artifact(self.alita, filepath)
            actual_filename = filename or artifact_filename
        else:
            file_bytes = filedata.encode('utf-8')
            actual_filename = filename

        try:
            site_id = self._resolve_site_id()
            list_id = self._resolve_list_id(list_title)

            att_url = (f"{_GRAPH_BASE}/sites/{site_id}/lists/{list_id}/"
                       f"items/{item_id}/attachments")

            # Check for existing attachment
            existing_data = self._get(att_url)
            existing = next(
                (a for a in existing_data.get('value', [])
                 if a.get('name', '').lower() == actual_filename.lower()),
                None)

            if existing:
                if not replace:
                    raise ToolException(
                        f"Attachment '{actual_filename}' already exists on list item "
                        f"{item_id}. Set replace=True to overwrite.")
                att_id = existing.get('id', actual_filename)
                self._delete(f"{att_url}/{att_id}")

            # Upload new attachment (Graph API accepts base64-encoded contentBytes)
            data = self._post(att_url, {
                "name": actual_filename,
                "contentBytes": base64.b64encode(file_bytes).decode('ascii'),
            })
            result = {
                'id': data.get('id', actual_filename),
                'name': data.get('name', actual_filename),
                'size': len(file_bytes),
            }
            logging.info(
                "Attachment '%s' added to list '%s' item %d via Graph API",
                actual_filename, list_title, item_id)
            return result
        except ToolException:
            raise
        except Exception as e:
            logging.error("Graph add_attachment_to_list_item failed: %s", e)
            raise ToolException(f"Attachment failed: {e}")

