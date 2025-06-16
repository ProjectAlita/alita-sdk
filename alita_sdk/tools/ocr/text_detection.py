import logging
import numpy as np
import cv2
from typing import Any, Dict
import pytesseract

logger = logging.getLogger(__name__)

def orientation_detection(image_array: np.ndarray, segment_id=None, page_num=None) -> tuple:
    """
    Enhanced method for text orientation detection using computer vision and OCR techniques.
    
    Args:
        image_array: Numpy array of the image
        segment_id: Optional segment identifier for logging
        page_num: Optional page number for logging
        
    Returns:
        tuple: (angle, success_flag)
    """
    try:
        segment_info = f"segment {segment_id} of page {page_num}" if segment_id is not None else "image"
        
        # Convert to grayscale if needed
        if len(image_array.shape) == 3:
            gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = image_array
        
        # Save original dimensions
        height, width = gray.shape
        
        # First check: If image has a lot of text, try OCR at different orientations to determine the best one
        if height * width < 4000000:  # Only for reasonably-sized images (avoid processing large images)
            try:
                # Check if image is text-dense based on edge density
                edges = cv2.Canny(gray, 50, 150)
                edge_density = np.count_nonzero(edges) / (height * width)
                
                # If edge density suggests text-dense image, use OCR orientation confidence
                if edge_density > 0.05:  # Image likely contains substantial text
                    # Test OCR confidence at different orientations
                    orientations = [0, 90, 180, 270]
                    best_orientation = 0
                    best_confidence = 0
                    best_text_length = 0
                    
                    for angle in orientations:
                        # Rotate image to test orientation
                        if angle == 0:
                            rotated = gray
                        else:
                            M = cv2.getRotationMatrix2D((width/2, height/2), angle, 1)
                            rotated = cv2.warpAffine(gray, M, (width, height), borderMode=cv2.BORDER_REPLICATE)
                        
                        # Use pytesseract with OSD (orientation and script detection)
                        try:
                            # Try to get OSD info
                            osd_info = pytesseract.image_to_osd(rotated, output_type=pytesseract.Output.DICT)
                            confidence = float(osd_info.get('orientation_conf', 0))
                            
                            # Also get text to check readability
                            text = pytesseract.image_to_string(rotated)
                            text_length = len(text.strip())
                            
                            logger.debug(f"OCR at {angle}°: conf={confidence}, text_len={text_length}")
                            
                            # Combine confidence and text length for scoring
                            # Weight text length more heavily for text-dense documents
                            combined_score = confidence + (text_length / 100)
                            
                            if combined_score > best_confidence:
                                best_confidence = combined_score
                                best_orientation = angle
                                best_text_length = text_length
                        except Exception as e:
                            logger.debug(f"OCR orientation check failed at {angle}°: {str(e)}")
                    
                    # If we found text with high enough confidence
                    if best_text_length > 20 and best_confidence > 1:
                        logger.info(f"Text orientation detected via OCR for {segment_info}: {best_orientation}° (confidence={best_confidence:.2f})")
                        return best_orientation, True
                    
                    logger.debug(f"OCR orientation check inconclusive: best={best_orientation}°, conf={best_confidence:.2f}, text_len={best_text_length}")
            except Exception as e:
                logger.debug(f"OCR orientation check skipped: {str(e)}")
        
        # Continue with enhanced computer vision approaches if OCR was not conclusive
        
        # Apply adaptive thresholding for better text detection
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                     cv2.THRESH_BINARY_INV, 11, 2)
        
        # Dilate to connect nearby text
        kernel = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(binary, kernel, iterations=1)
        
        # Find contours in the processed image
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter out very small contours that are likely noise
        min_contour_area = (image_array.shape[0] * image_array.shape[1]) * 0.001  # 0.1% of image
        significant_contours = [cnt for cnt in contours if cv2.contourArea(cnt) > min_contour_area]
        
        # If we have significant contours, analyze them
        if not significant_contours:
            logger.info(f"No significant contours found for orientation detection in {segment_info}")
            return 0, False
            
        # Method 1: Use minimum area rectangle and line detection approach
        all_points = []
        for cnt in significant_contours:
            all_points.extend([point[0] for point in cnt])
        
        if not all_points:
            logger.info(f"No valid points found for orientation detection in {segment_info}")
            return 0, False
            
        all_points = np.array(all_points)
        rect = cv2.minAreaRect(all_points)
        angle = rect[2]
        
        # Method 2: Detect horizontal text lines to better distinguish between 0/180 rotations
        # This helps determine if we need rotation or flipping
        horizontal_projection = np.sum(dilated, axis=1)
        line_count = 0
        in_line = False
        line_heights = []
        line_positions = []  # Track line positions for analyzing text structure
        current_line_start = 0
        
        # Detect text lines by analyzing horizontal projections
        for i, projection in enumerate(horizontal_projection):
            if projection > 0 and not in_line:
                in_line = True
                current_line_start = i
            elif projection == 0 and in_line:
                in_line = False
                line_height = i - current_line_start
                if line_height > 5:  # Minimum line height to count
                    line_count += 1
                    line_heights.append(line_height)
                    line_positions.append(current_line_start + line_height/2)  # Store middle of line
        
        # Compute line spacing statistics to determine text structure
        line_spacing = []
        if len(line_positions) > 1:
            for i in range(1, len(line_positions)):
                line_spacing.append(line_positions[i] - line_positions[i-1])
        
        # Analyze text structure for 0 vs 180 degree distinction
        # Text usually flows with smaller spacing at top and larger at bottom
        # (paragraph structures, headings typically at top)
        text_structure_score = 0
        if len(line_spacing) >= 3:
            # Calculate if spacing tends to increase (normal orientation) 
            # or decrease (180° rotation) going down the page
            increasing_gaps = sum(1 for i in range(1, len(line_spacing)) if line_spacing[i] > line_spacing[i-1])
            decreasing_gaps = sum(1 for i in range(1, len(line_spacing)) if line_spacing[i] < line_spacing[i-1])
            
            text_structure_score = (increasing_gaps - decreasing_gaps) / len(line_spacing)
            # Positive score suggests normal orientation, negative suggests 180° rotation
        
        if line_heights:
            avg_line_height = sum(line_heights) / len(line_heights)
            line_spacing_score = line_count * avg_line_height / len(horizontal_projection)
        else:
            line_spacing_score = 0
            
        # Method 3: Compare horizontal vs vertical projections to determine orientation
        vertical_projection = np.sum(dilated, axis=0)
        horizontal_variance = np.var(horizontal_projection)
        vertical_variance = np.var(vertical_projection)
        
        # Higher variance typically indicates text direction
        projection_ratio = horizontal_variance / vertical_variance if vertical_variance > 0 else float('inf')
        
        # Check image aspect ratio
        is_portrait = height > width
        
        # Analyze aspect ratios of individual contours
        contour_orientations = []
        for cnt in significant_contours:
            x, y, w, h = cv2.boundingRect(cnt)
            # Most text elements are wider than tall when properly oriented
            contour_orientations.append(w > h)
        
        # Calculate percentage of "wide" elements
        wide_percentage = sum(contour_orientations) / len(contour_orientations) if contour_orientations else 0.5
        
        # Enhanced: Count letters that have descenders (like 'g', 'j', 'p', 'q', 'y')
        # This can help distinguish between 0 and 180 degrees
        descender_evidence = 0
        ascender_evidence = 0
        
        # Use contour analysis for character shape detection
        for cnt in significant_contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if 0.5 < w / h < 2.0:  # Likely a character
                roi = dilated[y:y+h, x:x+w]
                # Check bottom half vs top half density for descenders/ascenders
                top_half = roi[:h//2, :]
                bottom_half = roi[h//2:, :]
                
                top_density = np.count_nonzero(top_half) / max(1, top_half.size)
                bottom_density = np.count_nonzero(bottom_half) / max(1, bottom_half.size)
                
                if bottom_density > top_density * 1.5:
                    descender_evidence += 1
                elif top_density > bottom_density * 1.5:
                    ascender_evidence += 1
        
        # Compute descender-ascender ratio to help determine orientation
        character_ratio = descender_evidence / max(1, ascender_evidence) if ascender_evidence > 0 else 0
        
        logger.info(f"Orientation metrics for {segment_info}: angle={angle}, "
                   f"projection_ratio={projection_ratio:.2f}, wide_percentage={wide_percentage:.2f}, "
                   f"text_structure_score={text_structure_score:.2f}, char_ratio={character_ratio:.2f}")
        
        # Determine the correct rotation angle based on multiple factors
        final_angle = 0
        
        # Step 1: Check for 90/270 degree rotations based on projections and contour analysis
        if projection_ratio < 0.8 and wide_percentage < 0.4:
            # Text is likely rotated 90 or 270 degrees
            if is_portrait:
                # For portrait images, prefer 90 degree rotation
                final_angle = 90
            else:
                # For landscape images that need rotation, likely 270 degrees
                final_angle = 270
        elif projection_ratio > 1.2 and wide_percentage > 0.6:
            # Text is likely correctly oriented or flipped 180
            # Enhanced decision logic for 0 vs 180 degrees
            if text_structure_score < -0.3:
                # Strong evidence of reversed text structure, suggest 180 rotation
                final_angle = 180
            elif character_ratio > 1.5:
                # More descenders than ascenders suggests 180 rotation
                final_angle = 180
            elif text_structure_score > 0.3 or character_ratio < 0.7:
                # Normal text structure or more ascenders - likely correct orientation
                final_angle = 0
            elif abs(angle) > 45:
                # Fall back to rectangle angle for ambiguous cases
                final_angle = angle
            else:
                # Default to no rotation when unsure for text-dense documents
                final_angle = 0
        else:
            # Use the minimum area rectangle angle with adjustments
            if abs(angle) < 45:
                # Minor rotation
                final_angle = angle
            elif angle < -45:
                # Common case where we need 90 degree rotation
                final_angle = 90 + angle
            else:
                # Check if we need 180 or 270 degree rotation
                if projection_ratio < 1.0:
                    final_angle = 270
                else:
                    # For text-dense documents, be more conservative about 180° rotation
                    if text_structure_score < -0.3 or character_ratio > 1.5:
                        final_angle = 180
                    else:
                        final_angle = 0
        
        # Round angle to nearest 90 degrees if it's close
        if abs(final_angle - 90) < 10:
            final_angle = 90
        elif abs(final_angle - 180) < 10:
            final_angle = 180
        elif abs(final_angle - 270) < 10:
            final_angle = 270
        elif abs(final_angle) < 10:
            final_angle = 0
            
        # Final safety check: For text-dense documents (many lines), be more conservative
        if line_count > 10 and final_angle == 180 and text_structure_score > -0.2:
            # If we have many text lines but weak evidence for 180° rotation, default to 0
            logger.info(f"Reversing 180° rotation decision for text-dense document with weak evidence")
            final_angle = 0
        
        logger.info(f"Final orientation detection for {segment_info}: angle={final_angle}")
        
        return final_angle, True
        
    except Exception as e:
        logger.warning(f"Fallback orientation detection failed: {str(e)}")
        return 0, False

def classify_document_image(image: np.ndarray) -> Dict[str, Any]:
    """
    Classify if an image contains a full document scan or photos of documents.
    If multiple documents are detected, it returns their regions.
    
    Args:
        image: Input image as numpy array
        
    Returns:
        Dictionary with classification result and document regions:
        {
            'type': 'scan' | 'photo' | 'multiple_photos',
            'confidence': float,
            'regions': List of (x, y, w, h) for detected document regions
        }
    """
    height, width = image.shape[:2]
    result = {
        'type': 'unknown',
        'confidence': 0.0,
        'regions': []
    }
    
    # Convert to grayscale if not already
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Check if image is likely a full document scan
    # 1. Check edges of the image - scans typically have uniform borders
    border_width = int(min(width, height) * 0.05)  # 5% of min dimension
    
    top_border = gray[:border_width, :]
    bottom_border = gray[-border_width:, :]
    left_border = gray[:, :border_width]
    right_border = gray[:, -border_width:]
    
    borders = [top_border, bottom_border, left_border, right_border]
    border_stds = [np.std(border) for border in borders]
    border_means = [np.mean(border) for border in borders]
    
    # If borders are mostly uniform (low std dev) and light colored (high mean), 
    # it's likely a full document scan
    uniform_borders = all(std < 25 for std in border_stds)  # Slightly more lenient
    light_borders = all(mean > 180 for mean in border_means)  # More lenient threshold
    
    # Enhanced preprocessing to better isolate document regions
    # Apply multiple techniques and combine their results
    document_regions = []
    
    # Method 1: Adaptive threshold with contour detection
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY_INV, 11, 2
    )
    
    # Dilate to connect nearby edges
    kernel = np.ones((5, 5), np.uint8)
    dilated = cv2.dilate(thresh, kernel, iterations=1)
    
    # Find contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter contours by size and shape
    min_doc_area = width * height * 0.03  # Lower threshold to catch smaller regions
    max_doc_area = width * height * 0.95  # At most 95% of image
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_doc_area or area > max_doc_area:
            continue
            
        # Approximate contour shape
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.04 * peri, True)  # More lenient approximation
        
        # Accept more flexible shapes, not just quads
        if 4 <= len(approx) <= 10:
            x, y, w, h = cv2.boundingRect(contour)
            
            # More flexible aspect ratio constraints
            aspect_ratio = w / h
            if 0.4 <= aspect_ratio <= 2.5:  # More permissive aspect ratio
                document_regions.append((x, y, w, h))
    
    # Method 2: Try using edge detection for finding document regions
    if len(document_regions) < 2:  # If first method didn't find multiple regions
        edges = cv2.Canny(gray, 50, 150)
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
        
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_doc_area or area > max_doc_area:
                continue
                
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.04 * peri, True)
            
            if len(approx) >= 4:
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h
                if 0.4 <= aspect_ratio <= 2.5:
                    # Check if this region is significantly different from ones we've already found
                    new_region = True
                    for ex_x, ex_y, ex_w, ex_h in document_regions:
                        # Calculate overlap
                        overlap_x = max(0, min(ex_x + ex_w, x + w) - max(ex_x, x))
                        overlap_y = max(0, min(ex_y + ex_h, y + h) - max(ex_y, y))
                        overlap_area = overlap_x * overlap_y
                        smaller_area = min(ex_w * ex_h, w * h)
                        
                        if overlap_area > 0.7 * smaller_area:  # If >70% overlap, not a new region
                            new_region = False
                            break
                    
                    if new_region:
                        document_regions.append((x, y, w, h))
    
    # Method 3: Content-based segmentation for highly contrasting regions
    if len(document_regions) < 2:
        # Convert to LAB color space for better color difference perception
        if len(image.shape) == 3:
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            
            # K-means clustering to segment by color
            pixel_data = lab.reshape((-1, 3))
            pixel_data = np.float32(pixel_data)
            
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
            k = 4  # Use more clusters to better separate documents
            _, labels, centers = cv2.kmeans(pixel_data, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
            
            # Create masks for each cluster
            for i in range(k):
                mask = np.zeros(gray.shape, dtype=np.uint8)
                mask[labels.reshape(height, width) == i] = 255
                
                # Find contours in this color segment
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area < min_doc_area or area > max_doc_area:
                        continue
                    
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = w / h
                    if 0.4 <= aspect_ratio <= 2.5:
                        new_region = True
                        for ex_x, ex_y, ex_w, ex_h in document_regions:
                            overlap_x = max(0, min(ex_x + ex_w, x + w) - max(ex_x, x))
                            overlap_y = max(0, min(ex_y + ex_h, y + h) - max(ex_y, y))
                            overlap_area = overlap_x * overlap_y
                            smaller_area = min(ex_w * ex_h, w * h)
                            
                            if overlap_area > 0.7 * smaller_area:  # If >70% overlap, not a new region
                                new_region = False
                                break
                        
                        if new_region:
                            document_regions.append((x, y, w, h))
    
    # Filter out regions that are too similar or contained within others
    final_regions = []
    if document_regions:
        # Sort regions by area (largest first)
        document_regions.sort(key=lambda r: r[2] * r[3], reverse=True)
        
        # Keep the largest region and any regions that don't significantly overlap with previous ones
        final_regions.append(document_regions[0])
        
        for region in document_regions[1:]:
            x, y, w, h = region
            is_unique = True
            
            for ex_x, ex_y, ex_w, ex_h in final_regions:
                # Check if region is mostly contained within an existing region
                overlap_x = max(0, min(ex_x + ex_w, x + w) - max(ex_x, x))
                overlap_y = max(0, min(ex_y + ex_h, y + h) - max(ex_y, y))
                overlap_area = overlap_x * overlap_y
                current_area = w * h
                
                if overlap_area > 0.7 * current_area:
                    is_unique = False
                    break
            
            if is_unique:
                final_regions.append(region)
    
    # Improved decision logic
    if uniform_borders and light_borders and len(final_regions) <= 1:
        # Likely a full document scan
        result['type'] = 'scan'
        result['confidence'] = 0.8
        # Still record the region if we found one
        if final_regions:
            result['regions'] = final_regions
    elif len(final_regions) == 1:
        # Single document photo
        result['type'] = 'photo'
        result['confidence'] = 0.7
        result['regions'] = final_regions
    elif len(final_regions) > 1:
        # Multiple document photos
        result['type'] = 'multiple_photos'
        result['confidence'] = 0.6
        result['regions'] = final_regions
    else:
        # Fallback - if we couldn't detect clear regions but the image has content,
        # treat it as a scan
        non_white_pixels = np.count_nonzero(gray < 200)
        non_white_ratio = non_white_pixels / (height * width)
        
        if non_white_ratio > 0.05:  # If the image has some content
            result['type'] = 'scan'
            result['confidence'] = 0.4
    
    logger.info(f"Document classification: {result['type']}, found {len(result['regions'])} regions")
    return result
