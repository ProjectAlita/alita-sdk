from typing import List, Any
from pydantic import create_model, BaseModel
from pydantic.fields import FieldInfo
from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_core.tools import BaseTool
from ..tools.datasource import DatasourcePredict, DatasourceSearch, datasourceToolSchema

class DatasourcesToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    
    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        return create_model(
            "datasource",
            client = (Any, FieldInfo(description="Client object", required=True, autopopulate=True)),
            datasource_ids = (list, FieldInfo(description="List of datasource ids")),
            selected_tools = (list, FieldInfo(description="List of selected tools", default=['chat', 'search'])),
            is_workflow = (bool, FieldInfo(description="Is this a workflow", default=False, required=False, autopopulate=True))
        )
    
    @classmethod
    def get_toolkit(cls, client: Any, datasource_ids: list[int], selected_tools: list[str] = [], is_workflow: bool=False):
        tools = []
        for datasource_id in datasource_ids:
            datasource = client.datasource(datasource_id)
            if len(selected_tools) == 0 or 'chat' in selected_tools:
                tools.append(DatasourcePredict(name=f'{datasource.name}Predict', 
                                            description=f'Search and summarize. {datasource.description}',
                                            datasource=datasource, 
                                            args_schema=datasourceToolSchema,
                                            return_type='dict' if is_workflow else 'str'))
            if len(selected_tools) == 0 or 'search' in selected_tools:
                tools.append(DatasourceSearch(name=f'{datasource.name}Search', 
                                                description=f'Search return results. {datasource.description}',
                                                datasource=datasource, 
                                                args_schema=datasourceToolSchema,
                                                return_type='dict' if is_workflow else 'str'))
        return cls(tools=tools)
            
    def get_tools(self):
        return self.tools
    