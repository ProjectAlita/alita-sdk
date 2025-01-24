# preloaded.py

**Path:** `src/alita_sdk/llms/preloaded.py`

## Data Flow

The data flow within `preloaded.py` revolves around the interaction between the `PreloadedEmbeddings` and `PreloadedChatModel` classes and their respective methods. Data originates from the input texts or messages provided to these classes. For instance, in the `embed_documents` method of `PreloadedEmbeddings`, the input texts are passed to the `task_node.start_task` method, which initiates a task to embed the documents. The task results are then retrieved using `task_node.join_task`.

Similarly, in the `PreloadedChatModel` class, the `_generate` and `_stream` methods handle the flow of messages through various transformations and tasks. The messages are first processed to map roles and limit tokens, then passed to the `task_node.start_task` method to invoke the model. The generated text or stream events are then processed and returned as results.

Example:
```python
# Example from PreloadedEmbeddings class

def embed_documents(self, texts):
    """ Embed search docs """
    task_id = self.task_node.start_task(
        name="invoke_model",
        kwargs={
            "routing key": self.model_name,
            "method": "embed_documents",
            "method_args": [texts],
            "method_kwargs": {},
        },
        pool="indexer",
    )
    return self.task_node.join_task(task_id)
```

## Functions Descriptions

### `PreloadedEmbeddings.__init__`

The constructor initializes the `PreloadedEmbeddings` class by setting up the model name and creating an event node and task node using the `arbiter` and `worker_core` modules. These nodes are essential for managing tasks related to embedding documents and queries.

### `PreloadedEmbeddings.embed_documents`

This method embeds a list of documents by starting a task with the `task_node` to invoke the model's `embed_documents` method. The task results are then joined and returned.

### `PreloadedEmbeddings.embed_query`

Similar to `embed_documents`, this method embeds a single query text by starting a task with the `task_node` to invoke the model's `embed_query` method. The task results are joined and returned.

### `PreloadedChatModel.__init__`

The constructor initializes the `PreloadedChatModel` class by setting up the model parameters and creating event and task nodes. It also sets up local streams for handling streaming events.

### `PreloadedChatModel._generate`

This method generates a response based on the input messages. It processes the messages, limits tokens, and starts a task with the `task_node` to invoke the model's `__call__` method. The generated text is then wrapped in an `AIMessage` and returned as a `ChatResult`.

### `PreloadedChatModel._stream`

This method handles streaming responses. It processes the input messages, starts a task with the `task_node` to invoke the model's `stream` method, and yields chunks of generated text as they are received.

## Dependencies Used and Their Descriptions

### `json`

Used for serializing and deserializing data, particularly in the `_generate` and `_stream` methods to convert messages to and from JSON format.

### `uuid`

Used in the `_stream` method to generate unique stream IDs for managing streaming events.

### `queue`

Used in the `_stream` method to handle the queue of streaming events.

### `pydantic`

Provides the `PrivateAttr` used for defining private attributes in the `PreloadedChatModel` class.

### `langchain_core`

Includes various modules such as `Embeddings`, `BaseChatModel`, `AIMessage`, `AIMessageChunk`, `ChatGeneration`, `ChatGenerationChunk`, and `ChatResult`, which are essential for the functionality of the `PreloadedEmbeddings` and `PreloadedChatModel` classes.

### `arbiter` and `worker_core`

These modules are used to create and manage event and task nodes, which are crucial for handling tasks related to embedding and generating responses.

## Functional Flow

1. **Initialization**: The `PreloadedEmbeddings` and `PreloadedChatModel` classes are initialized, setting up model parameters and creating event and task nodes.
2. **Embedding Documents/Queries**: The `embed_documents` and `embed_query` methods in `PreloadedEmbeddings` start tasks to invoke the model's embedding methods and return the results.
3. **Generating Responses**: The `_generate` method in `PreloadedChatModel` processes input messages, limits tokens, starts a task to invoke the model's `__call__` method, and returns the generated text as a `ChatResult`.
4. **Streaming Responses**: The `_stream` method in `PreloadedChatModel` handles streaming events by starting a task to invoke the model's `stream` method and yielding chunks of generated text.

## Endpoints Used/Created

No explicit endpoints are defined or called within the `preloaded.py` file. The functionality primarily revolves around embedding and generating responses using preloaded models and managing tasks through event and task nodes.
