"""Abstract base interface for SharePoint API implementations.

Two concrete implementations exist:
- :class:`SharepointRestWrapper`  : office365-rest-python-client (app credentials or REST token)
- :class:`SharepointGraphWrapper` : Microsoft Graph API (delegated access — requires token + scopes)
"""
from abc import ABC, abstractmethod
from typing import Optional


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
    ):
        """Return a list of file metadata dicts from document libraries.

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


