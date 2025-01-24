# splitters.py

**Path:** `src/alita_sdk/langchain/interfaces/splitters.py`

## Data Flow

The data flow within `splitters.py` revolves around the processing of documents to split them into smaller chunks based on various criteria. The data originates from a `Document` object, which contains the content and metadata of the document to be split. The `Splitter` class is responsible for managing the splitting process, which involves several steps:

1. **Initialization:** The `Splitter` class is initialized with parameters such as `chunk_size`, `chunk_overlap`, `separators`, and `regex_separator`. These parameters define how the document will be split.
2. **Language Detection:** If `autodetect_language` is enabled, the `autodeted_language` method is used to determine the language of the document based on its file extension.
3. **Splitting:** The `split` method is called with a `Document` object and a `splitter_name` to specify the splitting strategy. Depending on the `splitter_name`, the document is split into chunks, lines, paragraphs, or sentences using the corresponding method.
4. **Chunk Creation:** The `chunk_split` method uses the `RecursiveCharacterTextSplitter` class to create chunks of the document based on the specified parameters and separators.

Example:
```python
class Splitter:
    def __init__(self, chunk_size=1000, chunk_overlap=100, separators: Optional[List[str]] = None,
                 regex_separator: Optional[Any] = None, autodetect_language: bool = True, **kwargs: Any):
        self.languages = [e.value for e in Language]
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.autodetect_language = autodetect_language
        self.regex_separator = regex_separator
        self.separators = separators
```
*Initialization of the Splitter class with parameters defining the splitting process.*

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `Splitter` class with the following parameters:
- `chunk_size`: The size of each chunk.
- `chunk_overlap`: The overlap between consecutive chunks.
- `separators`: A list of separators to use for splitting.
- `regex_separator`: A regular expression to use as a separator.
- `autodetect_language`: A boolean indicating whether to autodetect the language of the document.

### `autodeted_language`

The `autodeted_language` method detects the language of a document based on its file extension. It returns a `Language` object if the language is recognized, otherwise it returns `None`.

Example:
```python
    def autodeted_language(self, filepath: str) -> Optional[Language]:
        _, file_ext = os.path.splitext(filepath)
        file_ext = file_ext.replace('.', '')
        if file_ext in self.languages:
            return Language(file_ext)
        else:
            return None
```
*Detects the language of the document based on its file extension.*

### `split`

The `split` method splits a document into smaller parts based on the specified `splitter_name`. It supports splitting by lines, paragraphs, sentences, or chunks.

Example:
```python
    def split(self, document: Document, splitter_name: Optional[str] = 'chunks'):
        if "og_data" in document.metadata:
            return [document]
        if splitter_name == 'lines':
            return self.line_split(document)
        if splitter_name == 'paragraphs':
            return self.paragraph_split(document)
        if splitter_name == 'sentences':
            return self.sentence_split(document)
        if splitter_name == 'chunks':
            return self.chunk_split(document, separators=self.separators)
        if splitter_name == 'nothing':
            return [document]
        raise NotImplementedError(f"Splitter {splitter_name} is not implemented yet")
```
*Splits the document based on the specified strategy.*

### `chunk_split`

The `chunk_split` method creates chunks of the document using the `RecursiveCharacterTextSplitter` class. It can use language detection, regular expressions, or specified separators to split the document.

Example:
```python
    def chunk_split(self, document: Document, separators: Optional[List[str]]):
        language = None
        splitter_params = {
            'chunk_size': self.chunk_size,
            'chunk_overlap': self.chunk_overlap,
        }
        if self.autodetect_language:
            language = self.autodeted_language(document.metadata['source'])
        if language:
            splitter = RecursiveCharacterTextSplitter.from_language(language=language, **splitter_params)
        else:
            if self.regex_separator:
                splitter_params['separator'] = self.regex_separator
                splitter_params['is_separator_regex'] = True
            if separators:
                splitter_params['separators'] = self.separators
            elif self.separators:
                splitter_params['separators'] = self.separators
            splitter = RecursiveCharacterTextSplitter(**splitter_params)
        return splitter.create_documents([document.page_content], [document.metadata])
```
*Creates chunks of the document using the specified parameters and separators.*

### `line_split`

The `line_split` method splits the document into lines using the newline character as a separator.

### `paragraph_split`

The `paragraph_split` method splits the document into paragraphs using double newline characters as separators.

### `sentence_split`

The `sentence_split` method splits the document into sentences using the period character as a separator.

## Dependencies Used and Their Descriptions

### `os`

The `os` module is used to handle file paths and extensions.

### `langchain_core.documents.Document`

The `Document` class from `langchain_core.documents` is used to represent the document to be split.

### `typing`

The `Optional`, `Any`, and `List` types from the `typing` module are used for type hinting.

### `langchain.text_splitter`

The `RecursiveCharacterTextSplitter` and `Language` classes from `langchain.text_splitter` are used to split the document into chunks based on the specified parameters and separators.

## Functional Flow

1. **Initialization:** The `Splitter` class is initialized with the specified parameters.
2. **Language Detection:** If enabled, the language of the document is detected based on its file extension.
3. **Splitting:** The document is split into smaller parts based on the specified strategy (lines, paragraphs, sentences, or chunks).
4. **Chunk Creation:** The `RecursiveCharacterTextSplitter` class is used to create chunks of the document based on the specified parameters and separators.

## Endpoints Used/Created

No endpoints are explicitly defined or called within this file.