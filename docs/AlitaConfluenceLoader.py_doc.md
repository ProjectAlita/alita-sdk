# AlitaConfluenceLoader.py

**Path:** `src/alita_sdk/langchain/document_loaders/AlitaConfluenceLoader.py`

## Data Flow

The data flow within the `AlitaConfluenceLoader` class primarily revolves around the processing of images and PDFs retrieved from Confluence. The data originates from Confluence links, which are fetched using HTTP requests. The content is then processed based on its format (image, PDF, or SVG). If the `bins_with_llm` flag is set and an LLM (Language Model) is provided, the content undergoes further analysis using the LLM to generate detailed descriptions or functional specifications. The processed data is then returned as text.

For example, in the `process_pdf` method:

```python
response = self.confluence.request(path=link, absolute=True)
if response.status_code == 200 and response.content:
    images = convert_from_bytes(response.content)
    for i, image in enumerate(images):
        result = self.__perform_llm_prediction_for_image(image)
        text += f"Page {i + 1}:\n{result}\n\n"
```

In this snippet, the PDF content is fetched, converted to images, and each image is processed using the LLM to generate text descriptions.

## Functions Descriptions

### `__init__(self, **kwargs)`

The constructor initializes the `AlitaConfluenceLoader` with optional parameters such as `bins_with_llm`, `prompt`, and `llm`. It sets these parameters and removes them from `kwargs` before calling the superclass constructor.

### `__perform_llm_prediction_for_image(self, image: Image) -> str`

This private method converts an image to a byte array, encodes it in base64, and sends it to the LLM for analysis. The LLM's response is returned as a string.

### `load(self, **kwargs)`

This method overrides the superclass's `load` method to map the `content_format` parameter to a specific `ContentFormat` enum value before calling the superclass method.

### `process_pdf(self, link: str, ocr_languages: Optional[str] = None) -> str`

This method processes a PDF from a Confluence link. If `bins_with_llm` is set and an LLM is provided, it converts the PDF to images and processes each image using the LLM. Otherwise, it calls the superclass method.

### `process_image(self, link: str, ocr_languages: Optional[str] = None) -> str`

This method processes an image from a Confluence link. If `bins_with_llm` is set and an LLM is provided, it processes the image using the LLM. Otherwise, it calls the superclass method.

### `process_svg(self, link: str, ocr_languages: Optional[str] = None) -> str`

This method processes an SVG from a Confluence link. If `bins_with_llm` is set and an LLM is provided, it converts the SVG to a PNG image and processes it using the LLM. Otherwise, it calls the superclass method.

## Dependencies Used and Their Descriptions

- `BytesIO` from `io`: Used for handling byte streams.
- `Optional` from `typing`: Used for type hinting optional parameters.
- `Image` from `PIL`: Used for image processing.
- `ConfluenceLoader` and `ContentFormat` from `langchain_community.document_loaders`: The superclass and content format enumeration.
- `HumanMessage` from `langchain_core.messages`: Used for creating messages to send to the LLM.
- `convert_from_bytes` from `pdf2image`: Used for converting PDF bytes to images.
- `renderPM` from `reportlab.graphics`: Used for rendering SVG to PNG.
- `svg2rlg` from `svglib.svglib`: Used for converting SVG to ReportLab graphics.
- `image_to_byte_array` and `bytes_to_base64` from `..tools.utils`: Utility functions for image processing and encoding.

## Functional Flow

1. **Initialization**: The `AlitaConfluenceLoader` is initialized with optional parameters for LLM integration.
2. **Loading Content**: The `load` method maps the `content_format` and calls the superclass method to load content from Confluence.
3. **Processing PDFs**: The `process_pdf` method fetches PDF content, converts it to images, and processes each image using the LLM if enabled.
4. **Processing Images**: The `process_image` method fetches and processes images using the LLM if enabled.
5. **Processing SVGs**: The `process_svg` method fetches SVG content, converts it to PNG, and processes it using the LLM if enabled.

## Endpoints Used/Created

The `AlitaConfluenceLoader` interacts with Confluence endpoints to fetch content. The specific endpoints are determined by the `link` parameter passed to the `process_pdf`, `process_image`, and `process_svg` methods. The HTTP requests are made using the `self.confluence.request` method, which handles the communication with Confluence.