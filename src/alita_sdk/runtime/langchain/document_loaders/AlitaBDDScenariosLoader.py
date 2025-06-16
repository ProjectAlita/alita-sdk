import os.path
from json import dumps
from tempfile import TemporaryDirectory
from typing import Any, Generator, List, Iterator

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from pandas import DataFrame

from ..tools import git
from ..tools.bdd_parser.bdd_parser import get_all_scenarios_from_directory, create_scenarios_data_frame
from ..tools.bdd_parser.parser import ScenarioTemplate
from ..tools.log import print_log


class BDDScenariosLoader(BaseLoader):

    def __init__(self, **kwargs):
        # Git repo url
        self.repo_url = kwargs.get('source')
        # Git branch
        self.branch = kwargs.get('branch', 'main')
        self.path = kwargs.get('path', TemporaryDirectory().name)
        # Git clone depth
        self.depth = kwargs.get('depth', None)
        # Delete git directory after loading
        self.delete_git_dir = kwargs.get('delete_git_dir', True)
        # Git username
        self.username = kwargs.get('username', None)
        # Git password
        self.password = kwargs.get('password', None)
        # Git key filename
        self.key_filename = kwargs.get('key_filename', None)
        # Git key data
        self.key_data = kwargs.get('key_data', None)
        # Path to search for the BDD scenarios in inside the cloned repo path
        self.path_to_get_features_from = kwargs.get('index_file_exts', None)

    def __clone_repository(self):
        print_log(self.repo_url)
        print_log(self.path)
        git.clone(
            source=self.repo_url,
            target=self.path,
            branch=self.branch,
            depth=self.depth,
            delete_git_dir=self.delete_git_dir,
            username=self.username,
            password=self.password,
            key_filename=self.key_filename,
            key_data=self.key_data,
        )

    def __parse_bdd_scenarios(self) -> list[dict]:
        if self.path_to_get_features_from:
            path_to_scenarios = os.path.join(self.path, self.path_to_get_features_from)
        else:
            path_to_scenarios = self.path
        scenarios: Generator[ScenarioTemplate, Any, None] = get_all_scenarios_from_directory(path_to_scenarios)
        scenarios_data_frame: DataFrame = create_scenarios_data_frame(scenarios)
        scenarios_data_frame.fillna('None', inplace=True)
        data = scenarios_data_frame[['Scenario Name', 'Scenario', 'Test Data', 'Tags']].to_dict('records')
        return data

    def load(self) -> List[Document]:
        self.__clone_repository()
        scenarios = self.__parse_bdd_scenarios()
        result = []
        for scenario in scenarios:
            page_content = scenario['Scenario']
            metadata = {
                'table_source': f'Automated scenarios from repo - {self.repo_url}',
                "source": f"{scenario['Scenario Name']}",
                "columns": list(scenario.keys()),
                "og_data": dumps(scenario),
                "tags": scenario['Tags'],
            }
            doc = Document(page_content=page_content, metadata=metadata)
            result.append(doc)
        return result

    def aload(self) -> Iterator[Document]:
        self.__clone_repository()
        scenarios = self.__parse_bdd_scenarios()
        for scenario in scenarios:
            page_content = scenario['Scenario']
            metadata = {
                'table_source': f'Automated scenarios from repo - {self.repo_url}',
                "source": f"{scenario['Scenario Name']}",
                "columns": list(scenario.keys()),
                "og_data": dumps(scenario),
                "tags": scenario['Tags'],
            }
            doc = Document(page_content=page_content, metadata=metadata)
            yield doc
