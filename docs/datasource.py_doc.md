# datasource.py

**Path:** `src/alita_sdk/clients/datasource.py`

## Data Flow

The data flow within the `datasource.py` file revolves around the `AlitaDataSource` class. This class is initialized with several parameters, including `alita`, `datasource_id`, `name`, `description`, `datasource_settings`, and `datasource_predict_settings`. The primary data interactions occur within the `predict` and `search` methods. The `predict` method takes `user_input` and an optional `chat_history` list, which defaults to an empty list if not provided. It then calls the `rag` method on the `alita` object, passing the `datasource_id`, `chat_history`, and `user_input`. The `search` method takes a `query` string and calls the `search` method on the `alita` object, passing the `datasource_id`, a list containing a `HumanMessage` with the query content, and the `datasource_settings`.

Example:
```python
class AlitaDataSource:
    def __init__(self, alita: Any, datasource_id: int, name: str, description: str,
                 datasource_settings, datasource_predict_settings):
        self.alita = alita
        self.name = name
        self.description = description
        self.datasource_id = datasource_id
        self.datasource_settings = datasource_settings
        self.datasource_predict_settings = datasource_predict_settings

    def predict(self, user_input: str, chat_history: Optional[list] = None):
        if chat_history is None:
            chat_history = []
        return self.alita.rag(datasource_id=self.datasource_id,
                              chat_history=chat_history,
                              user_input=user_input)

    def search(self, query: str):
        return self.alita.search(self.datasource_id, [HumanMessage(content=query)],
                                 self.datasource_settings)
```

## Functions Descriptions

### `__init__`

The `__init__` method initializes an instance of the `AlitaDataSource` class. It sets up the instance with the provided parameters: `alita`, `datasource_id`, `name`, `description`, `datasource_settings`, and `datasource_predict_settings`.

### `predict`

The `predict` method takes `user_input` and an optional `chat_history` list. If `chat_history` is not provided, it defaults to an empty list. The method then calls the `rag` method on the `alita` object, passing the `datasource_id`, `chat_history`, and `user_input`.

### `search`

The `search` method takes a `query` string and calls the `search` method on the `alita` object, passing the `datasource_id`, a list containing a `HumanMessage` with the query content, and the `datasource_settings`.

## Dependencies Used and Their Descriptions

### `typing`

The `typing` module is used for type hinting, specifically `Any` and `Optional`.

### `langchain_core.messages`

The `langchain_core.messages` module is used to import the `HumanMessage` class, which is used in the `search` method to wrap the query content.

## Functional Flow

1. An instance of `AlitaDataSource` is created with the required parameters.
2. The `predict` method is called with `user_input` and optionally `chat_history`.
3. The `predict` method calls the `rag` method on the `alita` object with the necessary parameters.
4. The `search` method is called with a `query` string.
5. The `search` method calls the `search` method on the `alita` object with the necessary parameters.

## Endpoints Used/Created

There are no explicit endpoints defined or used within this file. The interactions are primarily with the `alita` object, which is expected to have the `rag` and `search` methods.