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
import os
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
        description="Subfolder path to get list of files. When used alone, the document "
                    "library is resolved from the first path segment. When used together "
                    "with form_name, this is treated as a subfolder path relative to the "
                    "library identified by form_name (i.e. form_name pins the library, "
                    "folder_name navigates within it).", default=None)),
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
    include_extensions=(Optional[List[str]], Field(
        description="If provided, only files whose extension matches one of these values "
                    "are returned. Accepts 'pdf' or '.pdf' form; matched case-insensitively. "
                    "Example: ['pdf', 'docx'] or ['.pdf', '.docx'].",
        default=None)),
    skip_extensions=(Optional[List[str]], Field(
        description="If provided, files whose extension matches any of these values are "
                    "excluded. Accepts 'pdf' or '.pdf' form; matched case-insensitively. "
                    "Example: ['png', 'jpg'] or ['.png', '.jpg'].",
        default=None)),
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
        description=(
            "Server-relative folder path for upload, including the document-library name. "
            "Accepted formats:\n"
            "  - Default library with subfolder: '/sites/MySite/Shared Documents/folder'\n"
            "  - Non-default library with subfolder: '/sites/MySite/Alita_test/folder'\n"
            "  - Non-default library root: '/sites/MySite/Alita_test'\n"
            "The document-library segment (e.g. 'Shared Documents', 'Alita_test') is "
            "resolved automatically to the correct drive."
        )
    )),
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
#  OneNote input schemas                                              #
# ------------------------------------------------------------------ #

OnenoteGetNotebooksInput = create_model(
    "OnenoteGetNotebooksInput",
    select=(Optional[List[str]], Field(
        default=None,
        description=(
            "Optional list of fields to include in the response, e.g. ['id', 'displayName']. "
            "Omit (or pass null) to use the default field set. "
            "Pass an empty list [] to omit $select entirely and receive all fields."
        ),
    )),
)

OnenoteGetSectionsInput = create_model(
    "OnenoteGetSectionsInput",
    notebook_id=(str, Field(description="The ID of the notebook to list sections from.")),
    select=(Optional[List[str]], Field(
        default=None,
        description=(
            "Optional list of fields to include in the response, e.g. ['id', 'displayName']. "
            "Omit (or pass null) to use the default field set. "
            "Pass an empty list [] to omit $select entirely and receive all fields."
        ),
    )),
)

OnenoteGetPagesInput = create_model(
    "OnenoteGetPagesInput",
    section_id=(str, Field(description="The ID of the section to list pages from.")),
    limit=(Optional[int], Field(default=100, gt=0, description="Maximum number of pages to return.")),
    select=(Optional[List[str]], Field(
        default=None,
        description=(
            "Optional list of fields to include in the response, e.g. ['id', 'title', 'webUrl']. "
            "Omit (or pass null) to use the default field set. "
            "Pass an empty list [] to omit $select entirely and receive all fields. "
            "Do NOT include 'contentUrl' — it is not selectable and causes a 400 error."
        ),
    )),
)

OnenoteGetPageContentInput = create_model(
    "OnenoteGetPageContentInput",
    page_id=(str, Field(description="The ID of the OneNote page to retrieve raw HTML content for.")),
)

OnenoteReadPageInput = create_model(
    "OnenoteReadPageInput",
    page_id=(str, Field(description="The ID of the OneNote page to read.")),
    capture_images=(Optional[bool], Field(
        default=True,
        description=(
            "If True and an LLM is configured, download embedded images from the page "
            "and include an AI-generated description of each image inline. "
            "Set to False to replace images with a short [image: <alt>] placeholder."
        ),
    )),
    include_attachments=(Optional[bool], Field(
        default=True,
        description=(
            "If True, include attachment entries in the output (download URL + optional content). "
            "For onenote_read_page this also appends an 'Attachments' section at the end."
        ),
    )),
    read_attachment_content=(Optional[bool], Field(
        default=False,
        description=(
            "If True, download each attached file and parse its content inline "
            "(e.g. PDF text, DOCX text, image descriptions). "
            "Has no effect when include_attachments=False. "
            "Image-type attachments additionally require an LLM to be configured."
        ),
    )),
)

OnenoteReadPageItemsInput = create_model(
    "OnenoteReadPageItemsInput",
    page_id=(str, Field(description="The ID of the OneNote page to read.")),
    capture_images=(Optional[bool], Field(
        default=True,
        description=(
            "If True and an LLM is configured, download embedded images and include "
            "AI-generated descriptions in the returned items. "
            "Set to False to use a [image: <alt>] placeholder instead."
        ),
    )),
    include_attachments=(Optional[bool], Field(
        default=True,
        description=(
            "If True, include attachment items in the returned list with their download URLs."
        ),
    )),
    read_attachment_content=(Optional[bool], Field(
        default=False,
        description=(
            "If True, download and parse each attachment's content inline. "
            "Has no effect when include_attachments=False."
        ),
    )),
)

OnenoteCreateNotebookInput = create_model(
    "OnenoteCreateNotebookInput",
    display_name=(str, Field(description="Display name for the new notebook.")),
)

OnenoteCreateSectionInput = create_model(
    "OnenoteCreateSectionInput",
    notebook_id=(str, Field(description="The ID of the notebook to create the section in.")),
    display_name=(str, Field(description="Display name for the new section.")),
)

OnenoteCreatePageInput = create_model(
    "OnenoteCreatePageInput",
    section_id=(str, Field(description="The ID of the section to create the page in.")),
    html_content=(str, Field(
        description=(
            "Full HTML document for the page. Must include a <title> tag. "
            "Example: '<!DOCTYPE html><html><head><title>My Page</title></head>"
            "<body><p>Hello World</p></body></html>'"
        )
    )),
)

OnenoteUpdatePageInput = create_model(
    "OnenoteUpdatePageInput",
    page_id=(str, Field(description="The ID of the OneNote page to update.")),
    patch_commands=(List[dict], Field(
        description=(
            "List of OneNote PATCH command objects. Each must have: "
            "'target' (e.g. 'body', or a CSS selector such as '#div-id'), "
            "'action' ('append', 'prepend', 'replace', 'insert', or 'delete'), "
            "'content' (HTML string — not needed for 'delete'), "
            "'position' (optional: 'after' or 'before', used with 'insert'). "
            'Example: [{"target": "body", "action": "append", '
            '"content": "<p>New paragraph</p>"}]'
        )
    )),
)

OnenoteReplacePageContentInput = create_model(
    "OnenoteReplacePageContentInput",
    page_id=(str, Field(description="The ID of the OneNote page whose body will be replaced.")),
    html_content=(str, Field(
        description="New HTML content to set as the entire page body. Plain HTML fragment (no <html>/<head> wrapper needed)."
    )),
)

OnenoteDeletePageInput = create_model(
    "OnenoteDeletePageInput",
    page_id=(str, Field(description="The ID of the OneNote page to delete.")),
)

OnenoteSearchPagesInput = create_model(
    "OnenoteSearchPagesInput",
    query=(str, Field(description="Full-text search query to search across all OneNote pages on this site.")),
    limit=(Optional[int], Field(default=50, gt=0, description="Maximum number of results to return.")),
)

OnenoteListAttachmentsInput = create_model(
    "OnenoteListAttachmentsInput",
    page_id=(str, Field(description="The ID of the OneNote page whose file attachments should be listed.")),
)

OnenoteReadAttachmentInput = create_model(
    "OnenoteReadAttachmentInput",
    page_id=(str, Field(description="The ID of the OneNote page containing the attachment.")),
    attachment_name=(str, Field(
        description=(
            "Filename of the attachment to read, exactly as returned by "
            "onenote_list_attachments (e.g. 'report.pdf'). Case-sensitive."
        )
    )),
    capture_images=(Optional[bool], Field(
        default=True,
        description=(
            "When True and an LLM is configured, run image attachments through the "
            "vision pipeline to produce a description. Set to False to return a "
            "[image: …] placeholder instead."
        ),
    )),
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
                       form_name: Optional[str] = None,
                       include_extensions: Optional[List[str]] = None,
                       skip_extensions: Optional[List[str]] = None):
        """
        Lists all files including files from subfolders.
        If folder name is specified, lists files under that folder path; otherwise lists
        all files under the root catalog (Shared Documents).
        Number of files is limited by limit_files (default is 100).

        If form_name is specified, only files from specified form will be returned.
        If include_extensions is specified, only files with matching extensions are returned.
        If skip_extensions is specified, files with matching extensions are excluded.
        Extensions accept both 'pdf' and '.pdf' forms and are matched case-insensitively.
        Note:
            * URL anatomy: https://epam.sharepoint.com/sites/{some_site}/{form_name}/Forms/AllItems.aspx
            * Example of folders syntax: `{form_name} / Hello / inner-folder` - 1st folder is commonly form_name
        """
        self._sync_backend_context()
        return self._backend.get_files_list(
            folder_name, limit_files, form_name, include_extensions, skip_extensions)

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
    #  OneNote — delegates to backend                                     #
    # ------------------------------------------------------------------ #

    def onenote_get_notebooks(self, select: Optional[List[str]] = None) -> list:
        """List all OneNote notebooks in this SharePoint site.

        Returns a list of notebook objects. By default each object contains:
        id, displayName, createdDateTime, lastModifiedDateTime, isDefault,
        isShared, and webUrl (via links.oneNoteWebUrl).
        Pass select=[] to receive all available fields.
        Requires Graph API delegated access (token + scopes).
        """
        self._sync_backend_context()
        return self._backend.onenote_get_notebooks(select=select)

    def onenote_get_sections(self, notebook_id: str, select: Optional[List[str]] = None) -> list:
        """List all sections in a specific OneNote notebook on this site.

        Returns a list of section objects. By default each object contains:
        id, displayName, createdDateTime, lastModifiedDateTime,
        pagesUrl, and isDefault.
        Pass select=[] to receive all available fields.
        Requires Graph API delegated access (token + scopes).
        """
        self._sync_backend_context()
        return self._backend.onenote_get_sections(notebook_id, select=select)

    def onenote_get_pages(self, section_id: str, limit: int = 100, select: Optional[List[str]] = None) -> list:
        """List pages in a OneNote section on this site.

        Returns a list of page metadata objects. By default each object contains:
        id, title, createdDateTime, lastModifiedDateTime, and webUrl.
        Does NOT return page HTML content — use onenote_get_page_content() for that.
        Pass select=[] to receive all available fields.
        Note: 'contentUrl' cannot be used in select — it causes a 400 error.
        Requires Graph API delegated access (token + scopes).
        """
        self._sync_backend_context()
        return self._backend.onenote_get_pages(section_id, limit, select=select)

    def onenote_get_page_content(self, page_id: str) -> str:
        """Retrieve the raw HTML content of a OneNote page on this site.

        Returns the OneNote XHTML string as stored by the service.
        For human-readable parsed content including image descriptions
        and attachment listings, use onenote_read_page() instead.
        Requires Graph API delegated access (token + scopes).
        """
        self._sync_backend_context()
        return self._backend.onenote_get_page_content(page_id)

    def onenote_read_page(
        self,
        page_id: str,
        capture_images: bool = True,
        include_attachments: bool = True,
        read_attachment_content: bool = False,
    ) -> str:
        """Read and parse a OneNote page into human-readable plain text.

        Handles all three content types found in OneNote pages:
        - Text / HTML — stripped to plain text with paragraph structure preserved.
        - Embedded images — downloaded from Graph API and, when an LLM is
          configured and capture_images=True, described via the vision pipeline.
          Falls back to [image: <alt-text>] when no LLM is available.
        - File attachments — listed inline as [attachment: <filename>] and
          collected into an "Attachments" section with Graph API download URLs
          when include_attachments=True. When read_attachment_content=True,
          each attachment is also downloaded and its content parsed inline
          (e.g. PDF text, DOCX text, image descriptions).

        Requires Graph API delegated access (token + scopes).
        """
        self._sync_backend_context()
        return self._backend.onenote_read_page(
            page_id, capture_images, include_attachments, read_attachment_content
        )

    def onenote_create_notebook(self, display_name: str) -> dict:
        """Create a new OneNote notebook in this SharePoint site.

        Returns the created notebook object containing:
        id, displayName, createdDateTime, and webUrl.
        Requires Graph API delegated access (token + scopes).
        """
        self._sync_backend_context()
        return self._backend.onenote_create_notebook(display_name)

    def onenote_create_section(self, notebook_id: str, display_name: str) -> dict:
        """Create a new section in a OneNote notebook on this site.

        Returns the created section object containing:
        id, displayName, createdDateTime, and pagesUrl.
        Requires Graph API delegated access (token + scopes).
        """
        self._sync_backend_context()
        return self._backend.onenote_create_section(notebook_id, display_name)

    def onenote_create_page(self, section_id: str, html_content: str) -> dict:
        """Create a new OneNote page in a section on this site from raw HTML.

        The html_content must be a valid HTML document with a <title> tag.
        Example:
            '<!DOCTYPE html><html><head><title>My Page</title></head>
             <body><p>Content here</p></body></html>'

        Returns the created page object: id, title, createdDateTime, webUrl, contentUrl.
        Requires Graph API delegated access (token + scopes).
        """
        self._sync_backend_context()
        return self._backend.onenote_create_page(section_id, html_content)

    def onenote_update_page(self, page_id: str, patch_commands: list) -> str:
        """Update a OneNote page using Graph API PATCH commands.

        Each patch_command object must have:
        - target: CSS selector or 'body', 'title', or an element id
        - action: 'append', 'prepend', 'replace', 'insert', or 'delete'
        - content: HTML string (not required for 'delete' action)
        - position: optional — 'after' or 'before' (used with 'insert')

        Returns a success confirmation string.
        Requires Graph API delegated access (token + scopes).
        """
        self._sync_backend_context()
        return self._backend.onenote_update_page(page_id, patch_commands)

    def onenote_replace_page_content(self, page_id: str, html_content: str) -> str:
        """Replace the entire body of a OneNote page with new HTML content.

        Convenience wrapper that generates a single PATCH command to replace the
        full page body. html_content should be a plain HTML fragment
        (no <html>/<head> wrapper needed).

        Returns a success confirmation string.
        Requires Graph API delegated access (token + scopes).
        """
        self._sync_backend_context()
        return self._backend.onenote_replace_page_content(page_id, html_content)

    def onenote_delete_page(self, page_id: str) -> str:
        """Permanently delete a OneNote page on this site.

        This action is irreversible.
        Returns a success confirmation string.
        Requires Graph API delegated access (token + scopes).
        """
        self._sync_backend_context()
        return self._backend.onenote_delete_page(page_id)

    def onenote_search_pages(self, query: str, limit: int = 50) -> list:
        """Search for OneNote pages matching a full-text query on this site.

        Searches across all pages in all notebooks on the SharePoint site.
        Returns a list of matching page metadata objects, each containing:
        id, title, lastModifiedDateTime, createdDateTime, and webUrl.
        Requires Graph API delegated access (token + scopes).
        """
        self._sync_backend_context()
        return self._backend.onenote_search_pages(query, limit)

    def onenote_list_attachments(self, page_id: str) -> list:
        """List all file attachments on a OneNote page.

        Parses the page HTML and returns every user-uploaded file attachment
        (``<object data-attachment>`` elements). Embedded images are excluded.

        Returns a list of dicts, each containing:
        - **name**: The original attachment filename (e.g. "report.pdf").
        - **resource_id**: The Graph API resource ID — use this as a stable
          identifier when calling onenote_read_attachment.
        - **download_url**: The canonical Graph API URL to download the file.

        Use this tool to discover which attachments exist on a page before
        calling onenote_read_attachment to read a specific one.
        Requires Graph API delegated access (token + scopes).
        """
        self._sync_backend_context()
        return self._backend.onenote_list_attachments(page_id)

    def onenote_read_attachment(
        self,
        page_id: str,
        attachment_name: str,
        capture_images: bool = True,
    ) -> str:
        """Download and parse a single file attachment from a OneNote page.

        Looks up the attachment by name (as returned by onenote_list_attachments),
        downloads the file from the Graph API, and returns its parsed text content.

        Supported types include PDF, DOCX, XLSX, PPTX, plain text, and common
        image formats. For image attachments, an AI-generated description is
        returned when capture_images=True and an LLM is configured; otherwise
        a short [image: …] placeholder is used.

        Call onenote_list_attachments first to get the exact attachment names
        and confirm which attachments are present on the page.
        Requires Graph API delegated access (token + scopes).
        """
        self._sync_backend_context()
        return self._backend.onenote_read_attachment(page_id, attachment_name, capture_images)

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

        Requires Graph API delegated access (token + scopes).
        """
        self._sync_backend_context()
        return self._backend.onenote_read_page_items(
            page_id, capture_images, include_attachments, read_attachment_content
        )

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
                            "CONFIRMATION FROM A USER. Sharepoint ONLY.",
                default=1000, ge=0)),
            'include_extensions': (Optional[List[str]], Field(
                description="List of file extensions to include when processing. "
                            "Applies to both SharePoint document-library files and "
                            "OneNote page attachments (when include_attachments is enabled). "
                            "i.e. ['*.png', '*.jpg']. "
                            "If empty, all files will be processed (except skip_extensions).",
                default=[])),
            'skip_extensions': (Optional[List[str]], Field(
                description="List of file extensions to skip when processing. "
                            "Applies to both SharePoint document-library files and "
                            "OneNote page attachments (when include_attachments is enabled). "
                            "i.e. ['*.exe', '*.zip']",
                default=[])),
            'path': (Optional[str], Field(
                description="Folder path. "
                            "Accepts either a full server-relative path "
                            "(e.g., '/sites/SiteName/...') or a relative path. "
                            "If a relative path is provided, the search will be "
                            "performed recursively under 'Shared Documents' and "
                            "other private libraries. "
                            "When used together with form_name, this is treated as a "
                            "subfolder path relative to the library identified by form_name.",
                default=None)),
            'form_name': (Optional[str], Field(
                description="Document Library name to scope indexing to. "
                            "If specified, only files from this library will be indexed. "
                            "When used together with path, form_name pins the library and "
                            "path is treated as a subfolder within it. "
                            "Example: 'private_docs' or 'Shared Documents'.",
                default=None)),
            'include_onenote': (Optional[bool], Field(
                description="If True, also index OneNote pages from this SharePoint site "
                            "in addition to document library files. "
                            "Requires Graph API delegated access (token + scopes).",
                default=False)),
            'onenote_filter': (Optional[dict], Field(
                description=(
                    "Optional dict that controls which OneNote content is indexed "
                    "and how it is processed. All keys are optional — omit the whole param "
                    "or pass null to index everything with defaults.\n\n"
                    "Keys:\n"
                    "  notebooks (list)         — scope filter; omit to index all notebooks.\n"
                    "    Each entry: {id, sections: [{id, pages: [<page-id>, ...]}]}\n"
                    "    Omit 'sections' to include all sections in a notebook.\n"
                    "    Omit 'pages' to include all pages in a section.\n"
                    "  capture_images (bool)    — default True. LLM describes embedded images.\n"
                    "  include_attachments (bool) — default False. Index page file-attachments.\n\n"
                    "Attachment extension filtering reuses the top-level 'include_extensions'\n"
                    "and 'skip_extensions' params — no need to repeat them here.\n\n"
                    "Examples:\n"
                    "  Index one section with attachments:\n"
                    '  {"notebooks":[{"id":"nb1","sections":[{"id":"sec1"}]}],'
                    '"capture_images":True,"include_attachments":True}\n'
                    "  Index specific pages only:\n"
                    '  {"notebooks":[{"id":"nb1","sections":[{"id":"sec1",'
                    '"pages":["page-id-1","page-id-2"]}]}]}'
                ),
                default=None)),
        }

    def _base_loader(self, **kwargs) -> Generator[Document, None, None]:
        self._sync_backend_context()
        # Normalise onenote_filter (already a dict or None) and inject top-level
        # extension filters so include_extensions / skip_extensions apply uniformly
        # to both SharePoint files and OneNote attachments.
        raw_filter = kwargs.get('onenote_filter') or {}
        self._onenote_cfg: dict = {
            "notebooks": raw_filter.get("notebooks", []),
            "capture_images": raw_filter.get("capture_images", True),
            "include_attachments": raw_filter.get("include_attachments", False),
            "include_extensions": kwargs.get('include_extensions', []),
            "skip_extensions": kwargs.get('skip_extensions', []),
        }

        limit_files = kwargs.get('limit_files', 10000)
        include_extensions = kwargs.get('include_extensions') or None
        skip_extensions = kwargs.get('skip_extensions') or None
        form_name = kwargs.get('form_name') or None

        if limit_files > 0:
            self._log_tool_event(
                message="Starting SharePoint files extraction", tool_name="loader")
            try:
                all_files = self.get_files_list(
                    kwargs.get('path'), limit_files,
                    form_name=form_name,
                    include_extensions=include_extensions,
                    skip_extensions=skip_extensions)
                if isinstance(all_files, ToolException):
                    raise all_files
                self._log_tool_event(
                    message="List of the files has been extracted", tool_name="loader")
            except Exception as e:
                raise ToolException(f"Unable to extract files: {e}")

            for file in all_files:

                metadata = {
                    ("updated_on" if k == "Modified" else k): str(v)
                    for k, v in file.items()
                }
                yield Document(page_content="", metadata=metadata)

        # ── OneNote pages ─────────────────────────────────────────────
        if kwargs.get('include_onenote'):
            yield from self._onenote_base_loader(self._onenote_cfg)

    # ------------------------------------------------------------------ #
    #  OneNote helpers                                                     #
    # ------------------------------------------------------------------ #


    def _onenote_base_loader(
        self,
        cfg: dict,
    ) -> Generator[Document, None, None]:
        """Enumerate OneNote pages according to *cfg* and yield Document stubs.

        Each stub carries page metadata but no content; content is fetched
        lazily in ``_extend_data()`` via the ``source_type == 'onenote'`` marker.

        *cfg* is the dict produced by :meth:`_parse_onenote_filter`.
        """
        self._log_tool_event(
            message="Starting OneNote pages enumeration", tool_name="loader")
        try:
            # ── Build the list of (notebook_id, section_id, allowed_page_ids) ─
            # allowed_page_ids == None means "all pages in this section"
            work_items: list = []   # list of (section_id, allowed_page_ids | None)

            nb_filter: list = cfg.get("notebooks", [])

            if nb_filter:
                for nb_entry in nb_filter:
                    nb_id: str = nb_entry.get("id", "")
                    if not nb_id:
                        continue
                    sec_filter: list = nb_entry.get("sections", [])
                    if sec_filter:
                        for sec_entry in sec_filter:
                            sec_id: str = sec_entry.get("id", "")
                            if not sec_id:
                                continue
                            page_ids = sec_entry.get("pages") or None  # None = all
                            work_items.append((sec_id, page_ids))
                    else:
                        # All sections in this notebook
                        try:
                            for sec in self._backend.onenote_get_sections(nb_id):
                                work_items.append((sec["id"], None))
                        except Exception as exc:
                            logging.warning(
                                "Failed to get sections for notebook '%s': %s", nb_id, exc)
            else:
                # No filter — all notebooks on the site
                try:
                    notebooks = self._backend.onenote_get_notebooks()
                except Exception as exc:
                    raise ToolException(
                        f"Failed to list OneNote notebooks: {exc}") from exc
                for nb in notebooks:
                    nb_id = nb.get("id", "")
                    if not nb_id:
                        continue
                    try:
                        for sec in self._backend.onenote_get_sections(nb_id):
                            work_items.append((sec["id"], None))
                    except Exception as exc:
                        logging.warning(
                            "Failed to get sections for notebook '%s': %s", nb_id, exc)

            total = len(work_items)
            self._log_tool_event(
                message=f"Found {total} OneNote section(s) to enumerate",
                tool_name="loader",
            )

            for idx, (sec_id, allowed_page_ids) in enumerate(work_items, 1):
                self._log_tool_event(
                    message=f"Loading OneNote pages from section {idx}/{total}: {sec_id}",
                    tool_name="loader",
                )
                try:
                    pages = self._backend.onenote_get_pages(sec_id, limit=1000)
                except Exception as exc:
                    logging.warning(
                        "Failed to get pages for section '%s': %s", sec_id, exc)
                    continue

                for page in pages:
                    page_id = page.get("id", "")
                    if allowed_page_ids is not None and page_id not in allowed_page_ids:
                        continue
                    yield Document(
                        page_content="",
                        metadata={
                            "source_type": "onenote",
                            "id": page_id,
                            "title": page.get("title", ""),
                            "webUrl": page.get("webUrl", ""),
                            "contentUrl": page.get("contentUrl", ""),
                            "updated_on": page.get("lastModifiedDateTime", ""),
                            "created_on": page.get("createdDateTime", ""),
                            "section_id": sec_id,
                        },
                    )
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(
                f"Failed to enumerate OneNote pages: {e}"
            ) from e

    def _extend_data(self, documents: Generator[Document, None, None]):
        self._sync_backend_context()
        for document in documents:
            # ── OneNote page ──────────────────────────────────────────
            if document.metadata.get("source_type") == "onenote":
                page_id = document.metadata.get("id", "")
                try:
                    cfg = getattr(self, '_onenote_cfg', {})
                    capture_images = cfg.get('capture_images', True)
                    if capture_images:
                        items = self._backend.onenote_read_page_items(
                            page_id=page_id,
                            capture_images=True,
                            include_attachments=False,
                            read_attachment_content=False,
                        )

                        for idx, item in enumerate(items):
                            raw_bytes: bytes = item.get('raw_bytes')
                            if raw_bytes and item.get('type') == 'image':
                                description: str = item.get('description', '')
                                filename: str = item.get('filename') or f"image_{idx}.jpg"
                                img_id = f"img_{page_id}_{idx}"
                                document.metadata.setdefault(
                                    IndexerKeywords.DEPENDENT_DOCS.value, []
                                ).append(img_id)

                                content_bytes = description.encode('utf-8') if (
                                            capture_images and description) else raw_bytes
                                content_filename = filename.rsplit('.', 1)[0] + '.txt' if (
                                            capture_images and description) else filename

                                yield Document(
                                    page_content=description,
                                    metadata={
                                        IndexerKeywords.CONTENT_IN_BYTES.value: content_bytes,
                                        IndexerKeywords.CONTENT_FILE_NAME.value: content_filename,
                                        'id': img_id,
                                        'source_type': 'onenote_image',
                                        'page_id': page_id,
                                        'page_title': document.metadata.get('title', ''),
                                        'source': document.metadata.get('webUrl', ''),
                                        'filename': filename,
                                        'alt': item.get('alt', ''),
                                        'updated_on': document.metadata.get('updated_on', ''),
                                        IndexerKeywords.PARENT.value: page_id,
                                    },
                                )

                    page_text = self._backend.onenote_get_page_content(page_id)
                    document.metadata[IndexerKeywords.CONTENT_IN_BYTES.value] = (
                        page_text.encode("utf-8")
                    )
                    document.metadata[IndexerKeywords.CONTENT_FILE_NAME.value] = (
                        f"{page_id}.html"
                    )
                except Exception as e:
                    logging.error("Failed while parsing OneNote page '%s': %s", page_id, e)
                yield document

            # ── SharePoint file ───────────────────────────────────────
            else:
                file_path = document.metadata.get('Path') or document.metadata.get('file_path')
                if file_path:
                    try:
                        # Pass the full path — load_file_content_in_bytes will
                        # extract the drive ID from a Graph-style path
                        # (e.g. "/drives/{id}/root:/folder/file.txt") or fall
                        # back to the default drive for server-relative paths.
                        content_bytes = self._backend.load_file_content_in_bytes(file_path)
                        document.metadata[IndexerKeywords.CONTENT_IN_BYTES.value] = content_bytes
                        file_name = document.metadata.get('Name', file_path)
                        _, ext = os.path.splitext(file_name)
                        if ext:
                            document.metadata[IndexerKeywords.CONTENT_FILE_NAME.value] = file_name
                    except Exception as e:
                        logging.error("Failed while loading file content '%s': %s", file_path, e)
                yield document

    def _process_document(self, base_document: Document) -> Generator[Document, None, None]:
        """Yield dependent documents for a OneNote page:
        - One Document per file attachment (when include_attachments=True)

        Image documents are now yielded directly from _extend_data to avoid
        storing raw bytes in page document metadata.
        Requires Graph API delegated access (token + scopes).
        """
        if base_document.metadata.get('source_type') != 'onenote':
            return

        page_id = base_document.metadata.get('id', '')
        page_web_url = base_document.metadata.get('webUrl', '')
        page_updated_on = base_document.metadata.get('updated_on', '')
        page_title = base_document.metadata.get('title', '')
        cfg: dict = getattr(self, '_onenote_cfg', {})

        # ── File attachments → one Document each ──────────────────────
        if not cfg.get('include_attachments', False):
            return

        if not hasattr(self._backend, 'onenote_list_attachments'):
            raise ToolException(
                "OneNote attachment indexing requires Graph API delegated access "
                "(token + scopes). REST-only backends do not support onenote_list_attachments."
            )

        skip_patterns: list = cfg.get('skip_extensions', [])
        include_patterns: list = cfg.get('include_extensions', [])

        try:
            attachments = self._backend.onenote_list_attachments(page_id)
        except Exception as e:
            logging.error(
                "Failed to list attachments for OneNote page '%s': %s", page_id, e
            )
            return

        for attachment in attachments:
            att_name: str = attachment.get('name', '')
            download_url: str = attachment.get('download_url', '')
            resource_id: str = attachment.get('resource_id') or att_name

            if not att_name or not download_url:
                continue

            if include_patterns and not any(
                    re.match(
                        re.escape(pattern).replace(r'\*', '.*') + '$',
                        att_name, re.IGNORECASE,
                    )
                    for pattern in include_patterns
            ):
                logging.debug(
                    "Skipping OneNote attachment '%s' (not in include_extensions)", att_name
                )
                continue

            if skip_patterns and any(
                    re.match(
                        re.escape(pattern).replace(r'\*', '.*') + '$',
                        att_name, re.IGNORECASE,
                    )
                    for pattern in skip_patterns
            ):
                logging.debug(
                    "Skipping OneNote attachment '%s' (matched skip pattern)", att_name
                )
                continue

            attachment_id = f"attach_{resource_id}"
            base_document.metadata.setdefault(
                IndexerKeywords.DEPENDENT_DOCS.value, []
            ).append(attachment_id)

            try:
                content_bytes = self._backend._onenote_download_attachment_bytes(
                    download_url, att_name
                )
            except Exception as e:
                logging.error(
                    "Failed to download OneNote attachment '%s' on page '%s': %s",
                    att_name, page_id, e,
                )
                continue

            yield Document(
                page_content='',
                metadata={
                    IndexerKeywords.CONTENT_IN_BYTES.value: content_bytes,
                    IndexerKeywords.CONTENT_FILE_NAME.value: att_name,
                    'id': attachment_id,
                    'source_type': 'onenote_attachment',
                    'page_id': page_id,
                    'page_title': page_title,
                    'source': page_web_url,
                    'filename': att_name,
                    'updated_on': page_updated_on,
                    IndexerKeywords.PARENT.value: page_id,
                    'type': 'attachment',
                },
            )

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
            # NOTE: add_attachment_to_list_item is intentionally excluded from available tools.
            # Microsoft Graph API has no endpoint for SharePoint list item attachments (v1.0 or beta),
            # and the SharePoint REST API path requires app-only ACS tokens which are frequently blocked
            # by tenant-level policy (DisableCustomAppAuthentication=True). The implementation is
            # preserved in case future Graph API support is added or tenant restrictions are lifted.
            # {
            #     "name": "add_attachment_to_list_item",
            #     "description": self.add_attachment_to_list_item.__doc__,
            #     "args_schema": AddAttachmentToListItem,
            #     "ref": self.add_attachment_to_list_item,
            # },
            # ── OneNote ───────────────────────────────────────────────
            {
                "name": "onenote_get_notebooks",
                "description": self.onenote_get_notebooks.__doc__,
                "args_schema": OnenoteGetNotebooksInput,
                "ref": self.onenote_get_notebooks,
            },
            {
                "name": "onenote_get_sections",
                "description": self.onenote_get_sections.__doc__,
                "args_schema": OnenoteGetSectionsInput,
                "ref": self.onenote_get_sections,
            },
            {
                "name": "onenote_get_pages",
                "description": self.onenote_get_pages.__doc__,
                "args_schema": OnenoteGetPagesInput,
                "ref": self.onenote_get_pages,
            },
            {
                "name": "onenote_get_page_content",
                "description": self.onenote_get_page_content.__doc__,
                "args_schema": OnenoteGetPageContentInput,
                "ref": self.onenote_get_page_content,
            },
            {
                "name": "onenote_read_page",
                "description": self.onenote_read_page.__doc__,
                "args_schema": OnenoteReadPageInput,
                "ref": self.onenote_read_page,
            },
            {
                "name": "onenote_read_page_items",
                "description": self.onenote_read_page_items.__doc__,
                "args_schema": OnenoteReadPageItemsInput,
                "ref": self.onenote_read_page_items,
            },
            {
                "name": "onenote_create_notebook",
                "description": self.onenote_create_notebook.__doc__,
                "args_schema": OnenoteCreateNotebookInput,
                "ref": self.onenote_create_notebook,
            },
            {
                "name": "onenote_create_section",
                "description": self.onenote_create_section.__doc__,
                "args_schema": OnenoteCreateSectionInput,
                "ref": self.onenote_create_section,
            },
            {
                "name": "onenote_create_page",
                "description": self.onenote_create_page.__doc__,
                "args_schema": OnenoteCreatePageInput,
                "ref": self.onenote_create_page,
            },
            {
                "name": "onenote_update_page",
                "description": self.onenote_update_page.__doc__,
                "args_schema": OnenoteUpdatePageInput,
                "ref": self.onenote_update_page,
            },
            {
                "name": "onenote_replace_page_content",
                "description": self.onenote_replace_page_content.__doc__,
                "args_schema": OnenoteReplacePageContentInput,
                "ref": self.onenote_replace_page_content,
            },
            {
                "name": "onenote_delete_page",
                "description": self.onenote_delete_page.__doc__,
                "args_schema": OnenoteDeletePageInput,
                "ref": self.onenote_delete_page,
            },
            {
                "name": "onenote_search_pages",
                "description": self.onenote_search_pages.__doc__,
                "args_schema": OnenoteSearchPagesInput,
                "ref": self.onenote_search_pages,
            },
            {
                "name": "onenote_list_attachments",
                "description": self.onenote_list_attachments.__doc__,
                "args_schema": OnenoteListAttachmentsInput,
                "ref": self.onenote_list_attachments,
            },
            {
                "name": "onenote_read_attachment",
                "description": self.onenote_read_attachment.__doc__,
                "args_schema": OnenoteReadAttachmentInput,
                "ref": self.onenote_read_attachment,
            },
        ]

