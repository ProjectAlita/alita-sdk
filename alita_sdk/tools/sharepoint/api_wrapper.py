"""SharePoint toolkit facade.

Authentication precedence (evaluated in order):
1. ``token`` **+** ``scopes``  → :class:`~graph_wrapper.SharepointGraphWrapper`
   (delegated Graph API access — user-context token obtained via Azure AD OAuth)
2. ``client_id`` + ``client_secret``  → :class:`~rest_wrapper.SharepointRestWrapper`
   (app-credentials / ACS flow via office365-rest-python-client)
3. ``token`` only  → :class:`~rest_wrapper.SharepointRestWrapper`
   (plain bearer token, no Graph scopes, existing behaviour preserved)
"""
import logging
import re
from typing import Optional, Generator, List, Any

from langchain_core.documents import Document
from langchain_core.tools import ToolException
from pydantic import Field, PrivateAttr, create_model, model_validator, SecretStr

from .base_wrapper import BaseSharepointWrapper
from .graph_wrapper import SharepointGraphWrapper
from .rest_wrapper import SharepointRestWrapper
from ..non_code_indexer_toolkit import NonCodeIndexerToolkit
from ...runtime.utils.utils import IndexerKeywords

# ------------------------------------------------------------------ #
#  Pydantic tool-input schemas (unchanged)                            #
# ------------------------------------------------------------------ #

NoInput = create_model("NoInput")

ReadList = create_model(
    "ReadList",
    list_title=(str, Field(description="Name of a Sharepoint list to be read.")),
    limit=(Optional[int], Field(
        description="Limit (maximum number) of list items to be returned",
        default=1000, gt=0))
)

GetFiles = create_model(
    "GetFiles",
    folder_name=(Optional[str], Field(
        description="Folder name to get list of the files.", default=None)),
    form_name=(Optional[str], Field(
        description="Form (Document Library) name to filter files. "
                    "If specified, only files from this form will be returned. "
                    "Example: 'siblingdir' or 'SharedDocuments'.", default=None)),
    limit_files=(Optional[int], Field(
        description="Limit (maximum number) of files to be returned."
                    "Can be called with synonyms, such as First, Top, etc., "
                    "or can be reflected just by a number for example 'Top 10 files'. "
                    "Use default value if not specified in a query WITH NO EXTRA "
                    "CONFIRMATION FROM A USER", default=100, gt=0)),
)

ReadDocument = create_model(
    "ReadDocument",
    path=(str, Field(
        description="Contains the server-relative path of a document for reading.")),
    is_capture_image=(Optional[bool], Field(
        description="Determines is pictures in the document should be recognized.",
        default=False)),
    page_number=(Optional[int], Field(
        description="Specifies which page to read. "
                    "If it is None, then full document will be read.",
        default=None)),
    sheet_name=(Optional[str], Field(
        description="Specifies which sheet to read. "
                    "If it is None, then full document will be read.",
        default=None))
)

UploadFile = create_model(
    "UploadFile",
    folder_path=(str, Field(
        description="Server-relative folder path for upload "
                    "(e.g., '/sites/MySite/Shared Documents/folder')")),
    filepath=(Optional[str], Field(
        description="File path in format /{bucket}/{filename} from artifact storage. "
                    "Either filepath or filedata must be provided.", default=None)),
    filedata=(Optional[str], Field(
        description="String content to upload as a file. "
                    "Either filepath or filedata must be provided.", default=None)),
    filename=(Optional[str], Field(
        description="Target filename. Required when using filedata, optional when "
                    "using filepath (uses original filename if not specified).",
        default=None)),
    replace=(Optional[bool], Field(
        description="If True, overwrite existing file. "
                    "If False, raise error if file already exists.",
        default=True))
)

AddAttachmentToListItem = create_model(
    "AddAttachmentToListItem",
    list_title=(str, Field(description="Name of the SharePoint list")),
    item_id=(int, Field(
        description="Internal item ID (not the display ID) to attach file to")),
    filepath=(Optional[str], Field(
        description="File path in format /{bucket}/{filename} from artifact storage. "
                    "Either filepath or filedata must be provided.", default=None)),
    filedata=(Optional[str], Field(
        description="String content to attach as a file. "
                    "Either filepath or filedata must be provided.", default=None)),
    filename=(Optional[str], Field(
        description="Attachment filename. Required when using filedata, optional when "
                    "using filepath (uses original filename if not specified).",
        default=None)),
    replace=(Optional[bool], Field(
        description="If True, delete existing attachment with same name before adding. "
                    "If False, raise error if attachment already exists.",
        default=True))
)

GetListColumns = create_model(
    "GetListColumns",
    list_title=(str, Field(
        description="Title of the SharePoint list to get column metadata for"))
)

CreateListItem = create_model(
    "CreateListItem",
    list_title=(str, Field(
        description="Title of the SharePoint list to create an item in")),
    fields=(dict, Field(
        description="Dictionary of field name -> value pairs. "
                    "Use get_list_columns() first to discover available fields, "
                    "required fields, and valid choice values. "
                    "Title field is typically required. "
                    "For choice fields, value must match one of the allowed choices exactly. "
                    "For dateTime fields, use ISO 8601 format (e.g., '2026-02-01T00:00:00Z')."))
)


# ------------------------------------------------------------------ #
#  Main wrapper — factory + NonCodeIndexerToolkit integration         #
# ------------------------------------------------------------------ #

class SharepointApiWrapper(NonCodeIndexerToolkit):
    """Factory wrapper that selects the correct SharePoint backend at init time.

    Authentication precedence:
    1. ``token`` **+** ``scopes``  → :class:`SharepointGraphWrapper`
       (delegated Graph API — user-context access)
    2. ``client_id`` + ``client_secret``  → :class:`SharepointRestWrapper`
       (app credentials via office365-rest-python-client)
    3. ``token`` only  → :class:`SharepointRestWrapper`
       (REST token without Graph scopes — legacy behaviour)
    """

    site_url: str
    client_id: Optional[str] = None
    client_secret: Optional[SecretStr] = None
    token: Optional[SecretStr] = None
    scopes: Optional[List[str]] = Field(
        default=None,
        description="OAuth scopes for delegated Graph API access. "
                    "When provided together with *token*, activates the "
                    "Graph API backend (SharepointGraphWrapper).")
    alita: Any = None
    _backend: BaseSharepointWrapper = PrivateAttr()

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        site_url = values['site_url']
        client_id = values.get('client_id')
        raw_secret = values.get('client_secret')
        raw_token = values.get('token')
        scopes = values.get('scopes')

        # Unwrap SecretStr → plain text for internal use
        token_plain = (raw_token.get_secret_value()
                       if hasattr(raw_token, 'get_secret_value') else raw_token)
        secret_plain = (raw_secret.get_secret_value()
                        if hasattr(raw_secret, 'get_secret_value') else raw_secret)

        if token_plain and scopes:
            # ── Delegated Graph API path ──────────────────────────────
            logging.info(
                "SharePoint: using Graph API wrapper (delegated access, token + scopes).")
            cls._backend = SharepointGraphWrapper(
                site_url=site_url,
                token=token_plain,
                scopes=scopes,
            )
        elif client_id and secret_plain:
            # ── App-credential REST path ──────────────────────────────
            try:
                from office365.runtime.auth.client_credential import ClientCredential
                from office365.sharepoint.client_context import ClientContext
            except ImportError:
                raise ImportError(
                    "`office365` package not found, please run "
                    "`pip install office365-rest-python-client`")
            credentials = ClientCredential(client_id, secret_plain)
            office_client = ClientContext(site_url).with_credentials(credentials)
            logging.info(
                "SharePoint: using REST wrapper (app credentials).")
            cls._backend = SharepointRestWrapper(
                client=office_client,
                site_url=site_url,
                client_id=client_id,
                client_secret=secret_plain,
            )
        elif token_plain:
            # ── REST wrapper with plain bearer token (no Graph scopes) ─
            try:
                from office365.sharepoint.client_context import ClientContext
            except ImportError:
                raise ImportError(
                    "`office365` package not found, please run "
                    "`pip install office365-rest-python-client`")
            office_client = ClientContext(site_url).with_access_token(
                lambda: type('Token', (), {
                    'tokenType': 'Bearer',
                    'accessToken': token_plain,
                })())
            logging.info(
                "SharePoint: using REST wrapper (bearer token, no Graph scopes).")
            cls._backend = SharepointRestWrapper(
                client=office_client,
                site_url=site_url,
                client_id=client_id,
                client_secret=secret_plain,
            )
        else:
            raise ToolException(
                "Authentication error: provide either "
                "(token + scopes) for delegated Graph API access, "
                "(client_id + client_secret) for app-credentials access, or "
                "a token alone for REST bearer-token access.")

        logging.info("Successfully authenticated to SharePoint.")
        return super().validate_toolkit(values)

    # ------------------------------------------------------------------ #
    #  Backend injection helper                                            #
    # ------------------------------------------------------------------ #

    def _sync_backend_context(self) -> None:
        """Push current alita / llm references into the backend instance."""
        self._backend.alita = self.alita
        self._backend.llm = getattr(self, 'llm', None)

    # ------------------------------------------------------------------ #
    #  Lists — delegates to backend                                       #
    # ------------------------------------------------------------------ #

    def read_list(self, list_title: str, limit: int = 1000):
        """ Reads a specified List in sharepoint site. Number of list items is limited by limit (default is 1000). """
        self._sync_backend_context()
        return self._backend.read_list(list_title, limit)

    def get_lists(self):
        """Returns all SharePoint lists available on the site with their titles, IDs, and descriptions."""
        self._sync_backend_context()
        return self._backend.get_lists()

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
        self._sync_backend_context()
        return self._backend.get_list_columns(list_title)

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
        self._sync_backend_context()
        return self._backend.create_list_item(list_title, fields)

    # ------------------------------------------------------------------ #
    #  Files — delegates to backend                                       #
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
        self._sync_backend_context()
        return self._backend.get_files_list(folder_name, limit_files, form_name)

    def read_file(self, path: str,
                  is_capture_image: bool = False,
                  page_number: Optional[int] = None,
                  sheet_name: Optional[str] = None,
                  excel_by_sheets: bool = False):
        """ Reads file located at the specified server-relative path. """
        self._sync_backend_context()
        return self._backend.read_file(
            path, is_capture_image, page_number, sheet_name, excel_by_sheets)

    def upload_file(self, folder_path: str, filepath: Optional[str] = None,
                    filedata: Optional[str] = None, filename: Optional[str] = None,
                    replace: bool = True):
        """Upload file to SharePoint document library.

        Supports both artifact-based and direct content uploads. Files ≤4MB use simple PUT,
        larger files use chunked upload sessions (5MB chunks).

        Args:
            folder_path: Server-relative folder path (e.g., '/sites/MySite/Shared Documents/folder')
            filepath: File path in format /{bucket}/{filename} from artifact storage (mutually exclusive with filedata)
            filedata: String content to upload as a file (mutually exclusive with filepath)
            filename: Target filename. Required with filedata, optional with filepath
            replace: If True, overwrite existing file. If False, raise error on conflict

        Returns:
            dict with {id, webUrl, path, size, mime_type} or string with upload confirmation
        """
        self._sync_backend_context()
        return self._backend.upload_file(folder_path, filepath, filedata, filename, replace)

    def add_attachment_to_list_item(self, list_title: str, item_id: int,
                                    filepath: Optional[str] = None,
                                    filedata: Optional[str] = None,
                                    filename: Optional[str] = None,
                                    replace: bool = True):
        """Add attachment to SharePoint list item.

        Supports both artifact-based and direct content uploads.

        Args:
            list_title: Name of the SharePoint list
            item_id: Internal item ID (not the display ID)
            filepath: File path in format /{bucket}/{filename} from artifact storage (mutually exclusive with filedata)
            filedata: String content to attach as a file (mutually exclusive with filepath)
            filename: Attachment filename. Required with filedata, optional with filepath
            replace: If True, delete existing attachment with same name. If False, raise error on conflict

        Returns:
            dict with {id, name, size} or string with attachment confirmation
        """
        self._sync_backend_context()
        return self._backend.add_attachment_to_list_item(
            list_title, item_id, filepath, filedata, filename, replace)

    # ------------------------------------------------------------------ #
    #  Indexer support                                                     #
    # ------------------------------------------------------------------ #

    def _index_tool_params(self):
        return {
            'limit_files': (Optional[int], Field(
                description="Limit (maximum number) of files to be returned. "
                            "Can be called with synonyms, such as First, Top, etc., "
                            "or can be reflected just by a number for example 'Top 10 files'. "
                            "Use default value if not specified in a query WITH NO EXTRA "
                            "CONFIRMATION FROM A USER",
                default=1000, ge=0)),
            'include_extensions': (Optional[List[str]], Field(
                description="List of file extensions to include when processing: "
                            "i.e. ['*.png', '*.jpg']. "
                            "If empty, all files will be processed (except skip_extensions).",
                default=[])),
            'skip_extensions': (Optional[List[str]], Field(
                description="List of file extensions to skip when processing: "
                            "i.e. ['*.png', '*.jpg']",
                default=[])),
            'path': (Optional[str], Field(
                description="Folder path. "
                            "Accepts either a full server-relative path "
                            "(e.g., '/sites/SiteName/...') or a relative path. "
                            "If a relative path is provided, the search will be "
                            "performed recursively under 'Shared Documents' and "
                            "other private libraries.",
                default=None)),
        }

    def _base_loader(self, **kwargs) -> Generator[Document, None, None]:
        self._sync_backend_context()
        self._log_tool_event(
            message="Starting SharePoint files extraction", tool_name="loader")
        try:
            all_files = self.get_files_list(
                kwargs.get('path'), kwargs.get('limit_files', 10000))
            self._log_tool_event(
                message="List of the files has been extracted", tool_name="loader")
        except Exception as e:
            raise ToolException(f"Unable to extract files: {e}")

        include_extensions = kwargs.get('include_extensions', [])
        skip_extensions = kwargs.get('skip_extensions', [])
        self._log_tool_event(
            message=f"Files filtering started. "
                    f"Include extensions: {include_extensions}. "
                    f"Skip extensions: {skip_extensions}",
            tool_name="loader")

        total_files = len(all_files) if isinstance(all_files, list) else 0
        filtered_files_count = 0
        for file in all_files:
            filtered_files_count += 1
            if filtered_files_count % 10 == 0 or filtered_files_count == total_files:
                self._log_tool_event(
                    message=f"Files filtering progress: "
                            f"{filtered_files_count}/{total_files}",
                    tool_name="loader")
            file_name = file.get('Name', '')

            if any(re.match(
                    re.escape(pattern).replace(r'\*', '.*') + '$',
                    file_name, re.IGNORECASE)
                   for pattern in skip_extensions):
                continue

            if include_extensions and not any(
                    re.match(
                        re.escape(pattern).replace(r'\*', '.*') + '$',
                        file_name, re.IGNORECASE)
                    for pattern in include_extensions):
                continue

            metadata = {
                ("updated_on" if k == "Modified" else k): str(v)
                for k, v in file.items()
            }
            yield Document(page_content="", metadata=metadata)

    def _extend_data(self, documents: Generator[Document, None, None]):
        self._sync_backend_context()
        for document in documents:
            try:
                document.metadata[IndexerKeywords.CONTENT_IN_BYTES.value] = \
                    self._backend.load_file_content_in_bytes(document.metadata['Path'])
                document.metadata[IndexerKeywords.CONTENT_FILE_NAME.value] = \
                    document.metadata['Name']
                yield document
            except Exception as e:
                logging.error(
                    "Failed while parsing the file '%s': %s",
                    document.metadata['Path'], e)
                yield document

    # ------------------------------------------------------------------ #
    #  Tool registry                                                       #
    # ------------------------------------------------------------------ #

    def get_available_tools(self):
        return super().get_available_tools() + [
            {
                "name": "read_list",
                "description": self.read_list.__doc__,
                "args_schema": ReadList,
                "ref": self.read_list,
            },
            {
                "name": "get_lists",
                "description": self.get_lists.__doc__,
                "args_schema": NoInput,
                "ref": self.get_lists,
            },
            {
                "name": "get_list_columns",
                "description": self.get_list_columns.__doc__,
                "args_schema": GetListColumns,
                "ref": self.get_list_columns,
            },
            {
                "name": "create_list_item",
                "description": self.create_list_item.__doc__,
                "args_schema": CreateListItem,
                "ref": self.create_list_item,
            },
            {
                "name": "get_files_list",
                "description": self.get_files_list.__doc__,
                "args_schema": GetFiles,
                "ref": self.get_files_list,
            },
            {
                "name": "read_document",
                "description": self.read_file.__doc__,
                "args_schema": ReadDocument,
                "ref": self.read_file,
            },
            {
                "name": "upload_file",
                "description": self.upload_file.__doc__,
                "args_schema": UploadFile,
                "ref": self.upload_file,
            },
            {
                "name": "add_attachment_to_list_item",
                "description": self.add_attachment_to_list_item.__doc__,
                "args_schema": AddAttachmentToListItem,
                "ref": self.add_attachment_to_list_item,
            },
        ]

