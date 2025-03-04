# constants.py

**Path:** `src/alita_sdk/langchain/document_loaders/constants.py`

## Data Flow

The data flow within `constants.py` is primarily concerned with mapping file extensions to their respective loader classes. The file defines a dictionary named `loaders_map` that associates various file extensions with specific loader classes. This mapping allows the system to dynamically select the appropriate loader based on the file type being processed. The data flow can be summarized as follows:

1. **Import Statements:** The file begins by importing various loader classes from the `langchain_community.document_loaders` module and custom loaders from the current package.
2. **Dictionary Definition:** The `loaders_map` dictionary is defined, where each key is a file extension (e.g., `.png`, `.txt`), and the value is another dictionary containing the loader class, a flag indicating if multimodal processing is supported, and any additional keyword arguments required by the loader.
3. **Data Transformation:** When a file needs to be processed, the system looks up the file extension in the `loaders_map` dictionary to retrieve the corresponding loader class and its configuration.

### Example:
```python
loaders_map = {
    '.png': {
        'class': AlitaImageLoader,
        'is_multimodal_processing': True,
        'kwargs': {}
    },
    '.txt': {
        'class': TextLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'autodetect_encoding': True
        }
    }
}
```
*In this example, the `.png` files are mapped to `AlitaImageLoader` with multimodal processing enabled, while `.txt` files are mapped to `TextLoader` with automatic encoding detection.*

## Functions Descriptions

The `constants.py` file does not define any functions. Instead, it focuses on importing necessary modules and defining the `loaders_map` dictionary. The primary purpose of this file is to provide a centralized mapping of file extensions to their respective loader classes, which can be used throughout the application to dynamically select the appropriate loader based on the file type.

## Dependencies Used and Their Descriptions

The `constants.py` file imports several dependencies, primarily loader classes from the `langchain_community.document_loaders` module and custom loaders from the current package. These dependencies are used to populate the `loaders_map` dictionary with the appropriate loader classes for different file types.

### Imported Dependencies:
1. **TextLoader:** A loader class for processing text files.
2. **UnstructuredMarkdownLoader:** A loader class for processing Markdown files.
3. **PyPDFLoader:** A loader class for processing PDF files.
4. **UnstructuredPDFLoader:** A loader class for processing unstructured PDF files.
5. **UnstructuredWordDocumentLoader:** A loader class for processing Word documents.
6. **JSONLoader:** A loader class for processing JSON files.
7. **AirbyteJSONLoader:** A loader class for processing JSONL files.
8. **UnstructuredHTMLLoader:** A loader class for processing HTML files.
9. **UnstructuredPowerPointLoader:** A loader class for processing PowerPoint files.
10. **PythonLoader:** A loader class for processing Python files.
11. **AlitaCSVLoader:** A custom loader class for processing CSV files.
12. **AlitaDocxMammothLoader:** A custom loader class for processing DOCX files using Mammoth.
13. **AlitaExcelLoader:** A custom loader class for processing Excel files.
14. **AlitaImageLoader:** A custom loader class for processing image files.

## Functional Flow

The functional flow of `constants.py` is straightforward and involves the following steps:

1. **Import Loader Classes:** The file begins by importing various loader classes from the `langchain_community.document_loaders` module and custom loaders from the current package.
2. **Define `loaders_map` Dictionary:** The `loaders_map` dictionary is defined, mapping file extensions to their respective loader classes and configurations.
3. **Usage in Application:** When a file needs to be processed, the application looks up the file extension in the `loaders_map` dictionary to retrieve the corresponding loader class and its configuration. This allows the application to dynamically select the appropriate loader based on the file type.

### Example:
```python
from .AlitaCSVLoader import AlitaCSVLoader
from .AlitaDocxMammothLoader import AlitaDocxMammothLoader
from .AlitaExcelLoader import AlitaExcelLoader
from .AlitaImageLoader import AlitaImageLoader

loaders_map = {
    '.csv': {
        'class': AlitaCSVLoader,
        'is_multimodal_processing': False,
        'kwargs': {
            'encoding': 'utf-8',
            'raw_content': False,
            'cleanse': False
        }
    },
    '.docx': {
        'class': AlitaDocxMammothLoader,
        'is_multimodal_processing': True,
        'kwargs': {}
    }
}
```
*In this example, the `.csv` files are mapped to `AlitaCSVLoader` with specific keyword arguments, while `.docx` files are mapped to `AlitaDocxMammothLoader` with multimodal processing enabled.*

## Endpoints Used/Created

The `constants.py` file does not define or interact with any endpoints. Its primary purpose is to provide a centralized mapping of file extensions to their respective loader classes, which can be used throughout the application to dynamically select the appropriate loader based on the file type.