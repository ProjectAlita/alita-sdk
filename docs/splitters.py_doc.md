# splitters.py

**Path:** `src/alita_sdk/langchain/interfaces/splitters.py`

## Data Flow

The data flow within the `splitters.py` file revolves around the `Splitter` class, which is designed to handle the splitting of text documents into smaller chunks based on various criteria. The data originates from a `Document` object, which contains the text content and metadata. This document is passed to the `split` method of the `Splitter` class, which then determines the appropriate splitting strategy based on the `splitter_name` parameter. The data is transformed through different splitting methods such as `line_split`, `paragraph_split`, `sentence_split`, and `chunk_split`, each of which processes the text content and returns a list of smaller `Document` objects. The final destination of the data is the output of these methods, which is a list of split `Document` objects ready for further processing.

Example:
```python
# Example of splitting a document into chunks
splitter = Splitter()
document = Document(page_content="This is a sample text.", metadata={"source": "sample.txt"})
split_documents = splitter.split(document, splitter_name='chunks')
# split_documents now contains the document split into smaller chunks
```

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `Splitter` class with various parameters such as `chunk_size`, `chunk_overlap`, `separators`, `regex_separator`, and `autodetect_language`. These parameters configure the behavior of the text splitting process.

### `autodeted_language`

The `autodeted_language` method attempts to detect the language of a document based on its file extension. It returns a `Language` object if the language is detected, otherwise it returns `None`.

### `split`

The `split` method is the main entry point for splitting a document. It takes a `Document` object and a `splitter_name` parameter to determine the splitting strategy. It calls the appropriate splitting method based on the `splitter_name` and returns the split documents.

### `chunk_split`

The `chunk_split` method splits a document into chunks based on the specified separators or a regex separator. It uses the `RecursiveCharacterTextSplitter` class from the `langchain` library to perform the splitting.

### `line_split`

The `line_split` method splits a document into lines by calling the `chunk_split` method with a newline separator.

### `paragraph_split`

The `paragraph_split` method splits a document into paragraphs by calling the `chunk_split` method with a double newline separator.

### `sentence_split`

The `sentence_split` method splits a document into sentences by calling the `chunk_split` method with a period separator.

## Dependencies Used and Their Descriptions

### `os`

The `os` module is used to handle file path operations, such as extracting the file extension from a file path.

### `langchain_core.documents.Document`

The `Document` class from the `langchain_core.documents` module represents a text document with content and metadata. It is used as the input and output type for the splitting methods.

### `typing`

The `Optional`, `Any`, and `List` types from the `typing` module are used for type hinting in the method signatures.

### `langchain.text_splitter`

The `RecursiveCharacterTextSplitter` and `Language` classes from the `langchain.text_splitter` module are used to perform the actual text splitting based on language and character separators.

## Functional Flow

The functional flow of the `splitters.py` file begins with the initialization of the `Splitter` class, where various parameters are set to configure the splitting behavior. When the `split` method is called with a `Document` object and a `splitter_name`, it determines the appropriate splitting strategy and calls the corresponding method (`line_split`, `paragraph_split`, `sentence_split`, or `chunk_split`). Each of these methods processes the document's text content and returns a list of smaller `Document` objects. The `chunk_split` method uses the `RecursiveCharacterTextSplitter` class to perform the splitting based on the specified separators or a regex separator.

Example:
```python
# Example of splitting a document into sentences
splitter = Splitter()
document = Document(page_content="This is a sample text. It has multiple sentences.", metadata={"source": "sample.txt"})
split_documents = splitter.split(document, splitter_name='sentences')
# split_documents now contains the document split into sentences
```

## Endpoints Used/Created

The `splitters.py` file does not explicitly define or call any endpoints. It focuses on the internal logic for splitting text documents into smaller chunks based on various criteria.