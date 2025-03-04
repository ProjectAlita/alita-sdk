# llm_processor.py

**Path:** `src/alita_sdk/langchain/interfaces/llm_processor.py`

## Data Flow

The data flow within `llm_processor.py` revolves around the processing and transformation of data through various models and embeddings. The file primarily deals with the retrieval and summarization of documents, as well as the generation of responses using language models. Data originates from input parameters provided to functions, which are then processed by models or embeddings to produce outputs. For instance, in the `summarize` function, the document content is passed to the `llm_predict` function, which uses a language model to generate a summary. The result is then stored in the document's metadata. Temporary variables such as `content_length` and `file_summary` are used to hold intermediate data during processing.

Example:
```python
content_length = len(document.page_content)
if content_length < 1000 and metadata_key == 'document_summary':
    return document
file_summary = summorization_prompt
result = llm_predict(llmodel, file_summary, document.page_content)
if result:
    document.metadata[metadata_key] = result
return document
```
In this snippet, the document's content length is checked, and if it meets certain criteria, a summary is generated and stored in the document's metadata.

## Functions Descriptions

### get_model

This function retrieves a language model or chat model based on the provided `model_type` and `model_params`. It supports various model types, including preloaded models and custom models specified by their package and class names. The function uses `importlib` to dynamically import and instantiate the model class.

Inputs:
- `model_type` (str): The type of model to retrieve.
- `model_params` (dict): Parameters to initialize the model.

Outputs:
- An instance of the specified model.

Example:
```python
if model_type == "PreloadedChatModel":
    return PreloadedChatModel(**model_params)
if model_type == "Alita":
    from ...llms.alita import AlitaClient
    return AlitaClient(**model_params)
```

### get_embeddings

This function retrieves an embeddings model based on the provided `embeddings_model` and `embeddings_params`. It supports various embeddings models, including preloaded models and custom models specified by their package and class names. The function uses `importlib` to dynamically import and instantiate the embeddings class.

Inputs:
- `embeddings_model` (str): The type of embeddings model to retrieve.
- `embeddings_params` (dict): Parameters to initialize the embeddings model.

Outputs:
- An instance of the specified embeddings model.

Example:
```python
if embeddings_model == "PreloadedEmbeddings":
    return PreloadedEmbeddings(**embeddings_params)
if embeddings_model == "Chroma":
    from langchain_chroma import Chroma
    return Chroma(**embeddings_params)
```

### summarize

This function generates a summary for a given document using a language model and a summarization prompt. If the document's content length is below a certain threshold, the original document is returned. Otherwise, the `llm_predict` function is called to generate the summary, which is then stored in the document's metadata.

Inputs:
- `llmodel`: The language model to use for summarization.
- `document`: The document to summarize.
- `summorization_prompt`: The prompt to guide the summarization.
- `metadata_key` (str, optional): The key to store the summary in the document's metadata.

Outputs:
- The document with the summary stored in its metadata.

Example:
```python
result = llm_predict(llmodel, file_summary, document.page_content)
if result:
    document.metadata[metadata_key] = result
return document
```

### llm_predict

This function uses a language model to generate a prediction based on a given prompt and content. It creates a `PromptTemplate` from the prompt and uses an `LLMChain` to generate the prediction. If an error occurs during prediction, it logs the error and returns an empty string.

Inputs:
- `llmodel`: The language model to use for prediction.
- `prompt`: The prompt to guide the prediction.
- `content`: The content to generate the prediction for.

Outputs:
- The generated prediction as a string.

Example:
```python
try:
    result = llm.predict(content=content)
    return result
except:
    print_log("Failed to generate summary: ", format_exc())
    return ""
```

### get_vectorstore

This function retrieves a vector store object based on the provided `vectorstore_type` and `vectorstore_params`. It supports various vector store types and allows for the inclusion of an embedding function. The function uses `importlib` to dynamically import and instantiate the vector store class.

Inputs:
- `vectorstore_type` (str): The type of vector store to retrieve.
- `vectorstore_params` (dict): Parameters to initialize the vector store.
- `embedding_func` (optional): An embedding function to use with the vector store.

Outputs:
- An instance of the specified vector store.

Example:
```python
if vectorstore_type in vectorstores:
    vectorstore_params = vectorstore_params.copy()
    if embedding_func:
        vectorstore_params['embedding_function'] = embedding_func
    return get_vectorstore_cls(vectorstore_type)(**vectorstore_params)
```

### add_documents

This function adds documents to a vector store. It extracts the text content and metadata from each document and adds them to the vector store.

Inputs:
- `vectorstore`: The vector store to add documents to.
- `documents`: A list of documents to add.

Outputs:
- None

Example:
```python
texts = []
metadata = []
for document in documents:
    texts.append(document.page_content)
    metadata.append(document.metadata)
vectorstore.add_texts(texts, metadatas=metadata)
```

### generateResponse

This function generates a response based on the provided input, guidance message, context message, and other parameters. It retrieves the necessary models and vector stores, invokes a retriever to get relevant documents, and generates a response using a language model. The response can be streamed or returned as a complete text.

Inputs:
- `input`: The input query or message.
- `guidance_message`: A message to guide the response generation.
- `context_message`: A message to provide context for the response.
- `collection`: The name of the document collection to retrieve from.
- `top_k` (int, optional): The number of top documents to retrieve.
- `ai_model` (optional): The language model to use for response generation.
- `ai_model_params` (optional): Parameters to initialize the language model.
- `embedding_model` (optional): The embeddings model to use.
- `embedding_model_params` (optional): Parameters to initialize the embeddings model.
- `vectorstore` (optional): The type of vector store to use.
- `vectorstore_params` (optional): Parameters to initialize the vector store.
- `weights` (optional): Weights to use for the retriever.
- `stream` (bool, optional): Whether to stream the response.

Outputs:
- A dictionary containing the response text and references.

Example:
```python
if stream:
    return {
        "response_iterator": ai.stream(messages),
        "references": references
    }
response_text = ai.invoke(messages).content
return {
    "response": response_text,
    "references": references
}
```

## Dependencies Used and Their Descriptions

### importlib

The `importlib` module is used to dynamically import modules and classes based on their names. This allows for flexible and dynamic loading of models and embeddings specified by their package and class names.

Example:
```python
target_cls = getattr(
    importlib.import_module(target_pkg),
    target_name
)
```

### traceback

The `traceback` module is used to format and print stack traces of exceptions. It is used in the `llm_predict` function to log errors that occur during prediction.

Example:
```python
except:
    print_log("Failed to generate summary: ", format_exc())
```

### langchain.chains.llm.LLMChain

The `LLMChain` class from the `langchain` library is used to create a chain of language model operations. It is used in the `llm_predict` function to generate predictions based on a prompt and content.

Example:
```python
llm = LLMChain(
    llm=llmodel,
    prompt=file_summary_prompt,
    verbose=True,
)
```

### langchain_community.llms

The `langchain_community.llms` module is used to retrieve language models. The `get_llm` function is used to dynamically get a language model based on its name.

Example:
```python
if model_type in llms:
    return get_llm(model_type)(**model_params)
```

### langchain_community.chat_models

The `langchain_community.chat_models` module is used to retrieve chat models. The module's `__all__` attribute is used to check if a model type is a chat model.

Example:
```python
if model_type in chat_models:
    model = getattr(
        __import__("langchain_community.chat_models", fromlist=[model_type]),
        model_type
    )
    return model(**model_params)
```

### langchain_community.embeddings

The `langchain_community.embeddings` module is used to retrieve embeddings models. The module's `__all__` attribute is used to check if an embeddings model type is supported.

Example:
```python
if embeddings_model in embeddings:
    model = getattr(
        __import__("langchain_community.embeddings", fromlist=[embeddings_model]),
        embeddings_model
    )
    return model(**embeddings_params)
```

### langchain_community.vectorstores

The `langchain_community.vectorstores` module is used to retrieve vector store classes. The `get_vectorstore_cls` function is used to dynamically get a vector store class based on its name.

Example:
```python
return get_vectorstore_cls(vectorstore_type)(**vectorstore_params)
```

### langchain.prompts.PromptTemplate

The `PromptTemplate` class from the `langchain.prompts` module is used to create templates for prompts. It is used in the `llm_predict` function to create a prompt template from a given prompt.

Example:
```python
file_summary_prompt = PromptTemplate.from_template(prompt, template_format='jinja2')
```

### langchain.schema.HumanMessage, SystemMessage

The `HumanMessage` and `SystemMessage` classes from the `langchain.schema` module are used to create messages for the language model. They are used in the `generateResponse` function to create a sequence of messages for the language model to process.

Example:
```python
messages.append(SystemMessage(content=context_message))
messages.append(HumanMessage(content=context))
messages.append(HumanMessage(content=input))
```

### PreloadedEmbeddings, PreloadedChatModel

The `PreloadedEmbeddings` and `PreloadedChatModel` classes are custom classes used to represent preloaded embeddings and chat models. They are used in the `get_embeddings` and `get_model` functions to return instances of preloaded models.

Example:
```python
if model_type == "PreloadedChatModel":
    return PreloadedChatModel(**model_params)
if embeddings_model == "PreloadedEmbeddings":
    return PreloadedEmbeddings(**embeddings_params)
```

### AlitaRetriever

The `AlitaRetriever` class is a custom retriever used to retrieve documents from a vector store. It is used in the `generateResponse` function to get relevant documents based on the input query.

Example:
```python
retriever = AlitaRetriever(
    vectorstore=vs,
    doc_library=collection,
    top_k = top_k,
    page_top_k=1,
    weights=weights
)
```

### print_log

The `print_log` function is a custom logging function used to print log messages. It is used in various functions to log information and errors.

Example:
```python
print_log(f"Querying content length: {content_length}")
```

## Functional Flow

The functional flow of `llm_processor.py` involves several key steps:
1. **Model and Embeddings Retrieval:** Functions like `get_model` and `get_embeddings` are used to dynamically retrieve and instantiate models and embeddings based on the provided parameters.
2. **Document Summarization:** The `summarize` function generates summaries for documents using a language model and a summarization prompt. It calls the `llm_predict` function to generate the summary and stores it in the document's metadata.
3. **Prediction Generation:** The `llm_predict` function uses a language model to generate predictions based on a prompt and content. It creates a `PromptTemplate` and an `LLMChain` to perform the prediction.
4. **Vector Store Operations:** Functions like `get_vectorstore` and `add_documents` are used to retrieve vector store objects and add documents to them. These functions support various vector store types and allow for the inclusion of embedding functions.
5. **Response Generation:** The `generateResponse` function generates responses based on input queries, guidance messages, and context messages. It retrieves models and vector stores, invokes a retriever to get relevant documents, and generates responses using a language model. The responses can be streamed or returned as complete texts.

## Endpoints Used/Created

The `llm_processor.py` file does not explicitly define or call any endpoints. Its primary focus is on processing and transforming data using models, embeddings, and vector stores. The functions within the file are designed to be used as part of a larger system, where they can be integrated with other components to provide end-to-end functionality. The file does not include any direct interactions with external APIs or services, and there are no HTTP endpoints defined or called within the code.