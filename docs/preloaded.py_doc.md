# preloaded.py

**Path:** `src/alita_sdk/llms/preloaded.py`

## Data Flow

The data flow within `preloaded.py` revolves around the initialization and usage of preloaded models for embeddings and chat functionalities. The data originates from the input texts or messages provided to the `PreloadedEmbeddings` and `PreloadedChatModel` classes. These inputs are processed through various methods that interact with an event-driven architecture using `arbiter` and `worker_core` modules. The data is transformed into tasks that are managed by `TaskNode` instances, which handle the execution and retrieval of results. The final output is the embedded vectors or generated chat responses, which are returned to the caller.

Example:
```python
class PreloadedEmbeddings(Embeddings):
    def embed_documents(self, texts):
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
In this example, the `embed_documents` method takes a list of texts, creates a task with the necessary parameters, and starts the task using `task_node`. The result of the task is then retrieved and returned.

## Functions Descriptions

### `PreloadedEmbeddings.__init__`
Initializes the `PreloadedEmbeddings` class by setting up the event and task nodes using the `arbiter` and `worker_core` modules. It configures the task node with specific parameters such as pool, task limit, and retention period.

### `PreloadedEmbeddings.embed_documents`
Embeds a list of documents by creating and starting a task with the method `embed_documents`. The task is executed, and the result is returned.

### `PreloadedEmbeddings.embed_query`
Embeds a single query text by creating and starting a task with the method `embed_query`. The task is executed, and the result is returned.

### `PreloadedChatModel.__init__`
Initializes the `PreloadedChatModel` class by setting up the event and task nodes, similar to `PreloadedEmbeddings`. It also subscribes to stream events and initializes local streams for handling streaming data.

### `PreloadedChatModel._remove_non_system_messages`
Removes non-system messages from the data up to a specified count. This is used to manage the number of tokens in the input data.

### `PreloadedChatModel._count_tokens`
Counts the number of tokens in the input data using the `tiktoken` library.

### `PreloadedChatModel._limit_tokens`
Limits the number of tokens in the input data to ensure it does not exceed the token limit. It removes non-system messages iteratively until the token count is within the limit.

### `PreloadedChatModel._generate`
Generates a chat response by creating and starting a task with the method `__call__`. The task is executed, and the generated text is returned as a `ChatResult`.

### `PreloadedChatModel._stream`
Streams chat responses by creating and starting a task with the method `stream`. It handles stream events and yields `ChatGenerationChunk` instances as new tokens are generated.

## Dependencies Used and Their Descriptions

### `json`
Used for serializing and deserializing data to and from JSON format.

### `uuid`
Used for generating unique identifiers for stream IDs.

### `queue`
Used for managing local streams in the `PreloadedChatModel` class.

### `pydantic`
Used for data validation and settings management.

### `langchain_core`
Provides core functionalities for embeddings, language models, messages, and outputs.

### `arbiter`
Used for creating and managing event and task nodes, which handle the execution of tasks in an event-driven architecture.

### `worker_core`
Provides configurations and utilities for setting up event and task nodes.

### `tiktoken`
Used for encoding text data into tokens and counting the number of tokens in the input data.

## Functional Flow

1. **Initialization**: The `PreloadedEmbeddings` and `PreloadedChatModel` classes are initialized, setting up event and task nodes.
2. **Embedding Documents**: The `embed_documents` method in `PreloadedEmbeddings` creates and starts a task to embed a list of documents, and returns the result.
3. **Embedding Query**: The `embed_query` method in `PreloadedEmbeddings` creates and starts a task to embed a single query text, and returns the result.
4. **Generating Chat Response**: The `_generate` method in `PreloadedChatModel` creates and starts a task to generate a chat response, and returns the result as a `ChatResult`.
5. **Streaming Chat Response**: The `_stream` method in `PreloadedChatModel` creates and starts a task to stream chat responses, handling stream events and yielding `ChatGenerationChunk` instances.

## Endpoints Used/Created

No explicit endpoints are defined or called within the provided file. The functionality relies on event and task nodes for communication and task execution.