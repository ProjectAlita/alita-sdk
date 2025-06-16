import hashlib


class ImageDescriptionCache:
    """Cache for image descriptions to avoid processing the same image multiple times"""

    def __init__(self, max_size=50):
        self.cache = {}  # content_hash -> description
        self.max_size = max_size

    def get(self, image_data, image_name=""):
        """Get a cached description if available"""
        if not image_data:
            return None

        # Generate a content hash for the image
        content_hash = hashlib.md5(image_data).hexdigest()

        # Create a composite key that includes the image name when available
        cache_key = f"{content_hash}_{image_name}" if image_name else content_hash

        return self.cache.get(cache_key)

    def set(self, image_data, description, image_name=""):
        """Cache a description for an image"""
        if not image_data or not description:
            return

        # Generate content hash
        content_hash = hashlib.md5(image_data).hexdigest()

        # Create a composite key that includes the image name when available
        cache_key = f"{content_hash}_{image_name}" if image_name else content_hash

        # Only cache if we have room or if evicting one entry is enough
        if len(self.cache) < self.max_size:
            self.cache[cache_key] = description
        else:
            # Simple LRU: just remove a random entry if we're at capacity
            if len(self.cache) >= self.max_size:
                # Remove one entry to make room
                self.cache.pop(next(iter(self.cache)))
                self.cache[cache_key] = description