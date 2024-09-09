
import re

def clean_string(s):
    # This pattern matches characters that are NOT alphanumeric, underscores, or hyphens
    pattern = '[^a-zA-Z0-9_-]'
    
    # Replace these characters with an empty string
    cleaned_string = re.sub(pattern, '', s)
    
    return cleaned_string
