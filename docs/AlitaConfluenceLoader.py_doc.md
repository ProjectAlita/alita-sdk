# AlitaConfluenceLoader.py

**Path:** `src/alita_sdk/langchain/document_loaders/AlitaConfluenceLoader.py`

## Data Flow

The data flow within the `AlitaConfluenceLoader.py` file is centered around the processing of various types of content from Confluence, such as images, PDFs, and SVGs. The data originates from Confluence through HTTP requests and is then processed by the loader. The processing involves converting the content into a format that can be analyzed by a language model (LLM) if the `bins_with_llm` flag is set to `True`. The processed data is then returned as text, which can be used for further analysis or documentation.

For example, in the `process_pdf` method, the data flow is as follows:

1. An HTTP request is made to Confluence to retrieve the PDF content.
2. The PDF content is converted into images using the `convert_from_bytes` function.
3. Each image is processed by the LLM to generate a textual description.
4. The textual descriptions are concatenated and returned as the final output.

```python
response = self.confluence.request(path=link, absolute=True)
images = convert_from_bytes(response.content)
for i, image in enumerate(images):
    result = self.__perform_llm_prediction_for_image(image)
    text += f"Page {i + 1}:\n{result}\n\n"
return text
```

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `AlitaConfluenceLoader` class. It sets up the instance variables `bins_with_llm`, `prompt`, and `llm` based on the provided keyword arguments. It also removes these keys from the `kwargs` dictionary before calling the superclass's `__init__` method.

### `__perform_llm_prediction_for_image`

This private method takes an image as input, converts it to a byte array, and then to a base64 string. It then invokes the LLM with a prompt and the base64-encoded image, returning the LLM's response as text.

### `load`

The `load` method overrides the superclass's `load` method. It maps the `content_format` keyword argument to a corresponding `ContentFormat` enum value and then calls the superclass's `load` method with the updated `kwargs`.

### `process_pdf`

This method processes a PDF file from a given link. If `bins_with_llm` is `True` and an LLM is provided, it retrieves the PDF content, converts it to images, and processes each image with the LLM. The results are concatenated and returned as text. If `bins_with_llm` is `False`, it calls the superclass's `process_pdf` method.

### `process_image`

This method processes an image from a given link. If `bins_with_llm` is `True` and an LLM is provided, it retrieves the image content and processes it with the LLM. The result is returned as text. If `bins_with_llm` is `False`, it calls the superclass's `process_image` method.

### `process_svg`

This method processes an SVG file from a given link. If `bins_with_llm` is `True` and an LLM is provided, it retrieves the SVG content, converts it to a PNG image, and processes it with the LLM. The result is returned as text. If `bins_with_llm` is `False`, it calls the superclass's `process_svg` method.

## Dependencies Used and Their Descriptions

### `BytesIO`

Used for handling byte streams, particularly for converting image data.

### `Optional`

A type hinting utility from the `typing` module, used to indicate that a parameter can be of a specified type or `None`.

### `Image`

Imported from the `PIL` (Pillow) library, used for opening and manipulating images.

### `ConfluenceLoader` and `ContentFormat`

Imported from `langchain_community.document_loaders`, these are used as the base class and for specifying content formats, respectively.

### `HumanMessage`

Imported from `langchain_core.messages`, used for creating messages to be sent to the LLM.

### `convert_from_bytes`

Imported from `pdf2image`, used for converting PDF content into images.

### `renderPM` and `svg2rlg`

Imported from `reportlab.graphics` and `svglib.svglib`, respectively, used for converting SVG content into PNG images.

### `image_to_byte_array` and `bytes_to_base64`

Imported from `..tools.utils`, these utility functions are used for converting images to byte arrays and base64 strings.

## Functional Flow

The functional flow of the `AlitaConfluenceLoader.py` file involves initializing the loader with specific configurations, loading content from Confluence, and processing the content based on its type (PDF, image, or SVG). The processing can involve invoking an LLM to generate textual descriptions of the content.

For example, the flow for processing a PDF is as follows:

1. The `process_pdf` method is called with a link to the PDF.
2. The PDF content is retrieved from Confluence.
3. The content is converted to images.
4. Each image is processed by the LLM to generate text.
5. The generated text is returned.

## Endpoints Used/Created

The `AlitaConfluenceLoader.py` file interacts with Confluence endpoints to retrieve content. The specific endpoints are not hardcoded in the file but are constructed based on the provided links. The HTTP requests are made using the `self.confluence.request` method, which abstracts the details of the endpoint interactions.
