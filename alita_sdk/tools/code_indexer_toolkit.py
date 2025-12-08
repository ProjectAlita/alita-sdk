import ast
import fnmatch
import json
import logging
from typing import Optional, List, Generator

from langchain_core.documents import Document
from langchain_core.tools import ToolException
from pydantic import Field

from alita_sdk.tools.base_indexer_toolkit import BaseIndexerToolkit

logger = logging.getLogger(__name__)


class CodeIndexerToolkit(BaseIndexerToolkit):
    def _get_indexed_data(self, index_name: str):
        self._ensure_vectorstore_initialized()
        if not self.vector_adapter:
            raise ToolException("Vector adapter is not initialized. "
                             "Check your configuration: embedding_model and vectorstore_type.")
        return self.vector_adapter.get_code_indexed_data(self, index_name)

    def key_fn(self, document: Document):
        return document.metadata.get("filename")

    def compare_fn(self, document: Document, idx_data):
        return (document.metadata.get('commit_hash') and
            idx_data.get('commit_hashes') and
            document.metadata.get('commit_hash') in idx_data.get('commit_hashes')
        )

    def remove_ids_fn(self, idx_data, key: str):
        return idx_data[key]['ids']

    def _base_loader(
            self,
            branch: Optional[str] = None,
            whitelist: Optional[List[str]] = None,
            blacklist: Optional[List[str]] = None,
            **kwargs) -> Generator[Document, None, None]:
        """Index repository files in the vector store using code parsing."""
        yield from self.loader(
            branch=branch,
            whitelist=whitelist,
            blacklist=blacklist
        )

    def _extend_data(self, documents: Generator[Document, None, None]):
        yield from documents

    def _index_tool_params(self):
        """Return the parameters for indexing data."""
        return {
            "branch": (Optional[str], Field(
                description="Branch to index files from. Defaults to active branch if None.",
                default=None)),
            "whitelist": (Optional[List[str]], Field(
                description='File extensions or paths to include. Defaults to all files if None. Example: ["*.md", "*.java"]',
                default=None)),
            "blacklist": (Optional[List[str]], Field(
                description='File extensions or paths to exclude. Defaults to no exclusions if None. Example: ["*.md", "*.java"]',
                default=None)),
        }

    def loader(self,
               branch: Optional[str] = None,
               whitelist: Optional[List[str]] = None,
               blacklist: Optional[List[str]] = None,
               chunked: bool = True) -> Generator[Document, None, None]:
        """
        Generates Documents from files in a branch, respecting whitelist and blacklist patterns.
    
        Parameters:
        - branch (Optional[str]): Branch for listing files. Defaults to the current branch if None.
        - whitelist (Optional[List[str]]): File extensions or paths to include. Defaults to all files if None.
        - blacklist (Optional[List[str]]): File extensions or paths to exclude. Defaults to no exclusions if None.
        - chunked (bool): If True (default), applies universal chunker based on file type.
                         If False, returns raw Documents without chunking.
    
        Returns:
        - generator: Yields Documents from files matching the whitelist but not the blacklist.
                    Each document has exactly the key 'filename' in metadata, which is used as an ID
                    for further operations (indexing, deduplication, and retrieval).
    
        Example:
        # Use 'feature-branch', include '.py' files, exclude 'test_' files
        for doc in loader(branch='feature-branch', whitelist=['*.py'], blacklist=['*test_*']):
            print(doc.page_content)
    
        Notes:
        - Whitelist and blacklist use Unix shell-style wildcards.
        - Files must match the whitelist and not the blacklist to be included.
        - Each document MUST have exactly the key 'filename' in metadata. This key is used as an ID
          for further operations such as indexing, deduplication, and retrieval.
        - When chunked=True:
          - .md files → markdown chunker (header-based splitting)
          - .py/.js/.ts/etc → code parser (TreeSitter-based)
          - .json files → JSON chunker
          - other files → default text chunker
        """
        import hashlib
    
        _files = self.__handle_get_files("", self.__get_branch(branch))
        self._log_tool_event(message="Listing files in branch", tool_name="loader")
        logger.info(f"Files in branch: {_files}")
    
        def is_whitelisted(file_path: str) -> bool:
            if whitelist:
                return (any(fnmatch.fnmatch(file_path, pattern) for pattern in whitelist)
                        or any(file_path.endswith(f'.{pattern}') for pattern in whitelist))
            return True
    
        def is_blacklisted(file_path: str) -> bool:
            if blacklist:
                return (any(fnmatch.fnmatch(file_path, pattern) for pattern in blacklist)
                        or any(file_path.endswith(f'.{pattern}') for pattern in blacklist))
            return False
    
        def raw_document_generator() -> Generator[Document, None, None]:
            """Yields raw Documents without chunking."""
            self._log_tool_event(message="Reading the files", tool_name="loader")
            total_files = len(_files)
            processed = 0
            
            for idx, file in enumerate(_files, 1):
                if is_whitelisted(file) and not is_blacklisted(file):
                    try:
                        file_content = self._read_file(file, self.__get_branch(branch))
                    except Exception as e:
                        logger.error(f"Failed to read file {file}: {e}")
                        continue
                    
                    if not file_content:
                        continue
                    
                    # Ensure file content is a string
                    if isinstance(file_content, bytes):
                        file_content = file_content.decode("utf-8", errors="ignore")
                    elif isinstance(file_content, dict) and file.endswith('.json'):
                        file_content = json.dumps(file_content)
                    elif not isinstance(file_content, str):
                        file_content = str(file_content)
                    
                    # Hash the file content for uniqueness tracking
                    file_hash = hashlib.sha256(file_content.encode("utf-8")).hexdigest()
                    processed += 1
                    
                    yield Document(
                        page_content=file_content,
                        metadata={
                            'file_path': file,
                            'filename': file,
                            'source': file,
                            'commit_hash': file_hash,
                        }
                    )
                
                if idx % 10 == 0 or idx == total_files:
                    self._log_tool_event(
                        message=f"{idx} out of {total_files} files checked, {processed} matched",
                        tool_name="loader"
                    )
            
            self._log_tool_event(message=f"{processed} files loaded", tool_name="loader")

        if not chunked:
            # Return raw documents without chunking
            return raw_document_generator()
        
        # Apply universal chunker based on file type
        from .chunkers.universal_chunker import universal_chunker
        return universal_chunker(raw_document_generator())

    def __handle_get_files(self, path: str, branch: str):
        """
        Handles the retrieval of files from a specific path and branch.
        This method should be implemented in subclasses to provide the actual file retrieval logic.
        """
        _files = self._get_files(path=path, branch=branch)
        if isinstance(_files, str):
            try:
                # Attempt to convert the string to a list using ast.literal_eval
                _files = ast.literal_eval(_files)
                # Ensure that the result is actually a list of strings
                if not isinstance(_files, list) or not all(isinstance(item, str) for item in _files):
                    raise ValueError("The evaluated result is not a list of strings")
            except (SyntaxError, ValueError):
                # Handle the case where the string cannot be converted to a list
                raise ValueError("Expected a list of strings, but got a string that cannot be converted")

            # Ensure _files is a list of strings
        if not isinstance(_files, list) or not all(isinstance(item, str) for item in _files):
            raise ValueError("Expected a list of strings")
        return _files

    def __get_branch(self, branch):
       return (branch or getattr(self, 'active_branch', None)
               or getattr(self, '_active_branch', None) or getattr(self, 'branch', None))
