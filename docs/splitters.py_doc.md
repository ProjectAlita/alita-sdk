# splitters.py

**Path:** `src/alita_sdk/langchain/interfaces/splitters.py`

## Data Flow

The data flow within the `splitters.py` file revolves around the `Splitter` class, which is designed to handle the splitting of text documents into smaller chunks based on various criteria. The data originates from a `Document` object, which contains the text content and metadata. This document is passed to the `split` method of the `Splitter` class, which then determines the appropriate splitting strategy based on the `splitter_name` parameter. The text is then processed and split into smaller chunks, which are returned as a list of new `Document` objects.

Example:
```python
# Example of splitting a document into chunks
splitter = Splitter()
document = Document(page_content="This is a sample text.", metadata={"source": "sample.txt"})
chunks = splitter.split(document, splitter_name='chunks')
# chunks now contains the split text as smaller Document objects
```

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `Splitter` class with various parameters such as `chunk_size`, `chunk_overlap`, `separators`, `regex_separator`, and `autodetect_language`. These parameters control how the text will be split.

### `autodeted_language`

The `autodeted_language` method attempts to detect the language of a document based on its file extension. It returns a `Language` object if the language is detected, otherwise it returns `None`.

### `split`

The `split` method is the main entry point for splitting a document. It takes a `Document` object and a `splitter_name` parameter, which determines the splitting strategy. It calls the appropriate splitting method based on the `splitter_name`.

### `chunk_split`

The `chunk_split` method splits the document into chunks based on the specified separators or a regex pattern. It uses the `RecursiveCharacterTextSplitter` class from the `langchain.text_splitter` module to perform the actual splitting.

### `line_split`

The `line_split` method splits the document into chunks based on newline characters (`\n`).

### `paragraph_split`

The `paragraph_split` method splits the document into chunks based on double newline characters (`\n\n`).

### `sentence_split`

The `sentence_split` method splits the document into chunks based on periods (`.`).

## Dependencies Used and Their Descriptions

- `os`: Used for file path operations.
- `langchain_core.documents.Document`: Represents a document with text content and metadata.
- `typing.Optional`, `Any`, `List`: Used for type hinting.
- `langchain.text_splitter.RecursiveCharacterTextSplitter`, `Language`: Used for splitting text based on language and character patterns.

## Functional Flow

1. **Initialization**: The `Splitter` class is initialized with various parameters that control the splitting behavior.
2. **Language Detection**: If `autodetect_language` is enabled, the language of the document is detected based on its file extension.
3. **Splitting**: The `split` method is called with a `Document` object and a `splitter_name`. The appropriate splitting method is selected and called.
4. **Chunking**: The document is split into smaller chunks based on the selected strategy and returned as a list of new `Document` objects.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. It focuses on the internal logic for splitting text documents into smaller chunks.