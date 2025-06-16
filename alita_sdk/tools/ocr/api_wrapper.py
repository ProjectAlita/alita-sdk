import io
import os
import logging
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
from typing import Optional, Any, Dict, List
import tempfile
import subprocess

from pydantic import BaseModel, Field, model_validator
from langchain_core.tools import ToolException

from ..elitea_base import BaseToolApiWrapper
from ..utils import create_pydantic_model

from .text_detection import (
    classify_document_image,
    orientation_detection
)

logger = logging.getLogger(__name__)

MIME_TO_EXTENSION = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/gif": [".gif"],
    "image/bmp": [".bmp"],
    "image/tiff": [".tiff", ".tif"],
    "application/pdf": [".pdf"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx", '.doc'],
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx", '.ppt']
}

# Helper to map Office extensions to their MIME types for easier lookup
OFFICE_EXTENSIONS = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"
}

IMAGE_OCR_PROMPT_TEMPLATE = """Please extract all text from the image."""


# Models for tool arguments
class RecognizeArgs(BaseModel):
    file_path: str = Field(..., description="Path to the specific image, PDF, DOCX, or PPTX file to process")
    prompt: Optional[str] = Field(None, description="Optional prompt to guide OCR extraction")
    prepare_text: Optional[bool] = Field(False, description="Enhance image contrast and clarity before OCR (for images only)")

class RecognizeAllArgs(BaseModel):
    prompt: Optional[str] = Field(None, description="Optional prompt to guide OCR extraction")
    prepare_text: Optional[bool] = Field(False, description="Enhance image contrast and clarity before OCR")

class PrepareTextArgs(BaseModel):
    image_path: str = Field(..., description="Path to the image file to enhance")

class PdfToImagesArgs(BaseModel):
    pdf_path: str = Field(..., description="Path to the PDF file to convert to images")

class PdfsToImagesArgs(BaseModel):
    prepare_text: Optional[bool] = Field(False, description="Enhance image contrast and clarity after conversion")

class ProcessPdfArgs(BaseModel):
    prompt: Optional[str] = Field(None, description="Optional prompt to guide OCR extraction")
    prepare_text: Optional[bool] = Field(False, description="Enhance image contrast and clarity before OCR")

class FolderPathArgs(BaseModel):
    artifacts_folder: Optional[str] = Field(None, description="Path to the artifacts folder containing images or PDFs")

class ConvertOfficeArgs(BaseModel):
    file_path: str = Field(..., description="Path to the Office document (DOCX or PPTX) to convert to PDF")


def _check_libreoffice_installed() -> bool:
    """Check if LibreOffice is installed on the system"""
    try:
        # Try to run a simple command to check if LibreOffice is available
        subprocess.run(["libreoffice", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return True
    except FileNotFoundError:
        return False


class OCRApiWrapper(BaseToolApiWrapper):
    """Wrapper for OCR tools that can use either LLM-based vision capabilities or tesseract"""
    
    llm: Any = None
    struct_llm: Any = None
    alita: Any = None
    artifacts_folder: str = ""
    tesseract_settings: Dict[str, Any] = {}
    structured_output: bool = False
    expected_fields: Dict[str, Any] = {}
    
    
    @model_validator(mode='after')
    def validate_settings(self):
        """Validate that either LLM or tesseract is properly configured"""
        # self.artifact = self.alita.artifact(self.artifacts_folder)
        if self.structured_output and len(self.expected_fields.keys()) > 0:
            stuct_model = create_pydantic_model(f"OCR_{self.artifacts_folder}_Output", self.expected_fields)
            self.struct_llm = self.llm.with_structured_output(stuct_model)
        else:
            self.struct_llm = self.llm
        
        return self
    
    def _process_images_with_llm(self, images: List[str] | str, prompt: Optional[str] = None) -> Any:
        """
        Process one or more images with the LLM.
        
        Args:
            images: Either a single image path or a list of image paths to process
            prompt: Optional prompt to guide OCR extraction
            
        Returns:
            The LLM response (either structured or plain text)
        """
        if not self.struct_llm:
            raise ToolException("LLM not configured for OCR processing")
            
        try:
            import base64
            
            # Convert single image to list for uniform processing
            if isinstance(images, str):
                images = [images]
            
            # Set default prompt if not provided
            if not prompt:
                prompt = IMAGE_OCR_PROMPT_TEMPLATE
            
            # Prepare content array with text prompt and all images
            content = [{"type": "text", "text": prompt}]
            
            # Add all images to the message
            for img_path in images:
                # Download the image
                image_data = self.alita.download_artifact(self.artifacts_folder, img_path)
                
                # Determine MIME type based on file extension
                file_extension = os.path.splitext(img_path.lower())[1]
                mime_type = "image/jpeg"  # Default
                
                # Find the correct MIME type for this extension
                for mime, extensions in MIME_TO_EXTENSION.items():
                    if file_extension in extensions:
                        mime_type = mime
                        break
                
                # Encode image to base64
                base64_image = base64.b64encode(image_data).decode('utf-8')
                
                # Add to content
                content.append({
                    "type": "image_url", 
                    "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}
                })
            
            # Create the messages array with user role
            messages = [{"role": "user", "content": content}]
            
            # Process with LLM
            logger.info(f"Processing {len(images)} image(s) with LLM")
            response = self.struct_llm.invoke(messages)
            
            if self.structured_output:
                return response.model_dump()
            return response.content
                
        except Exception as e:
            raise ToolException(f"Error processing image(s) with LLM: {e}")

    def _process_with_tesseract(self, image_path: str) -> str:
        """Process image with Tesseract OCR"""
        try:
            import pytesseract
            from PIL import Image
            
            # Get data directly without context manager
            data = self.alita.download_artifact(self.artifacts_folder, image_path)
            image = Image.open(io.BytesIO(data))
            
            # Apply any tesseract settings
            config = self.tesseract_settings.get('config', '')
            lang = self.tesseract_settings.get('lang', 'eng')
            return pytesseract.image_to_string(image, lang=lang, config=config)
        except Exception as e:
            raise ToolException(f"Error processing image with Tesseract: {e}")
    
    def recognize(self, file_path: str, prompt: Optional[str] = None, prepare_text: Optional[bool] = False) -> Dict[str, Any]:
        """
        Recognize text in a specific image, PDF, or Office document.
        Uses LLM if configured, otherwise falls back to Tesseract OCR.
        
        Args:
            file_path: Path to the image, PDF, DOCX, or PPTX file to process
            prompt: Optional prompt to guide OCR extraction
            prepare_text: Whether to enhance image contrast before OCR (for images only)
            
        Returns:
            Dictionary containing the extracted text and other metadata
        """
        # Check if the file exists
        file_exists = False
        for f in self.alita.list_artifacts(self.artifacts_folder).get('rows', []):
            if f['name'] == file_path:
                file_exists = True
                break
                
        if not file_exists:
            raise ToolException(f"File not found: {file_path} in {self.artifacts_folder}")
            
        # Determine file type based on extension
        file_extension = os.path.splitext(file_path.lower())[1]
        result = {
            "filename": file_path,
            "file_type": "unknown",
            "images": [],
            "total_pages": 0,
            "extracted_text": None
        }
        
        # Handle Office documents by converting them to PDF first
        if file_extension in OFFICE_EXTENSIONS:
            logger.info(f"Converting Office document {file_path} to PDF")
            pdf_path = self.office_to_pdf(file_path)
            if pdf_path:
                # Update file_path to the converted PDF
                file_path = pdf_path
                file_extension = ".pdf"
                # Mark the result as converted from Office
                result["original_file_type"] = "office"
            else:
                logger.error(f"Failed to convert {file_path} to PDF")
                result['error'] = "Failed to convert Office document to PDF"
                return result
                
        # Process as PDF
        if file_extension == ".pdf":
            # Process the PDF
            pdf_data = self.process_single_pdf(file_path, prepare_text)
            result['file_type'] = "pdf"
            result['total_pages'] = pdf_data['total_pages']
            result['images'] = pdf_data['page_images']
        else:        
            supported = False
            for exts in MIME_TO_EXTENSION.values():
                if file_extension in exts:
                    supported = True
                    break
            result['file_type'] = "image"
            if not supported:
                logger.error(f"Unsupported file format: {file_extension}")
                raise ToolException(f"Unsupported file format: {file_extension}")
                
            # Enhance image if requested
            img_path = file_path
            if prepare_text:
                img_path = self.prepare_text(file_path)
            result['images'].append(img_path)
            result['total_pages'] = 1
                
        if result['total_pages'] == 0:
            return result
        if self.tesseract_settings:
            text = []
            for img_path in result['images']:
                text_result = self._process_with_tesseract(img_path)
                text.append(text_result)
            extracted_text = " ".join(text)
        else:
            extracted_text = self._process_images_with_llm(result['images'], prompt)    
        
        result['extracted_text'] = extracted_text
            
        # Clean up temporary images after processing
        logger.info(f"Cleaning up temporary image files")
        for img_path in result['images']:
            try:
                self.alita.delete_artifact(self.artifacts_folder, img_path)
                if img_path.endswith("_enhanced.png"):
                    # Remove the original image if it was enhanced
                    original_path = img_path.replace("_enhanced.png", ".png")
                    self.alita.delete_artifact(self.artifacts_folder, original_path)
                logger.debug(f"Deleted temporary image: {img_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary image {img_path}: {e}")
                
        # Also clean up temporary PDF if this was converted from an Office document
        if "original_file_type" in result and result["original_file_type"] == "office":
            try:
                self.alita.delete_artifact(self.artifacts_folder, file_path)
                logger.debug(f"Deleted temporary PDF converted from Office: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary PDF {file_path}: {e}")
                
        return result
        
        

    def recognize_all(self, prompt: Optional[str] = None, prepare_text: Optional[bool] = False) -> List[Dict[str, Any]]:
        """
        Recognize text in all images and PDF files in the artifacts folder.
        Uses LLM if configured, otherwise falls back to Tesseract OCR.
        
        Args:
            prompt: Optional prompt to guide OCR extraction
            prepare_text: Whether to enhance image contrast before OCR
            
        Returns:
            List of dictionaries containing the extracted text and other metadata for each file
        """
        # Find all supported files in artifacts folder
        results = []
        supported_extensions = [ext for exts in MIME_TO_EXTENSION.values() for ext in exts]
        for f in self.alita.list_artifacts(self.artifacts_folder).get('rows', []):
            file_extension = os.path.splitext(f['name'].lower())[1]
            if file_extension == '.pdf' or file_extension in supported_extensions:
               results.append(self.recognize(f['name'], prompt, prepare_text)) 
        return results
    
    def pdfs_to_images(self, prepare_text: Optional[bool] = False) -> List[Dict[str, Any]]:
        pdf_files = []
        result = []
        for f in self.alita.list_artifacts(self.artifacts_folder).get('rows', []):
            file_extension = os.path.splitext(f['name'].lower())[1]
            if file_extension == ".pdf":
                pdf_files.append(f['name'])
        if not pdf_files:
            raise ToolException(f"No PDF files found in {self.artifacts_folder}")
        for pdf_path in pdf_files:
            result.append(self.process_single_pdf(pdf_path, prepare_text))    
        return result
    
    def process_single_pdf(self, pdf_path: str, prepare_text: Optional[bool] = False) -> Dict[str, Any]:
        images = self.pdf_to_images(pdf_path)
        if not images:
            return {"pdf_filename": pdf_path, "page_images": [], "total_pages": 0}
        if prepare_text:
            for img_path in images:
                # Prepare text for each image
                prepared_image_path = self.prepare_text(img_path)
                images[images.index(img_path)] = prepared_image_path
        return {
            "pdf_filename": pdf_path,
            "page_images": images,
            "total_pages": len(images)
        }
        
    
    def prepare_text(self, image_path: str) -> str:
        """
        Enhance image for text clarity and correct text orientation for better OCR accuracy.
        This method applies image processing techniques and rotation correction based on text orientation.
        
        Args:
            image_path: Path to the image file in the artifacts folder
            
        Returns:
            Path to the processed image with enhanced text clarity
        """
        try:
            # Download the image
            image_data = self.alita.download_artifact(self.artifacts_folder, image_path)
            
            # Load the image as PIL Image first for rotation
            pil_img = Image.open(io.BytesIO(image_data))
            
            # Create a base filename for the processed image
            base_name = os.path.splitext(image_path)[0]
            processed_filename = f"{base_name}_enhanced.png"
            
            # 1. Detect text orientation and rotate if needed
            # Convert to OpenCV format for orientation detection
            img_array = np.array(pil_img)
            angle, orientation_detected = orientation_detection(img_array)
            
            # If significant rotation detected, rotate the image using PIL
            if orientation_detected and angle != 0:
                logger.info(f"Rotating image by {angle} degrees to correct orientation")
                
                # Use PIL's rotate with expand=True to properly handle the rotation
                # expand=True ensures the entire rotated image is visible
                rotated_pil_img = pil_img.rotate(angle, expand=True, resample=Image.BICUBIC)
                
                # Replace our working image with the rotated one
                pil_img = rotated_pil_img
                
            # Save as separate image
            img_bytes = io.BytesIO()
            pil_img.save(img_bytes, format='PNG')
            
            # Upload to artifacts folder
            self.alita.create_artifact(self.artifacts_folder, processed_filename, img_bytes.getvalue())
            return processed_filename
            
        except Exception as e:
            logger.error(f"Error in prepare_text: {e}")
            raise ToolException(f"Error enhancing text: {str(e)}")

    def pdf_to_images(self, pdf_path: str) -> List[str]:
        """
        Convert PDF pages to images and store them in artifacts folder.
        Detects document boundaries, handles multi-document pages, removes white borders,
        and skips blank pages.
        
        Args:
            pdf_path: Path to the PDF file to convert to images
            
        Returns:
            List of paths to the generated image files
        """
        try:
            # Get PDF data
            pdf_data = self.alita.download_artifact(self.artifacts_folder, pdf_path)
            
            # Open PDF from memory
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            image_paths = []
            
            # Create base filename without extension
            base_filename = os.path.splitext(pdf_path)[0]
            
            # Convert each page to an image
            for page_num, page in enumerate(doc):
                # Render page to an image with higher resolution
                pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))  # Increased resolution for better text detection
                
                # Convert to PIL Image
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                # Convert to numpy array
                img_array = np.array(img)

                # Detect if page is blank by checking pixel values
                # Calculate the average brightness of the image
                gray = np.mean(img_array, axis=2)
                avg_brightness = np.mean(gray)
                
                # Count non-white pixels (pixels below threshold)
                threshold = 245  # Threshold for considering a pixel as non-white
                non_white_pixels = np.sum(gray < threshold)
                non_white_ratio = non_white_pixels / (img_array.shape[0] * img_array.shape[1])
                
                # Skip if page is mostly blank (high brightness and few non-white pixels)
                if avg_brightness > 250 and non_white_ratio < 0.01:
                    logger.info(f"Skipping blank page {page_num + 1} in {pdf_path}")
                    continue
                
                # Process the page image - classify document types
                classification = classify_document_image(img_array)
                
                # Handle based on classification result
                if classification['type'] == 'multiple_photos' and len(classification['regions']) > 1:
                    logger.info(f"Multiple document photos detected on page {page_num + 1}. "
                               f"Splitting into {len(classification['regions'])} regions.")
                    
                    # Save each document region as a separate image
                    height, width = img_array.shape[:2]
                    
                    for i, (x, y, w, h) in enumerate(classification['regions']):
                        # Extract document region with padding
                        padding = 10
                        x_min = max(0, x - padding)
                        y_min = max(0, y - padding)
                        x_max = min(width, x + w + padding)
                        y_max = min(height, y + h + padding)
                        
                        # Extract the region
                        doc_region = img_array[y_min:y_max, x_min:x_max].copy()
                        
                        # Convert to PIL Image
                        region_pil = Image.fromarray(doc_region)
                        
                        # Create filename for this region
                        region_filename = f"{base_filename}_page_{page_num + 1}_doc_{i+1}.png"
                        
                        # Save to artifacts folder
                        img_bytes = io.BytesIO()
                        region_pil.save(img_bytes, format="PNG")
                        img_bytes.seek(0)
                        self.alita.create_artifact(self.artifacts_folder, region_filename, img_bytes.read())
                        image_paths.append(region_filename)
                    
                        logger.info(f"Created document region {i+1} from page {page_num + 1}: {region_filename}")
                
                elif classification['type'] == 'photo' and classification['regions']:
                    # Single document photo on page - extract just that region
                    height, width = img_array.shape[:2]
                    x, y, w, h = classification['regions'][0]
                    
                    # Add padding
                    padding = 15
                    x_min = max(0, x - padding)
                    y_min = max(0, y - padding)
                    x_max = min(width, x + w + padding)
                    y_max = min(height, y + h + padding)
                    
                    # Extract the document region
                    doc_region = img_array[y_min:y_max, x_min:x_max].copy()
                    
                    # Convert to PIL Image
                    region_pil = Image.fromarray(doc_region)
                    
                    # Create filename
                    image_filename = f"{base_filename}_page_{page_num + 1}.png"
                    
                    # Save to artifacts folder
                    img_bytes = io.BytesIO()
                    region_pil.save(img_bytes, format="PNG")
                    img_bytes.seek(0)
                    self.alita.create_artifact(self.artifacts_folder, image_filename, img_bytes.read())
                    image_paths.append(image_filename)
                    
                    logger.info(f"Extracted document from page {page_num + 1}: {image_filename}")
                
                else:
                    # Regular scan or unclassified - save the whole page
                    image_filename = f"{base_filename}_page_{page_num + 1}.png"
                    
                    # Upload to artifacts folder
                    img_bytes = io.BytesIO()
                    img.save(img_bytes, format="PNG")
                    img_bytes.seek(0)
                    # Save the image to the artifacts folder
                    self.alita.create_artifact(self.artifacts_folder, image_filename, img_bytes.read())
                    image_paths.append(image_filename)
                    
                    logger.info(f"Saved page {page_num + 1}: {image_filename}")
                    
        except Exception as e:
            logger.error(f"Error converting PDF to images: {e}")
            raise ToolException(f"Error converting PDF to images: {str(e)}")
            
        return image_paths

    
    def office_to_pdf(self, file_path: str) -> Optional[str]:
        """
        Convert an Office document (DOCX or PPTX) to PDF using LibreOffice.
        
        Args:
            file_path: Path to the Office document
            
        Returns:
            Path to the converted PDF file or None if conversion failed
        """
        if not _check_libreoffice_installed():
            logger.error("LibreOffice is not installed. It is required for Office document conversion.")
            return None
        
        try:
            # Create a temporary directory to work in
            with tempfile.TemporaryDirectory() as temp_dir:
                # Download the Office document
                office_data = self.alita.download_artifact(self.artifacts_folder, file_path)
                
                # Save the document to the temp directory
                temp_file_path = os.path.join(temp_dir, file_path)
                os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
                
                with open(temp_file_path, "wb") as f:
                    f.write(office_data)
                
                # Convert to PDF using LibreOffice
                pdf_dir = os.path.join(temp_dir, "pdf")
                os.makedirs(pdf_dir, exist_ok=True)
                
                # Run LibreOffice headless to convert the document
                subprocess.run([
                    "libreoffice", "--headless", "--convert-to", "pdf",
                    "--outdir", pdf_dir, temp_file_path
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                
                # Get the name of the PDF file (same as original with .pdf extension)
                pdf_filename = f"{os.path.splitext(file_path)[0]}.pdf"
                pdf_path = os.path.join(pdf_dir, os.path.basename(pdf_filename))
                
                # Check if the conversion was successful
                if os.path.exists(pdf_path):
                    # Read the PDF file
                    with open(pdf_path, "rb") as f:
                        pdf_data = f.read()
                    
                    # Save the PDF to the artifacts folder
                    self.alita.create_artifact(self.artifacts_folder, pdf_filename, pdf_data)
                    
                    logger.info(f"Successfully converted {file_path} to {pdf_filename}")
                    return pdf_filename
                else:
                    logger.error(f"Failed to convert {file_path} to PDF. Output file not found.")
                    return None
        except subprocess.SubprocessError as e:
            logger.error(f"LibreOffice conversion failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Error converting Office document to PDF: {e}")
            return None
    
    def convert_office_to_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        Convert an Office document (DOCX or PPTX) to PDF and return metadata about the conversion.
        
        Args:
            file_path: Path to the Office document
            
        Returns:
            Dictionary with metadata about the conversion
        """
        # Check if the file exists
        file_exists = False
        for f in self.alita.list_artifacts(self.artifacts_folder).get('rows', []):
            if f['name'] == file_path:
                file_exists = True
                break
        
        if not file_exists:
            raise ToolException(f"File not found: {file_path} in {self.artifacts_folder}")
        
        # Check if it's a supported Office format
        file_extension = os.path.splitext(file_path.lower())[1]
        if file_extension not in OFFICE_EXTENSIONS:
            raise ToolException(f"Unsupported file format: {file_extension}. Expected .docx or .pptx")
        
        # Convert to PDF
        pdf_path = self.office_to_pdf(file_path)
        if not pdf_path:
            logger.error(f"Failed to convert {file_path} to PDF")
            return None
        
        return {
            "original_file": file_path,
            "converted_pdf": pdf_path,
            "success": True
        }
    
    def get_available_tools(self):
        """Get available OCR tools"""
        return [
            {
                "name": "recognize",
                "description": "Recognize text in a specific image, PDF, DOCX, or PPTX file",
                "args_schema": RecognizeArgs,
                "ref": self.recognize
            },
            {
                "name": "recognize_all",
                "description": "Recognize text in all supported files in the artifacts folder",
                "args_schema": RecognizeAllArgs,
                "ref": self.recognize_all
            },
            {
                "name": "convert_office_to_pdf",
                "description": "Convert an Office document (DOCX or PPTX) to PDF",
                "args_schema": ConvertOfficeArgs,
                "ref": self.convert_office_to_pdf
            },
            {
                "name": "pdf_to_images",
                "description": "Convert PDF pages to images and store in artifacts folder",
                "args_schema": PdfToImagesArgs,
                "ref": self.pdf_to_images
            },
            {
                "name": "pdfs_to_images",
                "description": "Convert all PDF files in folder to images",
                "args_schema": PdfsToImagesArgs,
                "ref": self.pdfs_to_images
            },
            {
                "name": "prepare_text",
                "description": "Enhance image contrast and clarity to improve text recognition on blurred scans",
                "args_schema": PrepareTextArgs,
                "ref": self.prepare_text
            }
        ]