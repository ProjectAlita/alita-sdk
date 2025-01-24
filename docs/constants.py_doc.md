# constants.py

**Path:** `src/alita_sdk/langchain/document_loaders/constants.py`

## Data Flow

In the `constants.py` file, the data flow revolves around the mapping of file extensions to their respective document loader classes and configurations. The data originates from the file extensions and is transformed into a dictionary format where each key is a file extension, and the value is another dictionary containing the loader class and its keyword arguments. This mapping is stored in the `loaders_map` variable. The data flow is straightforward, with no intermediate variables or temporary storage. The data is used to configure the appropriate loader for each file type based on its extension.

Example:
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
    # ... other mappings
}
```
In this example, the data flow involves mapping the `.txt` extension to the `TextLoader` class with the `autodetect_encoding` argument set to `True`.

## Functions Descriptions

The `constants.py` file does not contain any functions. Instead, it focuses on defining a dictionary that maps file extensions to their respective loader classes and configurations. Each entry in the dictionary specifies the loader class and any keyword arguments required for that loader. This approach allows for easy configuration and extension of supported file types by simply adding new entries to the dictionary.

## Dependencies Used and Their Descriptions

The `constants.py` file imports several loader classes from the `langchain_community.document_loaders` module and two custom loader classes from the current package. These dependencies are used to define the loader classes for different file types in the `loaders_map` dictionary.

- `TextLoader`: Used for loading text files with optional encoding autodetection.
- `UnstructuredMarkdownLoader`: Used for loading Markdown files.
- `PyPDFLoader`: Used for loading PDF files.
- `UnstructuredPDFLoader`: Used for loading unstructured PDF files.
- `UnstructuredWordDocumentLoader`: Used for loading Word documents.
- `JSONLoader`: Used for loading JSON files.
- `AirbyteJSONLoader`: Used for loading JSONL files.
- `UnstructuredHTMLLoader`: Used for loading HTML files.
- `UnstructuredPowerPointLoader`: Used for loading PowerPoint files.
- `PythonLoader`: Used for loading Python files.
- `AlitaCSVLoader`: Custom loader for loading CSV files with specific configurations.
- `AlitaExcelLoader`: Custom loader for loading Excel files with specific configurations.

## Functional Flow

The functional flow of the `constants.py` file is straightforward. It begins with importing the necessary loader classes from the `langchain_community.document_loaders` module and the custom loader classes from the current package. Then, it defines the `loaders_map` dictionary, which maps file extensions to their respective loader classes and configurations. The file does not contain any functions or complex logic. The primary purpose of this file is to provide a centralized configuration for document loaders based on file extensions.

## Endpoints Used/Created

The `constants.py` file does not define or interact with any endpoints. Its primary purpose is to define a mapping of file extensions to document loader classes and configurations. This mapping is used by other parts of the application to determine the appropriate loader for each file type based on its extension.