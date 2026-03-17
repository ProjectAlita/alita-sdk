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
from typing import Optional, List, Tuple
from urllib.parse import quote, unquote

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
        self.__drives_cache: Optional[List[dict]] = None

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

    def _list_drives(self) -> List[dict]:
        """Return all document-library drives for the site (cached).

        Each entry is a Graph drive object with at least ``id``, ``name``,
        and ``webUrl`` fields.
        """
        if self.__drives_cache is not None:
            return self.__drives_cache
        data = self._get(
            f"{_GRAPH_BASE}/sites/{self._resolve_site_id()}/drives",
            params={"$select": "id,name,webUrl"},
        )
        self.__drives_cache = data.get('value', [])
        return self.__drives_cache

    def _resolve_drive_and_folder(self, folder_path: str) -> List[Tuple[str, str]]:
        """Resolve a server-relative *folder_path* to a list of ``(drive_id, drive_relative_folder)`` pairs.

        The method enumerates all document-library drives on the site and
        matches the first path segment (after the site prefix) against each
        drive's URL.  This correctly handles:

        * Default ``Shared Documents`` library::

            '/sites/MySite/Shared Documents/upload'
            → [(default_drive_id, 'upload')]

        * Non-default document libraries::

            '/sites/MySite/Alita_test/subfolder'
            → [(alita_test_drive_id, 'subfolder')]

            '/sites/MySite/Alita_test'
            → [(alita_test_drive_id, '')]

        * Bare subfolder name not matching any library (e.g. ``"test"``)::

            All drives are probed; every drive that contains the folder is
            returned so that results from multiple libraries are included.

            'test'  (exists in both Alita_test and Elitea_test)
            → [(alita_test_drive_id, 'test'), (elitea_test_drive_id, 'test')]

        Falls back to the default drive (keeping the full cleaned path) when
        no drive matches and no probe succeeds, so existing callers that already
        pass a drive-relative path continue to work.
        """
        # Derive the site-relative path portion of the site URL
        # e.g. "https://tenant.sharepoint.com/sites/MyTeam" → "sites/MyTeam"
        site_path = re.sub(r'^https?://[^/]+', '', self.site_url).strip('/')

        # Clean the incoming folder_path (strip leading slash, decode percent-encoding)
        folder_clean = unquote(folder_path).strip('/')

        # Strip the site prefix so we are left with:
        # "Shared Documents/upload" or "Alita_test/subfolder"
        if folder_clean.lower().startswith(site_path.lower()):
            folder_clean = folder_clean[len(site_path):].lstrip('/')

        # Walk all drives and find every drive whose library name is a prefix match
        matched: List[Tuple[str, str]] = []

        for drive in self._list_drives():
            drive_weburl = unquote(drive.get('webUrl', ''))
            drive_full_path = re.sub(r'^https?://[^/]+', '', drive_weburl).strip('/')

            # Strip site prefix to get the library name segment
            if not drive_full_path.lower().startswith(site_path.lower()):
                continue
            drive_lib = drive_full_path[len(site_path):].lstrip('/')
            if not drive_lib:
                continue

            # Check if folder_clean starts with this library name (case-insensitive)
            folder_lower = folder_clean.lower()
            lib_lower = drive_lib.lower()
            if folder_lower == lib_lower or folder_lower.startswith(lib_lower + '/'):
                remainder = folder_clean[len(drive_lib):].lstrip('/')
                did = drive.get('id', '')
                if did:
                    matched.append((did, remainder))

        if matched:
            logging.debug(
                "_resolve_drive_and_folder: folder_path=%r → %d drive(s) matched",
                folder_path, len(matched),
            )
            return matched

        # Fallback: no drive's library name matched the first path segment.
        # This happens when folder_clean is a bare subfolder name (e.g. "test")
        # that exists inside one or more non-default libraries.
        # Probe ALL drives to find every one that contains the folder.
        encoded = quote(folder_clean, safe='/')
        probed: List[Tuple[str, str]] = []
        for drive in self._list_drives():
            did = drive.get('id', '')
            if not did:
                continue
            probe_url = f"{_GRAPH_BASE}/drives/{did}/root:/{encoded}"
            resp = requests.get(
                probe_url,
                headers=self._auth_headers(),
                params={"$select": "id,folder"},
                timeout=15,
            )
            if resp.status_code == 200:
                item = resp.json()
                if 'folder' in item or 'id' in item:
                    logging.debug(
                        "_resolve_drive_and_folder: folder_path=%r found in drive_id=%s (probe)",
                        folder_path, did,
                    )
                    probed.append((did, folder_clean))

        if probed:
            return probed

        # Last resort: default drive, pass the path as-is (preserves old behaviour)
        logging.warning(
            "_resolve_drive_and_folder: no drive matched folder_path=%r; "
            "falling back to default drive with relative path=%r",
            folder_path, folder_clean,
        )
        return [(self._resolve_drive_id(), folder_clean)]

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

    @staticmethod
    def _detect_column_type(col: dict) -> str:
        """Infer a simplified column type string from a Graph API column descriptor."""
        if 'number' in col or 'currency' in col:
            return 'number'
        if 'boolean' in col:
            return 'boolean'
        if 'dateTime' in col:
            return 'dateTime'
        if 'choice' in col:
            return 'choice'
        return 'text'

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
                col_type = self._detect_column_type(col)
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
    #  Files — private helpers                                            #
    # ------------------------------------------------------------------ #

    def _validate_and_resolve_file_source(
        self,
        filepath: Optional[str],
        filedata: Optional[str],
        filename: Optional[str],
    ) -> tuple:
        """Validate file source args and return (file_bytes, actual_filename).

        Shared by upload_file() and add_attachment_to_list_item().
        Imports are done lazily to avoid circular dependencies.
        """
        from ..utils import get_file_bytes_from_artifact

        if not filepath and not filedata:
            raise ToolException("Either filepath or filedata must be provided")
        if filepath and filedata:
            raise ToolException("Cannot specify both filepath and filedata")
        if filedata and not filename:
            raise ToolException("filename is required when using filedata")

        if filepath:
            file_bytes, artifact_filename = get_file_bytes_from_artifact(self.alita, filepath)
            return file_bytes, filename or artifact_filename
        return filedata.encode('utf-8'), filename

    def _build_drive_item_path(self, folder_path: str, actual_filename: str) -> str:
        """Build a URL-safe, drive-relative item path from *folder_path* and *actual_filename*.

        .. deprecated::
            Prefer :meth:`_resolve_drive_and_folder` which correctly identifies
            the target drive.  This method is kept for backwards compatibility with
            callers that already pass a drive-relative path.

        The method strips the site prefix (if present) but does **not** strip the
        document-library segment — use :meth:`_resolve_drive_and_folder` for that.
        """
        site_path = re.sub(r'^https?://[^/]+', '', self.site_url).strip('/')
        folder_clean = folder_path.strip('/')
        if folder_clean.startswith(site_path):
            folder_clean = folder_clean[len(site_path):].lstrip('/')
        item_path = f"{folder_clean}/{actual_filename}".strip('/')
        return quote(item_path, safe='/')

    def _upload_small_file(
        self, drive_id: str, safe_item_path: str, conflict: str,
        file_bytes: bytes, mime_type: str,
    ) -> dict:
        """PUT a small file (≤4 MB) directly to the drive item endpoint."""
        url = (
            f"{_GRAPH_BASE}/drives/{drive_id}/root:/{safe_item_path}:/content"
            f"?@microsoft.graph.conflictBehavior={conflict}"
        )
        resp = requests.put(
            url,
            headers={"Authorization": f"Bearer {self._token}", "Content-Type": mime_type},
            data=file_bytes,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()

    def _upload_large_file(
        self, drive_id: str, safe_item_path: str, conflict: str, file_bytes: bytes,
    ) -> dict:
        """Upload a large file (>4 MB) via a resumable upload session (5 MB chunks)."""
        session_url = (
            f"{_GRAPH_BASE}/drives/{drive_id}/root:/{safe_item_path}:/createUploadSession"
        )
        session = self._post(session_url, {"item": {"@microsoft.graph.conflictBehavior": conflict}})
        upload_url = session.get('uploadUrl')
        if not upload_url:
            raise RuntimeError("No uploadUrl returned in upload session response")

        total = len(file_bytes)
        offset = 0
        result: dict = {}
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
                timeout=120,
            )
            chunk_resp.raise_for_status()
            if chunk_resp.status_code in (200, 201):
                result = chunk_resp.json()
            offset += len(chunk)
        return result

    # ------------------------------------------------------------------ #
    #  Files                                                               #
    # ------------------------------------------------------------------ #

    def get_files_list(self, folder_name: Optional[str] = None,
                       limit_files: int = 100,
                       form_name: Optional[str] = None,
                       include_extensions: Optional[List[str]] = None,
                       skip_extensions: Optional[List[str]] = None):
        """
        Lists all files including files from subfolders across **all document
        libraries** on the site.

        When ``folder_name`` is supplied alone the method resolves the correct
        drive automatically (e.g. ``private_docs/some/sub``) and lists only
        within that subtree.  When no ``folder_name`` is given, every
        document-library drive on the site is enumerated so that files from
        libraries other than ``Shared Documents`` (e.g. ``private_docs``) are
        included.

        When **both** ``form_name`` and ``folder_name`` are supplied,
        ``form_name`` pins the document library and ``folder_name`` is treated
        as a subfolder path *relative to that library's root* (not as a library
        resolver).

        Number of files is limited by limit_files (default is 100).

        If form_name is specified alone, only files from the specified form will be returned.
        If include_extensions is specified, only files with matching extensions are returned.
        If skip_extensions is specified, files with matching extensions are excluded.
        Extensions accept both 'pdf' and '.pdf' forms and are matched case-insensitively.
        Note:
            * URL anatomy: https://epam.sharepoint.com/sites/{some_site}/{form_name}/Forms/AllItems.aspx
            * Example of folders syntax: `{form_name} / Hello / inner-folder` - 1st folder is commonly form_name
        """
        from .base_wrapper import _normalize_extensions, _matches_extension
        from urllib.parse import unquote as _unquote
        try:
            norm_include = _normalize_extensions(include_extensions)
            norm_skip = _normalize_extensions(skip_extensions)

            params = {
                "$top": 999,
                "$select": ("id,name,file,folder,webUrl,createdDateTime,"
                             "lastModifiedDateTime,parentReference,size"),
            }

            result: list = []

            # Build the initial BFS queue as (drive_id, url) tuples so that
            # sub-folder expansions always stay within the correct drive.
            #
            # • form_name + folder_name → pin the drive by form_name, then
            #   navigate into folder_name as a subfolder within that library.
            # • folder_name only → use _resolve_drive_and_folder to pick the
            #   right drive (handles non-default libraries like "private_docs").
            # • no folder_name → seed from EVERY drive on the site so files
            #   outside "Shared Documents" are found too.
            typed_queue: List[Tuple[str, str]] = []
            if folder_name and form_name:
                # Pin the drive by form_name, treat folder_name as a relative subfolder
                matched_drive = next(
                    (d for d in self._list_drives()
                     if _unquote(d.get('webUrl', '').rstrip('/').split('/')[-1]).lower()
                     == form_name.lower()),
                    None
                )
                if not matched_drive:
                    return ToolException(
                        f"Document library '{form_name}' not found. "
                        "Please check the form name and read permissions.")
                drive_id = matched_drive['id']
                encoded = quote(folder_name.strip('/'), safe='/')
                typed_queue.append(
                    (drive_id,
                     f"{_GRAPH_BASE}/drives/{drive_id}/root:/{encoded}:/children"))
            elif folder_name:
                for drive_id, relative in self._resolve_drive_and_folder(folder_name):
                    if relative:
                        encoded = quote(relative.strip('/'), safe='/')
                        typed_queue.append(
                            (drive_id,
                             f"{_GRAPH_BASE}/drives/{drive_id}/root:/{encoded}:/children"))
                    else:
                        typed_queue.append(
                            (drive_id, f"{_GRAPH_BASE}/drives/{drive_id}/root/children"))
            else:
                for drive in self._list_drives():
                    did = drive.get('id', '')
                    if not did:
                        continue
                    # When form_name is given, skip drives whose name doesn't
                    # match upfront — mirrors the REST wrapper's per-library
                    # skipping and avoids crawling irrelevant drives entirely.
                    if form_name:
                        drive_web_url = drive.get('webUrl', '')
                        drive_lib = _unquote(drive_web_url.rstrip('/').split('/')[-1])
                        if form_name.lower() != drive_lib.lower():
                            continue
                    typed_queue.append(
                        (did, f"{_GRAPH_BASE}/drives/{did}/root/children"))

            while typed_queue and len(result) < limit_files:
                drive_id, url = typed_queue.pop(0)
                next_link: Optional[str] = url
                while next_link and len(result) < limit_files:
                    data = self._get(
                        next_link,
                        params=params if next_link == url else None)
                    for item in data.get('value', []):
                        if 'folder' in item:
                            # Enqueue subfolder for processing (same drive)
                            item_id = item.get('id', '')
                            if item_id:
                                typed_queue.append(
                                    (drive_id,
                                     f"{_GRAPH_BASE}/drives/{drive_id}/items/{item_id}/children"))
                            continue
                        if 'file' not in item:
                            continue
                        file_name = item.get('name', '')
                        if norm_skip and _matches_extension(file_name, norm_skip):
                            continue
                        if norm_include and not _matches_extension(file_name, norm_include):
                            continue
                        parent_path = item.get('parentReference', {}).get('path', '')
                        result.append({
                            'Name': file_name,
                            'Path': f"{parent_path}/{file_name}",
                            'Created': item.get('createdDateTime', ''),
                            'Modified': item.get('lastModifiedDateTime', ''),
                            'Link': item.get('webUrl', ''),
                            'id': item.get('id', ''),
                        })
                        if len(result) >= limit_files:
                            break
                    next_link = data.get('@odata.nextLink')

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
        # Try to extract drive_id directly from the path when it is in
        # Graph API format: "/drives/{drive_id}/root:/{relative_path}"
        # This is the format returned by parentReference.path in get_files_list.
        drive_match = re.match(r'/?drives/([^/]+)/root:/(.*)', path)
        if drive_match:
            drive_id = drive_match.group(1)
            relative = drive_match.group(2).strip('/')
        else:
            drive_id = self._resolve_drive_id()
            # Strip server-relative prefix so we get a drive-relative path
            # e.g. "/sites/MySite/Shared Documents/folder/file.txt" → "folder/file.txt"
            # We resolve the drive root path to strip it
            drive_data = self._get(f"{_GRAPH_BASE}/drives/{drive_id}/root")
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
            folder_path: Server-relative folder path including the document-library name.
                         Supported formats:

                         * Full server-relative path (default library):
                           ``'/sites/MySite/Shared Documents/subfolder'``
                         * Full server-relative path (non-default library):
                           ``'/sites/MySite/Alita_test/subfolder'``
                         * Library root (upload directly into the library):
                           ``'/sites/MySite/Alita_test'``

                         The document-library segment is automatically resolved to the
                         correct drive — you do **not** need to know the drive ID.
            filepath: File path in format /{bucket}/{filename} from artifact storage
                      (mutually exclusive with filedata)
            filedata: String content to upload as a file
                      (mutually exclusive with filepath)
            filename: Target filename. Required with filedata, optional with filepath
            replace: If True, overwrite existing file. If False, raise error on conflict

        Returns:
            dict with {id, webUrl, path, size, mime_type}
        """
        from ..utils import detect_mime_type

        file_bytes, actual_filename = self._validate_and_resolve_file_source(
            filepath, filedata, filename
        )
        mime_type = detect_mime_type(file_bytes, actual_filename)

        # Resolve the correct drive and the path relative to that drive's root.
        # This fixes two issues:
        #   1. "Shared Documents" was being passed as a subfolder of the default
        #      drive instead of being stripped (→ nested Shared Documents folder).
        #   2. Non-default libraries (e.g. "Alita_test") were silently routed to
        #      the default drive instead of their own drive.
        # _resolve_drive_and_folder returns a list; for upload we always use the first match.
        drive_id, rel_folder = self._resolve_drive_and_folder(folder_path)[0]
        item_path = f"{rel_folder}/{actual_filename}".strip('/')
        safe_item_path = quote(item_path, safe='/')
        conflict = "replace" if replace else "fail"

        try:
            if len(file_bytes) <= _SMALL_FILE_THRESHOLD:
                result = self._upload_small_file(drive_id, safe_item_path, conflict, file_bytes, mime_type)
            else:
                result = self._upload_large_file(drive_id, safe_item_path, conflict, file_bytes)

            logging.info("Uploaded '%s' to '%s' via Graph API (drive=%s, rel=%r)",
                         actual_filename, folder_path, drive_id, rel_folder)
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
        file_bytes, actual_filename = self._validate_and_resolve_file_source(
            filepath, filedata, filename
        )
        try:
            site_id = self._resolve_site_id()
            list_id = self._resolve_list_id(list_title)
            att_url = (f"{_GRAPH_BASE}/sites/{site_id}/lists/{list_id}/"
                       f"items/{item_id}/attachments")

            existing_data = self._get(att_url)
            existing = next(
                (a for a in existing_data.get('value', [])
                 if a.get('name', '').lower() == actual_filename.lower()),
                None,
            )
            if existing:
                if not replace:
                    raise ToolException(
                        f"Attachment '{actual_filename}' already exists on list item "
                        f"{item_id}. Set replace=True to overwrite.")
                self._delete(f"{att_url}/{existing.get('id', actual_filename)}")

            data = self._post(att_url, {
                "name": actual_filename,
                "contentBytes": base64.b64encode(file_bytes).decode('ascii'),
            })
            logging.info(
                "Attachment '%s' added to list '%s' item %d via Graph API",
                actual_filename, list_title, item_id)
            return {
                'id': data.get('id', actual_filename),
                'name': data.get('name', actual_filename),
                'size': len(file_bytes),
            }
        except ToolException:
            raise
        except Exception as e:
            logging.error("Graph add_attachment_to_list_item failed: %s", e)
            raise ToolException(f"Attachment failed: {e}")

    # ------------------------------------------------------------------ #
    #  OneNote  (site-scoped: /sites/{site_id}/onenote)                  #
    # ------------------------------------------------------------------ #

    @property
    def _onenote_prefix(self) -> str:
        return f"{_GRAPH_BASE}/sites/{self._resolve_site_id()}/onenote"

    # Default $select fields for each OneNote resource type.
    # Override by passing select=["field1","field2"] to the respective method.
    _NOTEBOOK_SELECT_DEFAULT = (
        "id,displayName,createdDateTime,lastModifiedDateTime,links,isDefault,isShared"
    )
    _SECTION_SELECT_DEFAULT = (
        "id,displayName,createdDateTime,lastModifiedDateTime,pagesUrl,isDefault"
    )
    # NOTE: contentUrl is intentionally excluded — the Graph API returns 400
    # when it is included in $select for the pages endpoint.
    _PAGE_SELECT_DEFAULT = (
        "id,title,createdDateTime,lastModifiedDateTime"
    )

    def _build_onenote_select_params(
        self, select: Optional[List[str]], default: str, extra: Optional[dict] = None
    ) -> dict:
        """Build a Graph API params dict with an appropriate $select value.

        Args:
            select: Caller-supplied field list. ``None`` → use *default*.
                    Empty list → omit $select entirely.
            default: The comma-separated default field string for this resource type.
            extra: Any additional params to merge in (e.g. ``{"$top": 100}``).
        """
        params: dict = dict(extra or {})
        if select is None:
            params["$select"] = default
        elif select:
            # For pages, silently drop the known-bad field so callers never
            # need to remember this Graph API quirk.
            fields = [f for f in select if f != "contentUrl"]
            if fields:
                params["$select"] = ",".join(fields)
        return params

    def onenote_get_notebooks(self, select: Optional[List[str]] = None) -> list:
        """List all OneNote notebooks in this SharePoint site.

        Returns a list of notebook objects. By default each object contains:
        id, displayName, createdDateTime, lastModifiedDateTime, isDefault,
        isShared, and webUrl (via links.oneNoteWebUrl).

        Args:
            select: Optional list of fields to return instead of the defaults,
                    e.g. ["id", "displayName"]. Pass an empty list to omit
                    $select entirely and let Graph return all fields.
        """
        try:
            params = self._build_onenote_select_params(select, self._NOTEBOOK_SELECT_DEFAULT)
            data = self._get(f"{self._onenote_prefix}/notebooks", params=params)
            return data.get("value", [])
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Failed to list OneNote notebooks: {e}") from e

    def onenote_get_sections(
        self, notebook_id: str, select: Optional[List[str]] = None
    ) -> list:
        """List all sections in a specific OneNote notebook on this site.

        Returns a list of section objects. By default each object contains:
        id, displayName, createdDateTime, lastModifiedDateTime,
        pagesUrl, and isDefault.

        Args:
            notebook_id: The ID of the notebook to list sections from.
            select: Optional list of fields to return instead of the defaults.
                    Pass an empty list to omit $select entirely.
        """
        if not notebook_id:
            raise ToolException("notebook_id is required")
        try:
            params = self._build_onenote_select_params(select, self._SECTION_SELECT_DEFAULT)
            data = self._get(
                f"{self._onenote_prefix}/notebooks/{notebook_id}/sections",
                params=params,
            )
            return data.get("value", [])
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(
                f"Failed to list sections for notebook '{notebook_id}': {e}"
            ) from e

    def onenote_get_pages(
        self,
        section_id: str,
        limit: int = 100,
        select: Optional[List[str]] = None,
    ) -> list:
        """List pages in a OneNote section on this site.

        Returns a list of page metadata objects. By default each object contains:
        id, title, createdDateTime, lastModifiedDateTime, and webUrl.
        Does NOT return page HTML content — use onenote_get_page_content() for that.

        Note: ``contentUrl`` cannot be used in ``$select`` — the Graph API returns
        HTTP 400. To fetch page content use onenote_get_page_content(page_id).

        Args:
            section_id: The ID of the section to list pages from.
            limit: Maximum number of pages to return (max 100 per request).
            select: Optional list of fields to return instead of the defaults.
                    Pass an empty list to omit $select entirely.
                    Do NOT include 'contentUrl' — it is not selectable.
        """
        if not section_id:
            raise ToolException("section_id is required")
        try:
            params = self._build_onenote_select_params(
                select, self._PAGE_SELECT_DEFAULT, extra={"$top": min(limit, 100)}
            )
            data = self._get(
                f"{self._onenote_prefix}/sections/{section_id}/pages",
                params=params,
            )
            return data.get("value", [])
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(
                f"Failed to list pages for section '{section_id}': {e}"
            ) from e

    def _onenote_fetch_page_html(self, page_id: str) -> str:
        """Fetch raw OneNote page HTML from Graph API (internal helper)."""
        if not page_id:
            raise ToolException("page_id is required")
        try:
            resp = requests.get(
                f"{self._onenote_prefix}/pages/{page_id}/content",
                headers=self._auth_headers(),
                timeout=60,
            )
            resp.raise_for_status()
            return resp.content.decode("utf-8")
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(
                f"Failed to get content for OneNote page '{page_id}': {e}"
            ) from e

    def onenote_get_page_content(self, page_id: str) -> str:
        """Retrieve the raw HTML content of a OneNote page on this site.

        Returns the OneNote XHTML string as stored by the service.
        For human-readable parsed content — including image descriptions
        and attachment listings — use onenote_read_page() instead.
        """
        return self._onenote_fetch_page_html(page_id)

    # ------------------------------------------------------------------ #
    #  Attachment helpers                                                  #
    # ------------------------------------------------------------------ #

    def _onenote_resolve_resource_url(self, src: str) -> str:
        """Rewrite a raw OneNote resource URL to the canonical Graph API form.

        OneNote embeds resource URLs that may look like::

            https://graph.microsoft.com/.../resources/<id>/$value
            https://graph.microsoft.com/.../resources/<id>/content
            https://graph.microsoft.com/.../resources/<id>

        All forms are normalised to::

            {_GRAPH_BASE}/sites/{site_id}/onenote/resources/{resource_id}/content
        """
        resource_match = (
            re.search(r'resources/([^/]+)/\$value', src)
            or re.search(r'resources/([^/]+)/content', src)
            or re.search(r'resources/([^/?]+)', src)
        )
        if resource_match:
            resource_id = resource_match.group(1)
            return (
                f"{_GRAPH_BASE}/sites/{self._resolve_site_id()}"
                f"/onenote/resources/{resource_id}/content"
            )
        return src

    def onenote_list_attachments(self, page_id: str) -> list:
        """List all file attachments on a OneNote page.

        Parses the page HTML and extracts every ``<object data-attachment="…">``
        element.  Embedded images (``<img>``) are intentionally excluded — only
        user-uploaded file attachments are returned.

        Returns a list of dicts, each containing:

        - **name** (str): The original attachment filename
          (from ``data-attachment``).
        - **resource_id** (str | None): The Graph API resource ID parsed from
          the ``data`` attribute URL.  Use this as a stable identifier for
          :meth:`onenote_read_attachment`.
        - **download_url** (str): The canonical Graph API download URL for this
          attachment (``…/onenote/resources/{resource_id}/content``).

        Args:
            page_id: The ID of the OneNote page to inspect.
        """
        from html.parser import HTMLParser

        if not page_id:
            raise ToolException("page_id is required")

        html = self._onenote_fetch_page_html(page_id)

        class _AttachmentParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.attachments: list = []

            def handle_starttag(self, tag, attrs):
                if tag == "object":
                    d = dict(attrs)
                    fname = d.get("data-attachment", "")
                    src = d.get("data", "")
                    if fname:
                        self.attachments.append((fname, src))

        parser = _AttachmentParser()
        parser.feed(html)

        results = []
        for fname, src in parser.attachments:
            canonical_url = self._onenote_resolve_resource_url(src) if src else ""
            resource_match = re.search(r'resources/([^/?]+)', src) if src else None
            resource_id = resource_match.group(1) if resource_match else None
            results.append({
                "name": fname,
                "resource_id": resource_id,
                "download_url": canonical_url,
            })
        return results

    def onenote_read_attachment(
        self,
        page_id: str,
        attachment_name: str,
        capture_images: bool = True,
    ) -> str:
        """Download and parse a single file attachment from a OneNote page.

        Looks up the attachment by *attachment_name* (case-sensitive, matches
        the ``data-attachment`` attribute from the page HTML) using
        :meth:`onenote_list_attachments`, downloads its bytes from the Graph
        API, and passes them through the shared content parser
        (``parse_content_from_bytes``).

        Supports every file type registered in the SDK loader map — including
        PDF, DOCX, XLSX, XLS, PPTX, PPT, DOC, XML, JSONL, ODP, images, plain
        text, and more.  For image attachments an AI-generated description is
        returned when ``capture_images=True`` and an LLM is configured.

        Args:
            page_id: The ID of the OneNote page containing the attachment.
            attachment_name: The filename of the attachment to read, exactly as
                returned by :meth:`onenote_list_attachments` (e.g.
                ``"report.pdf"``).
            capture_images: When True and an LLM is configured, run image
                attachments through the vision pipeline.

        Returns:
            Parsed text content of the attachment as a string.
        """
        from ..utils.content_parser import parse_content_from_bytes

        if not page_id:
            raise ToolException("page_id is required")
        if not attachment_name:
            raise ToolException("attachment_name is required")

        attachments = self.onenote_list_attachments(page_id)
        match = next((a for a in attachments if a["name"] == attachment_name), None)
        if match is None:
            available = [a["name"] for a in attachments]
            raise ToolException(
                f"Attachment '{attachment_name}' not found on page '{page_id}'. "
                f"Available attachments: {available}"
            )

        download_url = match["download_url"]
        if not download_url:
            raise ToolException(
                f"Attachment '{attachment_name}' has no resolvable download URL."
            )

        try:
            att_resp = requests.get(
                download_url,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=60,
                allow_redirects=True,
            )
            if att_resp.status_code in (400, 404):
                raise ToolException(
                    f"Graph API returned {att_resp.status_code} when downloading "
                    f"attachment '{attachment_name}' from page '{page_id}'."
                )
            att_resp.raise_for_status()

            return parse_content_from_bytes(
                file_bytes=att_resp.content,
                filename=attachment_name,
                content_type=att_resp.headers.get("Content-Type", ""),
                is_capture_image=capture_images,
                llm=self.llm,
            )

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(
                f"Failed to read attachment '{attachment_name}' "
                f"from page '{page_id}': {e}"
            ) from e

    def _onenote_download_attachment_bytes(self, download_url: str, attachment_name: str) -> bytes:
        """Download raw bytes for a OneNote attachment from its canonical Graph API URL.

        Unlike :meth:`onenote_read_attachment`, this method returns the raw bytes
        without any parsing so the indexing pipeline can pass them through
        ``CONTENT_IN_BYTES`` / ``process_document_by_type`` itself.

        Args:
            download_url: The canonical Graph API content URL (from onenote_list_attachments).
            attachment_name: Used only for error messages.

        Returns:
            Raw bytes of the attachment content.
        """
        try:
            resp = requests.get(
                download_url,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=60,
                allow_redirects=True,
            )
            if resp.status_code in (400, 404):
                raise ToolException(
                    f"Graph API returned {resp.status_code} when downloading "
                    f"attachment '{attachment_name}'."
                )
            resp.raise_for_status()
            return resp.content
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(
                f"Failed to download attachment bytes for '{attachment_name}': {e}"
            ) from e

    # ------------------------------------------------------------------ #
    #  onenote_read_page — private helpers                                #
    # ------------------------------------------------------------------ #

    _MIME_TO_EXT = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
        "image/tiff": ".tiff",
        "image/svg+xml": ".svg",
    }

    @classmethod
    def _sniff_image_extension(cls, content_type: str, img_bytes: bytes) -> str:
        """Return a file extension for an image given its Content-Type and raw bytes.

        Falls back to magic-byte sniffing when the MIME type is not a recognised
        image type (e.g. ``application/octet-stream``), and to ``.jpg`` as a
        final safe fallback.
        """
        ext = cls._MIME_TO_EXT.get(content_type)
        if ext:
            return ext
        magic = img_bytes[:4] if len(img_bytes) >= 4 else img_bytes
        if magic[:2] == b'\xff\xd8':
            return ".jpg"
        if magic[:4] == b'\x89PNG':
            return ".png"
        if magic[:4] == b'GIF8':
            return ".gif"
        if magic[:4] == b'RIFF':
            return ".webp"
        return ".jpg"

    def _fetch_onenote_image(self, src: str, alt: str, capture_images: bool) -> tuple:
        """Download a OneNote embedded image and return ``(description, raw_bytes, filename)``.

        - ``description`` – human-readable text (LLM vision result, or fallback placeholder).
        - ``raw_bytes``   – raw image bytes, or ``None`` if the image could not be fetched.
        - ``filename``    – e.g. ``"image0_<resource_id>.png"`` derived from the resource URL.

        This is the canonical image-processing helper. Both the read-page formatter
        and the indexing pipeline call this so the image is only downloaded once.
        """
        from ..utils.content_parser import parse_file_content

        description = f"[image: {alt or 'no description'}]"
        if not src or "graph.microsoft.com" not in src:
            return description, None, None

        canonical_src = self._onenote_resolve_resource_url(src)
        # Derive a stable filename from the resource URL
        resource_match = re.search(r'resources/([^/?]+)', canonical_src)
        resource_id = resource_match.group(1) if resource_match else "unknown"

        if not capture_images:
            return description, None, f"image_{resource_id}.jpg"

        try:
            img_resp = requests.get(
                canonical_src,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=30,
                allow_redirects=True,
            )
            if img_resp.status_code in (400, 404):
                logging.warning(
                    "OneNote image URL returned %d, skipping: %s",
                    img_resp.status_code, canonical_src,
                )
                return description, None, f"image_{resource_id}.jpg"
            img_resp.raise_for_status()
            img_bytes = img_resp.content
            ct = img_resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip().lower()
            ext = self._sniff_image_extension(ct, img_bytes)
            filename = f"image_{resource_id}{ext}"
            if self.llm:
                result = parse_file_content(
                    file_name=filename,
                    file_content=img_bytes,
                    is_capture_image=True,
                    llm=self.llm,
                )
                if isinstance(result, str) and result.strip():
                    description = f"[image description: {result.strip()}]"
            return description, img_bytes, filename
        except Exception as img_exc:
            logging.warning("Could not process OneNote image '%s': %s", src, img_exc)
            return description, None, f"image_{resource_id}.jpg"

    def _process_onenote_image(self, src: str, alt: str, capture_images: bool) -> str:
        """Return the text description for an embedded OneNote image (backward-compat wrapper)."""
        description, _, _ = self._fetch_onenote_image(src, alt, capture_images)
        return description

    def _resolve_page_attachment_data(
        self,
        attachments: list,
        page_id: str,
        capture_images: bool,
        include_attachments: bool,
        read_attachment_content: bool,
    ) -> tuple:
        """Pre-resolve canonical URLs and optionally parse content for all attachments.

        Returns:
            (attachment_download_urls, attachment_contents) — both are dicts keyed
            by the attachment placeholder string used inside ``parser.chunks``.
        """
        download_urls: dict = {}
        contents: dict = {}

        for fname, src, placeholder in attachments:
            download_urls[placeholder] = self._onenote_resolve_resource_url(src) if src else ""

        if read_attachment_content and include_attachments:
            for fname, src, placeholder in attachments:
                try:
                    parsed = self.onenote_read_attachment(
                        page_id=page_id,
                        attachment_name=fname,
                        capture_images=capture_images,
                    )
                    contents[placeholder] = (
                        parsed if parsed and not parsed.startswith("[attachment") else None
                    )
                except Exception as att_exc:
                    logging.warning(
                        "Could not process OneNote attachment '%s': %s", fname, att_exc
                    )
                    contents[placeholder] = None

        return download_urls, contents

    def _build_attachments_footer(
        self,
        attachments: list,
        download_urls: dict,
        contents: dict,
        read_attachment_content: bool,
    ) -> str:
        """Build the trailing '--- Attachments ---' footer block."""
        lines = ["\n\n--- Attachments ---"]
        for fname, src, placeholder in attachments:
            url = download_urls.get(placeholder) or "(no download URL)"
            lines.append(f"  {fname}  ->  {url}")
            parsed = contents.get(placeholder)
            if read_attachment_content and parsed:
                indented = "\n".join(f"    {line}" for line in parsed.splitlines())
                lines.append(f"    Content:\n{indented}")
        return "\n".join(lines)

    def _onenote_parse_page_items(
        self,
        page_id: str,
        capture_images: bool = True,
        include_attachments: bool = True,
        read_attachment_content: bool = False,
    ) -> list:
        """Parse a OneNote page and return a structured list of typed items.

        Each item is a dict with a ``type`` key:

        - ``{"type": "text", "content": "<plain text>"}``
        - ``{"type": "image", "description": "<LLM description or alt text>",
             "src": "<Graph API resource URL>", "alt": "<original alt attr>"}``
        - ``{"type": "attachment", "name": "<filename>",
             "download_url": "<Graph API URL>",
             "content": "<parsed text or None>"}``

        Args:
            page_id: The ID of the OneNote page to parse.
            capture_images: Run embedded images through the LLM vision pipeline.
            include_attachments: Resolve and include attachment download URLs.
            read_attachment_content: Also download and parse each attachment's content.

        Returns:
            List of typed item dicts in document order.
        """
        from html.parser import HTMLParser

        if not page_id:
            raise ToolException("page_id is required")

        html = self._onenote_fetch_page_html(page_id)

        # ── Step 1: parse XHTML into raw chunks ──────────────────────
        class _Parser(HTMLParser):
            _SKIP = {"script", "style", "head"}
            _BLOCK = {
                "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
                "li", "br", "tr", "td", "th",
            }

            def __init__(self):
                super().__init__()
                self.chunks: list = []
                self.images: list = []       # (placeholder, src, alt)
                self.attachments: list = []  # (filename, src, placeholder)
                self._skip_depth = 0

            def handle_starttag(self, tag, attrs):
                d = dict(attrs)
                if tag in self._SKIP:
                    self._skip_depth += 1
                    return
                if self._skip_depth:
                    return
                if tag == "img":
                    src = d.get("src", "")
                    alt = d.get("alt", "")
                    ph = f"\x00IMG{len(self.images)}\x00"
                    self.images.append((ph, src, alt))
                    self.chunks.append(ph)
                elif tag == "object":
                    fname = d.get("data-attachment", "")
                    src = d.get("data", "")
                    if fname:
                        ph = f"\x00ATT{len(self.attachments)}\x00"
                        self.attachments.append((fname, src, ph))
                        self.chunks.append(ph)
                elif tag in self._BLOCK:
                    self.chunks.append("\n")

            def handle_endtag(self, tag):
                if tag in self._SKIP:
                    self._skip_depth = max(0, self._skip_depth - 1)
                elif tag in self._BLOCK and not self._skip_depth:
                    self.chunks.append("\n")

            def handle_data(self, data):
                if not self._skip_depth:
                    self.chunks.append(data)

        parser = _Parser()
        parser.feed(html)

        # ── Step 2: resolve image placeholders → descriptions + raw bytes ──
        image_data: dict = {}
        for ph, src, alt in parser.images:
            description, raw_bytes, filename = self._fetch_onenote_image(src, alt, capture_images)
            image_data[ph] = {
                "description": description,
                "src": self._onenote_resolve_resource_url(src) if src else "",
                "alt": alt,
                "raw_bytes": raw_bytes,     # bytes or None — used by indexing pipeline
                "filename": filename,       # e.g. "image_<resource_id>.png"
            }

        # ── Step 3: resolve attachment placeholders → URLs + content ──
        download_urls, att_contents = self._resolve_page_attachment_data(
            parser.attachments, page_id, capture_images,
            include_attachments, read_attachment_content,
        )

        # ── Step 4: walk chunks and build typed item list ─────────────
        items: list = []
        text_buf: list = []

        def _flush_text():
            if text_buf:
                text = re.sub(r"\n{3,}", "\n\n", "".join(text_buf)).strip()
                if text:
                    items.append({"type": "text", "content": text})
                text_buf.clear()

        img_phs = {ph for ph, _, _ in parser.images}
        att_phs = {ph for _, _, ph in parser.attachments}

        for chunk in parser.chunks:
            if chunk in img_phs:
                _flush_text()
                info = image_data[chunk]
                items.append({
                    "type": "image",
                    "description": info["description"],
                    "src": info["src"],
                    "alt": info["alt"],
                    "raw_bytes": info["raw_bytes"],
                    "filename": info["filename"],
                })
            elif chunk in att_phs:
                _flush_text()
                # Look up the attachment tuple by placeholder
                att_tuple = next(
                    (t for t in parser.attachments if t[2] == chunk), None
                )
                if att_tuple:
                    fname, _src, ph = att_tuple
                    url = download_urls.get(ph, "")
                    content = att_contents.get(ph) if read_attachment_content else None
                    items.append({
                        "type": "attachment",
                        "name": fname,
                        "download_url": url,
                        "content": content,
                    })
            else:
                text_buf.append(chunk)

        _flush_text()
        return items

    def onenote_read_page(
            self,
            page_id: str,
            capture_images: bool = True,
            include_attachments: bool = True,
            read_attachment_content: bool = False,
    ) -> str:
        """Read and parse a OneNote page into a beautified plain-text string.

        Each content item (text block, image, attachment) is separated by a
        ``-----`` divider. Text is stripped of HTML; images become their LLM
        description (or ``[image: <alt>]`` without LLM); attachments are shown
        as ``[attachment: <name>]`` followed by their download URL and, when
        ``read_attachment_content=True``, their parsed content.

        Args:
            page_id: The ID of the OneNote page to read.
            capture_images: Pass embedded images through the LLM vision pipeline.
            include_attachments: Include attachment entries in the output.
            read_attachment_content: Also parse and inline each attachment's content.

        Returns:
            Beautified plain-text string with ``-----`` separators between items.
        """
        if not page_id:
            raise ToolException("page_id is required")
        try:
            items = self._onenote_parse_page_items(
                page_id=page_id,
                capture_images=capture_images,
                include_attachments=include_attachments,
                read_attachment_content=read_attachment_content,
            )

            parts: list = []
            for item in items:
                t = item["type"]
                if t == "text":
                    parts.append(item["content"])
                elif t == "image":
                    parts.append(item["description"])
                elif t == "attachment":
                    block = f"[attachment: {item['name']}]\n  {item['download_url']}"
                    if item.get("content"):
                        indented = "\n".join(
                            f"  {line}" for line in item["content"].splitlines()
                        )
                        block += f"\n  Content:\n{indented}"
                    parts.append(block)

            return "\n-----\n".join(p for p in parts if p)

        except ToolException:
            raise
        except Exception as e:
            raise ToolException(
                f"Failed to read OneNote page '{page_id}': {e}"
            ) from e

    def onenote_read_page_items(
            self,
            page_id: str,
            capture_images: bool = True,
            include_attachments: bool = True,
            read_attachment_content: bool = False,
    ) -> list:
        """Read and parse a OneNote page into a structured list of typed items.

        Returns a list of dicts, one per content element, in document order:

        - ``{"type": "text", "content": "<plain text block>"}``
        - ``{"type": "image", "description": "<LLM description or alt text>",
             "src": "<canonical Graph API resource URL>", "alt": "<original alt>"}``
        - ``{"type": "attachment", "name": "<filename>",
             "download_url": "<canonical Graph API URL>",
             "content": "<parsed text or None>"}``

        Args:
            page_id: The ID of the OneNote page to read.
            capture_images: Pass embedded images through the LLM vision pipeline.
            include_attachments: Resolve attachment download URLs and include them.
            read_attachment_content: Also download and parse each attachment inline.

        Returns:
            List of typed item dicts in document order.
        """
        if not page_id:
            raise ToolException("page_id is required")
        try:
            return self._onenote_parse_page_items(
                page_id=page_id,
                capture_images=capture_images,
                include_attachments=include_attachments,
                read_attachment_content=read_attachment_content,
            )
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(
                f"Failed to read OneNote page items for '{page_id}': {e}"
            ) from e

    def onenote_create_notebook(self, display_name: str) -> dict:
        """Create a new OneNote notebook in this SharePoint site.

        Returns the created notebook object containing:
        id, displayName, createdDateTime, and webUrl.
        """
        if not display_name or not display_name.strip():
            raise ToolException("display_name is required and cannot be empty")
        try:
            result = self._post(
                f"{self._onenote_prefix}/notebooks",
                {"displayName": display_name.strip()},
            )
            return {
                "id": result.get("id"),
                "displayName": result.get("displayName"),
                "createdDateTime": result.get("createdDateTime"),
                "webUrl": (
                    result.get("links", {})
                    .get("oneNoteWebUrl", {})
                    .get("href")
                ),
            }
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(
                f"Failed to create OneNote notebook '{display_name}': {e}"
            ) from e

    def onenote_create_section(self, notebook_id: str, display_name: str) -> dict:
        """Create a new section in a OneNote notebook on this site.

        Returns the created section object containing:
        id, displayName, createdDateTime, and pagesUrl.
        """
        if not notebook_id:
            raise ToolException("notebook_id is required")
        if not display_name or not display_name.strip():
            raise ToolException("display_name is required and cannot be empty")
        try:
            result = self._post(
                f"{self._onenote_prefix}/notebooks/{notebook_id}/sections",
                {"displayName": display_name.strip()},
            )
            return {
                "id": result.get("id"),
                "displayName": result.get("displayName"),
                "createdDateTime": result.get("createdDateTime"),
                "pagesUrl": result.get("pagesUrl"),
            }
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(
                f"Failed to create section '{display_name}' in notebook "
                f"'{notebook_id}': {e}"
            ) from e

    def onenote_create_page(self, section_id: str, html_content: str) -> dict:
        """Create a new OneNote page in a section on this site from raw HTML.

        The html_content must be a valid HTML document containing a <title> tag.
        Example:
            '<!DOCTYPE html><html><head><title>My Page</title></head>
             <body><p>Content here</p></body></html>'

        Returns the created page object containing:
        id, title, createdDateTime, webUrl, and contentUrl.
        """
        if not section_id:
            raise ToolException("section_id is required")
        if not html_content or not html_content.strip():
            raise ToolException("html_content is required and cannot be empty")
        try:
            resp = requests.post(
                f"{self._onenote_prefix}/sections/{section_id}/pages",
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "text/html",
                },
                data=html_content.encode("utf-8"),
                timeout=60,
            )
            resp.raise_for_status()
            result = resp.json()
            return {
                "id": result.get("id"),
                "title": result.get("title"),
                "createdDateTime": result.get("createdDateTime"),
                "webUrl": result.get("webUrl"),
                "contentUrl": result.get("contentUrl"),
            }
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(
                f"Failed to create OneNote page in section '{section_id}': {e}"
            ) from e

    def onenote_update_page(self, page_id: str, patch_commands: list) -> str:
        """Update a OneNote page using Graph API PATCH commands.

        Each patch_command object must have:
        - target: CSS selector or 'body', 'title', or an element id
        - action: 'append', 'prepend', 'replace', 'insert', or 'delete'
        - content: HTML string (not required for 'delete' action)
        - position: optional — 'after' or 'before' (used with 'insert')

        Returns a success confirmation string.
        """
        if not page_id:
            raise ToolException("page_id is required")
        if not patch_commands:
            raise ToolException("patch_commands must be a non-empty list")
        try:
            resp = requests.patch(
                f"{self._onenote_prefix}/pages/{page_id}/content",
                headers=self._auth_headers("application/json"),
                json=patch_commands,
                timeout=60,
            )
            resp.raise_for_status()
            return (
                f"OneNote page '{page_id}' updated successfully with "
                f"{len(patch_commands)} patch command(s)."
            )
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(
                f"Failed to update OneNote page '{page_id}': {e}"
            ) from e

    def onenote_replace_page_content(self, page_id: str, html_content: str) -> str:
        """Replace the entire body of a OneNote page with new HTML content.

        Convenience wrapper around onenote_update_page() that generates a single
        PATCH command to replace the full page body.
        html_content should be a plain HTML fragment (no <html>/<head> wrapper).

        Returns a success confirmation string.
        """
        if not page_id:
            raise ToolException("page_id is required")
        if not html_content:
            raise ToolException("html_content is required")
        return self.onenote_update_page(
            page_id,
            [{"target": "body", "action": "replace", "content": html_content}],
        )

    def onenote_delete_page(self, page_id: str) -> str:
        """Permanently delete a OneNote page on this site.

        This action is irreversible.
        Returns a success confirmation string.
        """
        if not page_id:
            raise ToolException("page_id is required")
        try:
            self._delete(f"{self._onenote_prefix}/pages/{page_id}")
            return f"OneNote page '{page_id}' deleted successfully."
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(
                f"Failed to delete OneNote page '{page_id}': {e}"
            ) from e

    def onenote_search_pages(self, query: str, limit: int = 50) -> list:
        """Search for OneNote pages matching a full-text query on this site.

        Returns a list of matching page metadata objects, each containing:
        id, title, lastModifiedDateTime, createdDateTime, and webUrl.
        """
        if not query or not query.strip():
            raise ToolException("query is required and cannot be empty")
        try:
            data = self._get(
                f"{self._onenote_prefix}/pages",
                params={
                    "search": query.strip(),
                    "$select": (
                        "id,title,lastModifiedDateTime,createdDateTime,webUrl"
                    ),
                    "$top": min(limit, 100),
                },
            )
            return data.get("value", [])
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(
                f"Failed to search OneNote pages with query '{query}': {e}"
            ) from e
