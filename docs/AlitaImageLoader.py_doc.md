# AlitaImageLoader.py

**Path:** `src/alita_sdk/langchain/document_loaders/AlitaImageLoader.py`

## Data Flow

The data flow within the `AlitaImageLoader.py` file begins with the initialization of the `AlitaImageLoader` class, which requires a file path and optionally an LLM (Language Learning Model) and OCR (Optical Character Recognition) language. The primary function of this class is to load and process image files, either through OCR using `pytesseract` or through an LLM for advanced analysis. The data flow can be summarized as follows:

1. **Initialization:** The file path, LLM, and OCR language are set during the initialization of the `AlitaImageLoader` class.
2. **Image Loading:** The `load` method reads the image file from the specified path.
3. **Image Processing:** Depending on the file type (SVG or raster image), the image is processed either through OCR or LLM.
4. **Text Extraction:** The extracted text content is then returned as a `Document` object with metadata.

Example:
```python
image = Image.open(self.file_path)
text_content = pytesseract.image_to_string(image, lang=self.ocr_language)
```
In this example, the image is opened and processed using OCR to extract text content.

## Functions Descriptions

### `__init__(self, **kwargs)`

The constructor initializes the `AlitaImageLoader` class with the provided parameters. It sets the file path, LLM, OCR language, and prompt.

### `__perform_llm_prediction_for_image(self, image: Image, llm, prompt: str) -> str`

This private method performs LLM prediction for the given image. It converts the image to a byte array, encodes it in base64, and invokes the LLM with the prompt and image data.

### `__process_svg_with_llm(self, svg_content: bytes, llm, prompt: str) -> str`

This private method processes SVG content using the LLM. It converts the SVG to a PNG image and then performs LLM prediction on the image.

### `load(self) -> List[Document]`

The `load` method reads the image file from the specified path and processes it using either OCR or LLM, depending on the file type and the presence of an LLM. It returns a list of `Document` objects containing the extracted text content and metadata.

## Dependencies Used and Their Descriptions

### `pytesseract`

Used for performing OCR on image files to extract text content.

### `PIL (Pillow)`

Used for opening and manipulating image files.

### `langchain_core.document_loaders`

Provides the base class `BaseLoader` for the `AlitaImageLoader` class.

### `langchain_core.documents`

Provides the `Document` class used to return the extracted text content.

### `langchain_core.messages`

Provides the `HumanMessage` class used to format the prompt and image data for LLM invocation.

### `reportlab.graphics.renderPM`

Used for rendering SVG content to a PNG image.

### `svglib.svglib`

Used for converting SVG content to a drawing object that can be rendered to a PNG image.

## Functional Flow

The functional flow of the `AlitaImageLoader.py` file is as follows:

1. **Initialization:** The `AlitaImageLoader` class is initialized with the required parameters.
2. **Image Loading:** The `load` method reads the image file from the specified path.
3. **Image Processing:** Depending on the file type (SVG or raster image), the image is processed either through OCR or LLM.
4. **Text Extraction:** The extracted text content is then returned as a `Document` object with metadata.

## Endpoints Used/Created

No explicit endpoints are used or created within the `AlitaImageLoader.py` file.