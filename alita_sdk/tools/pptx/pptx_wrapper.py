from typing import Dict, Any, List, Optional
from copy import copy
import os
import tempfile
import zipfile
import xml.etree.ElementTree as ET
import chardet
from langchain_core.tools import ToolException
from pydantic import create_model, BaseModel, Field
from ..elitea_base import BaseToolApiWrapper
from logging import getLogger
import traceback
from langchain_core.messages import HumanMessage
import pptx
from pptx.enum.shapes import MSO_SHAPE_TYPE
logger = getLogger(__name__)


INTRO_PROMPT = """I need content for PowerPoint slide {slide_idx}.
Based on the image of the slide and the data available for use 
Please provide replacements for ALL these placeholders in the slide

<Data Available for use>
{content_description}
</Data Available for use>"""


class PPTXWrapper(BaseToolApiWrapper):
    """
    API wrapper for PPTX file manipulation.
    Uses the Alita artifact API to download and upload PPTX files from/to buckets.
    """
    bucket_name: str
    alita: Any  # AlitaClient
    llm: Any  # LLMLikeObject

    def _bytes_content(self, content: Any) -> bytes:
        """
        Returns the content of the file as bytes
        """
        if isinstance(content, bytes):
            return content
        return content.encode('utf-8')

    def get(self, artifact_name: str, bucket_name: str = None):
        if not bucket_name:
            bucket_name = self.bucket_name
        data = self.client.download_artifact(bucket_name, artifact_name)
        if len(data) == 0:
            # empty file might be created
            return ""
        if isinstance(data, dict) and data['error']:
            return f"{data['error']}. {data['content'] if data['content'] else ''}"
        detected = chardet.detect(data)
        if detected['encoding'] is not None:
            return data.decode(detected['encoding'])
        else:
            return "Could not detect encoding"

    def _download_pptx(self, file_name: str) -> str:
        """
        Download PPTX from bucket to a temporary file.
        
        Args:
            file_name: The name of the file in the bucket
            
        Returns:
            Path to the temporary file
        """
        try:
            # Create a temporary file
            temp_dir = tempfile.gettempdir()
            local_path = os.path.join(temp_dir, file_name)
            data = self.alita.download_artifact(self.bucket_name, file_name)
            if isinstance(data, dict) and data['error']:
                raise NameError(f"{data['error']}. {data['content'] if data['content'] else ''}")
            with open(local_path, 'wb') as f:
                f.write(data)
            logger.info(f"Downloaded PPTX from bucket {self.bucket_name} to {local_path}")
            return local_path
        except Exception as e:
            logger.error(f"Error downloading PPTX file {file_name}: {str(e)}")
            raise e

    def _upload_pptx(self, local_path: str, file_name: str) -> str:
        """
        Upload PPTX to bucket from a local file.
        
        Args:
            local_path: Path to the local file
            file_name: The name to give the file in the bucket
            
        Returns:
            URL of the uploaded file
        """
        try:
            # Upload file to the bucket
            response = None
            with open(local_path, 'rb') as f:
                response = self.alita.create_artifact(
                    bucket_name=self.bucket_name,
                    artifact_name=file_name,
                    artifact_data=f.read()
                )
            
            logger.info(f"Uploaded PPTX to bucket {self.bucket_name} as {file_name}")
            return response
        except Exception as e:
            logger.error(f"Error uploading PPTX file {file_name}: {str(e)}")
            raise e

    def _get_structured_output_llm(self, stuct_model, method: Literal["function_calling", "json_mode", "json_schema"] = "function_calling"):
        """
        Returns the structured output LLM if available, otherwise returns the regular LLM
        """
        shalow_llm = copy(self.llm)
        return shalow_llm.with_structured_output(stuct_model, method)

    def _extract_text_from_shape(self, shape) -> List[str]:
        """
        Safely extract text from any shape type including SmartArt, tables, and text frames.

        Args:
            shape: A shape object from python-pptx

        Returns:
            List of text strings found in the shape
        """
        texts = []

        try:
            # Handle regular text frames
            if hasattr(shape, "text_frame") and shape.text_frame:
                try:
                    text = shape.text_frame.text
                    if text:
                        texts.append(text)
                except Exception as e:
                    logger.debug(f"Could not extract text from text_frame: {e}")

            # Handle tables
            if hasattr(shape, "has_table") and shape.has_table:
                try:
                    for row in shape.table.rows:
                        for cell in row.cells:
                            if cell.text_frame and cell.text_frame.text:
                                texts.append(cell.text_frame.text)
                except Exception as e:
                    logger.debug(f"Could not extract text from table: {e}")

            # Handle SmartArt and other GraphicFrame shapes
            if shape.shape_type == MSO_SHAPE_TYPE.PLACEHOLDER or shape.shape_type not in [
                MSO_SHAPE_TYPE.PICTURE,
                MSO_SHAPE_TYPE.TABLE,
                MSO_SHAPE_TYPE.TEXT_BOX,
                MSO_SHAPE_TYPE.AUTO_SHAPE,
                MSO_SHAPE_TYPE.GROUP
            ]:
                # Try to extract text from graphic frame elements via XML
                try:
                    if hasattr(shape, 'element'):
                        # Navigate through the XML to find text elements
                        element = shape.element
                        # Look for text in a:t elements (drawingML text)
                        namespaces = {
                            'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
                            'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
                        }
                        text_elements = element.findall('.//a:t', namespaces)
                        for text_elem in text_elements:
                            if text_elem.text:
                                texts.append(text_elem.text)

                        if text_elements:
                            logger.debug(f"Extracted {len(text_elements)} text elements from SmartArt/GraphicFrame via XML")
                except Exception as e:
                    logger.debug(f"Could not extract text from SmartArt/GraphicFrame via XML: {e}")

        except Exception as e:
            logger.debug(f"Error extracting text from shape: {e}")

        return texts

    def _create_slide_model(self, placeholders: List[str]) -> type:
        """
        Dynamically creates a Pydantic model for a slide based on its placeholders
        
        Args:
            placeholders: List of placeholder texts found in the slide
            
        Returns:
            A Pydantic model class for the slide
        """
        field_dict = {}
        for i, placeholder in enumerate(placeholders):
            # Clean placeholder text for field name
            field_name = f"placeholder_{i}"
            # Add a field for each placeholder
            field_dict[field_name] = (str, Field(description=f"Content for: {placeholder}"))
            
        # Create and return the model
        return create_model(f"SlideModel", **field_dict)

    def fill_template(self, file_name: str, output_file_name: str, content_description: str, pdf_file_name: str = None) -> Dict[str, Any]:
        """
        Fill a PPTX template with content based on the provided description.
        
        Args:
            file_name: PPTX file name in the bucket
            output_file_name: Output PPTX file name to save in the bucket
            content_description: Detailed description of what content to put where in the template
            pdf_file_name: Optional PDF file name in the bucket that matches the PPTX template 1:1
            
        Returns:
            Dictionary with result information
        """
        import pptx
        import base64
        from io import BytesIO
        
        try:
            # Download the PPTX file
            local_path = self._download_pptx(file_name)
            
            # Load the presentation
            presentation = pptx.Presentation(local_path)
            
            # If PDF file is provided, download and extract images from it
            pdf_pages = {}
            if pdf_file_name:
                try:
                    import fitz  # PyMuPDF
                    from PIL import Image
                    
                    # Download PDF file
                    pdf_data = self.alita.download_artifact(self.bucket_name, pdf_file_name)
                    if isinstance(pdf_data, dict) and pdf_data.get('error'):
                        raise ValueError(f"Error downloading PDF: {pdf_data.get('error')}")
                    
                    # Create a temporary memory buffer for PDF
                    pdf_buffer = BytesIO(pdf_data)
                    
                    # Open the PDF
                    pdf_doc = fitz.open(stream=pdf_buffer, filetype="pdf")
                    
                    # Extract images from each page
                    for page_idx in range(len(pdf_doc)):
                        page = pdf_doc.load_page(page_idx)
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x scale for better readability
                        
                        # Convert to PIL Image
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        
                        # Convert to base64 for LLM
                        buffered = BytesIO()
                        img.save(buffered, format="PNG")
                        img_str = base64.b64encode(buffered.getvalue()).decode()
                        
                        # Store image for later use
                        pdf_pages[page_idx] = img_str
                    
                    logger.info(f"Successfully extracted {len(pdf_pages)} pages from PDF {pdf_file_name}")
                except ImportError:
                    logger.warning("PyMuPDF (fitz) or PIL not installed. PDF processing skipped. Install with 'pip install PyMuPDF Pillow'")
                except Exception as e:
                    logger.warning(f"Failed to process PDF {pdf_file_name}: {str(e)}")
            
            # Process each slide based on the content description
            for slide_idx, slide in enumerate(presentation.slides):
                # Collect all placeholders in this slide
                placeholders = []
                placeholder_shapes = []
                
                # Get all shapes that contain text
                for shape in slide.shapes:
                    shape_type_name = shape.shape_type if hasattr(shape, 'shape_type') else 'unknown'

                    # Check text frames for placeholders
                    try:
                        if hasattr(shape, "text_frame") and shape.text_frame:
                            # Check if this is a placeholder that needs to be filled
                            text = shape.text_frame.text
                            if text and ("{{" in text or "[PLACEHOLDER]" in text):
                                placeholders.append(text)
                                placeholder_shapes.append(shape)
                                logger.debug(f"Found placeholder in text_frame (shape_type={shape_type_name})")
                    except Exception as e:
                        logger.debug(f"Could not access text_frame for shape_type={shape_type_name}: {e}")

                    # Check tables for placeholders in cells
                    try:
                        if hasattr(shape, "has_table") and shape.has_table:
                            for row_idx, row in enumerate(shape.table.rows):
                                for col_idx, cell in enumerate(row.cells):
                                    if cell.text_frame:
                                        text = cell.text_frame.text
                                        if text and ("{{" in text or "[PLACEHOLDER]" in text):
                                            placeholders.append(text)
                                            # Store tuple with table info: (shape, row_idx, col_idx)
                                            placeholder_shapes.append((shape, row_idx, col_idx))
                                            logger.debug(f"Found placeholder in table cell [{row_idx},{col_idx}]")
                    except Exception as e:
                        logger.debug(f"Could not access table for shape_type={shape_type_name}: {e}")

                    # Check SmartArt and other GraphicFrame shapes for placeholders
                    if shape_type_name not in [MSO_SHAPE_TYPE.PICTURE, MSO_SHAPE_TYPE.TABLE, MSO_SHAPE_TYPE.TEXT_BOX]:
                        try:
                            smartart_texts = self._extract_text_from_shape(shape)
                            for text in smartart_texts:
                                if text and ("{{" in text or "[PLACEHOLDER]" in text):
                                    placeholders.append(text)
                                    placeholder_shapes.append(shape)
                                    logger.debug(f"Found placeholder in SmartArt/GraphicFrame (shape_type={shape_type_name})")
                        except Exception as e:
                            logger.debug(f"Could not extract text from SmartArt/GraphicFrame (shape_type={shape_type_name}): {e}")


                logger.info(f"Found {len(placeholders)} placeholders in slide {slide_idx + 1}")
                if placeholders:
                    # Create a dynamic Pydantic model for this slide
                    slide_model = self._create_slide_model(placeholders)
                    # Create a prompt with image and all placeholders on this slide
                    prompt_parts = [
                        {
                            "type": "text", 
                            "text": INTRO_PROMPT.format(slide_idx=slide_idx + 1,
                                                        content_description=content_description)
                        }
                    ]
                    
                    # Add each placeholder text
                    for i, placeholder in enumerate(placeholders):
                        prompt_parts.append({
                            "type": "text",
                            "text": f"Placeholder {i+1}: {placeholder}"
                        })
                    
                    # Add PDF image if available
                    if pdf_pages and slide_idx in pdf_pages:
                        prompt_parts.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{pdf_pages[slide_idx]}"
                            }
                        })
                    
                    # Get the structured output LLM
                    structured_llm = self._get_structured_output_llm(slide_model)
                    try:
                        result = structured_llm.invoke([HumanMessage(content=prompt_parts)])
                    except Exception as e:
                        logger.error(f"Error invoking structured LLM: {str(e)}")
                        return ToolException(f"Cannot fill the pptx template: \nerror invoking structured LLM: {str(e)}")
                    for key, value in result.model_dump().items():
                        # Replace the placeholder text with the generated content
                        for i, shape_or_cell_info in enumerate(placeholder_shapes):
                            if key == f"placeholder_{i}":
                                # Store the text frame for cleaner code
                                if isinstance(shape_or_cell_info, tuple):
                                    table_shape, row_idx, col_idx = shape_or_cell_info
                                    text_frame = table_shape.table.rows[row_idx].cells[col_idx].text_frame
                                else:
                                    text_frame = shape_or_cell_info.text_frame
                                
                                # Save paragraph formatting settings before clearing
                                paragraph_styles = []
                                for paragraph in text_frame.paragraphs:
                                    # Save paragraph level properties
                                    para_style = {
                                        'alignment': paragraph.alignment,
                                        'level': paragraph.level,
                                        'line_spacing': paragraph.line_spacing,
                                        'space_before': paragraph.space_before,
                                        'space_after': paragraph.space_after
                                    }
                                    
                                    # Save run level properties for each run in the paragraph
                                    runs_style = []
                                    for run in paragraph.runs:
                                        run_style = {
                                            'font': run.font,
                                            'text_len': len(run.text)
                                        }
                                        runs_style.append(run_style)
                                    
                                    para_style['runs'] = runs_style
                                    paragraph_styles.append(para_style)
                                
                                # Clear the text frame but keep the formatting
                                text_frame.clear()
                                
                                # Get the first paragraph (created automatically when frame is cleared)
                                p = text_frame.paragraphs[0]
                                
                                # Apply the first paragraph's style if available
                                if paragraph_styles:
                                    first_para_style = paragraph_styles[0]
                                    p.alignment = first_para_style['alignment']
                                    p.level = first_para_style['level']
                                    p.line_spacing = first_para_style['line_spacing']
                                    p.space_before = first_para_style['space_before']
                                    p.space_after = first_para_style['space_after']
                                    
                                    # If we have style info for runs, apply it to segments of the new text
                                    if first_para_style['runs']:
                                        remaining_text = value
                                        for run_style in first_para_style['runs']:
                                            if not remaining_text:
                                                break
                                                
                                            # Calculate text length for this run (use original or remaining, whichever is smaller)
                                            text_len = min(run_style['text_len'], len(remaining_text))
                                            run_text = remaining_text[:text_len]
                                            remaining_text = remaining_text[text_len:]
                                            
                                            # Create a run with the style from the original
                                            run = p.add_run()
                                            run.text = run_text
                                            
                                            # Copy font properties safely
                                            # Some font attributes in python-pptx are read-only
                                            # Only copy attributes that can be safely set
                                            safe_font_attrs = ['bold', 'italic', 'underline']
                                            for attr in safe_font_attrs:
                                                if hasattr(run_style['font'], attr):
                                                    try:
                                                        setattr(run.font, attr, getattr(run_style['font'], attr))
                                                    except (AttributeError, TypeError):
                                                        # Skip if attribute can't be set
                                                        logger.debug(f"Couldn't set font attribute: {attr}")
                                            
                                            # Handle color safely - check if color attribute exists and has rgb
                                            try:
                                                if (hasattr(run_style['font'], 'color') and 
                                                    hasattr(run_style['font'].color, 'rgb') and 
                                                    run_style['font'].color.rgb is not None):
                                                    run.font.color.rgb = run_style['font'].color.rgb
                                            except (AttributeError, TypeError) as e:
                                                logger.debug(f"Couldn't set font color: {e}")
                                            
                                            # Handle size specially
                                            if hasattr(run_style['font'], 'size') and run_style['font'].size is not None:
                                                try:
                                                    run.font.size = run_style['font'].size
                                                except (AttributeError, TypeError):
                                                    logger.debug("Couldn't set font size")
                                        
                                        # If there's still text left, add it with the last style
                                        if remaining_text and first_para_style['runs']:
                                            run = p.add_run()
                                            run.text = remaining_text
                                            last_style = first_para_style['runs'][-1]
                                            
                                            # Copy font properties safely for the remaining text
                                            safe_font_attrs = ['bold', 'italic', 'underline']
                                            for attr in safe_font_attrs:
                                                if hasattr(last_style['font'], attr):
                                                    try:
                                                        setattr(run.font, attr, getattr(last_style['font'], attr))
                                                    except (AttributeError, TypeError):
                                                        # Skip if attribute can't be set
                                                        logger.debug(f"Couldn't set font attribute: {attr}")
                                            
                                            # Handle color safely for remaining text
                                            try:
                                                if (hasattr(last_style['font'], 'color') and 
                                                    hasattr(last_style['font'].color, 'rgb') and 
                                                    last_style['font'].color.rgb is not None):
                                                    run.font.color.rgb = last_style['font'].color.rgb
                                            except (AttributeError, TypeError) as e:
                                                logger.debug(f"Couldn't set font color: {e}")
                                            
                                            # Handle size specially
                                            if hasattr(last_style['font'], 'size') and last_style['font'].size is not None:
                                                try:
                                                    run.font.size = last_style['font'].size
                                                except (AttributeError, TypeError):
                                                    logger.debug("Couldn't set font size")
                                    else:
                                        # No run style information available, just add the text
                                        p.text = value
                                else:
                                    # No style information available, just add the text
                                    p.text = value
            # Save the modified presentation
            temp_output_path = os.path.join(tempfile.gettempdir(), output_file_name)
            presentation.save(temp_output_path)
            
            # Upload the modified file
            result_url = self._upload_pptx(temp_output_path, output_file_name)
            
            # Clean up temporary files
            try:
                os.remove(local_path)
                os.remove(temp_output_path)
            except:
                pass
            
            return {
                "status": "success",
                "message": f"Successfully filled template and saved as {output_file_name}",
                "url": result_url
            }
            
        except Exception as e:
            logger.error(f"Error filling PPTX template: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to fill template: {traceback.format_exc()}"
            }

    def unzip_pptx(self, pptx_path, extract_dir):
        # Unzip the pptx file
        with zipfile.ZipFile(pptx_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

    def edit_smartart_xml(self, diagram_folder, target_language):
        """
        Translate SmartArt texts in batch mode.
        """
        # Phase 1: Collect all texts with their element references
        text_items = []  # List of (element, original_text) tuples

        for root_dir, dirs, files in os.walk(diagram_folder):
            for file in files:
                if file.startswith('data') and file.endswith('.xml'):
                    xml_file = os.path.join(root_dir, file)
                    tree = ET.parse(xml_file)
                    root = tree.getroot()

                    for elem in root.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'):
                        if elem.text:
                            text_items.append((elem, xml_file, tree))

        # Phase 2: Translate all texts in a single batch
        if text_items:
            texts_to_translate = [elem.text for elem, _, _ in text_items]
            translated_texts = self.translate_batch(texts_to_translate, target_language)

            # Phase 3: Update elements with translations
            files_to_save = {}  # Track which files need to be saved
            for (elem, xml_file, tree), translated_text in zip(text_items, translated_texts):
                elem.text = translated_text
                files_to_save[xml_file] = tree

            # Save all modified XML files
            for xml_file, tree in files_to_save.items():
                tree.write(xml_file, encoding='utf-8', xml_declaration=True)
                logger.debug(f"Edited {xml_file}")


    def rezip_pptx(self, extract_dir, output_pptx):
        with zipfile.ZipFile(output_pptx, 'w', zipfile.ZIP_DEFLATED) as pptx_zip:
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, extract_dir)
                    pptx_zip.write(full_path, arcname)

    def translate_batch(self, texts: List[str], target_language: str, max_batch_size: int = 20) -> List[str]:
        """
        Translate multiple texts in a single LLM call (or multiple calls if texts exceed max_batch_size).

        Args:
            texts: List of texts to translate
            target_language: Target language name (e.g., 'Spanish', 'Ukrainian')
            max_batch_size: Maximum number of texts to translate in a single LLM call (default: 100)
                           Adjust this based on your LLM's token limits and average text length.

        Returns:
            List of translated texts in the same order as input
        """
        if not texts:
            return []

        # If texts exceed max_batch_size, process in chunks
        if len(texts) > max_batch_size:
            logger.info(f"Processing {len(texts)} texts in chunks of {max_batch_size}")
            all_translations = []

            for i in range(0, len(texts), max_batch_size):
                chunk = texts[i:i + max_batch_size]
                chunk_num = (i // max_batch_size) + 1
                total_chunks = (len(texts) + max_batch_size - 1) // max_batch_size
                logger.info(f"Translating chunk {chunk_num}/{total_chunks} ({len(chunk)} texts)")

                chunk_translations = self._translate_batch_single(chunk, target_language, start_index=i)
                all_translations.extend(chunk_translations)

            logger.info(f"Completed translation of {len(all_translations)} texts in {total_chunks} chunks")
            return all_translations

        # Process all texts in a single call
        return self._translate_batch_single(texts, target_language, start_index=0)

    def _translate_batch_single(self, texts: List[str], target_language: str, start_index: int = 0) -> List[str]:
        """
        Internal method to translate a batch of texts in a single LLM call.

        Args:
            texts: List of texts to translate
            target_language: Target language name
            start_index: Starting index for numbering (used when chunking)

        Returns:
            List of translated texts in the same order as input
        """
        if not texts:
            return []

        # Escape texts for JSON-like format to handle newlines properly
        import json

        # Create a structured list of texts with indices
        texts_list = [{"index": start_index + i + 1, "text": text} for i, text in enumerate(texts)]
        texts_json = json.dumps(texts_list, ensure_ascii=False, indent=2)

        prompt = f"""Please translate the following {len(texts)} texts to {target_language}.
The texts are provided in JSON format below. Some texts may contain newlines or special characters.

Return your response as a JSON array with the same structure, keeping the same index numbers.
Format: [{{"index": {start_index + 1}, "translation": "translated text"}}, {{"index": {start_index + 2}, "translation": "translated text"}}, ...]

IMPORTANT: Preserve any newlines (\\n) in the translated text. Only translate the content, keep the formatting.

Texts to translate:
{texts_json}"""

        result = self.llm.invoke([HumanMessage(content=[{"type": "text", "text": prompt}])])
        translated_content = result.content.strip()

        # Parse the JSON response
        translated_texts = []
        try:
            # Try to extract JSON from the response (LLM might wrap it in markdown)
            import re

            # Remove markdown code blocks if present
            json_match = re.search(r'```(?:json)?\s*(\[.*\])\s*```', translated_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON array directly
                json_match = re.search(r'(\[.*\])', translated_content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = translated_content

            # Parse the JSON
            translations_list = json.loads(json_str)

            # Sort by index to ensure correct order
            translations_list.sort(key=lambda x: x.get('index', 0))

            # Extract translations in order
            for item in translations_list:
                translated_text = item.get('translation', item.get('text', ''))
                translated_texts.append(translated_text)

            logger.debug(f"Successfully parsed {len(translated_texts)} translations from JSON response")

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse JSON response: {e}. Falling back to line-by-line parsing.")

            # Fallback to old parsing method
            for line in translated_content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                # Remove numbering and quotes
                match = re.match(r'^\d+[\.\)]\s*(.*)', line)
                if match:
                    translated_texts.append(match.group(1).strip().strip('"\''))
                else:
                    # Try to extract from JSON-like format
                    trans_match = re.search(r'"translation":\s*"([^"]*)"', line)
                    if trans_match:
                        translated_texts.append(trans_match.group(1))

        # Ensure we have the same number of translations as inputs
        if len(translated_texts) != len(texts):
            logger.warning(f"Expected {len(texts)} translations but got {len(translated_texts)}. Falling back to original texts for missing translations.")
            # Pad with original texts if needed
            while len(translated_texts) < len(texts):
                translated_texts.append(texts[len(translated_texts)])

        return translated_texts[:len(texts)]

    def _translate_smart_objects(self, local_path, output_file_name, target_language_name):
        # Translate smart objects in the presentation from unzipped resources folder

        # Create a unique temporary directory for extraction
        extract_dir = tempfile.mkdtemp(prefix='pptx_translate_')

        self.unzip_pptx(pptx_path=local_path, extract_dir=extract_dir)
        self.edit_smartart_xml(extract_dir, target_language_name)

        # Save to the proper output path
        temp_output_path = os.path.join(tempfile.gettempdir(), output_file_name)
        self.rezip_pptx(extract_dir, temp_output_path)

        # Load the modified presentation to ensure it's valid
        presentation = pptx.Presentation(temp_output_path)
        return temp_output_path

    def translate_presentation(self, file_name: str, output_file_name: str, target_language: str) -> Dict[str, Any]:
        """
        Translate text in a PowerPoint presentation to another language.

        Args:
            file_name: PPTX file name in the bucket
            output_file_name: Output PPTX file name to save in the bucket
            target_language: Target language code (e.g., 'es' for Spanish, 'ua' for Ukrainian)
            
        Returns:
            Dictionary with result information
        """
        try:
            # Download the PPTX file
            local_path = self._download_pptx(file_name)
            
            # Load the presentation
            presentation = pptx.Presentation(local_path)
            
            # Map of language codes to full language names
            language_names = {
                'en': 'English',
                'es': 'Spanish',
                'fr': 'French',
                'de': 'German',
                'it': 'Italian',
                'pt': 'Portuguese',
                'ru': 'Russian',
                'ja': 'Japanese',
                'zh': 'Chinese',
                'ar': 'Arabic',
                'hi': 'Hindi',
                'ko': 'Korean',
                'ua': 'Ukrainian'
            }
            
            # Get the full language name if available, otherwise use the code
            target_language_name = language_names.get(target_language.lower(), target_language)
            
            # Phase 1: Collect all texts with their locations
            text_items = []  # List of (text, location_reference) tuples

            # Process each slide and collect text
            for slide_idx, slide in enumerate(presentation.slides):
                logger.debug(f"Collecting texts from slide {slide_idx + 1} for translation")

                # Get all shapes that contain text
                for shape in slide.shapes:
                    shape_type_name = shape.shape_type if hasattr(shape, 'shape_type') else 'unknown'

                    # Collect text from text frames
                    try:
                        if hasattr(shape, "text_frame") and shape.text_frame:
                            # Check if there's text to translate
                            if shape.text_frame.text:
                                logger.debug(f"Collecting text_frame in shape_type={shape_type_name}")
                                # Collect each paragraph
                                for para_idx, paragraph in enumerate(shape.text_frame.paragraphs):
                                    if paragraph.text:
                                        text_items.append((
                                            paragraph.text,
                                            ('text_frame', slide_idx, shape, para_idx)
                                        ))
                    except Exception as e:
                        logger.debug(f"Could not collect text_frame for shape_type={shape_type_name}: {e}")

                    # Collect text from tables
                    try:
                        if hasattr(shape, "has_table") and shape.has_table:
                            logger.debug(f"Collecting table texts in shape_type={shape_type_name}")
                            for row_idx, row in enumerate(shape.table.rows):
                                for col_idx, cell in enumerate(row.cells):
                                    if cell.text_frame and cell.text_frame.text:
                                        # Collect each paragraph in the cell
                                        for para_idx, paragraph in enumerate(cell.text_frame.paragraphs):
                                            if paragraph.text:
                                                text_items.append((
                                                    paragraph.text,
                                                    ('table', slide_idx, shape, row_idx, col_idx, para_idx)
                                                ))
                    except Exception as e:
                        logger.debug(f"Could not collect table texts for shape_type={shape_type_name}: {e}")

            logger.info(f"Collected {len(text_items)} text items for translation")

            # Phase 2: Translate all texts in a single batch call
            if text_items:
                texts_to_translate = [item[0] for item in text_items]
                translated_texts = self.translate_batch(texts_to_translate, target_language_name)

                # Phase 3: Apply translations back to their original locations
                for (original_text, location), translated_text in zip(text_items, translated_texts):
                    try:
                        if location[0] == 'text_frame':
                            _, slide_idx, shape, para_idx = location
                            shape.text_frame.paragraphs[para_idx].text = translated_text
                            logger.debug(f"Updated text_frame paragraph {para_idx} on slide {slide_idx + 1}")
                        elif location[0] == 'table':
                            _, slide_idx, shape, row_idx, col_idx, para_idx = location
                            cell = shape.table.rows[row_idx].cells[col_idx]
                            cell.text_frame.paragraphs[para_idx].text = translated_text
                            logger.debug(f"Updated table cell [{row_idx},{col_idx}] paragraph {para_idx} on slide {slide_idx + 1}")
                    except Exception as e:
                        logger.error(f"Failed to apply translation at location {location}: {e}")


            # Save already translated version of presentation (it can be modified for smart objects later)
            temp_output_path = os.path.join(tempfile.gettempdir(), output_file_name)
            presentation.save(temp_output_path)

            # Translate text in SmartArt and other GraphicFrame shapes from the unzipped resources
            try:
               translated_pptx_path = self._translate_smart_objects(temp_output_path, output_file_name, target_language_name)
               result_url = self._upload_pptx(translated_pptx_path, output_file_name)
            except Exception as e:
                logger.debug(f"Could not translate SmartArt objects: {e}")
                # Upload the translated file
                result_url = self._upload_pptx(temp_output_path, output_file_name)

            # Clean up temporary files
            try:
                os.remove(local_path)
                os.remove(temp_output_path)
                os.remove(translated_pptx_path)
            except:
                pass
            
            return {
                "status": "success",
                "message": f"Successfully translated presentation to {target_language_name} and saved as {output_file_name}",
                "url": result_url
            }
            
        except Exception as e:
            logger.error(f"Error translating PPTX: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to translate presentation: {str(e)}"
            }
    
    
    def get_available_tools(self):
        """
        Return list of available tools.
        """
        return [{
            "name": "fill_template",
            "description": "Fill a PPTX template with content based on the provided description",
            "ref": self.fill_template,
            "args_schema": create_model(
                "FillTemplateArgs",
                file_name=(str, Field(description="PPTX file name in the bucket")),
                output_file_name=(str, Field(description="Output PPTX file name to save in the bucket")),
                content_description=(str, Field(description="Detailed description of what content to put where in the template")),
                pdf_file_name=(Optional[str], Field(description="Optional PDF file name in the bucket that matches the PPTX template 1:1", default=None))
            )
        },{
            "name": "translate_presentation",
            "description": "Translate text in a PowerPoint presentation to another language",
            "ref": self.translate_presentation,
            "args_schema": create_model(
                "TranslatePresentationArgs",
                file_name=(str, Field(description="PPTX file name in the bucket")),
                output_file_name=(str, Field(description="Output PPTX file name to save in the bucket")),
                target_language=(str, Field(description="Target language code (e.g., 'es' for Spanish, 'ua' for Ukrainian)"))
            )
        }]
