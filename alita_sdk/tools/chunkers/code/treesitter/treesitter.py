from abc import ABC

import tree_sitter
from tree_sitter_languages import get_language, get_parser

from ..constants import Language
from .treesitter_registry import TreesitterRegistry


class TreesitterMethodNode:
    def __init__(
        self,
        name: "str | bytes | None",
        doc_comment: "str | None",
        method_source_code: "str | None",
        node: tree_sitter.Node,
    ):
        self.name = name
        self.doc_comment = doc_comment
        self.method_source_code = method_source_code or node.text.decode()
        self.node = node


class Treesitter(ABC):
    def __init__(
        self,
        language: Language,
        method_declaration_identifier: str,
        name_identifier: str,
        doc_comment_identifier: str,
    ):
        self.parser = get_parser(language.value)
        self.language = get_language(language.value)
        self.method_declaration_identifier = method_declaration_identifier
        self.method_name_identifier = name_identifier
        self.doc_comment_identifier = doc_comment_identifier

    @staticmethod
    def create_treesitter(language: Language) -> "Treesitter":
        return TreesitterRegistry.create_treesitter(language)

    def parse(self, file_bytes: bytes) -> list[TreesitterMethodNode]:
        """Parses the given file bytes and extracts method nodes.

        If no nodes matching the configured ``method_declaration_identifier`` are
        found, a single fallback node spanning the entire file is returned so
        that callers always receive at least one ``TreesitterMethodNode``.

        Args:
            file_bytes (bytes): The content of the file to be parsed.

        Returns:
            list[TreesitterMethodNode]: A list of TreesitterMethodNode objects
            representing the methods in the file, or a single fallback node
            covering the whole file when no methods are detected.
        """
        self.tree = self.parser.parse(file_bytes)
        methods = self._query_all_methods(self.tree.root_node)

        # Normal path: at least one method node was found.
        if methods:
            result: list[TreesitterMethodNode] = []
            for method in methods:
                method_name = self._query_method_name(method["method"])
                doc_comment = method["doc_comment"]
                result.append(
                    TreesitterMethodNode(
                        method_name, doc_comment, None, method["method"]
                    )
                )
            return result

        # Fallback path: no method nodes were found. Return a single node that
        # spans the entire file so that callers can still index/summarize the
        # content even when the language-specific patterns do not match.
        full_source = file_bytes.decode(errors="replace")
        fallback_node = self.tree.root_node
        return [
            TreesitterMethodNode(
                name=None,
                doc_comment=None,
                method_source_code=full_source,
                node=fallback_node,
            )
        ]

    def _query_all_methods(
        self,
        node: tree_sitter.Node,
    ):
        """
        Recursively queries all method nodes in the given syntax tree node.

        Args:
            node (tree_sitter.Node): The root node to start the query from.

        Returns:
            list: A list of dictionaries, each containing a method node and its
            associated doc comment (if any).
        """
        methods = []
        if node.type == self.method_declaration_identifier:
            doc_comment_node = None
            if (
                node.prev_named_sibling
                and node.prev_named_sibling.type == self.doc_comment_identifier
            ):
                doc_comment_node = node.prev_named_sibling.text.decode()
            methods.append({"method": node, "doc_comment": doc_comment_node})
        else:
            for child in node.children:
                methods.extend(self._query_all_methods(child))
        return methods

    def _query_method_name(self, node: tree_sitter.Node):
        """Queries the method name from the given syntax tree node.

        Args:
            node (tree_sitter.Node): The syntax tree node to query.

        Returns:
            str or None: The method name if found, otherwise None.
        """
        if node.type == self.method_declaration_identifier:
            for child in node.children:
                if child.type == self.method_name_identifier:
                    return child.text.decode()
        return None
