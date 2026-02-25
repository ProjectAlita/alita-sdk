"""SharePoint REST / office365-rest-python-client wrapper.

Used when *client_id + client_secret* (app credentials) or a plain bearer
*token* (without Graph scopes) are provided.  Falls back automatically to the
:class:`authorization_helper.SharepointAuthorizationHelper` Graph API client
when the primary REST call fails.
"""
from __future__ import annotations

import logging
from io import BytesIO
from typing import Optional

from langchain_core.tools import ToolException

from .base_wrapper import BaseSharepointWrapper
from .utils import decode_sharepoint_string


class SharepointRestWrapper(BaseSharepointWrapper):
    """Concrete SharePoint wrapper backed by *office365-rest-python-client*.

    Args:
        client: Already-authenticated ``office365.sharepoint.client_context.ClientContext``
                instance.
        site_url: Full SharePoint site URL.
        client_id: Azure AD / ACS application (client) ID — used when building
                   the Graph API fallback helper.
        client_secret: Raw (plain-text) client secret — used for the fallback.
        alita: Optional Alita client (needed by :meth:`upload_file` /
               :meth:`add_attachment_to_list_item` to resolve artifact paths).
        llm: Optional LLM instance forwarded to the content parser.
    """

    def __init__(self, client, site_url: str,
                 client_id: Optional[str] = None,
                 client_secret: Optional[str] = None,
                 alita=None, llm=None):
        self._client = client
        self.site_url = site_url
        self._client_id = client_id
        self._client_secret = client_secret   # plain text already
        self.alita = alita
        self.llm = llm

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _graph_helper(self):
        """Return a :class:`SharepointAuthorizationHelper` for fallback calls."""
        from .authorization_helper import SharepointAuthorizationHelper
        return SharepointAuthorizationHelper(
            client_id=self._client_id,
            client_secret=self._client_secret,
            tenant="",
            scope="",
            token_json="",
        )

    # ------------------------------------------------------------------ #
    #  Lists                                                               #
    # ------------------------------------------------------------------ #

    def read_list(self, list_title: str, limit: int = 1000):
        """Reads a specified List in sharepoint site. Number of list items is limited by limit (default is 1000)."""
        try:
            target_list = self._client.web.lists.get_by_title(list_title)
            self._client.load(target_list)
            self._client.execute_query()
            items = target_list.items.top(limit).get().execute_query()
            logging.info("%d items loaded from SharePoint REST API.", len(items))
            return [item.properties for item in items]
        except Exception as base_e:
            logging.warning(
                "Primary SharePoint REST list read failed: %s. Trying Graph API fallback.", base_e)
            try:
                graph_items = self._graph_helper().get_list_items(
                    self.site_url, list_title, limit)
                if graph_items:
                    logging.info("%d items loaded via Graph API fallback.", len(graph_items))
                    return graph_items
                return ToolException(
                    "List appears empty or inaccessible via both REST and Graph APIs.")
            except Exception as graph_e:
                logging.error("Graph API fallback failed: %s", graph_e)
                return ToolException(
                    f"Cannot read list '{list_title}'. "
                    f"Check list name and permissions: {base_e} | {graph_e}")

    def get_lists(self):
        """Returns all SharePoint lists available on the site with their titles, IDs, and descriptions."""
        try:
            lists = self._client.web.lists.get().execute_query()
            result = []
            for lst in lists:
                if lst.properties.get('Hidden', False):
                    continue
                result.append({
                    'Title': lst.properties.get('Title', ''),
                    'Id': lst.properties.get('Id', ''),
                    'Description': lst.properties.get('Description', ''),
                    'ItemCount': lst.properties.get('ItemCount', 0),
                    'BaseTemplate': lst.properties.get('BaseTemplate', 0),
                })
            return result
        except Exception as base_e:
            logging.warning(
                "Primary SharePoint REST lists fetch failed: %s. Trying Graph API fallback.", base_e)
            try:
                graph_lists = self._graph_helper().get_lists(self.site_url)
                if graph_lists:
                    return graph_lists
                return ToolException(
                    "No lists found or inaccessible via both REST and Graph APIs.")
            except Exception as graph_e:
                logging.error("Graph API fallback failed: %s", graph_e)
                return ToolException(
                    f"Cannot retrieve lists. Check permissions: {base_e} | {graph_e}")

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
            lists = self._client.web.lists.get().execute_query()
            target_list = next(
                (l for l in lists
                 if l.properties.get('Title', '').lower() == list_title.lower()),
                None)
            if not target_list:
                raise RuntimeError(f"List '{list_title}' not found")

            fields = target_list.fields.get().execute_query()
            result = []
            for field in fields:
                props = field.properties
                if props.get('Hidden', False) or props.get('ReadOnlyField', False):
                    continue
                field_type = props.get('TypeAsString', '').lower()
                if 'lookup' in field_type:
                    continue

                column_info = {
                    'name': props.get('InternalName', props.get('Title', '')),
                    'displayName': props.get('Title', props.get('InternalName', '')),
                    'columnType': 'text',
                    'required': props.get('Required', False),
                }
                if field_type in ('text', 'note'):
                    column_info['columnType'] = 'text'
                elif field_type in ('number', 'currency'):
                    column_info['columnType'] = 'number'
                elif field_type == 'boolean':
                    column_info['columnType'] = 'boolean'
                elif field_type == 'datetime':
                    column_info['columnType'] = 'dateTime'
                elif field_type in ('choice', 'multichoice'):
                    column_info['columnType'] = 'choice'
                    choices = props.get('Choices', [])
                    if choices:
                        column_info['choice'] = {'choices': choices}

                result.append(column_info)
            return result
        except Exception as base_e:
            logging.warning(
                "REST API failed for get_list_columns: %s. Trying Graph API fallback.", base_e)
            try:
                return self._graph_helper().get_list_columns(self.site_url, list_title)
            except Exception as graph_e:
                raise ToolException(f"Get list columns failed: {graph_e}") from graph_e

    def create_list_item(self, list_title: str, fields: dict):
        """Create a new item in a SharePoint list."""
        if not list_title:
            raise ToolException("list_title is required")
        if not fields or not isinstance(fields, dict):
            raise ToolException("fields must be a non-empty dictionary")
        try:
            lists = self._client.web.lists.get().execute_query()
            target_list = next(
                (l for l in lists
                 if l.properties.get('Title', '').lower() == list_title.lower()),
                None)
            if not target_list:
                raise RuntimeError(f"List '{list_title}' not found")

            new_item = target_list.add_item(fields).execute_query()
            result = {
                'id': new_item.properties.get('Id', ''),
                'fields': new_item.properties,
            }
            logging.info("Created list item %s in list '%s'", result['id'], list_title)
            return result
        except Exception as base_e:
            logging.warning(
                "REST API failed for create_list_item: %s. Trying Graph API fallback.", base_e)
            try:
                graph_result = self._graph_helper().create_list_item(
                    self.site_url, list_title, fields)
                logging.info("Created list item via Graph API: %s", graph_result.get('id'))
                return graph_result
            except Exception as graph_e:
                raise ToolException(f"Create list item failed: {graph_e}") from graph_e

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
            all_libraries = (
                self._client.web.lists
                .filter("BaseTemplate eq 101 and Title ne 'Form Templates' "
                        "and Title ne 'Site Assets' and Title ne 'Style Library'")
                .get().execute_query()
            )
            result = []
            limit_files = limit_files or 100

            site_segments = [s for s in self.site_url.strip('/').split('/') if s][-2:]
            full_path_prefix = '/'.join(site_segments)

            for lib in all_libraries:
                library_type = decode_sharepoint_string(lib.properties["EntityTypeName"])
                if form_name and form_name.lower() != library_type.lower():
                    continue

                target_folder_url = library_type
                if folder_name:
                    folder_path = folder_name.strip('/')
                    expected_prefix = f'{full_path_prefix}/{library_type}'
                    if folder_path.startswith(full_path_prefix):
                        if folder_path.startswith(expected_prefix):
                            target_folder_url = folder_path.removeprefix(
                                f'{full_path_prefix}/')
                        else:
                            continue
                    else:
                        target_folder_url = f"{library_type}/{folder_name}"

                files = (
                    self._client.web
                    .get_folder_by_server_relative_path(target_folder_url)
                    .get_files(True).execute_query()
                )
                for file in files:
                    if f"{library_type}/Forms" in file.properties['ServerRelativeUrl']:
                        continue
                    if len(result) >= limit_files:
                        break
                    result.append({
                        'Name': file.properties['Name'],
                        'Path': file.properties['ServerRelativeUrl'],
                        'Created': file.properties['TimeCreated'],
                        'Modified': file.properties['TimeLastModified'],
                        'Link': file.properties['LinkingUrl'],
                        'id': file.properties['UniqueId'],
                    })
            return result if result else ToolException(
                "Can not get files or folder is empty. "
                "Please, double check folder name and read permissions.")
        except Exception as e:
            try:
                files = self._graph_helper().get_files_list(
                    self.site_url, folder_name, limit_files)
                return files
            except Exception as graph_e:
                logging.error("Failed to load files via REST: %s", e)
                logging.error("Failed to load files via Graph API: %s", graph_e)
                return ToolException(
                    f"Can not get files. Please, double check folder name and "
                    f"read permissions: {e} and {graph_e}")

    def read_file(self, path: str, is_capture_image: bool = False,
                  page_number: Optional[int] = None, sheet_name: Optional[str] = None,
                  excel_by_sheets: bool = False):
        """Reads file located at the specified server-relative path."""
        from ..utils.content_parser import parse_file_content
        try:
            file = self._client.web.get_file_by_server_relative_path(path)
            self._client.load(file).execute_query()
            file_content = file.read()
            file_name = file.name
            self._client.execute_query()
        except Exception as e:
            try:
                file_content = self._graph_helper().get_file_content(self.site_url, path)
                file_name = path.split('/')[-1]
            except Exception as graph_e:
                logging.error(
                    "Failed to load file via REST (%s): %s. Check file name and path.", path, e)
                logging.error(
                    "Failed to load file via Graph API (%s): %s.", path, graph_e)
                return ToolException(
                    f"File not found. Please, check file name and path: {e} and {graph_e}")

        return parse_file_content(
            file_name=file_name,
            file_content=file_content,
            is_capture_image=is_capture_image,
            page_number=page_number,
            sheet_name=sheet_name,
            excel_by_sheets=excel_by_sheets,
            llm=self.llm,
        )

    def load_file_content_in_bytes(self, path: str) -> bytes:
        try:
            file = self._client.web.get_file_by_server_relative_path(path)
            self._client.load(file).execute_query()
            file_content = file.read()
            self._client.execute_query()
            return file_content
        except Exception:
            return self._graph_helper().get_file_content(self.site_url, path)

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

        try:
            result = self._graph_helper().upload_file_to_library(
                site_url=self.site_url,
                folder_path=folder_path,
                filename=actual_filename,
                file_bytes=file_bytes,
                replace=replace,
            )
            logging.info("File '%s' uploaded successfully to '%s'", actual_filename, folder_path)
            return result
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
            target_list = self._client.web.lists.get_by_title(list_title)
            self._client.load(target_list)
            self._client.execute_query()

            list_item = target_list.get_item_by_id(item_id)
            self._client.load(list_item)
            self._client.execute_query()

            attachments = list_item.attachment_files
            self._client.load(attachments)
            self._client.execute_query()

            existing = next(
                (a for a in attachments
                 if a.properties.get('FileName', '').lower() == actual_filename.lower()),
                None)
            if existing:
                if not replace:
                    raise ToolException(
                        f"Attachment '{actual_filename}' already exists on list item "
                        f"{item_id}. Set replace=True to overwrite.")
                existing.delete_object()
                self._client.execute_query()

            file_object = BytesIO(file_bytes)
            file_object.name = actual_filename
            attachment = list_item.attachment_files.upload(file_object).execute_query()
            result = {
                'id': attachment.properties.get('ServerRelativeUrl', ''),
                'name': actual_filename,
                'size': len(file_bytes),
            }
            logging.info(
                "Attachment '%s' added to list '%s' item %d",
                actual_filename, list_title, item_id)
            return result
        except ToolException:
            raise
        except Exception as e:
            logging.error("Failed to add attachment via REST: %s", e)
            raise ToolException(f"Attachment failed: {e}")

