"""
Image generation tool for Alita SDK.
"""
import logging
from typing import Optional, Type, Any, List, Literal
from langchain_core.tools import BaseTool, BaseToolkit
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
    description: str = "Generate images from text prompts using AI models"
    args_schema: Type[BaseModel] = ImageGenerationInput
    alita_client: Any = None
    
    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self.alita_client = client
    
    def _run(self, prompt: str, n: int = 1, size: str = "auto",
             quality: str = "auto", style: Optional[str] = None) -> list:
        """Generate an image based on the provided parameters."""
        try:
            logger.info(f"Generating image with prompt: {prompt[:50]}...")
            
            result = self.alita_client.generate_image(
                prompt=prompt,
                n=n,
                size=size,
                quality=quality,
                style=style
            )
            
            # Return multimodal content format for LLM consumption
            if 'data' in result:
                images = result['data']
                content_chunks = []
                
                # Add a text description of what was generated
                if len(images) == 1:
                    content_chunks.append({
                        "type": "text",
                        "text": f"Generated image for prompt: '{prompt}'"
                    })
                else:
                    content_chunks.append({
                        "type": "text",
                        "text": f"Generated {len(images)} images for "
                                f"prompt: '{prompt}'"
                    })
                
                # Add image content for each generated image
                for image_data in images:
                    if image_data.get('url'):
                        content_chunks.append({
                            "type": "image_url",
                            "image_url": {
                                "url": image_data['url']
                            }
                        })
                    elif image_data.get('b64_json'):
                        content_chunks.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,"
                                       f"{image_data['b64_json']}"
                            }
                        })
                
                return content_chunks
            
            # Fallback to text response if no images in result
            return [{
                "type": "text",
                "text": f"Image generation completed but no images "
                        f"returned: {result}"
            }]
            
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            return [{
                "type": "text",
                "text": f"Error generating image: {str(e)}"
            }]
    
    async def _arun(self, prompt: str, n: int = 1, size: str = "256x256",
                    quality: str = "auto",
                    style: Optional[str] = None) -> list:
        """Async version - for now just calls the sync version."""
        return self._run(prompt, n, size, quality, style)


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
