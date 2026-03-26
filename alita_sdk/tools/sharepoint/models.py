"""Typed return-value models for the SharePoint / OneNote toolkit.

These dataclasses are the public API surface for ``onenote_read_page_items``.
They are intentionally kept free of ``bytes`` fields and use only JSON-safe
scalar types so they can be safely serialised and passed to any LLM API.

The internal ``_onenote_parse_page_items`` helper in ``graph_wrapper.py``
still returns plain dicts (with ``raw_bytes``) for the indexing pipeline.
These models are the *tool-caller* view only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class OnenoteTextItem:
    """A plain-text content block from a OneNote page."""
    content: str

    def __str__(self) -> str:
        return self.content


@dataclass
class OnenoteImageItem:
    """An embedded image from a OneNote page.

    ``description`` is the LLM vision result (or an ``[image: <alt>]``
    placeholder when no LLM is configured / ``capture_images=False``).
    ``src`` is the canonical Graph API resource URL — useful for callers
    that want to download the image themselves.
    ``alt`` is the original ``alt`` attribute from the HTML, if any.
    """
    description: str
    src: str = ""
    alt: str = ""

    def __str__(self) -> str:
        return self.description


@dataclass
class OnenoteAttachmentItem:
    """A file attachment on a OneNote page.

    ``name`` is the original filename (e.g. ``"report.pdf"``).
    ``download_url`` is the canonical Graph API URL to download the file.
    ``content`` is the parsed text content of the attachment, or ``None``
    when ``read_attachment_content=False`` (the default).
    """
    name: str
    download_url: str = ""
    content: Optional[str] = None

    def __str__(self) -> str:
        text = f"[attachment: {self.name}]"
        if self.download_url:
            text += f"\n  download_url: {self.download_url}"
        if self.content:
            indented = "\n".join(f"  {line}" for line in self.content.splitlines())
            text += f"\n  content:\n{indented}"
        return text


# Union type for a single page item
OnenotePageItem = OnenoteTextItem | OnenoteImageItem | OnenoteAttachmentItem


@dataclass
class OnenotePageItems:
    """Ordered collection of typed items parsed from a OneNote page.

    This is the return type of ``onenote_read_page_items``.  It behaves like
    a list (iterable, indexable, has ``len``) but also renders itself as a
    readable plain-text string for LLM consumption via ``str()``.

    Example::

        items = wrapper.onenote_read_page_items(page_id="...")
        for item in items:
            if isinstance(item, OnenoteImageItem):
                print("Image:", item.description)
            elif isinstance(item, OnenoteAttachmentItem):
                print("Attachment:", item.name, item.download_url)
            else:
                print("Text:", item.content)

        # Or just hand it to the LLM as a string:
        print(str(items))
    """
    items: List[OnenotePageItem] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    #  List-like interface                                                 #
    # ------------------------------------------------------------------ #

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]

    # ------------------------------------------------------------------ #
    #  String rendering — used by llm.py str(tool_result) path            #
    # ------------------------------------------------------------------ #

    def __str__(self) -> str:
        parts = [str(item) for item in self.items if str(item).strip()]
        return "\n-----\n".join(parts)

    def __repr__(self) -> str:
        return f"OnenotePageItems({len(self.items)} items)"

