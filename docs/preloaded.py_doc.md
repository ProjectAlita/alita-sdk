# preloaded.py

**Path:** `src/alita_sdk/llms/preloaded.py`

## Data Flow

The data flow within `preloaded.py` revolves around the interaction between the `PreloadedEmbeddings` and `PreloadedChatModel` classes and their respective methods. Data originates from the input parameters provided to these methods, such as texts for embedding or messages for generating chat responses. The data is then processed through various transformations and tasks managed by the `arbiter` library's `TaskNode` and `EventNode` components. These nodes handle the execution of tasks and the communication of events, ensuring that the data is processed asynchronously and efficiently. The final output is the result of these tasks, such as embedded vectors or generated chat messages, which are returned to the caller.

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
In this example, the `embed_documents` method starts a task to embed the provided texts and waits for the task to complete, returning the result.

## Functions Descriptions

### `PreloadedEmbeddings.__init__`

Initializes the `PreloadedEmbeddings` class, setting up the `EventNode` and `TaskNode` for managing tasks and events.

### `PreloadedEmbeddings.embed_documents`

Embeds a list of documents by starting a task with the `TaskNode` and returning the result.

### `PreloadedEmbeddings.embed_query`

Embeds a single query text by starting a task with the `TaskNode` and returning the result.

### `PreloadedChatModel.__init__`

Initializes the `PreloadedChatModel` class, setting up the `EventNode`, `TaskNode`, and local streams for managing tasks, events, and streaming data.

### `PreloadedChatModel._remove_non_system_messages`

Removes non-system messages from a list of messages, up to a specified count.

### `PreloadedChatModel._count_tokens`

Counts the number of tokens in a list of messages or a single message using the `tiktoken` library.

### `PreloadedChatModel._limit_tokens`

Limits the number of tokens in a list of messages to ensure it does not exceed the token limit.

### `PreloadedChatModel._generate`

Generates a chat response by starting a task with the `TaskNode` and returning the result.

### `PreloadedChatModel._stream`

Streams chat responses by starting a task with the `TaskNode` and yielding chunks of the response as they are received.

## Dependencies Used and Their Descriptions

### `json`

Used for serializing and deserializing JSON data.

### `uuid`

Used for generating unique identifiers for streams.

### `queue`

Used for managing queues of events in the streaming process.

### `pydantic`

Used for data validation and settings management.

### `langchain_core`

Provides core components for language models, embeddings, messages, and outputs.

### `arbiter`

Manages tasks and events, providing the `EventNode` and `TaskNode` components used for asynchronous processing.

### `tiktoken`

Used for encoding and counting tokens in text data.

## Functional Flow

1. **Initialization**: The `PreloadedEmbeddings` and `PreloadedChatModel` classes are initialized, setting up the necessary components for task and event management.
2. **Embedding Documents**: The `embed_documents` method in `PreloadedEmbeddings` starts a task to embed the provided texts and waits for the result.
3. **Embedding Query**: The `embed_query` method in `PreloadedEmbeddings` starts a task to embed the provided query text and waits for the result.
4. **Generating Chat Response**: The `_generate` method in `PreloadedChatModel` starts a task to generate a chat response based on the provided messages and waits for the result.
5. **Streaming Chat Response**: The `_stream` method in `PreloadedChatModel` starts a task to stream chat responses and yields chunks of the response as they are received.

## Endpoints Used/Created

No explicit endpoints are defined or called within this file. The functionality relies on the `arbiter` library's `TaskNode` and `EventNode` for managing tasks and events asynchronously.