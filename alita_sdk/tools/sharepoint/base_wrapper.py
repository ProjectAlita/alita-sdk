"""Abstract base interface for SharePoint API implementations.

Two concrete implementations exist:
- :class:`SharepointRestWrapper`  : office365-rest-python-client (app credentials or REST token)
- :class:`SharepointGraphWrapper` : Microsoft Graph API (delegated access — requires token + scopes)
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from langchain_core.tools import ToolException


def _normalize_extensions(extensions):
    """Normalize extension filters to lowercase dot-prefixed form.

    Accepts ``'pdf'``, ``'.pdf'``, or ``'*.pdf'``; returns e.g. ``['.pdf', '.docx']``.
    An empty / None input returns an empty list.
    """
    if not extensions:
        return []
    normalized = []
    for e in extensions:
        if not e or not e.strip():
            continue
        e = e.strip()
        # Strip glob prefix: '*.pdf' -> 'pdf', '*pdf' -> 'pdf'
        if e.startswith('*'):
            e = e.lstrip('*')
        # Strip leading dot(s): '.pdf' -> 'pdf'
        e = e.lstrip('.')
        if e:
            normalized.append(f'.{e.lower()}')
    return normalized

def _matches_extension(filename: str, normalized_extensions: list) -> bool:
    """Return True if *filename*'s extension is in *normalized_extensions*."""
    if not normalized_extensions:
        return False
    ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in normalized_extensions


class BaseSharepointWrapper(ABC):
    """Abstract base defining the SharePoint operations contract.

    All concrete wrappers must implement every abstract method so that the
    factory in :class:`SharepointApiWrapper` can transparently swap backends.
    """

    # ------------------------------------------------------------------ #
    #  Lists                                                               #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def read_list(self, list_title: str, limit: int = 1000):
        """Return items (up to *limit*) from the named list.

        Returns:
            list[dict] on success, :class:`ToolException` on failure.
        """

    @abstractmethod
    def get_lists(self):
        """Return all non-hidden lists on the site.

        Returns:
            list[dict] on success, :class:`ToolException` on failure.
        """

    @abstractmethod
    def get_list_columns(self, list_title: str):
        """Return column metadata for the named list.

        Returns:
            list[dict] on success, raises :class:`ToolException` on failure.
        """

    @abstractmethod
    def create_list_item(self, list_title: str, fields: dict):
        """Create a new item in the named list.

        Returns:
            dict with {id, fields, ...} on success, raises :class:`ToolException` on failure.
        """

    # ------------------------------------------------------------------ #
    #  Files                                                               #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def get_files_list(
        self,
        folder_name: Optional[str] = None,
        limit_files: int = 100,
        form_name: Optional[str] = None,
        include_extensions: Optional[List[str]] = None,
        skip_extensions: Optional[List[str]] = None,
    ):
        """Return a list of file metadata dicts from document libraries,
        including files from subfolders.

        Args:
            folder_name: Optional sub-folder path to restrict listing.
            limit_files: Maximum number of files to return.
            form_name: Optional Document Library name filter.
            include_extensions: If provided, only files whose extension matches
                one of these values are returned.  Accepts ``'pdf'`` or ``'.pdf'``
                form; matched case-insensitively.
            skip_extensions: If provided, files whose extension matches any of
                these values are excluded.  Same format as *include_extensions*.

        Returns:
            list[dict] on success, :class:`ToolException` on failure.
        """

    @abstractmethod
    def read_file(
        self,
        path: str,
        is_capture_image: bool = False,
        page_number: Optional[int] = None,
        sheet_name: Optional[str] = None,
        excel_by_sheets: bool = False,
    ):
        """Return parsed textual / structured content of the file at *path*.

        Returns:
            str | dict on success, :class:`ToolException` on failure.
        """

    @abstractmethod
    def load_file_content_in_bytes(self, path: str) -> bytes:
        """Return raw bytes of the file at *path*.

        Raises:
            RuntimeError | Exception on failure (do not return ToolException here
            since it is used as an internal helper for the indexer).
        """

    @abstractmethod
    def upload_file(
        self,
        folder_path: str,
        filepath: Optional[str] = None,
        filedata: Optional[str] = None,
        filename: Optional[str] = None,
        replace: bool = True,
    ):
        """Upload a file to a document library folder.

        Returns:
            dict with {id, webUrl, path, size, mime_type} on success.
        Raises:
            :class:`ToolException` on failure.
        """

    @abstractmethod
    def add_attachment_to_list_item(
        self,
        list_title: str,
        item_id: int,
        filepath: Optional[str] = None,
        filedata: Optional[str] = None,
        filename: Optional[str] = None,
        replace: bool = True,
    ):
        """Attach a file to a list item.

        Returns:
            dict with {id, name, size} on success.
        Raises:
            :class:`ToolException` on failure.
        """

    # ------------------------------------------------------------------ #
    #  OneNote  (Graph API only — delegated access required)             #
    # ------------------------------------------------------------------ #

    _ONENOTE_NOT_SUPPORTED = (
        "OneNote operations require Graph API delegated access. "
        "Provide token + scopes to enable OneNote support."
    )

    def onenote_get_notebooks(self, select: Optional[List[str]] = None) -> list:
        raise ToolException(self._ONENOTE_NOT_SUPPORTED)

    def onenote_get_sections(self, notebook_id: str, select: Optional[List[str]] = None) -> list:
        raise ToolException(self._ONENOTE_NOT_SUPPORTED)

    def onenote_get_pages(self, section_id: str, limit: int = 100, select: Optional[List[str]] = None) -> list:
        raise ToolException(self._ONENOTE_NOT_SUPPORTED)

    def onenote_get_page_content(self, page_id: str) -> str:
        raise ToolException(self._ONENOTE_NOT_SUPPORTED)

    def onenote_list_attachments(self, page_id: str) -> list:
        raise ToolException(self._ONENOTE_NOT_SUPPORTED)

    def onenote_read_attachment(
        self,
        page_id: str,
        attachment_name: str,
        capture_images: bool = True,
    ) -> str:
        raise ToolException(self._ONENOTE_NOT_SUPPORTED)

    def onenote_read_page(
        self,
        page_id: str,
        capture_images: bool = True,
        include_attachments: bool = True,
        read_attachment_content: bool = False,
    ) -> str:
        raise ToolException(self._ONENOTE_NOT_SUPPORTED)

    def onenote_create_notebook(self, display_name: str) -> dict:
        raise ToolException(self._ONENOTE_NOT_SUPPORTED)

    def onenote_create_section(self, notebook_id: str, display_name: str) -> dict:
        raise ToolException(self._ONENOTE_NOT_SUPPORTED)

    def onenote_create_page(self, section_id: str, html_content: str) -> dict:
        raise ToolException(self._ONENOTE_NOT_SUPPORTED)

    def onenote_update_page(self, page_id: str, patch_commands: list) -> str:
        raise ToolException(self._ONENOTE_NOT_SUPPORTED)

    def onenote_replace_page_content(self, page_id: str, html_content: str) -> str:
        raise ToolException(self._ONENOTE_NOT_SUPPORTED)

    def onenote_delete_page(self, page_id: str) -> str:
        raise ToolException(self._ONENOTE_NOT_SUPPORTED)

