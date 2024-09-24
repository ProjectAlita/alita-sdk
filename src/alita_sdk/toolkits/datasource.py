from typing import List, Any
from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_core.tools import BaseTool
from ..tools.datasource import DatasourcePredict, DatasourceSearch, datasourceToolSchema

class DatasourcesToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    
    @classmethod
    def get_toolkit(cls, client: Any, datasource_ids: list[int], selected_tools: list[str] = []):
        tools = []
        for datasource_id in datasource_ids:
            datasource = client.datasource(datasource_id)
            if len(selected_tools) == 0 or 'chat' in selected_tools:
                tools.append(DatasourcePredict(name=f'{datasource.name}Predict', 
                                            description=f'Search and summarize. {datasource.description}',
                                            datasource=datasource, 
                                            args_schema=datasourceToolSchema))
            if len(selected_tools) == 0 or 'search' in selected_tools:
                tools.append(DatasourceSearch(name=f'{datasource.name}Search', 
                                                description=f'Search return results. {datasource.description}',
                                                datasource=datasource, 
                                                args_schema=datasourceToolSchema))
        return cls(tools=tools)
            
    def get_tools(self):
        return self.tools
    