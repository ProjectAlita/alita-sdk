# splitters.py

**Path:** `src/alita_sdk/langchain/interfaces/splitters.py`

## Data Flow

The data flow within the `splitters.py` file revolves around the processing and splitting of text documents. The primary class, `Splitter`, is designed to handle various methods of text splitting, such as by lines, paragraphs, sentences, or custom chunks. The data originates from a `Document` object, which contains the text content and metadata. This document is passed to the `split` method, which determines the appropriate splitting strategy based on the `splitter_name` parameter. The text is then processed and split into smaller chunks, which are returned as a list of new `Document` objects. Intermediate variables such as `splitter_params` and `language` are used to store temporary data during the splitting process.

Example:
```python
class Splitter:
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
In this example, the `split` method directs the document to the appropriate splitting method based on the `splitter_name` parameter.

## Functions Descriptions

### `__init__`
The constructor initializes the `Splitter` class with default values for chunk size, chunk overlap, separators, regex separator, and language autodetection. It sets up the initial configuration for the splitter.

### `autodeted_language`
This method attempts to autodetect the language of a document based on its file extension. It returns a `Language` object if the extension matches a known language, otherwise it returns `None`.

### `split`
The main method that determines the splitting strategy based on the `splitter_name` parameter. It calls the appropriate splitting method and returns the resulting list of `Document` objects.

### `chunk_split`
This method handles splitting the document into chunks based on the specified separators or regex patterns. It uses the `RecursiveCharacterTextSplitter` class from the `langchain.text_splitter` module to perform the actual splitting.

### `line_split`
Splits the document into chunks based on newline characters (`\n`).

### `paragraph_split`
Splits the document into chunks based on double newline characters (`\n\n`).

### `sentence_split`
Splits the document into chunks based on periods (`.`).

## Dependencies Used and Their Descriptions

### `os`
Used for file path operations, specifically to extract the file extension in the `autodeted_language` method.

### `langchain_core.documents.Document`
Represents the document object that contains the text content and metadata to be split.

### `typing`
Provides type hints for optional parameters and lists.

### `langchain.text_splitter`
Contains the `RecursiveCharacterTextSplitter` class and `Language` enum used for splitting text based on language or custom separators.

## Functional Flow

1. **Initialization**: The `Splitter` class is instantiated with default or provided parameters.
2. **Language Detection**: If autodetect language is enabled, the `autodeted_language` method is called to determine the document's language.
3. **Splitting Strategy**: The `split` method is called with the document and splitter name, directing the document to the appropriate splitting method.
4. **Chunk Splitting**: The `chunk_split` method is used for custom chunk splitting, utilizing the `RecursiveCharacterTextSplitter` class.
5. **Line/Paragraph/Sentence Splitting**: The `line_split`, `paragraph_split`, and `sentence_split` methods handle splitting based on specific separators.
6. **Return Result**: The resulting list of split `Document` objects is returned.

## Endpoints Used/Created

This file does not explicitly define or call any endpoints. It focuses on the internal processing and splitting of text documents.