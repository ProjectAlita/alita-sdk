# AlitaTableLoader.py

**Path:** `src/alita_sdk/langchain/document_loaders/AlitaTableLoader.py`

## Data Flow

The data flow within the `AlitaTableLoader.py` file begins with the initialization of the `AlitaTableLoader` class, which sets up various parameters such as `file_path`, `json_documents`, `raw_content`, `columns`, and `cleanse`. When the `load` method is called, it reads data from the specified file path and processes each row of data. The data is then transformed based on the specified columns and cleansing options before being converted into `Document` objects. These `Document` objects are then returned as a list. The data flow can be summarized as follows:

1. Initialization of the `AlitaTableLoader` class with specified parameters.
2. Reading data from the file path using the `read` method.
3. Processing each row of data using the `row_processor` method.
4. Transforming the data based on specified columns and cleansing options.
5. Converting the transformed data into `Document` objects.
6. Returning the list of `Document` objects.

Example:
```python
class AlitaTableLoader(BaseLoader):
    def __init__(self, file_path: str, json_documents: bool = True, raw_content: bool = False, columns: Optional[List[str]] = None, cleanse: bool = True):
        self.raw_content = raw_content
        self.file_path = file_path
        self.json_documents = json_documents
        self.columns = columns
        self.cleanse = cleanse

    def load(self) -> List[Document]:
        docs = []
        for idx, row in enumerate(self.read()):
            metadata = {
                "source": f'{self.file_path}:{idx+1}',
                "table_source": self.file_path,
            }
            if self.raw_content:
                docs.append(Document(page_content=row, metadata=metadata))
                continue
            if self.json_documents:
                metadata['columns'] = list(row.keys())
                metadata['og_data'] = dumps(row)
                docs.append(Document(page_content=self.row_processor(row), metadata=metadata))
            else:
                content = "\t".join([str(value) for value in row.values()])
                docs.append(Document(page_content=content, metadata=metadata))
        return docs
```

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `AlitaTableLoader` class with the following parameters:
- `file_path`: The path to the file to be loaded.
- `json_documents`: A boolean indicating whether to convert rows to JSON documents.
- `raw_content`: A boolean indicating whether to keep the raw content of the rows.
- `columns`: An optional list of columns to be included in the processed data.
- `cleanse`: A boolean indicating whether to cleanse the data.

Example:
```python
def __init__(self, file_path: str, json_documents: bool = True, raw_content: bool = False, columns: Optional[List[str]] = None, cleanse: bool = True):
    self.raw_content = raw_content
    self.file_path = file_path
    self.json_documents = json_documents
    self.columns = columns
    self.cleanse = cleanse
```

### `load`

The `load` method reads data from the file path and processes each row of data. It then converts the processed data into `Document` objects and returns them as a list.

Example:
```python
def load(self) -> List[Document]:
    docs = []
    for idx, row in enumerate(self.read()):
        metadata = {
            "source": f'{self.file_path}:{idx+1}',
            "table_source": self.file_path,
        }
        if self.raw_content:
            docs.append(Document(page_content=row, metadata=metadata))
            continue
        if self.json_documents:
            metadata['columns'] = list(row.keys())
            metadata['og_data'] = dumps(row)
            docs.append(Document(page_content=self.row_processor(row), metadata=metadata))
        else:
            content = "\t".join([str(value) for value in row.values()])
            docs.append(Document(page_content=content, metadata=metadata))
    return docs
```

### `row_processor`

The `row_processor` method processes a row of data based on the specified columns and cleansing options. It returns the processed data as a string.

Example:
```python
def row_processor(self, row: dict) -> str:
    if self.columns:
        row_slice = (
            str(row[column.strip()]).lower()
            for column in self.columns
        )
        if self.cleanse:
            return cleanse_data('\n'.join(row_slice))
        return '\n'.join(row_slice)
    else:
        if self.cleanse:
            return cleanse_data('\n'.join(str(value) for value in row.values()))
        return '\n'.join(str(value) for value in row.values())
```

## Dependencies Used and Their Descriptions

### `langchain_community.document_loaders.base`

The `BaseLoader` class from the `langchain_community.document_loaders.base` module is used as the base class for `AlitaTableLoader`. It provides the basic structure and functionality for loading documents.

### `langchain_core.documents`

The `Document` class from the `langchain_core.documents` module is used to create document objects that store the processed data and metadata.

### `typing`

The `List`, `Optional`, and `Iterator` types from the `typing` module are used for type hinting in the `AlitaTableLoader` class.

### `json`

The `dumps` function from the `json` module is used to convert rows of data into JSON format.

### `utils`

The `cleanse_data` function from the `utils` module is used to cleanse the data before processing it.

### `log`

The `print_log` function from the `log` module is used for logging purposes.

## Functional Flow

The functional flow of the `AlitaTableLoader.py` file can be summarized as follows:

1. The `AlitaTableLoader` class is initialized with the specified parameters.
2. The `load` method is called to read and process the data from the file path.
3. The `row_processor` method is used to process each row of data based on the specified columns and cleansing options.
4. The processed data is converted into `Document` objects and returned as a list.

Example:
```python
loader = AlitaTableLoader(file_path='path/to/file', json_documents=True, raw_content=False, columns=['column1', 'column2'], cleanse=True)
documents = loader.load()
```

## Endpoints Used/Created

There are no explicit endpoints used or created in the `AlitaTableLoader.py` file. The file primarily focuses on reading and processing data from a specified file path and converting it into `Document` objects.