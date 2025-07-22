import re

from docx import Document
from io import BytesIO
import pandas as pd
from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
import io
import pymupdf
from langchain_core.tools import ToolException
from transformers import BlipProcessor, BlipForConditionalGeneration
from langchain_core.messages import HumanMessage

from ...runtime.langchain.tools.utils import bytes_to_base64

image_processing_prompt='''
You are an AI model designed for analyzing images. Your task is to accurately describe the content of the given image. Depending on the type of image, follow these specific instructions:

If the image is a diagram (e.g., chart, table, pie chart, bar graph, etc.):

Identify the type of diagram.
Extract all numerical values, labels, axis titles, headings, legends, and any other textual elements.
Describe the relationships or trends between the data, if visible.
If the image is a screenshot:

Describe what is shown in the screenshot.
If it is a software interface, identify the program or website name (if visible).
List the key interface elements (e.g., buttons, menus, text fields, images, headers).
If there is text, extract it.
If the screenshot shows a conversation, describe the participants, the content of the messages, and timestamps (if visible).
If the image is a photograph:

Describe the main objects, people, animals, or elements visible in the photo.
Specify the setting (e.g., indoors, outdoors, nature, urban area).
If possible, identify the actions being performed by people or objects in the photo.
If the image is an illustration or drawing:

Describe the style of the illustration (e.g., realistic, cartoonish, abstract).
Identify the main elements, their colors, and the composition of the image.
If there is text, extract it.
If the image contains text:

Extract all text from the image.
Specify the format of the text (e.g., heading, paragraph, list).
If the image is a mixed type (e.g., a diagram within a screenshot):

Identify all types of content present in the image.
Perform an analysis for each type of content separately, following the relevant instructions above.
If the image does not fit into any of the above categories:

Provide a detailed description of what is shown in the image.
Highlight any visible details that could help in understanding the image.
Be as precise and thorough as possible in your responses. If something is unclear or illegible, state that explicitly.
'''

IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp', 'svg']

def parse_file_content(file_name, file_content, is_capture_image: bool = False, page_number: int = None, sheet_name: str = None, llm=None):
    if file_name.endswith('.txt'):
        return parse_txt(file_content)
    elif file_name.endswith('.docx'):
        return read_docx_from_bytes(file_content)
    elif file_name.endswith('.xlsx') or file_name.endswith('.xls'):
        return parse_excel(file_content, sheet_name)
    elif file_name.endswith('.pdf'):
        return parse_pdf(file_content, page_number, is_capture_image, llm)
    elif file_name.endswith('.pptx'):
        return parse_pptx(file_content, page_number, is_capture_image, llm)
    elif any(file_name.lower().endswith(f".{ext}") for ext in IMAGE_EXTENSIONS):
        match = re.search(r'\.([a-zA-Z0-9]+)$', file_name)
        return __perform_llm_prediction_for_image(llm, file_content, match.group(1), image_processing_prompt)
    else:
        return ToolException(
            "Not supported type of files entered. Supported types are TXT, DOCX, PDF, PPTX, XLSX and XLS only.")

def parse_txt(file_content):
    try:
        return file_content.decode('utf-8')
    except Exception as e:
        return ToolException(f"Error decoding file content: {e}")

def parse_excel(file_content, sheet_name = None):
    try:
        excel_file = io.BytesIO(file_content)
        if sheet_name:
            return parse_sheet(excel_file, sheet_name)
        dfs = pd.read_excel(excel_file, sheet_name=sheet_name)
        result = []
        for sheet_name, df in dfs.items():
            df.fillna('', inplace=True)
            result.append(f"=== Sheet: {sheet_name} ===\n{df.to_string(index=False)}")
        return "\n\n".join(result)
    except Exception as e:
        return ToolException(f"Error reading Excel file: {e}")

def parse_sheet(excel_file, sheet_name):
    df = pd.read_excel(excel_file, sheet_name=sheet_name)
    df.fillna('', inplace=True)
    return df.to_string()

def parse_pdf(file_content, page_number, is_capture_image, llm):
    with pymupdf.open(stream=file_content, filetype="pdf") as report:
        text_content = ''
        if page_number is not None:
            page = report.load_page(page_number - 1)
            text_content += read_pdf_page(report, page, page_number, is_capture_image, llm)
        else:
            for index, page in enumerate(report, start=1):
                text_content += read_pdf_page(report, page, index, is_capture_image, llm)
        return text_content

def parse_pptx(file_content, page_number, is_capture_image, llm=None):
    prs = Presentation(io.BytesIO(file_content))
    text_content = ''
    if page_number is not None:
        text_content += read_pptx_slide(prs.slides[page_number - 1], page_number, is_capture_image, llm)
    else:
        for index, slide in enumerate(prs.slides, start=1):
            text_content += read_pptx_slide(slide, index, is_capture_image, llm)
    return text_content

def read_pdf_page(report, page, index, is_capture_images, llm=None):
    text_content = f'Page: {index}\n'
    text_content += page.get_text()
    if is_capture_images:
        images = page.get_images(full=True)
        for i, img in enumerate(images):
            xref = img[0]
            base_image = report.extract_image(xref)
            img_bytes = base_image["image"]
            text_content += __perform_llm_prediction_for_image(llm, img_bytes)
    return text_content

def read_docx_from_bytes(file_content):
    """Read and return content from a .docx file using a byte stream."""
    try:
        doc = Document(BytesIO(file_content))
        text = []
        for paragraph in doc.paragraphs:
            text.append(paragraph.text)
        return '\n'.join(text)
    except Exception as e:
        print(f"Error reading .docx from bytes: {e}")
        return ""

def read_pptx_slide(slide, index, is_capture_image, llm):
    text_content = f'Slide: {index}\n'
    for shape in slide.shapes:
        if hasattr(shape, "text"):
            text_content += shape.text + "\n"
        elif is_capture_image and shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            try:
                caption = __perform_llm_prediction_for_image(llm, shape.image.blob)
            except:
                caption = "\n[Picture: unknown]\n"
            text_content += caption
    return text_content

def describe_image(image):
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    inputs = processor(image, return_tensors="pt")
    out = model.generate(**inputs)
    return "\n[Picture: " + processor.decode(out[0], skip_special_tokens=True) + "]\n"

def __perform_llm_prediction_for_image(llm, image: bytes, image_format='png', prompt=image_processing_prompt) -> str:
    base64_string = bytes_to_base64(image)
    result = llm.invoke([
        HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/{image_format};base64,{base64_string}"},
                },
            ])
    ])
    return f"\n[Image description: {result.content}]\n"