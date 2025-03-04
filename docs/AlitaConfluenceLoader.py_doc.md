# AlitaConfluenceLoader.py

**Path:** `src/alita_sdk/langchain/document_loaders/AlitaConfluenceLoader.py`

## Data Flow

The data flow within the `AlitaConfluenceLoader` class is centered around the processing of various types of content from Confluence, specifically images, PDFs, and SVGs. The data originates from Confluence links, which are fetched using HTTP requests. The content is then processed based on its type, and if the `bins_with_llm` flag is set, the data is further analyzed using a language model (LLM). The processed data is then returned as text.

For example, in the `process_pdf` method, the PDF content is fetched from a Confluence link, converted to images, and each image is analyzed using the LLM to generate descriptive text:

```python
response = self.confluence.request(path=link, absolute=True)
images = convert_from_bytes(response.content)
for i, image in enumerate(images):
    result = self.__perform_llm_prediction_for_image(image)
    text += f"Page {i + 1}:\n{result}\n\n"
```

In this snippet, the PDF content is converted to images, and each image is processed to generate text descriptions.

## Functions Descriptions

### `__init__`

The `__init__` method initializes the `AlitaConfluenceLoader` class. It sets up the instance variables `bins_with_llm`, `prompt`, and `llm` based on the provided keyword arguments. It also removes these keys from the `kwargs` dictionary before calling the superclass initializer.

### `__perform_llm_prediction_for_image`

This private method takes an image as input, converts it to a byte array, encodes it in base64, and sends it to the LLM for analysis. The LLM's response is returned as a string.

### `load`

The `load` method overrides the superclass method to map the `content_format` argument to a specific `ContentFormat` enum value before calling the superclass method.

### `process_pdf`

This method processes a PDF from a Confluence link. If `bins_with_llm` is set, it converts the PDF to images and uses the LLM to analyze each image. Otherwise, it calls the superclass method.

### `process_image`

Similar to `process_pdf`, this method processes an image from a Confluence link. It uses the LLM to analyze the image if `bins_with_llm` is set, otherwise, it calls the superclass method.

### `process_svg`

This method processes an SVG from a Confluence link. It converts the SVG to a PNG image and uses the LLM to analyze the image if `bins_with_llm` is set. Otherwise, it calls the superclass method.

## Dependencies Used and Their Descriptions

### `BytesIO`

Used for handling byte streams, particularly for converting image data.

### `Optional`

A type hint indicating that a parameter can be of a specified type or `None`.

### `Image` from `PIL`

Used for opening and manipulating images.

### `ConfluenceLoader` from `langchain_community.document_loaders`

The superclass that `AlitaConfluenceLoader` extends.

### `ContentFormat` from `langchain_community.document_loaders.confluence`

An enum representing different content formats in Confluence.

### `HumanMessage` from `langchain_core.messages`

Used for creating messages to be sent to the LLM.

### `convert_from_bytes` from `pdf2image`

Converts PDF byte data to images.

### `renderPM` from `reportlab.graphics`

Used for rendering SVG drawings to PNG format.

### `svg2rlg` from `svglib.svglib`

Converts SVG data to a ReportLab drawing object.

### `image_to_byte_array` and `bytes_to_base64` from `..tools.utils`

Utility functions for converting images to byte arrays and encoding byte arrays in base64.

## Functional Flow

The functional flow of the `AlitaConfluenceLoader` class involves initializing the loader with specific configurations, loading content from Confluence, and processing the content based on its type. The processing methods (`process_pdf`, `process_image`, `process_svg`) handle the content differently based on the `bins_with_llm` flag. If set, the content is analyzed using the LLM; otherwise, the superclass methods are called.

For example, the `process_image` method follows this flow:

1. Fetch the image content from Confluence.
2. If `bins_with_llm` is set, analyze the image using the LLM.
3. Return the analysis result or call the superclass method.

## Endpoints Used/Created

The `AlitaConfluenceLoader` class interacts with Confluence endpoints to fetch content. The specific endpoints are not hardcoded but are constructed based on the provided links. The HTTP requests are made using the `confluence.request` method, which handles the communication with Confluence.