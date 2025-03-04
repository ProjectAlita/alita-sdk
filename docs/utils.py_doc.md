# utils.py

**Path:** `src/alita_sdk/langchain/tools/utils.py`

## Data Flow

The data flow within `utils.py` is primarily concerned with text processing, data transformation, and utility functions. The file contains functions that tokenize and untokenize strings, equalize differences between strings, and convert data formats. Data typically originates as strings or bytes, undergoes various transformations, and is returned in a modified format. For example, the `equalize` function takes two strings, tokenizes them, and then processes them to highlight differences, returning two new strings with differences marked. Intermediate variables are used to store tokenized lists and results of transformations.

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
This function processes two strings to highlight differences, using intermediate lists to store tokenized strings and results.

## Functions Descriptions

1. **tokenize(s):** Splits a string into tokens based on whitespace.
2. **untokenize(ts):** Joins a list of tokens into a single string with spaces.
3. **untokenize_cellrichtext(ts):** Converts a list of tokens into a `CellRichText` object, handling spaces between tokens.
4. **equalize(s1, s2):** Highlights differences between two strings by tokenizing them and marking differences.
5. **equalize_markdown(s1, s2):** Similar to `equalize`, but marks removed text with strikethrough and added text in bold.
6. **equalize_openpyxl(s1, s2):** Similar to `equalize`, but uses `TextBlock` objects to mark differences for Openpyxl.
7. **replace_source(document, source_replacers, keys=None):** Replaces parts of a document's metadata based on provided replacers.
8. **unpack_json(json_data):** Unpacks JSON data from a string or dictionary, handling different formats.
9. **download_nltk(target, force=False):** Downloads NLTK data to a specified target directory, with optional force download.
10. **bytes_to_base64(bt):** Converts bytes to a base64-encoded string.
11. **path_to_base64(path):** Reads a file and converts its contents to a base64-encoded string.
12. **image_to_byte_array(image):** Converts a PIL Image to a byte array.
13. **LockedIterator:** A class that makes an iterator thread-safe using a lock.

## Dependencies Used and Their Descriptions

1. **base64:** Used for encoding bytes to base64 strings.
2. **io:** Provides the `BytesIO` class for handling byte streams.
3. **json:** Used for parsing and generating JSON data.
4. **difflib:** Provides tools for comparing sequences, used in equalizing functions.
5. **re:** Regular expressions for tokenizing strings.
6. **threading:** Used in `LockedIterator` to make iteration thread-safe.
7. **PIL.Image:** Used for image processing in `image_to_byte_array`.
8. **openpyxl.cell.text.InlineFont:** Used for formatting text in Openpyxl.
9. **openpyxl.cell.rich_text.TextBlock, CellRichText:** Used for handling rich text in Openpyxl.
10. **nltk:** Used for downloading and handling natural language processing data.

## Functional Flow

The functional flow in `utils.py` involves a series of utility functions that are called as needed. The flow typically starts with data input (e.g., strings, bytes), followed by processing through one or more functions, and ends with the output of transformed data. Functions like `equalize` and `equalize_markdown` process input strings to highlight differences, while functions like `bytes_to_base64` and `path_to_base64` handle data conversion. The `LockedIterator` class ensures thread-safe iteration over data.

Example:
```python
def path_to_base64(path) -> str:
    with open(path, 'rb') as binary_file:
        return base64.b64encode(binary_file.read()).decode('utf-8')
```
This function reads a file and converts its contents to a base64-encoded string, demonstrating a simple data conversion flow.

## Endpoints Used/Created

The `utils.py` file does not explicitly define or call any endpoints. Its primary focus is on utility functions for data processing and transformation within the codebase.