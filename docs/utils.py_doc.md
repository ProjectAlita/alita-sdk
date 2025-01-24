# utils.py

**Path:** `src/alita_sdk/langchain/document_loaders/utils.py`

## Data Flow

The data flow within `utils.py` revolves around the transformation and cleansing of textual data. The primary function, `cleanse_data`, takes a string input (`document`), processes it through several stages of cleansing, and returns a cleaned string. The data originates as a raw text document, which is then subjected to various transformations such as removing numbers, single characters, punctuation, non-alphanumeric characters, and stopwords. The final output is a sanitized string with irrelevant elements removed, making it suitable for further processing or analysis.

Example:
```python
# Original document
original_document = "This is a sample document with numbers 123 and punctuation!"

# Cleaned document
cleaned_document = cleanse_data(original_document)
# cleaned_document: "this sample document numbers punctuation"
```

In this example, the `cleanse_data` function removes numbers and punctuation from the original document, resulting in a cleaner version of the text.

## Functions Descriptions

### cleanse_data

The `cleanse_data` function is responsible for cleaning and preprocessing textual data. It performs the following steps:

1. **Remove Numbers:** Uses a regular expression to remove all numeric characters from the document.
2. **Remove Single Characters:** Filters out single-character words from the document.
3. **Remove Punctuation:** Strips punctuation and converts all characters to lowercase.
4. **Remove Non-Alphanumeric Characters:** Removes any remaining non-alphanumeric characters.
5. **Remove Stopwords:** Utilizes the `remove_stopwords` function from the `gensim` library to eliminate common stopwords.

The function takes a single parameter, `document` (a string), and returns the cleaned document as a string.

Example:
```python
def cleanse_data(document: str) -> str:
    # remove numbers
    document = re.sub(r"\d+", " ", document)

    # remove single characters
    document = " ".join([w for w in document.split() if len(w) > 1])

    # remove punctuations and convert characters to lower case
    document = "".join([
        char.lower()
        for char in document
        if char not in string.punctuation
    ])

    # Remove remove all non-alphanumeric characaters
    document = re.sub(r"\W+", " ", document)

    # Remove 'out of the box' stopwords
    document = remove_stopwords(document)

    return document
```

In this example, the function processes the input document through multiple stages to produce a cleaned version of the text.

## Dependencies Used and Their Descriptions

The `utils.py` file relies on several dependencies:

1. **re:** A standard Python library for regular expressions, used for pattern matching and text manipulation.
2. **string:** A standard Python library for string operations, used to access string punctuation characters.
3. **gensim.parsing.remove_stopwords:** A function from the `gensim` library, used to remove common stopwords from the text.
4. **print_log:** A custom logging function imported from `..tools.log`, used for logging intermediate steps (commented out in the provided code).

These dependencies are crucial for the text cleansing operations performed in the `cleanse_data` function.

## Functional Flow

The functional flow of `utils.py` is straightforward. The primary function, `cleanse_data`, is designed to be called with a string input. The function processes the input through a series of cleansing steps and returns the cleaned text. The flow can be summarized as follows:

1. The `cleanse_data` function is called with a raw text document.
2. The function removes numbers, single characters, punctuation, non-alphanumeric characters, and stopwords from the document.
3. The cleaned document is returned as the output.

Example:
```python
# Input document
input_document = "Example text with numbers 456 and symbols #!"

# Processed document
processed_document = cleanse_data(input_document)
# processed_document: "example text numbers symbols"
```

In this example, the `cleanse_data` function processes the input document and returns a cleaned version of the text.

## Endpoints Used/Created

The `utils.py` file does not explicitly define or call any endpoints. Its primary focus is on the cleansing and preprocessing of textual data through the `cleanse_data` function.