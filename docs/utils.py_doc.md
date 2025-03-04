# utils.py

**Path:** `src/alita_sdk/langchain/document_loaders/utils.py`

## Data Flow

The `utils.py` file is primarily focused on cleansing textual data. The data flow within this file begins with the input of a raw text document into the `cleanse_data` function. This function processes the text through several stages: removing numbers, single characters, punctuation, non-alphanumeric characters, and stopwords. The final output is a cleaned and processed text string. The data transformations are sequential and cumulative, with each step building upon the previous one to refine the text further.

Example:
```python
# Example of data transformation in cleanse_data function
# Initial raw document
raw_document = "This is a sample document with numbers 123 and punctuation!"

# After removing numbers
step1 = re.sub(r"\d+", " ", raw_document)  # "This is a sample document with numbers and punctuation!"

# After removing single characters
step2 = " ".join([w for w in step1.split() if len(w) > 1])  # "This is sample document with numbers and punctuation!"

# After removing punctuation and converting to lower case
step3 = "".join([char.lower() for char in step2 if char not in string.punctuation])  # "this is sample document with numbers and punctuation"

# After removing non-alphanumeric characters
step4 = re.sub(r"\W+", " ", step3)  # "this is sample document with numbers and punctuation"

# After removing stopwords
final_output = remove_stopwords(step4)  # "sample document numbers punctuation"
```

## Functions Descriptions

### cleanse_data

The `cleanse_data` function is designed to clean and preprocess a given text document. It takes a single string parameter `document` and returns a cleaned string. The function performs the following operations:

1. **Remove Numbers:** Uses a regular expression to replace all digits with a space.
2. **Remove Single Characters:** Splits the document into words and removes any word with a length of one.
3. **Remove Punctuation and Convert to Lower Case:** Iterates through each character, removes punctuation, and converts the character to lower case.
4. **Remove Non-Alphanumeric Characters:** Uses a regular expression to replace non-alphanumeric characters with a space.
5. **Remove Stopwords:** Utilizes the `remove_stopwords` function from the `gensim` library to remove common stopwords from the text.

The function ensures that the text is in a clean and standardized format, suitable for further processing or analysis.

Example:
```python
# Example usage of cleanse_data function
raw_text = "Hello World! This is a test document with numbers 12345 and symbols #@$%."
cleaned_text = cleanse_data(raw_text)
print(cleaned_text)  # Output: "hello world test document numbers symbols"
```

## Dependencies Used and Their Descriptions

### re

The `re` module is used for regular expression operations. In this file, it is utilized to remove numbers and non-alphanumeric characters from the text.

### string

The `string` module provides a collection of string constants. It is used to identify and remove punctuation characters from the text.

### gensim.parsing.remove_stopwords

The `remove_stopwords` function from the `gensim.parsing` module is used to remove common stopwords from the text, helping to reduce noise and focus on the meaningful words.

### ..tools.log.print_log

The `print_log` function from the `..tools.log` module is imported but commented out in the code. It appears to be intended for logging purposes during the data cleansing process.

## Functional Flow

The functional flow of the `utils.py` file is straightforward. The primary function `cleanse_data` is called with a raw text document as input. The function processes the text through a series of cleansing steps, each step refining the text further. The final output is a cleaned text string, which can then be used for further analysis or processing.

1. **Input:** Raw text document.
2. **Processing:** Sequential cleansing steps (remove numbers, single characters, punctuation, non-alphanumeric characters, and stopwords).
3. **Output:** Cleaned text string.

Example:
```python
# Example of functional flow
raw_text = "Example text with numbers 123 and punctuation!"
cleaned_text = cleanse_data(raw_text)
print(cleaned_text)  # Output: "example text numbers punctuation"
```

## Endpoints Used/Created

The `utils.py` file does not explicitly define or call any endpoints. Its primary focus is on data cleansing and preprocessing within the `cleanse_data` function.
