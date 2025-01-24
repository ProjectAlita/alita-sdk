# utils.py

**Path:** `src/alita_sdk/langchain/document_loaders/utils.py`

## Data Flow

The data flow within the `utils.py` file primarily revolves around the transformation and cleansing of text data. The main function, `cleanse_data`, takes a string input (`document`) and processes it through several stages to produce a cleaned version of the text. The data flow can be summarized as follows:

1. **Input:** The function receives a string (`document`) as input.
2. **Remove Numbers:** The function uses a regular expression to remove all numeric characters from the text.
3. **Remove Single Characters:** The function splits the text into words and removes any word that is a single character long.
4. **Remove Punctuation and Lowercase:** The function iterates through each character in the text, removes punctuation, and converts all characters to lowercase.
5. **Remove Non-Alphanumeric Characters:** The function uses a regular expression to remove all non-alphanumeric characters.
6. **Remove Stopwords:** The function uses the `remove_stopwords` method from the `gensim` library to remove common stopwords from the text.
7. **Output:** The function returns the cleaned text as output.

### Example

```python
import re
import string
from gensim.parsing import remove_stopwords

from ..tools.log import print_log


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

In this example, the `cleanse_data` function processes the input text through various stages, transforming it into a cleaned version by removing numbers, single characters, punctuation, non-alphanumeric characters, and stopwords.

## Functions Descriptions

### `cleanse_data`

The `cleanse_data` function is responsible for cleaning and preprocessing text data. Its primary purpose is to remove unwanted characters and words from the input text to produce a cleaner version. The function performs the following steps:

1. **Input:** The function takes a single parameter, `document`, which is a string containing the text to be cleaned.
2. **Remove Numbers:** The function uses the `re.sub` method to remove all numeric characters from the text.
3. **Remove Single Characters:** The function splits the text into words and removes any word that is a single character long.
4. **Remove Punctuation and Lowercase:** The function iterates through each character in the text, removes punctuation, and converts all characters to lowercase.
5. **Remove Non-Alphanumeric Characters:** The function uses the `re.sub` method to remove all non-alphanumeric characters.
6. **Remove Stopwords:** The function uses the `remove_stopwords` method from the `gensim` library to remove common stopwords from the text.
7. **Output:** The function returns the cleaned text as a string.

The function does not have any side effects, as it does not modify any global variables or depend on external state. It is a pure function that transforms the input text and returns the result.

### Example

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

In this example, the `cleanse_data` function processes the input text through various stages, transforming it into a cleaned version by removing numbers, single characters, punctuation, non-alphanumeric characters, and stopwords.

## Dependencies Used and Their Descriptions

The `utils.py` file relies on several dependencies to perform its text cleansing operations. These dependencies are imported at the beginning of the file and are used within the `cleanse_data` function.

### Dependencies

1. **`re`**: This module provides support for regular expressions in Python. It is used to perform pattern matching and text manipulation operations, such as removing numbers and non-alphanumeric characters from the text.

2. **`string`**: This module provides a collection of string constants, such as punctuation characters. It is used to identify and remove punctuation from the text.

3. **`gensim.parsing.remove_stopwords`**: This method from the `gensim` library is used to remove common stopwords from the text. Stopwords are words that are frequently used in a language but do not carry significant meaning (e.g., "and", "the", "is").

4. **`..tools.log.print_log`**: This is a custom logging function imported from the `tools.log` module. It is used for logging purposes, although it is commented out in the provided code.

### Example

```python
import re
import string
from gensim.parsing import remove_stopwords

from ..tools.log import print_log
```

In this example, the necessary dependencies are imported at the beginning of the file. The `re` and `string` modules are standard Python libraries, while `remove_stopwords` is a method from the `gensim` library. The `print_log` function is a custom logging function that is not used in the provided code.

## Functional Flow

The functional flow of the `utils.py` file is straightforward, as it contains a single function, `cleanse_data`, which is responsible for cleaning and preprocessing text data. The sequence of operations within the file can be summarized as follows:

1. **Import Dependencies:** The necessary modules and functions are imported at the beginning of the file.
2. **Define `cleanse_data` Function:** The `cleanse_data` function is defined, which takes a string input and processes it through several stages to produce a cleaned version of the text.
3. **Text Cleansing Operations:** The `cleanse_data` function performs various text cleansing operations, such as removing numbers, single characters, punctuation, non-alphanumeric characters, and stopwords.
4. **Return Cleaned Text:** The function returns the cleaned text as output.

### Example

```python
import re
import string
from gensim.parsing import remove_stopwords

from ..tools.log import print_log


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

In this example, the `cleanse_data` function is defined and performs various text cleansing operations on the input text. The function is then called with a sample input, and the cleaned text is returned as output.

## Endpoints Used/Created

The `utils.py` file does not explicitly define or call any endpoints. It is a utility file that provides a text cleansing function (`cleanse_data`) to be used by other parts of the application. The function can be imported and utilized by other modules or scripts that require text preprocessing capabilities.

### Example

```python
from src.alita_sdk.langchain.document_loaders.utils import cleanse_data

text = "This is a sample text with numbers 123 and punctuation!"
cleaned_text = cleanse_data(text)
print(cleaned_text)
```

In this example, the `cleanse_data` function is imported from the `utils.py` file and used to clean a sample text. The cleaned text is then printed to the console.