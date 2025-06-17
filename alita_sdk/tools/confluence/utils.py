import base64
import io

from PIL.Image import Image

def bytes_to_base64(bt: bytes) -> str:
    return base64.b64encode(bt).decode('utf-8')

def path_to_base64(path) -> str:
    with open(path, 'rb') as binary_file:
        return base64.b64encode(binary_file.read()).decode('utf-8')

def image_to_byte_array(image: Image) -> bytes:
    raw_bytes = io.BytesIO()
    image.save(raw_bytes, format='PNG')
    return raw_bytes.getvalue()
