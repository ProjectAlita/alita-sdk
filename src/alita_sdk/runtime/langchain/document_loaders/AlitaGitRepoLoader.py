from typing import Iterator

from langchain_core.documents import Document
from tempfile import TemporaryDirectory
from ..tools import git
from ..tools.log import print_log

from .AlitaDirectoryLoader import AlitaDirectoryLoader

class AlitaGitRepoLoader(AlitaDirectoryLoader):

    def __init__(self, **kwargs):
        self.source = kwargs.get('source') # Git repo url
        self.branch = kwargs.get('branch', 'main') # Git branch
        self.path = kwargs.get('path', TemporaryDirectory().name) # Target directory to clone the repo
        self.depth = kwargs.get('depth', None) # Git clone depth
        self.delete_git_dir = kwargs.get('delete_git_dir', True) # Delete git directory after loading
        self.username = kwargs.get('username', None) # Git username
        self.password = kwargs.get('password', None) # Git password
        self.key_filename = kwargs.get('key_filename', None) # Git key filename
        self.key_data = kwargs.get('key_data', None) # Git key data
        self.llm = kwargs.get('llm', None) # get the llm if it was passed
        self.prompt = kwargs.get('prompt', None)

        kwargs['path'] = self.path # this could happen and cause an exception that directory loader missing path
        for key in ['source', 'branch', 'depth', 'delete_git_dir', 'username', 'password', 'key_filename', 'key_data']:
            try:
                del kwargs[key]
            except:
                pass
        super().__init__(**kwargs)

    def __clone_repo(self):
        git.clone(
            source=self.source,
            target=self.path,
            branch=self.branch,
            depth=self.depth,
            delete_git_dir=self.delete_git_dir,
            username=self.username,
            password=self.password,
            key_filename=self.key_filename,
            key_data=self.key_data,
        )

    def __fix_source(self, document):
        document_source = document.metadata["source"]
        #
        target_prefix = f'{self.source}@{self.branch}:'
        fixed_source = document_source.replace(self.path, target_prefix, 1)
        #
        document.metadata["source"] = fixed_source

    def load(self):
        self.__clone_repo()
        #
        documents = []
        for document in super().load():
            self.__fix_source(document)
            documents.append(document)
        #
        return documents

    def lazy_load(self) -> Iterator[Document]:
        self.__clone_repo()
        #
        for document in super().lazy_load():
            self.__fix_source(document)
            yield document
        #
        return
