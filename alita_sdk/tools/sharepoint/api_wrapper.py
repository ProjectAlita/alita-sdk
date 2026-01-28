import logging
import re
from io import BytesIO
from typing import Optional, Generator, List, Any

from langchain_core.documents import Document
from langchain_core.tools import ToolException
from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.client_context import ClientContext
from pydantic import Field, PrivateAttr, create_model, model_validator, SecretStr

from .utils import decode_sharepoint_string
from ..non_code_indexer_toolkit import NonCodeIndexerToolkit
from ..utils import get_file_bytes_from_artifact, detect_mime_type
from ..utils.content_parser import parse_file_content
from ...runtime.utils.utils import IndexerKeywords

NoInput = create_model(
    "NoInput"
)

ReadList = create_model(
    "ReadList",
    list_title=(str, Field(description="Name of a Sharepoint list to be read.")),
    limit=(Optional[int], Field(description="Limit (maximum number) of list items to be returned", default=1000, gt=0))
)

GetFiles = create_model(
    "GetFiles",
    folder_name=(Optional[str], Field(description="Folder name to get list of the files.", default=None)),
    form_name=(Optional[str], Field(description="Form (Document Library) name to filter files. "
                                                "If specified, only files from this form will be returned. "
                                                "Example: 'siblingdir' or 'SharedDocuments'.", default=None)),
    limit_files=(Optional[int], Field(description="Limit (maximum number) of files to be returned."
                                                  "Can be called with synonyms, such as First, Top, etc., "
                                                  "or can be reflected just by a number for example 'Top 10 files'. "
                                                  "Use default value if not specified in a query WITH NO EXTRA "
                                                  "CONFIRMATION FROM A USER", default=100, gt=0)),
)

ReadDocument = create_model(
    "ReadDocument",
    path=(str, Field(description="Contains the server-relative path of a document for reading.")),
    is_capture_image=(Optional[bool], Field(description="Determines is pictures in the document should be recognized.", default=False)),
    page_number=(Optional[int], Field(description="Specifies which page to read. If it is None, then full document will be read.", default=None)),
    sheet_name=(Optional[str], Field(
                        description="Specifies which sheet to read. If it is None, then full document will be read.",
                        default=None))
)

UploadFile = create_model(
    "UploadFile",
    folder_path=(str, Field(description="Server-relative folder path for upload (e.g., '/sites/MySite/Shared Documents/folder')")),
    artifact_id=(Optional[str], Field(description="Artifact ID from artifact storage. Either artifact_id or filedata must be provided.", default=None)),
    filedata=(Optional[str], Field(description="String content to upload as a file. Either artifact_id or filedata must be provided.", default=None)),
    filename=(Optional[str], Field(description="Target filename. Required when using filedata, optional when using artifact_id (uses original filename if not specified).", default=None)),
    replace=(Optional[bool], Field(description="If True, overwrite existing file. If False, raise error if file already exists.", default=True))
)

AddAttachmentToListItem = create_model(
    "AddAttachmentToListItem",
    list_title=(str, Field(description="Name of the SharePoint list")),
    item_id=(int, Field(description="Internal item ID (not the display ID) to attach file to")),
    artifact_id=(Optional[str], Field(description="Artifact ID from artifact storage. Either artifact_id or filedata must be provided.", default=None)),
    filedata=(Optional[str], Field(description="String content to attach as a file. Either artifact_id or filedata must be provided.", default=None)),
    filename=(Optional[str], Field(description="Attachment filename. Required when using filedata, optional when using artifact_id (uses original filename if not specified).", default=None)),
    replace=(Optional[bool], Field(description="If True, delete existing attachment with same name before adding. If False, raise error if attachment already exists.", default=True))
)

GetListColumns = create_model(
    "GetListColumns",
    list_title=(str, Field(description="Title of the SharePoint list to get column metadata for"))
)

CreateListItem = create_model(
    "CreateListItem",
    list_title=(str, Field(description="Title of the SharePoint list to create an item in")),
    fields=(dict, Field(description="Dictionary of field name -> value pairs. Use get_list_columns() first to discover available fields, required fields, and valid choice values. Title field is typically required. For choice fields, value must match one of the allowed choices exactly. For dateTime fields, use ISO 8601 format (e.g., '2026-02-01T00:00:00Z')."))
)


class SharepointApiWrapper(NonCodeIndexerToolkit):
    site_url: str
    client_id: str = None
    client_secret: SecretStr = None
    token: SecretStr = None
    alita: Any = None
    _client: Optional[ClientContext] = PrivateAttr()  # Private attribute for the office365 client

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        try:
            from office365.runtime.auth.authentication_context import AuthenticationContext
            from office365.sharepoint.client_context import ClientContext
        except ImportError:
            raise ImportError(
                "`office365` package not found, please run "
               "`pip install office365-rest-python-client`"
            )

        site_url = values['site_url']
        client_id = values.get('client_id')
        client_secret = values.get('client_secret')
        token = values.get('token')

        try:
            if client_id and client_secret:
                credentials = ClientCredential(client_id, client_secret)
                cls._client = ClientContext(site_url).with_credentials(credentials)
                logging.info("Authenticated with secret id")
            elif token:
                cls._client = ClientContext(site_url).with_access_token(lambda: type('Token', (), {
                    'tokenType': 'Bearer',
                    'accessToken': token
                })())
                logging.info("Authenticated with token")
            else:
                raise ToolException("You have to define token or client id&secret.")
            logging.info("Successfully authenticated to SharePoint.")
        except Exception as e:
            logging.error(f"Failed to authenticate with SharePoint: {str(e)}")
        return super().validate_toolkit(values)

    def read_list(self, list_title, limit: int = 1000):
        """ Reads a specified List in sharepoint site. Number of list items is limited by limit (default is 1000). """
        try:
            target_list = self._client.web.lists.get_by_title(list_title)
            self._client.load(target_list)
            self._client.execute_query()
            items = target_list.items.top(limit).get().execute_query()
            logging.info("{0} items from sharepoint loaded successfully via SharePoint REST API.".format(len(items)))
            result = []
            for item in items:
                # TODO: Filter out internal/system fields (@odata.etag, AuthorLookupId, _ComplianceFlags, etc.)
                # to reduce LLM context pollution. Return only user-defined fields and essential metadata.
                result.append(item.properties)
            return result
        except Exception as base_e:
            logging.warning(f"Primary SharePoint REST list read failed: {base_e}. Attempting Graph API fallback.")
            # Attempt Graph API fallback
            try:
                from .authorization_helper import SharepointAuthorizationHelper
                auth_helper = SharepointAuthorizationHelper(
                    client_id=self.client_id,
                    client_secret=self.client_secret.get_secret_value() if self.client_secret else None,
                    tenant="",  # optional for graph api (derived inside helper)
                    scope="",  # optional for graph api
                    token_json="",  # not needed for client credentials flow here
                )
                graph_items = auth_helper.get_list_items(self.site_url, list_title, limit)
                if graph_items:
                    logging.info(f"{len(graph_items)} items from sharepoint loaded successfully via Graph API fallback.")
                    return graph_items
                else:
                    return ToolException("List appears empty or inaccessible via both REST and Graph APIs.")
            except Exception as graph_e:
                logging.error(f"Graph API fallback failed: {graph_e}")
                return ToolException(f"Cannot read list '{list_title}'. Check list name and permissions: {base_e} | {graph_e}")

    def get_lists(self):
        """Returns all SharePoint lists available on the site with their titles, IDs, and descriptions."""
        try:
            lists = self._client.web.lists.get().execute_query()
            logging.info(f"{len(lists)} lists loaded successfully via SharePoint REST API.")
            result = []
            for lst in lists:
                # Skip hidden system lists
                if lst.properties.get('Hidden', False):
                    continue
                result.append({
                    'Title': lst.properties.get('Title', ''),
                    'Id': lst.properties.get('Id', ''),
                    'Description': lst.properties.get('Description', ''),
                    'ItemCount': lst.properties.get('ItemCount', 0),
                    'BaseTemplate': lst.properties.get('BaseTemplate', 0)
                })
            return result
        except Exception as base_e:
            logging.warning(f"Primary SharePoint REST lists fetch failed: {base_e}. Attempting Graph API fallback.")
            # Attempt Graph API fallback
            try:
                from .authorization_helper import SharepointAuthorizationHelper
                auth_helper = SharepointAuthorizationHelper(
                    client_id=self.client_id,
                    client_secret=self.client_secret.get_secret_value() if self.client_secret else None,
                    tenant="",
                    scope="",
                    token_json="",
                )
                graph_lists = auth_helper.get_lists(self.site_url)
                if graph_lists:
                    logging.info(f"{len(graph_lists)} lists loaded successfully via Graph API fallback.")
                    return graph_lists
                else:
                    return ToolException("No lists found or inaccessible via both REST and Graph APIs.")
            except Exception as graph_e:
                logging.error(f"Graph API fallback failed: {graph_e}")
                return ToolException(f"Cannot retrieve lists. Check permissions: {base_e} | {graph_e}")

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
            # Try REST API first (primary method)
            logging.info(f"Getting columns for list '{list_title}' via REST API")
            
            lists = self._client.web.lists.get().execute_query()
            target_list = None
            
            for lst in lists:
                if lst.properties.get('Title', '').lower() == list_title.lower():
                    target_list = lst
                    break
            
            if not target_list:
                raise RuntimeError(f"List '{list_title}' not found")
            
            # Get fields/columns
            fields = target_list.fields.get().execute_query()
            
            result = []
            for field in fields:
                props = field.properties
                
                # Skip hidden fields
                if props.get('Hidden', False):
                    continue
                
                # Skip read-only fields
                if props.get('ReadOnlyField', False):
                    continue
                
                # Skip lookup fields
                field_type = props.get('TypeAsString', '').lower()
                if 'lookup' in field_type:
                    continue
                
                column_info = {
                    'name': props.get('InternalName', props.get('Title', '')),
                    'displayName': props.get('Title', props.get('InternalName', '')),
                    'columnType': 'text',  # default
                    'required': props.get('Required', False)
                }
                
                # Map SharePoint field types to simplified types
                if field_type == 'text' or field_type == 'note':
                    column_info['columnType'] = 'text'
                elif field_type == 'number' or field_type == 'currency':
                    column_info['columnType'] = 'number'
                elif field_type == 'boolean':
                    column_info['columnType'] = 'boolean'
                elif field_type == 'datetime':
                    column_info['columnType'] = 'dateTime'
                elif field_type == 'choice' or field_type == 'multichoice':
                    column_info['columnType'] = 'choice'
                    choices = props.get('Choices', [])
                    if choices:
                        column_info['choice'] = {'choices': choices}
                
                result.append(column_info)
            
            logging.info(f"Retrieved {len(result)} columns for list '{list_title}'")
            return result
            
        except Exception as base_e:
            # Fallback to Graph API
            logging.warning(f"REST API failed for get_list_columns: {base_e}. Trying Graph API...")
            
            try:
                from .authorization_helper import SharepointAuthorizationHelper
                auth_helper = SharepointAuthorizationHelper(
                    client_id=self.client_id,
                    client_secret=self.client_secret.get_secret_value() if self.client_secret else None,
                    tenant="",
                    scope="",
                    token_json="",
                )
                
                graph_columns = auth_helper.get_list_columns(self.site_url, list_title)
                logging.info(f"Retrieved {len(graph_columns)} columns via Graph API")
                return graph_columns
                
            except Exception as graph_e:
                logging.error(f"Both REST and Graph API failed for get_list_columns: {graph_e}")
                raise ToolException(f"Get list columns failed: {str(graph_e)}")

    def create_list_item(self, list_title: str, fields: dict):
        """Create a new item in a SharePoint list.
        
        Args:
            list_title: The title of the SharePoint list
            fields: Dictionary of field name -> value pairs
            
        Returns:
            Dictionary with created item metadata including:
            - id: Item ID
            - fields: All field values including system fields
            - webUrl: URL to view the item (Graph API only)
            
        Note: Use get_list_columns() first to discover available fields,
        required fields, and valid choice values. Title field is typically required.
        
        Example:
            create_list_item(
                list_title="Tasks",
                fields={
                    "Title": "New Task",
                    "Status": "In Progress",
                    "Priority": "High"
                }
            )
        """
        if not list_title:
            raise ToolException("list_title is required")
        if not fields or not isinstance(fields, dict):
            raise ToolException("fields must be a non-empty dictionary")
        
        try:
            # Try REST API first (primary method)
            logging.info(f"Creating list item in '{list_title}' via REST API")
            
            lists = self._client.web.lists.get().execute_query()
            target_list = None
            
            for lst in lists:
                if lst.properties.get('Title', '').lower() == list_title.lower():
                    target_list = lst
                    break
            
            if not target_list:
                raise RuntimeError(f"List '{list_title}' not found")
            
            # Create the item
            new_item = target_list.add_item(fields).execute_query()
            
            # TODO: Filter out internal/system fields (@odata.etag, AuthorLookupId, _ComplianceFlags, etc.)
            # to reduce LLM context pollution. Return only id, user-defined fields, and essential metadata.
            result = {
                'id': new_item.properties.get('Id', ''),
                'fields': new_item.properties
            }
            
            logging.info(f"Created list item with ID {result['id']} in list '{list_title}'")
            return result
            
        except Exception as base_e:
            # Fallback to Graph API
            logging.warning(f"REST API failed for create_list_item: {base_e}. Trying Graph API...")
            
            try:
                from .authorization_helper import SharepointAuthorizationHelper
                auth_helper = SharepointAuthorizationHelper(
                    client_id=self.client_id,
                    client_secret=self.client_secret.get_secret_value() if self.client_secret else None,
                    tenant="",
                    scope="",
                    token_json="",
                )
                
                graph_result = auth_helper.create_list_item(self.site_url, list_title, fields)
                logging.info(f"Created list item via Graph API with ID {graph_result['id']}")
                return graph_result
                
            except Exception as graph_e:
                logging.error(f"Both REST and Graph API failed for create_list_item: {graph_e}")
                raise ToolException(f"Create list item failed: {str(graph_e)}")

    def get_files_list(self, folder_name: str = None, limit_files: int = 100, form_name: Optional[str] = None):
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
            # exclude default system libraries like 'Form Templates', 'Site Assets', 'Style Library'
            all_libraries = self._client.web.lists.filter("BaseTemplate eq 101 and Title ne 'Form Templates' and Title ne 'Site Assets' and Title ne 'Style Library'").get().execute_query()
            result = []
            if not limit_files:
                limit_files = 100
            #
            site_segments = [seg for seg in self.site_url.strip('/').split('/') if seg][-2:]
            full_path_prefix = '/'.join(site_segments)
            #
            for lib in all_libraries:
                library_type = decode_sharepoint_string(lib.properties["EntityTypeName"])
                if form_name:
                    # if form_name is specified, only files from specified form will be returned
                    if form_name.lower() != library_type.lower():
                        continue
                target_folder_url = library_type
                if folder_name:
                    folder_path = folder_name.strip('/')
                    expected_prefix = f'{full_path_prefix}/{library_type}'
                    if folder_path.startswith(full_path_prefix):
                        if folder_path.startswith(expected_prefix):
                            target_folder_url = folder_path.removeprefix(f'{full_path_prefix}/')
                        else:
                            # ignore full path folder which is not targeted to current library
                            continue
                    else:
                        target_folder_url = f"{library_type}/{folder_name}"
                #
                files = (self._client.web.get_folder_by_server_relative_path(target_folder_url)
                         .get_files(True)
                         .execute_query())
                #
                for file in files:
                    if f"{library_type}/Forms" in file.properties['ServerRelativeUrl']:
                        # skip files from system folder "Forms"
                        continue
                    if len(result) >= limit_files:
                        break
                    temp_props = {
                        'Name': file.properties['Name'],
                        'Path': file.properties['ServerRelativeUrl'],
                        'Created': file.properties['TimeCreated'],
                        'Modified': file.properties['TimeLastModified'],
                        'Link': file.properties['LinkingUrl'],
                        'id': file.properties['UniqueId']
                    }
                    result.append(temp_props)
            return result if result else ToolException("Can not get files or folder is empty. Please, double check folder name and read permissions.")
        except Exception as e:
            # attempt to get via graph api
            try:
                # attempt to get files via graph api
                from .authorization_helper import SharepointAuthorizationHelper
                auth_helper = SharepointAuthorizationHelper(
                    client_id=self.client_id,
                    client_secret=self.client_secret.get_secret_value(),
                    tenant="", # optional for graph api
                    scope="", # optional for graph api
                    token_json="", # optional for graph api
                )
                files = auth_helper.get_files_list(self.site_url, folder_name, limit_files)
                return files
            except Exception as graph_e:
                logging.error(f"Failed to load files from sharepoint via base api: {e}")
                logging.error(f"Failed to load files from sharepoint via graph api: {graph_e}")
                return ToolException(f"Can not get files. Please, double check folder name and read permissions: {e} and {graph_e}")

    def read_file(self, path,
                  is_capture_image: bool = False,
                  page_number: int = None,
                  sheet_name: str = None,
                  excel_by_sheets: bool = False) -> str | dict | ToolException:
        """ Reads file located at the specified server-relative path. """
        try:
            file = self._client.web.get_file_by_server_relative_path(path)
            self._client.load(file).execute_query()

            file_content = file.read()
            file_name = file.name
            self._client.execute_query()
        except Exception as e:
            # attempt to get via graph api
            try:
                # attempt to get files via graph api
                from .authorization_helper import SharepointAuthorizationHelper
                auth_helper = SharepointAuthorizationHelper(
                    client_id=self.client_id,
                    client_secret=self.client_secret.get_secret_value(),
                    tenant="",  # optional for graph api
                    scope="",  # optional for graph api
                    token_json="",  # optional for graph api
                )
                file_content = auth_helper.get_file_content(self.site_url, path)
                file_name = path.split('/')[-1]
            except Exception as graph_e:
                logging.error(f"Failed to load file from SharePoint via base api: {e}. Path: {path}. Please, double check file name and path.")
                logging.error(f"Failed to load file from SharePoint via graph api: {graph_e}. Path: {path}. Please, double check file name and path.")
                return ToolException(f"File not found. Please, check file name and path: {e} and {graph_e}")
        #
        return parse_file_content(file_name=file_name,
                                  file_content=file_content,
                                  is_capture_image=is_capture_image,
                                  page_number=page_number,
                                  sheet_name=sheet_name,
                                  excel_by_sheets=excel_by_sheets,
                                  llm=self.llm)

    def _index_tool_params(self):
        return {
            'limit_files': (Optional[int], Field(
                description="Limit (maximum number) of files to be returned. Can be called with synonyms, "
                            "such as First, Top, etc., or can be reflected just by a number for example 'Top 10 files'. "
                            "Use default value if not specified in a query WITH NO EXTRA CONFIRMATION FROM A USER",
                default=1000, ge=0)),
            'include_extensions': (Optional[List[str]], Field(
                description="List of file extensions to include when processing: i.e. ['*.png', '*.jpg']. "
                            "If empty, all files will be processed (except skip_extensions).",
                default=[])),
            'skip_extensions': (Optional[List[str]], Field(
                description="List of file extensions to skip when processing: i.e. ['*.png', '*.jpg']",
                default=[])),
            'path': (Optional[str], Field(
                description="Folder path. "
                            "Accepts either a full server-relative path (e.g., '/sites/SiteName/...') or a relative path. "
                            "If a relative path is provided, the search will be performed recursively under 'Shared Documents' and other private libraries.",
                default=None)),
        }

    def _base_loader(self, **kwargs) -> Generator[Document, None, None]:

        self._log_tool_event(message="Starting SharePoint files extraction", tool_name="loader")
        try:
            all_files = self.get_files_list(kwargs.get('path'), kwargs.get('limit_files', 10000))
            self._log_tool_event(message="List of the files has been extracted", tool_name="loader")
        except Exception as e:
            raise ToolException(f"Unable to extract files: {e}")

        include_extensions = kwargs.get('include_extensions', [])
        skip_extensions = kwargs.get('skip_extensions', [])
        self._log_tool_event(message=f"Files filtering started. Include extensions: {include_extensions}. "
                                     f"Skip extensions: {skip_extensions}", tool_name="loader")
        # show the progress of filtering
        total_files = len(all_files) if isinstance(all_files, list) else 0
        filtered_files_count = 0
        for file in all_files:
            filtered_files_count += 1
            if filtered_files_count % 10 == 0 or filtered_files_count == total_files:
                self._log_tool_event(message=f"Files filtering progress: {filtered_files_count}/{total_files}", tool_name="loader")
            file_name = file.get('Name', '')

            # Check if file should be skipped based on skip_extensions
            if any(re.match(re.escape(pattern).replace(r'\*', '.*') + '$', file_name, re.IGNORECASE)
                   for pattern in skip_extensions):
                continue

            # Check if file should be included based on include_extensions
            # If include_extensions is empty, process all files (that weren't skipped)
            if include_extensions and not (any(re.match(re.escape(pattern).replace(r'\*', '.*') + '$', file_name, re.IGNORECASE)
                        for pattern in include_extensions)):
                continue

            metadata = {
                ("updated_on" if k == "Modified" else k): str(v)
                for k, v in file.items()
            }
            yield Document(page_content="", metadata=metadata)

    def _extend_data(self, documents: Generator[Document, None, None]):
        for document in documents:
            try:
                document.metadata[IndexerKeywords.CONTENT_IN_BYTES.value] = self._load_file_content_in_bytes(document.metadata['Path'])
                document.metadata[IndexerKeywords.CONTENT_FILE_NAME.value] = document.metadata['Name']
                yield document
            except Exception as e:
                logging.error(f"Failed while parsing the file '{document.metadata['Path']}': {e}")
                yield document

    def _load_file_content_in_bytes(self, path):
        try:
            file = self._client.web.get_file_by_server_relative_path(path)
            self._client.load(file).execute_query()
            file_content = file.read()
            self._client.execute_query()
            #
            return file_content
        except Exception as e:
            # attempt to get via graph api
            from .authorization_helper import SharepointAuthorizationHelper
            auth_helper = SharepointAuthorizationHelper(
                client_id=self.client_id,
                client_secret=self.client_secret.get_secret_value(),
                tenant="",  # optional for graph api
                scope="",  # optional for graph api
                token_json="",  # optional for graph api
            )
            return auth_helper.get_file_content(self.site_url, path)

    def upload_file(self, folder_path: str, artifact_id: Optional[str] = None, 
                   filedata: Optional[str] = None, filename: Optional[str] = None, 
                   replace: bool = True):
        """Upload file to SharePoint document library.
        
        Supports both artifact-based and direct content uploads. Files ≤4MB use simple PUT,
        larger files use chunked upload sessions (5MB chunks).
        
        Args:
            folder_path: Server-relative folder path (e.g., '/sites/MySite/Shared Documents/folder')
            artifact_id: Artifact ID from artifact storage (mutually exclusive with filedata)
            filedata: String content to upload as a file (mutually exclusive with artifact_id)
            filename: Target filename. Required with filedata, optional with artifact_id
            replace: If True, overwrite existing file. If False, raise error on conflict
            
        Returns:
            dict with {id, webUrl, path, size, mime_type} or string with upload confirmation
        """
        # Validate inputs
        if not artifact_id and not filedata:
            raise ToolException("Either artifact_id or filedata must be provided")
        if artifact_id and filedata:
            raise ToolException("Cannot specify both artifact_id and filedata")
        if filedata and not filename:
            raise ToolException("filename is required when using filedata")
        
        # Resolve file content
        if artifact_id:
            file_bytes, artifact_filename = get_file_bytes_from_artifact(self.alita, artifact_id)
            actual_filename = filename or artifact_filename
        else:
            file_bytes = filedata.encode('utf-8')
            actual_filename = filename
        
        # Detect MIME type
        mime_type = detect_mime_type(file_bytes, actual_filename)
        
        try:
            # Attempt Graph API upload via helper
            from .authorization_helper import SharepointAuthorizationHelper
            auth_helper = SharepointAuthorizationHelper(
                client_id=self.client_id,
                client_secret=self.client_secret.get_secret_value() if self.client_secret else None,
                tenant="",
                scope="",
                token_json="",
            )
            
            result = auth_helper.upload_file_to_library(
                site_url=self.site_url,
                folder_path=folder_path,
                filename=actual_filename,
                file_bytes=file_bytes,
                replace=replace
            )
            
            logging.info(f"File '{actual_filename}' uploaded successfully to '{folder_path}'")
            return result
            
        except Exception as e:
            raise ToolException(f"Upload failed: {str(e)}") from None

    def add_attachment_to_list_item(self, list_title: str, item_id: int, 
                                    artifact_id: Optional[str] = None,
                                    filedata: Optional[str] = None, 
                                    filename: Optional[str] = None,
                                    replace: bool = True):
        """Add attachment to SharePoint list item.
        
        Supports both artifact-based and direct content uploads.
        
        Args:
            list_title: Name of the SharePoint list
            item_id: Internal item ID (not the display ID)
            artifact_id: Artifact ID from artifact storage (mutually exclusive with filedata)
            filedata: String content to attach as a file (mutually exclusive with artifact_id)
            filename: Attachment filename. Required with filedata, optional with artifact_id
            replace: If True, delete existing attachment with same name. If False, raise error on conflict
            
        Returns:
            dict with {id, name, size} or string with attachment confirmation
        """
        # Validate inputs
        if not artifact_id and not filedata:
            raise ToolException("Either artifact_id or filedata must be provided")
        if artifact_id and filedata:
            raise ToolException("Cannot specify both artifact_id and filedata")
        if filedata and not filename:
            raise ToolException("filename is required when using filedata")
        
        # Resolve file content
        if artifact_id:
            file_bytes, artifact_filename = get_file_bytes_from_artifact(self.alita, artifact_id)
            actual_filename = filename or artifact_filename
        else:
            file_bytes = filedata.encode('utf-8')
            actual_filename = filename
        
        try:
            # Use SharePoint REST API for list item attachments
            # Get the list and item (must load list first like in read_list method)
            target_list = self._client.web.lists.get_by_title(list_title)
            self._client.load(target_list)
            self._client.execute_query()
            
            list_item = target_list.get_item_by_id(item_id)
            self._client.load(list_item)
            self._client.execute_query()
            
            # Check for existing attachments with same name
            attachments = list_item.attachment_files
            self._client.load(attachments)
            self._client.execute_query()
            
            existing_attachment = None
            for att in attachments:
                if att.properties.get('FileName', '').lower() == actual_filename.lower():
                    existing_attachment = att
                    break
            
            if existing_attachment:
                if not replace:
                    raise ToolException(
                        f"Attachment '{actual_filename}' already exists on list item {item_id}. "
                        f"Set replace=True to overwrite."
                    )
                # Delete existing attachment
                existing_attachment.delete_object()
                self._client.execute_query()
            
            # Add new attachment using file-like object (office365-rest-python-client API requirement)
            # The upload() method expects a file object with .read() and .name attributes
            file_object = BytesIO(file_bytes)
            file_object.name = actual_filename  # Set filename attribute for API
            attachment = list_item.attachment_files.upload(file_object).execute_query()
            
            # Return attachment metadata
            result = {
                'id': attachment.properties.get('ServerRelativeUrl', ''),
                'name': actual_filename,
                'size': len(file_bytes)
            }
            
            logging.info(f"Attachment '{actual_filename}' added to list '{list_title}' item {item_id}")
            return result
            
        except Exception as e:
            logging.error(f"Failed to add attachment: {e}")
            raise ToolException(f"Attachment failed: {str(e)}")

    def get_available_tools(self):
        return super().get_available_tools() + [
            {
                "name": "read_list",
                "description": self.read_list.__doc__,
                "args_schema": ReadList,
                "ref": self.read_list
            },
            {
                "name": "get_lists",
                "description": self.get_lists.__doc__,
                "args_schema": NoInput,
                "ref": self.get_lists
            },
            {
                "name": "get_list_columns",
                "description": self.get_list_columns.__doc__,
                "args_schema": GetListColumns,
                "ref": self.get_list_columns
            },
            {
                "name": "create_list_item",
                "description": self.create_list_item.__doc__,
                "args_schema": CreateListItem,
                "ref": self.create_list_item
            },
            {
                "name": "get_files_list",
                "description": self.get_files_list.__doc__,
                "args_schema": GetFiles,
                "ref": self.get_files_list
            },
            {
                "name": "read_document",
                "description": self.read_file.__doc__,
                "args_schema": ReadDocument,
                "ref": self.read_file
            },
            {
                "name": "upload_file",
                "description": self.upload_file.__doc__,
                "args_schema": UploadFile,
                "ref": self.upload_file
            },
            {
                "name": "add_attachment_to_list_item",
                "description": self.add_attachment_to_list_item.__doc__,
                "args_schema": AddAttachmentToListItem,
                "ref": self.add_attachment_to_list_item
            }
        ]