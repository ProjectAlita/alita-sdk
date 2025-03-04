# utils.py

**Path:** `src/alita_sdk/langchain/document_loaders/utils.py`

## Data Flow

The data flow within the `utils.py` file primarily revolves around the `cleanse_data` function. This function takes a string input, processes it through several transformation steps, and returns a cleaned string. The data flow can be summarized as follows:

1. **Input:** The function receives a string `document` as input.
2. **Remove Numbers:** The function uses a regular expression to remove all numeric characters from the string.
3. **Remove Single Characters:** The function splits the string into words and removes any single-character words.
4. **Remove Punctuation and Lowercase:** The function removes all punctuation characters and converts the remaining characters to lowercase.
5. **Remove Non-Alphanumeric Characters:** The function uses a regular expression to remove all non-alphanumeric characters.
6. **Remove Stopwords:** The function uses the `remove_stopwords` function from the `gensim` library to remove common stopwords.
7. **Output:** The function returns the cleaned string.

Example:
```python
# Example of data transformation in cleanse_data function
import re
import string
from gensim.parsing import remove_stopwords

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

## Functions Descriptions

### cleanse_data

The `cleanse_data` function is designed to clean and preprocess a given text document. Its primary purpose is to remove unwanted characters, words, and stopwords to prepare the text for further processing or analysis.

- **Parameters:**
  - `document` (str): The input text document to be cleaned.
- **Returns:**
  - `str`: The cleaned and processed text document.

The function performs the following steps:
1. **Remove Numbers:** Uses a regular expression to remove all numeric characters from the input string.
2. **Remove Single Characters:** Splits the string into words and removes any single-character words.
3. **Remove Punctuation and Lowercase:** Removes all punctuation characters and converts the remaining characters to lowercase.
4. **Remove Non-Alphanumeric Characters:** Uses a regular expression to remove all non-alphanumeric characters.
5. **Remove Stopwords:** Uses the `remove_stopwords` function from the `gensim` library to remove common stopwords.

Example:
```python
# Example usage of cleanse_data function
text = "Hello World! This is a test document with numbers 123 and punctuation."
cleaned_text = cleanse_data(text)
print(cleaned_text)  # Output: "hello world test document numbers punctuation"
```

## Dependencies Used and Their Descriptions

The `utils.py` file imports several dependencies to perform its text cleaning operations:

- `re`: The `re` module provides support for regular expressions, which are used to search, match, and manipulate strings.
- `string`: The `string` module provides a collection of string constants, including punctuation characters, which are used to remove punctuation from the input text.
- `gensim.parsing.remove_stopwords`: The `remove_stopwords` function from the `gensim` library is used to remove common stopwords from the input text.
- `..tools.log.print_log`: The `print_log` function from the `tools.log` module is imported but commented out in the code. It is intended for logging purposes.

## Functional Flow

The functional flow of the `utils.py` file is straightforward and revolves around the `cleanse_data` function. The sequence of operations is as follows:

1. The `cleanse_data` function is defined with a single parameter `document`.
2. The function applies a series of transformations to the input `document` to clean and preprocess the text.
3. The cleaned text is returned as the output of the function.

Example:
```python
# Functional flow of cleanse_data function
text = "Sample text with numbers 123 and punctuation!"
cleaned_text = cleanse_data(text)
print(cleaned_text)  # Output: "sample text numbers punctuation"
```

## Endpoints Used/Created

The `utils.py` file does not explicitly define or call any endpoints. Its primary focus is on text cleaning and preprocessing through the `cleanse_data` function.
