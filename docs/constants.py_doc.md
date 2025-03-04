# constants.py

**Path:** `src/alita_sdk/langchain/document_loaders/constants.py`

## Data Flow

The data flow within `constants.py` is primarily focused on mapping file extensions to their respective loader classes. The file begins by importing various loader classes from the `langchain_community.document_loaders` module and custom loaders from the same directory. These loaders are then organized into a dictionary called `loaders_map`, where each key is a file extension and the value is a dictionary containing the loader class, a boolean indicating if multimodal processing is supported, and any additional keyword arguments required for the loader.

For example, the `.png` file extension is mapped to the `AlitaImageLoader` class with multimodal processing enabled and no additional keyword arguments:

```python
loaders_map = {
    '.png': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {}
    },
    # Other mappings...
}
```

This structure allows for easy retrieval of the appropriate loader class based on the file extension, facilitating the processing of various document types.

## Functions Descriptions

The `constants.py` file does not define any functions. Instead, it focuses on importing necessary classes and defining the `loaders_map` dictionary. The primary purpose of this file is to provide a centralized mapping of file extensions to their corresponding loader classes, which can be used by other parts of the application to load and process different types of documents.

## Dependencies Used and Their Descriptions

The file imports several loader classes from the `langchain_community.document_loaders` module and custom loaders from the same directory. These dependencies are essential for the functionality of the `loaders_map` dictionary, as they provide the necessary classes for loading and processing various document types.

### Imported Dependencies:

- `TextLoader`: Used for loading text files.
- `UnstructuredMarkdownLoader`: Used for loading Markdown files.
- `PyPDFLoader`: Used for loading PDF files.
- `UnstructuredPDFLoader`: Used for loading unstructured PDF files.
- `UnstructuredWordDocumentLoader`: Used for loading unstructured Word documents.
- `JSONLoader`: Used for loading JSON files.
- `AirbyteJSONLoader`: Used for loading JSONL files.
- `UnstructuredHTMLLoader`: Used for loading HTML files.
- `UnstructuredPowerPointLoader`: Used for loading PowerPoint files.
- `PythonLoader`: Used for loading Python files.
- `AlitaCSVLoader`: Custom loader for loading CSV files.
- `AlitaDocxMammothLoader`: Custom loader for loading DOCX files using Mammoth.
- `AlitaExcelLoader`: Custom loader for loading Excel files.
- `AlitaImageLoader`: Custom loader for loading image files.

## Functional Flow

The functional flow of `constants.py` is straightforward. The file imports the necessary loader classes and defines the `loaders_map` dictionary. This dictionary is then used by other parts of the application to determine the appropriate loader class for a given file extension. The flow can be summarized as follows:

1. Import necessary loader classes.
2. Define the `loaders_map` dictionary with file extension keys and corresponding loader class values.
3. Use the `loaders_map` dictionary in other parts of the application to load and process documents based on their file extensions.

## Endpoints Used/Created

The `constants.py` file does not define or interact with any endpoints. Its primary purpose is to provide a mapping of file extensions to loader classes, which can be used by other parts of the application to load and process documents.