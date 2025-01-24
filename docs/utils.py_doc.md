# utils.py

**Path:** `src/alita_sdk/langchain/tools/utils.py`

## Data Flow

The data flow within `utils.py` is primarily focused on text processing, data transformation, and utility functions. The file contains functions that tokenize and untokenize strings, equalize text sequences, replace sources in documents, unpack JSON data, download NLTK data, and convert data to base64 encoding. The data flow typically starts with input data (e.g., strings, JSON data, file paths), which is then processed by various functions to produce transformed output data. For example, the `equalize` function takes two strings, tokenizes them, and then processes them to produce two equalized strings. Similarly, the `unpack_json` function takes a JSON string or dictionary and returns a parsed JSON object. The data flow is linear, with each function performing a specific transformation on the input data and returning the processed output.

Example:
```python
def equalize(s1, s2):
    l1 = tokenize(s1)
    l2 = tokenize(s2)
    res1 = []
    res2 = []
    prev = difflib.Match(0, 0, 0)
    for match in difflib.SequenceMatcher(a=l1, b=l2).get_matching_blocks():
        if prev.a + prev.size != match.a:
            for i in range(prev.a + prev.size, match.a):
                res2 += ['_' * len(l1[i])]
            res1 += l1[prev.a + prev.size:match.a]
        if prev.b + prev.size != match.b:
            for i in range(prev.b + prev.size, match.b):
                res1 += ['_' * len(l2[i])]
            res2 += l2[prev.b + prev.size:match.b]
        res1 += l1[match.a:match.a + match.size]
        res2 += l2[match.b:match.b + match.size]
        prev = match
    return untokenize(res1), untokenize(res2)
```
This example shows the `equalize` function, which processes two input strings to produce two equalized strings by tokenizing, matching, and untokenizing the input data.

## Functions Descriptions

1. **tokenize(s):**
   - **Purpose:** Tokenizes a string into a list of words based on whitespace.
   - **Inputs:** A string `s`.
   - **Outputs:** A list of tokens (words).
   - **Example:**
     ```python
     tokens = tokenize("Hello world")
     # tokens = ['Hello', 'world']
     ```

2. **untokenize(ts):**
   - **Purpose:** Converts a list of tokens back into a single string with spaces.
   - **Inputs:** A list of tokens `ts`.
   - **Outputs:** A single string.
   - **Example:**
     ```python
     sentence = untokenize(['Hello', 'world'])
     # sentence = 'Hello world'
     ```

3. **untokenize_cellrichtext(ts):**
   - **Purpose:** Converts a list of tokens into a `CellRichText` object with spaces.
   - **Inputs:** A list of tokens `ts`.
   - **Outputs:** A `CellRichText` object.
   - **Example:**
     ```python
     cell_rich_text = untokenize_cellrichtext(['Hello', 'world'])
     # cell_rich_text contains 'Hello world' with CellRichText formatting
     ```

4. **equalize(s1, s2):**
   - **Purpose:** Equalizes two strings by tokenizing, matching, and untokenizing them.
   - **Inputs:** Two strings `s1` and `s2`.
   - **Outputs:** Two equalized strings.
   - **Example:**
     ```python
     eq1, eq2 = equalize("Hello world", "Hello there world")
     # eq1 = 'Hello _____ world'
     # eq2 = 'Hello there world'
     ```

5. **equalize_markdown(s1, s2):**
   - **Purpose:** Equalizes two strings with markdown formatting for differences.
   - **Inputs:** Two strings `s1` and `s2`.
   - **Outputs:** Two equalized strings with markdown formatting.
   - **Example:**
     ```python
     eq1, eq2 = equalize_markdown("Hello world", "Hello there world")
     # eq1 = 'Hello ~~_____~~ world'
     # eq2 = 'Hello **there** world'
     ```

6. **equalize_openpyxl(s1, s2):**
   - **Purpose:** Equalizes two strings with OpenPyXL formatting for differences.
   - **Inputs:** Two strings `s1` and `s2`.
   - **Outputs:** Two equalized `CellRichText` objects.
   - **Example:**
     ```python
     eq1, eq2 = equalize_openpyxl("Hello world", "Hello there world")
     # eq1 and eq2 contain 'Hello world' with OpenPyXL formatting
     ```

7. **replace_source(document, source_replacers, keys=None):**
   - **Purpose:** Replaces source start(s) in a document's metadata.
   - **Inputs:** A document object, a dictionary of source replacers, and an optional list of keys.
   - **Outputs:** None (modifies the document in place).
   - **Example:**
     ```python
     replace_source(doc, {"old_source": "new_source"})
     # Replaces 'old_source' with 'new_source' in the document's metadata
     ```

8. **unpack_json(json_data):**
   - **Purpose:** Unpacks a JSON string or dictionary into a JSON object.
   - **Inputs:** A JSON string or dictionary `json_data`.
   - **Outputs:** A JSON object.
   - **Example:**
     ```python
     data = unpack_json('{"key": "value"}')
     # data = {'key': 'value'}
     ```

9. **download_nltk(target, force=False):**
   - **Purpose:** Downloads NLTK data to a specified target directory.
   - **Inputs:** A target directory path and an optional force flag.
   - **Outputs:** None (downloads NLTK data to the target directory).
   - **Example:**
     ```python
     download_nltk('/path/to/nltk_data')
     # Downloads NLTK data to the specified directory
     ```

10. **bytes_to_base64(bt):**
    - **Purpose:** Converts bytes to a base64-encoded string.
    - **Inputs:** A bytes object `bt`.
    - **Outputs:** A base64-encoded string.
    - **Example:**
      ```python
      b64_str = bytes_to_base64(b'hello')
      # b64_str = 'aGVsbG8='
      ```

11. **path_to_base64(path):**
    - **Purpose:** Converts the contents of a file at a given path to a base64-encoded string.
    - **Inputs:** A file path `path`.
    - **Outputs:** A base64-encoded string.
    - **Example:**
      ```python
      b64_str = path_to_base64('/path/to/file')
      # b64_str contains the base64-encoded contents of the file
      ```

12. **image_to_byte_array(image):**
    - **Purpose:** Converts an image to a byte array.
    - **Inputs:** An `Image` object `image`.
    - **Outputs:** A byte array.
    - **Example:**
      ```python
      byte_array = image_to_byte_array(image)
      # byte_array contains the byte representation of the image
      ```

## Dependencies Used and Their Descriptions

1. **base64:**
   - **Purpose:** Provides functions for encoding and decoding data in base64.
   - **Usage:** Used in `bytes_to_base64` and `path_to_base64` functions to encode data to base64 strings.
   - **Example:**
     ```python
     import base64
     b64_str = base64.b64encode(b'hello').decode('utf-8')
     # b64_str = 'aGVsbG8='
     ```

2. **io:**
   - **Purpose:** Provides core tools for working with streams.
   - **Usage:** Used in `image_to_byte_array` to create an in-memory byte stream for image data.
   - **Example:**
     ```python
     import io
     byte_stream = io.BytesIO()
     ```

3. **json:**
   - **Purpose:** Provides functions for parsing and manipulating JSON data.
   - **Usage:** Used in `unpack_json` to parse JSON strings and dictionaries.
   - **Example:**
     ```python
     import json
     data = json.loads('{"key": "value"}')
     # data = {'key': 'value'}
     ```

4. **difflib:**
   - **Purpose:** Provides classes and functions for comparing sequences.
   - **Usage:** Used in `equalize`, `equalize_markdown`, and `equalize_openpyxl` to find matching blocks between sequences.
   - **Example:**
     ```python
     import difflib
     matcher = difflib.SequenceMatcher(a='hello', b='hallo')
     matches = matcher.get_matching_blocks()
     ```

5. **re:**
   - **Purpose:** Provides support for regular expressions.
   - **Usage:** Used in `tokenize` to split strings based on whitespace.
   - **Example:**
     ```python
     import re
     tokens = re.split(r'\s+', 'Hello world')
     # tokens = ['Hello', 'world']
     ```

6. **PIL.Image:**
   - **Purpose:** Provides image processing capabilities.
   - **Usage:** Used in `image_to_byte_array` to handle image objects and convert them to byte arrays.
   - **Example:**
     ```python
     from PIL import Image
     image = Image.open('/path/to/image.png')
     ```

7. **openpyxl.cell.text.InlineFont:**
   - **Purpose:** Provides font styling for OpenPyXL cells.
   - **Usage:** Used in `equalize_openpyxl` to apply strikethrough and bold formatting to text.
   - **Example:**
     ```python
     from openpyxl.cell.text import InlineFont
     bold_font = InlineFont(b=True)
     ```

8. **openpyxl.cell.rich_text.TextBlock, CellRichText:**
   - **Purpose:** Provides rich text capabilities for OpenPyXL cells.
   - **Usage:** Used in `equalize_openpyxl` to create and manipulate rich text objects in cells.
   - **Example:**
     ```python
     from openpyxl.cell.rich_text import TextBlock, CellRichText
     rich_text = CellRichText()
     rich_text.append(TextBlock(bold_font, 'Hello'))
     ```

## Functional Flow

The functional flow of `utils.py` involves a series of utility functions that perform specific tasks related to text processing, data transformation, and encoding. The sequence of operations typically starts with input data being passed to one of the utility functions, which then processes the data and returns the transformed output. The functions are designed to be independent and modular, allowing them to be used in various contexts within the codebase. For example, the `equalize` function can be used to compare and equalize two strings, while the `unpack_json` function can be used to parse JSON data. The flow is straightforward, with each function performing a specific task and returning the result.

Example:
```python
# Example of functional flow using equalize and unpack_json
s1 = "Hello world"
s2 = "Hello there world"

# Equalize the strings
eq1, eq2 = equalize(s1, s2)

# Unpack JSON data
json_data = '{"key": "value"}'
parsed_data = unpack_json(json_data)
```
This example demonstrates the functional flow of using the `equalize` and `unpack_json` functions to process input data and obtain the desired output.

## Endpoints Used/Created

The `utils.py` file does not explicitly define or call any endpoints. It primarily contains utility functions for text processing, data transformation, and encoding. Therefore, there are no endpoints used or created within this file.