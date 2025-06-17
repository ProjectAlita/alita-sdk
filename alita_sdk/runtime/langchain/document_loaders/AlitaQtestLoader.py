import logging
import string
from json import dumps
from typing import Optional, List, Iterator

import swagger_client
from gensim.parsing.preprocessing import strip_tags
from langchain_community.document_loaders.base import BaseLoader
from langchain_core.documents import Document
from swagger_client import SearchApi
from swagger_client.rest import ApiException

PAGE_NUMBER = 1

logger = logging.getLogger(__name__)


class AlitaQTestApiDataLoader(BaseLoader):

    def __init__(self,
                 project_id: int,
                 no_of_test_cases_per_page: int,
                 qtest_api_token: str,
                 qtest_api_base_url: str,
                 dql: Optional[str] = None,
                 columns: Optional[List[str]] = None
                 ):
        self.project_id = project_id
        self.no_of_test_cases_per_page = no_of_test_cases_per_page
        self.qtest_api_token = qtest_api_token
        self.qtest_api_base_url = qtest_api_base_url
        self.columns = columns
        self.dql = dql

    def __get_all_modules_for_project(self):
        module_api = swagger_client.ModuleApi(self.__build_qtest_client())
        expand = 'descendants'
        try:
            modules = module_api.get_sub_modules_of(self.project_id, expand=expand)
        except ApiException as e:
            logger.error("Exception when calling ModuleApi->get_sub_modules_of: %s\n" % e)
            raise ValueError(
                f"""Unable to get all the modules information from following qTest project - {self.project_id}.
                                Exception: \n%s""" % e)
        return modules

    def _parse_modules(self) -> list[dict]:
        modules = self.__get_all_modules_for_project()
        result = []

        def parse_module(module, parent_name=""):
            module_id = module.id
            module_name = f"{module.pid} {module.name}"
            result.append({
                'module_id': module_id,
                'module_name': module_name
            })

            # Recursively parse children if they exist
            if module.children:
                for child in module.children:
                    parse_module(child, module_name)

        for module in modules:
            parse_module(module)

        return result

    def __parse_data(self, response_to_parse: dict, parsed_data: list, parsed_modules: list[dict]):
        import html
        for item in response_to_parse['items']:
            if item.get('test_steps', []):
                parsed_data_row = {
                    'Id': item['pid'],
                    'Module': ''.join([mod['module_name'] for mod in parsed_modules if mod['module_id'] == item['parent_id']]),
                    'Name': item['name'],
                    'Status': ''.join([properties['field_value_name'] for properties in item['properties']
                                       if properties['field_name'] == 'Status']),
                    'Type': ''.join([properties['field_value_name'] for properties in item['properties']
                                       if properties['field_name'] == 'Type']),
                    'Functional Area': ''.join([properties['field_value_name'] for properties in item['properties']
                                       if properties['field_name'] == 'Functional Area']),
                    'Squad': ''.join([properties['field_value_name'] for properties in item['properties']
                                       if properties['field_name'] == 'Squad']),
                    'Description': html.unescape(strip_tags(item['description'])),
                    'Precondition': html.unescape(strip_tags(item['precondition'])),
                    'Test Step Description': '\n'.join(map(str,
                                                           [html.unescape(
                                                               strip_tags(str(item['order']) + '. ' + item['description']))
                                                               for item in item['test_steps']
                                                               for key in item if key == 'description'])),
                    'Test Expected Result': '\n'.join(map(str,
                                                          [html.unescape(
                                                              strip_tags(str(item['order']) + '. ' + item['expected']))
                                                              for item in item['test_steps']
                                                              for key in item if key == 'expected'])),
                }
                parsed_data.append(parsed_data_row)
            else:
                continue

    def __build_qtest_client(self):
        configuration = swagger_client.Configuration()
        configuration.host = self.qtest_api_base_url
        configuration.api_key['Authorization'] = self.qtest_api_token
        configuration.api_key_prefix['Authorization'] = 'Bearer'
        return swagger_client.ApiClient(configuration)

    def __search_tests_by_dql(self) -> list:
        search_instance: SearchApi = swagger_client.SearchApi(self.__build_qtest_client())
        body = swagger_client.ArtifactSearchParams(object_type='test-cases', fields=['*'],
                                                   query=self.dql.strip())
        append_test_steps = True
        include_external_properties = True
        parsed_modules = self._parse_modules()
        parsed_data = []
        try:
            api_response = search_instance.search_artifact(self.project_id, body, append_test_steps=append_test_steps,
                                                           include_external_properties=include_external_properties,
                                                           page_size=self.no_of_test_cases_per_page, page=1)
            self.__parse_data(api_response, parsed_data, parsed_modules)

            if api_response['links']:
                while api_response['links'][0]['rel'] == 'next':
                    next_page = api_response['page'] + 1
                    api_response = search_instance.search_artifact(self.project_id, body,
                                                                   append_test_steps=append_test_steps,
                                                                   include_external_properties=include_external_properties,
                                                                   page_size=self.no_of_test_cases_per_page,
                                                                   page=next_page)
                    self.__parse_data(api_response, parsed_data, parsed_modules)
        except ApiException as e:
            logger.error("Exception when calling SearchApi->search_artifact: %s\n" % e)
            raise ValueError(
                f"""Unable to get the test cases by dql: {self.dql} from following qTest project - {self.project_id}.
                    Exception: \n%s""" % e)
        return parsed_data

    def __search_tests(self, page_number: int):
        test_api_instance = swagger_client.TestCaseApi(self.__build_qtest_client())
        expand_steps = 'true'
        try:
            api_response = test_api_instance.get_test_cases(self.project_id, page=page_number,
                                                            size=self.no_of_test_cases_per_page,
                                                            expand_steps=expand_steps)
        except ApiException as e:
            logger.error("Exception when calling TestCaseApi->get_test_cases: %s\n" % e)
            raise ValueError(f"""Unable to get the test cases from following qTest project - {self.project_id}.
                    Exception: \n%s""" % e)
        return api_response

    def __fetch_test_cases_from_qtest_as_data_frame(self) -> list:
        no_of_test_cases_returned_by_api_per_page = self.no_of_test_cases_per_page
        no_of_pages_counter = PAGE_NUMBER

        test_cases_list: list = []

        while no_of_test_cases_returned_by_api_per_page == self.no_of_test_cases_per_page:
            json_response = self.__search_tests(page_number=no_of_pages_counter)

            no_of_test_cases_returned_by_api_per_page = len(json_response)
            if no_of_test_cases_returned_by_api_per_page < 1:
                break

            temp_list: list = self.__transform_test_data_into_dict(json_response)
            test_cases_list += temp_list
            no_of_pages_counter += 1

        return test_cases_list

    @staticmethod
    def __transform_test_data_into_dict(json_response: list) -> list:
        import html
        fields_to_pick: list = ['name', 'pid', 'description', 'precondition', 'test_steps']
        result: list = []

        for obj in json_response:
            if not obj.get('test_steps'):
                continue

            api_data_dict = {}
            for key, value in obj.items():
                if key not in fields_to_pick:
                    continue

                if key == 'test_steps':
                    descriptions = []
                    expected_results = []
                    for step in value:
                        order = str(step.get('order', ''))
                        description = html.unescape(strip_tags(step.get('description', '')))
                        expected = html.unescape(strip_tags(step.get('expected', '')))
                        descriptions.append(f"{order}. {description}")
                        expected_results.append(f"{order}. {expected}")

                    api_data_dict['Test Step Description'] = '\n'.join(descriptions)
                    api_data_dict['Test Expected Result'] = '\n'.join(expected_results)

                elif key in ['description', 'precondition']:
                    filtered_data = html.unescape(strip_tags(value))
                    api_data_dict[string.capwords(key)] = filtered_data

                elif key == 'pid':
                    api_data_dict['Id'] = value

                else:
                    api_data_dict[string.capwords(key)] = value

            result.append(api_data_dict)

        return result

    def __fetch_qtest_data_from_project(self) -> list:
        if self.dql:
            qtest_data: list = self.__search_tests_by_dql()
        else:
            qtest_data: list = self.__fetch_test_cases_from_qtest_as_data_frame()
        return qtest_data

    def load(self) -> List[Document]:
        documents: List[Document] = []
        qtest_data: list = self.__fetch_qtest_data_from_project()
        if self.columns:
            for row in qtest_data:
                # Merge specified content using a new line symbol
                page_content = '\n'.join([col + ":\n" + row[col] for col in self.columns])
                # Create metadata dictionary
                meta = {
                    'table_source': f'qTest project id - {self.project_id}',
                    'source': str(row['Id']),
                    'columns': list(row.keys()),
                    'og_data': dumps(row),
                }
                # Create Langchain document and add to the list
                documents.append(Document(page_content, metadata=meta))
        else:
            for row in qtest_data:
                # Merge specified content using a new line symbol
                page_content = '\n'.join([col + ":\n" + row[col] for col in row.keys()])
                # Create metadata dictionary
                meta = {
                    'table_source': f'qTest project id - {self.project_id}',
                    'source': str(row['Id']),
                    'columns': list(row.keys()),
                    'og_data': dumps(row),
                }
                # Create Langchain document and add to the list
                documents.append(Document(page_content, metadata=meta))
        return documents

    def lazy_load(self) -> Iterator[Document]:
        qtest_data: list = self.__fetch_qtest_data_from_project()
        if self.columns:
            for row in qtest_data:
                # Merge specified content using a new line symbol
                page_content = '\n'.join([col + ":\n" + row[col] for col in self.columns])
                # Create metadata dictionary
                meta = {
                    'table_source': f'qTest project id - {self.project_id}',
                    'source': str(row['Id']),
                    'columns': list(row.keys()),
                    'og_data': dumps(row),
                }
                # Create Langchain document and add to the list
                yield Document(page_content, metadata=meta)
        else:
            for row in qtest_data:
                # Merge specified content using a new line symbol
                page_content = '\n'.join([col + ":\n" + row[col] for col in row.keys()])
                # Create metadata dictionary
                meta = {
                    'table_source': f'qTest project id - {self.project_id}',
                    'source': str(row['Id']),
                    'columns': list(row.keys()),
                    'og_data': dumps(row),
                }
                # Create Langchain document and add to the list
                yield Document(page_content, metadata=meta)
