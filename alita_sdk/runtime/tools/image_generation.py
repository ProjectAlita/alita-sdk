"""
Image generation tool for Alita SDK.
"""
import base64
import json
import logging
import uuid
from datetime import datetime
from typing import Optional, Type, Any, List, Literal
from langchain_core.callbacks import dispatch_custom_event
from langchain_core.tools import BaseTool, BaseToolkit, ToolException
from pydantic import BaseModel, Field, create_model, ConfigDict

logger = logging.getLogger(__name__)

name = "image_generation"


def get_tools(tools_list: list, alita_client=None, llm=None,
              memory_store=None):
    """
    Get image generation tools for the provided tool configurations.

    Args:
        tools_list: List of tool configurations
        alita_client: Alita client instance (required for image generation)
        llm: LLM client instance (unused for image generation)
        memory_store: Optional memory store instance (unused)

    Returns:
        List of image generation tools
    """
    all_tools = []

    for tool in tools_list:
        if (tool.get('type') == 'image_generation' or
                tool.get('toolkit_name') == 'image_generation'):
            try:
                if not alita_client:
                    logger.error("Alita client is required for image "
                                 "generation tools")
                    continue

                toolkit_instance = ImageGenerationToolkit.get_toolkit(
                    client=alita_client,
                    toolkit_name=tool.get('toolkit_name', '')
                )
                all_tools.extend(toolkit_instance.get_tools())
            except Exception as e:
                logger.error(f"Error in image generation toolkit "
                             f"get_tools: {e}")
                logger.error(f"Tool config: {tool}")
                raise

    return all_tools


class ImageGenerationInput(BaseModel):
    """Input schema for image generation tool."""
    prompt: str = Field(
        description="Text prompt describing the image to generate"
    )
    filename: str = Field(
        default="image",
        description="Base filename for the generated image(s) without extension (e.g., 'sunset', 'logo'). "
                    "For multiple images, numbers will be appended (image_1.png, image_2.png)."
    )
    n: int = Field(
        default=1, description="Number of images to generate (1-10)",
        ge=1, le=10
    )
    size: str = Field(
        default="auto",
        description="Size of the generated image (e.g., '1024x1024')"
    )
    quality: str = Field(
        default="auto",
        description="Quality of the generated image ('low', 'medium', 'high')"
    )
    style: Optional[str] = Field(
        default=None, description="Style of the generated image (optional)"
    )


class ImageGenerationTool(BaseTool):
    """Tool for generating images using the Alita client."""
    
    name: str = "generate_image"
    description: str = (
        "Generate images from text prompts using AI models. "
        "Images are automatically saved to the conversation bucket with the specified filename. "
        "Returns a JSON array with bucket_name and image_name for each generated image. "
        "These images persist across conversation turns and can be referenced by name in future prompts."
    )
    args_schema: Type[BaseModel] = ImageGenerationInput
    alita_client: Any = None
    
    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self.alita_client = client
    
    def _run(self, prompt: str, filename: str = "image", n: int = 1, size: str = "auto",
             quality: str = "auto", style: Optional[str] = None) -> str:
        """Generate an image based on the provided parameters."""
        try:
            logger.debug(f"Generating image with prompt: {prompt[:50]}...")
            
            result = self.alita_client.generate_image(
                prompt=prompt,
                n=n,
                size=size,
                quality=quality,
                style=style
            )
            
            # Get image generation bucket and artifact interface
            if not hasattr(self.alita_client, 'image_generation_bucket'):
                return json.dumps({
                    "status": "error",
                    "message": "Image generation bucket not configured in client"
                })

            bucket_name = self.alita_client.image_generation_bucket
            artifact = self.alita_client.artifact(bucket_name)

            # Save images to bucket instead of cache
            if 'data' in result:
                images = result['data']

                # Process all images and save to bucket
                images_list = []
                for idx, image_data in enumerate(images, 1):
                    if not image_data.get('b64_json'):
                        continue

                    # Generate unique filename with timestamp to prevent conflicts between users
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]  # millisecond precision
                    image_name = f"{filename}_{timestamp}.png"
                    binary_data = base64.b64decode(image_data['b64_json'])

                    create_response = artifact.create(image_name, binary_data, bucket_name, prompt=prompt)
                    logger.debug(f"Saved generated image to bucket '{bucket_name}' as '{image_name}'")

                    response_data = json.loads(create_response)
                    if "error" in response_data:
                        raise ToolException(f"Failed to create artifact for '{image_name}': {response_data['error']}")

                    artifact_id = response_data['artifact_id']
                    logger.debug(f"Artifact created with ID: {artifact_id}")

                    dispatch_custom_event("file_modified", {
                        "message": f"Image '{image_name}' generated and saved successfully",
                        "artifact_id": artifact_id,
                        "filename": image_name,
                        "tool_name": "generate_image",
                        "toolkit": "image_generation",
                        "operation_type": "create",
                        "meta": {
                            "bucket": bucket_name,
                            "image_number": idx,
                            "prompt": prompt,
                            "source": "generated"
                        }
                    })

                    images_list.append({
                        "artifact_id": artifact_id,
                        "image_name": image_name,
                        "image_number": idx,
                        "image_type": "png",
                        "bucket": bucket_name
                    })

                if not images_list:
                    return json.dumps({
                        "status": "error",
                        "message": "No base64 image data found"
                    })

                return json.dumps({
                    "status": "success",
                    "prompt": prompt,
                    "total_images": len(images_list),
                    "images": images_list
                })

            # Fallback to error response if no images in result
            return json.dumps({
                "status": "error",
                "message": f"Image generation completed but no images returned: {result}"
            })

        except Exception as e:
            logger.error(f"Error generating image: {e}")
            return json.dumps({
                "status": "error",
                "message": f"Error generating image: {str(e)}"
            })
    
    async def _arun(self, prompt: str, filename: str = "image", n: int = 1, size: str = "256x256",
                    quality: str = "auto",
                    style: Optional[str] = None) -> list:
        """Async version - for now just calls the sync version."""
        return self._run(prompt, filename, n, size, quality, style)


def create_image_generation_tool(client):
    """Create an image generation tool with the provided Alita client."""
    return ImageGenerationTool(client=client)


class ImageGenerationToolkit(BaseToolkit):
    """Toolkit for image generation tools."""
    tools: List[BaseTool] = []

    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        """Get the configuration schema for the image generation toolkit."""
        # Create sample tool to get schema
        sample_tool = ImageGenerationTool(client=None)
        selected_tools = {sample_tool.name: sample_tool.args_schema.schema()}

        return create_model(
            'image_generation',
            selected_tools=(
                List[Literal[tuple(selected_tools)]],
                Field(
                    default=[],
                    json_schema_extra={'args_schemas': selected_tools}
                )
            ),
            __config__=ConfigDict(json_schema_extra={
                'metadata': {
                    "label": "Image Generation",
                    "icon_url": "image_generation.svg",
                    "hidden": True,
                    "categories": ["internal_tool"],
                    "extra_categories": ["image generation"],
                }
            })
        )

    @classmethod
    def get_toolkit(cls, client=None, **kwargs):
        """
        Get toolkit with image generation tools.

        Args:
            client: Alita client instance (required)
            **kwargs: Additional arguments
        """
        if not client:
            raise ValueError("Alita client is required for image generation")
            
        tools = [ImageGenerationTool(client=client)]
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
