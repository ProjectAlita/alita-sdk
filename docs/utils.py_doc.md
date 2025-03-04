# utils.py

**Path:** `src/alita_sdk/langchain/tools/utils.py`

## Data Flow

The data flow within `utils.py` primarily revolves around text processing and transformation functions. Data typically enters these functions as strings or bytes and undergoes various transformations before being returned in a modified format. For instance, the `equalize` function takes two strings, tokenizes them, and then processes them to highlight differences. The data flow can be visualized as follows:

1. **Input:** Data is received as function parameters (e.g., strings, bytes).
2. **Processing:** Functions manipulate the data using tokenization, transformation, and comparison techniques.
3. **Output:** The processed data is returned in a new format (e.g., modified strings, base64 encoded strings).

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
In this example, the `equalize` function processes two input strings, tokenizes them, and then compares them to highlight differences, returning the modified strings.

## Functions Descriptions

### `tokenize(s)`

**Purpose:** Splits a string into tokens based on whitespace.
**Inputs:** A string `s`.
**Outputs:** A list of tokens.

### `untokenize(ts)`

**Purpose:** Joins a list of tokens into a single string with spaces.
**Inputs:** A list of tokens `ts`.
**Outputs:** A single string.

### `untokenize_cellrichtext(ts)`

**Purpose:** Joins a list of tokens into a `CellRichText` object with spaces.
**Inputs:** A list of tokens `ts`.
**Outputs:** A `CellRichText` object.

### `equalize(s1, s2)`

**Purpose:** Compares two strings and highlights differences.
**Inputs:** Two strings `s1` and `s2`.
**Outputs:** Two modified strings with differences highlighted.

### `equalize_markdown(s1, s2)`

**Purpose:** Compares two strings and highlights differences using Markdown syntax.
**Inputs:** Two strings `s1` and `s2`.
**Outputs:** Two modified strings with differences highlighted using Markdown.

### `equalize_openpyxl(s1, s2)`

**Purpose:** Compares two strings and highlights differences using Openpyxl rich text.
**Inputs:** Two strings `s1` and `s2`.
**Outputs:** Two `CellRichText` objects with differences highlighted.

### `replace_source(document, source_replacers, keys=None)`

**Purpose:** Replaces source metadata in a document.
**Inputs:** A document object, a dictionary of source replacers, and an optional list of keys.
**Outputs:** None.

### `unpack_json(json_data)`

**Purpose:** Unpacks JSON data from a string or dictionary.
**Inputs:** A JSON string or dictionary `json_data`.
**Outputs:** A dictionary.

### `download_nltk(target, force=False)`

**Purpose:** Downloads NLTK data to a specified target directory.
**Inputs:** A target directory path and an optional force flag.
**Outputs:** None.

### `bytes_to_base64(bt)`

**Purpose:** Encodes bytes to a base64 string.
**Inputs:** A bytes object `bt`.
**Outputs:** A base64 encoded string.

### `path_to_base64(path)`

**Purpose:** Encodes the contents of a file to a base64 string.
**Inputs:** A file path `path`.
**Outputs:** A base64 encoded string.

### `image_to_byte_array(image)`

**Purpose:** Converts an image to a byte array.
**Inputs:** An `Image` object `image`.
**Outputs:** A byte array.

### `LockedIterator`

**Purpose:** Makes an iterator thread-safe.
**Inputs:** An iterator `iterator`.
**Outputs:** A thread-safe iterator.

## Dependencies Used and Their Descriptions

### `base64`

**Purpose:** Provides functions for encoding and decoding data in base64.

### `io`

**Purpose:** Provides core tools for working with streams.

### `json`

**Purpose:** Provides functions for parsing and serializing JSON data.

### `difflib`

**Purpose:** Provides tools for computing and working with differences between sequences.

### `re`

**Purpose:** Provides support for regular expressions.

### `threading`

**Purpose:** Provides support for creating and managing threads.

### `PIL.Image`

**Purpose:** Provides support for opening, manipulating, and saving image files.

### `openpyxl.cell.text.InlineFont`

**Purpose:** Provides support for inline font styling in Openpyxl.

### `openpyxl.cell.rich_text.TextBlock`

**Purpose:** Provides support for rich text blocks in Openpyxl.

### `openpyxl.cell.rich_text.CellRichText`

**Purpose:** Provides support for rich text cells in Openpyxl.

## Functional Flow

The functional flow of `utils.py` involves a series of utility functions that perform specific tasks related to text processing, JSON handling, and file encoding. The sequence of operations typically follows these steps:

1. **Text Processing:** Functions like `tokenize`, `untokenize`, and `equalize` handle text tokenization and comparison.
2. **JSON Handling:** The `unpack_json` function processes JSON data.
3. **File Encoding:** Functions like `bytes_to_base64` and `path_to_base64` handle file encoding.
4. **Thread Safety:** The `LockedIterator` class ensures thread-safe iteration.

Example:
```python
def path_to_base64(path) -> str:
    with open(path, 'rb') as binary_file:
        return base64.b64encode(binary_file.read()).decode('utf-8')
```
In this example, the `path_to_base64` function reads a file and encodes its contents to a base64 string.

## Endpoints Used/Created

There are no explicit endpoints used or created within `utils.py`. The file primarily consists of utility functions for internal use.