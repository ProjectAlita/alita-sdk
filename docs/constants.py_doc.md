# constants.py

**Path:** `src/alita_sdk/langchain/document_loaders/constants.py`

## Data Flow

The `constants.py` file primarily defines a mapping between file extensions and their corresponding document loader classes. The data flow in this file is straightforward: it starts with the importation of various loader classes from the `langchain_community.document_loaders` module and custom loaders from the same directory. These classes are then mapped to specific file extensions in the `loaders_map` dictionary. This dictionary is used to dynamically select the appropriate loader class based on the file extension of the document being processed.

For example, when a `.txt` file is encountered, the `TextLoader` class is selected with the `autodetect_encoding` parameter set to `True`.

```python
loaders_map = {
    '.txt': {
        'class': TextLoader,
        'kwargs': {
            'autodetect_encoding': True
        }
    },
    '.md': {
        'class': UnstructuredMarkdownLoader,
        'kwargs': {}
    },
    '.csv': {
        'class': AlitaCSVLoader,
        'kwargs': {
            'encoding': 'utf-8',
            'raw_content': False
        }
    },
    # ... other mappings ...
}
```

In this snippet, the `loaders_map` dictionary maps file extensions to their respective loader classes and any necessary keyword arguments. This allows for flexible and dynamic document loading based on file type.

## Functions Descriptions

The `constants.py` file does not define any functions. Instead, it focuses on importing necessary classes and defining the `loaders_map` dictionary. The primary purpose of this file is to provide a centralized mapping of file extensions to their corresponding loader classes, which can be used throughout the application to load documents dynamically based on their file type.

## Dependencies Used and Their Descriptions

The `constants.py` file imports several dependencies, primarily loader classes from the `langchain_community.document_loaders` module and custom loaders from the same directory. These dependencies are used to define the `loaders_map` dictionary, which maps file extensions to their corresponding loader classes.

- `TextLoader`: A loader class for text files, with an option to autodetect encoding.
- `UnstructuredMarkdownLoader`: A loader class for Markdown files.
- `PyPDFLoader`: A loader class for PDF files.
- `UnstructuredPDFLoader`: A loader class for unstructured PDF files.
- `UnstructuredWordDocumentLoader`: A loader class for Word documents.
- `JSONLoader`: A loader class for JSON files.
- `AirbyteJSONLoader`: A loader class for JSONL files.
- `UnstructuredHTMLLoader`: A loader class for HTML files.
- `UnstructuredPowerPointLoader`: A loader class for PowerPoint files.
- `PythonLoader`: A loader class for Python files.
- `AlitaCSVLoader`: A custom loader class for CSV files.
- `AlitaExcelLoader`: A custom loader class for Excel files.

These dependencies are essential for the dynamic loading of documents based on their file type, as defined in the `loaders_map` dictionary.

## Functional Flow

The functional flow of the `constants.py` file is straightforward. It begins with the importation of necessary loader classes and the definition of the `loaders_map` dictionary. This dictionary maps file extensions to their corresponding loader classes and any necessary keyword arguments. The `loaders_map` dictionary is then used throughout the application to dynamically select the appropriate loader class based on the file extension of the document being processed.

For example, when a document with a `.csv` extension is encountered, the `AlitaCSVLoader` class is selected with the `encoding` parameter set to `utf-8` and the `raw_content` parameter set to `False`.

```python
'.csv': {
    'class': AlitaCSVLoader,
    'kwargs': {
        'encoding': 'utf-8',
        'raw_content': False
    }
}
```

This allows for flexible and dynamic document loading based on file type, ensuring that the appropriate loader class is used for each document.

## Endpoints Used/Created

The `constants.py` file does not define or interact with any endpoints. Its primary purpose is to provide a centralized mapping of file extensions to their corresponding loader classes, which can be used throughout the application to load documents dynamically based on their file type.