from typing import List, Any
from pydantic import create_model, BaseModel, Field
from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_core.tools import BaseTool, ToolException
from ..tools.datasource import DatasourcePredict, DatasourceSearch, datasourceToolSchema
from alita_tools.utils import clean_string


class DatasourcesToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    
    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        return create_model(
            "datasource",
            # client = (Any, FieldInfo(description="Client object", required=True, autopopulate=True)),
            datasource_ids = (list, Field(description="List of datasource ids", alias="datasource_id")),
            selected_tools = (list, Field(description="List of selected tools", default=['chat', 'search']))
        )
    
    @classmethod
    def get_toolkit(cls, client: Any, datasource_ids: list[int], selected_tools: list[str] = []):
        tools = []
        for datasource_id in datasource_ids:
            datasource = client.datasource(datasource_id)
            ds_name = clean_string(datasource.name)
            if len(ds_name) == 0:
                raise ToolException(f'Datasource with id {datasource_id} has incorrect name (i.e. special characters, etc.)')
            if len(selected_tools) == 0 or 'chat' in selected_tools:
                tools.append(DatasourcePredict(name=f'{ds_name}Predict',
                                            description=f'Search and summarize. {datasource.description}',
                                            datasource=datasource, 
                                            args_schema=datasourceToolSchema,
                                            return_type='str'))
            if len(selected_tools) == 0 or 'search' in selected_tools:
                tools.append(DatasourceSearch(name=f'{ds_name}Search',
                                                description=f'Search return results. {datasource.description}',
                                                datasource=datasource, 
                                                args_schema=datasourceToolSchema,
                                                return_type='str'))
        return cls(tools=tools)
            
    def get_tools(self):
        return self.tools
    