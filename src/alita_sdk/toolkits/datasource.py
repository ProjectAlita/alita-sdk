from typing import List, Any
from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_core.tools import BaseTool
from ..tools.datasource import DatasourcePredict, DatasourceSearch

class DatasourcesToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    
    @classmethod
    def get_toolkit(cls, client: Any, datasource_ids: list[int], selected_tools: list[str] = [] ):
        tools = []
        for datasource_id in datasource_ids:
            datasource = client.datasource(datasource_id)
            if selected_tools:
                if 'chat' in selected_tools:
                    tools.append(DatasourcePredict(name=f'{datasource.name}Predict', 
                                                description=f'Search and summarize. {datasource.description}',
                                                datasource=datasource))
                if 'search' in selected_tools:
                    tools.append(DatasourceSearch(name=f'{datasource.name}Search', 
                                                  description=f'Search return results. {datasource.description}',
                                                  datasource=datasource))
            else:
                tools.append(DatasourcePredict(datasource=datasource, name=f'{datasource.name}Predict', 
                                               description=f'Search and summarize. {datasource.description}'))
                
                tools.append(DatasourceSearch(datasource=datasource,name=f'{datasource.name}Search', 
                                              description=f'Search return results. {datasource.description}'))
        return cls(tools=tools)
            
    def get_tools(self):
        return self.tools
    