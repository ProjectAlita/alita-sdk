# preloaded.py

**Path:** `src/alita_sdk/llms/preloaded.py`

## Data Flow

The data flow within `preloaded.py` revolves around the interaction with preloaded models for embeddings and chat functionalities. The data originates from the input texts or messages provided to the `PreloadedEmbeddings` and `PreloadedChatModel` classes. These inputs are processed and transformed into embeddings or chat responses through a series of method calls and interactions with task nodes. The data is temporarily stored in variables and task nodes before being returned as the final output. For example, in the `embed_documents` method of `PreloadedEmbeddings`, the input texts are passed to the `start_task` method of the task node, and the resulting embeddings are retrieved using the `join_task` method.

```python
# Example of data transformation in embed_documents method

def embed_documents(self, texts):
    """ Embed search docs """
    task_id = self.task_node.start_task(
        name="invoke_model",
        kwargs={
            "routing_key": self.model_name,
            "method": "embed_documents",
            "method_args": [texts],
            "method_kwargs": {},
        },
        pool="indexer",
    )
    return self.task_node.join_task(task_id)
```

## Functions Descriptions

### PreloadedEmbeddings

- **__init__**: Initializes the `PreloadedEmbeddings` class with the model name and sets up the event and task nodes.
- **embed_documents**: Embeds the input documents by starting a task on the task node and retrieving the embeddings.
- **embed_query**: Embeds the input query text by starting a task on the task node and retrieving the embeddings.

### PreloadedChatModel

- **__init__**: Initializes the `PreloadedChatModel` class with various parameters and sets up the event and task nodes, as well as local streams.
- **_remove_non_system_messages**: Removes non-system messages from the input data up to a specified count.
- **_count_tokens**: Counts the number of tokens in the input data using the `tiktoken` library.
- **_limit_tokens**: Limits the number of tokens in the input data to stay within the token limit.
- **_llm_type**: Returns the model name.
- **_generate**: Generates a chat response by starting a task on the task node and retrieving the result.
- **_stream**: Streams chat responses by starting a task on the task node and yielding the result chunks.

## Dependencies Used and Their Descriptions

- **json**: Used for serializing and deserializing JSON data.
- **uuid**: Used for generating unique identifiers for streams.
- **queue**: Used for managing local streams.
- **pydantic**: Used for data validation and settings management.
- **langchain_core**: Provides core functionalities for embeddings, language models, messages, and outputs.
- **arbiter**: Used for creating and managing event and task nodes.
- **tools.worker_core**: Provides configurations for the event node.
- **tiktoken**: Used for encoding and counting tokens in the input data.

## Functional Flow

The functional flow in `preloaded.py` involves initializing the `PreloadedEmbeddings` and `PreloadedChatModel` classes, setting up event and task nodes, and processing input data to generate embeddings or chat responses. The process is initiated by calling the respective methods (`embed_documents`, `embed_query`, `_generate`, `_stream`) with the input data. The data is then transformed and processed through the task nodes, and the final output is returned or streamed. Error handling is implemented using try-except blocks to catch and log exceptions during task execution.

## Endpoints Used/Created

There are no explicit endpoints defined or called within `preloaded.py`. The functionality primarily revolves around interacting with preloaded models through event and task nodes.
