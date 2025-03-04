# tools.py

**Path:** `src/alita_sdk/toolkits/tools.py`

## Data Flow

The data flow within `tools.py` is structured around the retrieval and configuration of various toolkits and tools. The primary functions, `get_toolkits` and `get_tools`, orchestrate the collection and assembly of these components. Data originates from the predefined configurations and settings within the toolkits and tools, which are then aggregated and returned as comprehensive lists.

For instance, in the `get_tools` function, the data flow begins with the input parameter `tools_list`, which contains the specifications for the tools to be retrieved. This list is iterated over, and based on the type of each tool, corresponding toolkit methods are invoked to fetch the necessary tools. The data is temporarily stored in lists such as `prompts` and `tools`, which are then combined and returned as the final output.

```python
prompts = []
tools = []
for tool in tools_list:
    if tool['type'] == 'prompt':
        prompts.append([
            int(tool['settings']['prompt_id']),
            int(tool['settings']['prompt_version_id'])
        ])
    elif tool['type'] == 'datasource':
        tools.extend(DatasourcesToolkit.get_toolkit(
            alita,
            datasource_ids=[int(tool['settings']['datasource_id'])],
            selected_tools=tool['settings']['selected_tools']).get_tools())
    # Additional conditions for other tool types
```

In this snippet, the data flow is evident as the `tools_list` is processed, and data is collected into the `prompts` and `tools` lists based on the tool type.

## Functions Descriptions

### `get_toolkits`

This function is responsible for aggregating the configurations of core and community toolkits. It calls the `toolkit_config_schema` method of each toolkit to retrieve their configurations and combines them into a single list.

- **Inputs:** None
- **Processing:** Calls `toolkit_config_schema` on each toolkit and combines the results.
- **Outputs:** A list of toolkit configurations.

```python
def get_toolkits():
    core_toolkits = [
        PromptToolkit.toolkit_config_schema(),
        DatasourcesToolkit.toolkit_config_schema(),
        ApplicationToolkit.toolkit_config_schema(),
        ArtifactToolkit.toolkit_config_schema(),
        VectorStoreToolkit.toolkit_config_schema()
    ]
    
    community_toolkits = [ 
        AnalyseJira.toolkit_config_schema()
    ]
    
    return  core_toolkits + community_toolkits + alita_toolkits()
```

### `get_tools`

This function retrieves the tools specified in the `tools_list` parameter. It processes each tool based on its type and uses the corresponding toolkit to fetch the tools. The function supports various tool types such as `prompt`, `datasource`, `application`, `artifact`, `analyse_jira`, and `vectorstore`.

- **Inputs:** `tools_list` (list of tool specifications), `alita` (AlitaClient instance), `llm` (LLMLikeObject instance)
- **Processing:** Iterates over `tools_list`, fetches tools from the appropriate toolkit, and aggregates them.
- **Outputs:** A list of tools.

```python
def get_tools(tools_list: list, alita: 'AlitaClient', llm: 'LLMLikeObject') -> list:
    prompts = []
    tools = []
    for tool in tools_list:
        if tool['type'] == 'prompt':
            prompts.append([
                int(tool['settings']['prompt_id']),
                int(tool['settings']['prompt_version_id'])
            ])
        elif tool['type'] == 'datasource':
            tools.extend(DatasourcesToolkit.get_toolkit(
                alita,
                datasource_ids=[int(tool['settings']['datasource_id'])],
                selected_tools=tool['settings']['selected_tools']).get_tools())
        elif tool['type'] == 'application':
            tools.extend(ApplicationToolkit.get_toolkit(
                alita,
                application_id=int(tool['settings']['application_id']),
                application_version_id=int(tool['settings']['application_version_id']),
                app_api_key=alita.auth_token,
                selected_tools=[]
            ).get_tools())
        elif tool['type'] == 'artifact':
            tools.extend(ArtifactToolkit.get_toolkit(
                client=alita,
                bucket=tool['settings']['bucket'],
                selected_tools=tool['settings'].get('selected_tools', [])
            ).get_tools())
        if tool['type'] == 'analyse_jira':
            tools.extend(AnalyseJira.get_toolkit(
                client=alita, 
                **tool['settings']).get_tools())
        if tool['type'] == 'vectorstore':
            tools.extend(VectorStoreToolkit.get_toolkit(
                llm=llm,
                **tool['settings']).get_tools())
    if len(prompts) > 0:
        tools += PromptToolkit.get_toolkit(alita, prompts).get_tools()
    tools += alita_tools(tools_list, alita, llm)
    return tools
```

## Dependencies Used and Their Descriptions

### `logging`

- **Purpose:** Used for logging messages within the module.
- **Usage:** Configures a logger instance for the module.

```python
import logging
logger = logging.getLogger(__name__)
```

### `alita_tools` and `alita_toolkits`

- **Purpose:** These are imported from the `alita_tools` module and are used to fetch additional tools and toolkits.
- **Usage:** The `alita_tools` function is called within `get_tools` to fetch additional tools, and `alita_toolkits` is used in `get_toolkits` to fetch additional toolkits.

```python
from alita_tools import get_tools as alita_tools
from alita_tools import get_toolkits as alita_toolkits
```

### Various Toolkit Modules

- **Purpose:** These modules provide the configurations and tools for different functionalities such as prompts, datasources, applications, artifacts, and vector stores.
- **Usage:** Each toolkit module is imported and used within the `get_toolkits` and `get_tools` functions to fetch configurations and tools.

```python
from .prompt import PromptToolkit
from .datasource import DatasourcesToolkit
from .application import ApplicationToolkit
from .artifact import ArtifactToolkit
from .vectorstore import VectorStoreToolkit
```

### `AnalyseJira`

- **Purpose:** This is a community toolkit for analyzing Jira data.
- **Usage:** Imported and used within the `get_toolkits` and `get_tools` functions to fetch configurations and tools related to Jira analysis.

```python
from ..community.eda.jiratookit import AnalyseJira
```

## Functional Flow

The functional flow of `tools.py` revolves around the retrieval and configuration of toolkits and tools. The process begins with the invocation of `get_toolkits` to fetch the configurations of all core and community toolkits. This function aggregates the configurations and returns them as a single list.

Next, the `get_tools` function is called with a list of tool specifications. This function iterates over the list, determines the type of each tool, and uses the corresponding toolkit to fetch the tools. The tools are aggregated into a list and returned as the final output.

The flow can be summarized as follows:
1. Call `get_toolkits` to fetch toolkit configurations.
2. Call `get_tools` with a list of tool specifications.
3. Iterate over the tool specifications and fetch tools from the appropriate toolkit.
4. Aggregate the fetched tools and return them.

## Endpoints Used/Created

There are no explicit endpoints used or created within `tools.py`. The module focuses on the internal retrieval and configuration of toolkits and tools based on predefined specifications.