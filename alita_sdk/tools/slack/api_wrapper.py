import logging
from typing import Optional
from pydantic import BaseModel, Field, SecretStr, create_model, model_validator
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from alita_sdk.tools.elitea_base import BaseToolApiWrapper


logger = logging.getLogger(__name__)

SendMessageModel = create_model(
                    "SendMessageModel",                    
                    message=(str, Field(description="The message text to send."))
                    )

ReadMessagesModel = create_model(
                    "ReadMessagesModel",                    
                    limit=(int, Field(default=10, description="The number of messages to fetch (default is 10)."))
                    )

CreateChannelModel = create_model(
                    "CreateChannelModel",                     
                    channel_name=(str, Field(description="Channel ID, user ID, or conversation ID to send the message to. (like C12345678 for public channels, D12345678 for DMs)")),
                    is_private=(bool, Field(default=False, description="Whether to make the channel private (default: False)."))
                    )

ListUsersModel = create_model(
                    "ListUsersModel"                 
                    )


class SlackApiWrapper(BaseToolApiWrapper):

    """
    Slack API wrapper for interacting with Slack channels and messages.
    """
    slack_token: Optional[SecretStr] = Field(default=None,description="Slack Bot/User OAuth Token like XOXB-*****-*****-*****-*****")
    channel_id: Optional[str] = Field(default=None, description="Channel ID, user ID, or conversation ID to send the message to. (like C12345678 for public channels, D12345678 for DMs)")

    @model_validator(mode="before")
    @classmethod
    def validate_toolkit(cls, values):
        token = values.get("slack_token")
        if not token:
            logger.error("Slack token is required for authentication.")
            raise ValueError("Slack token is required for authentication.")
        return values
    def _get_client(self):
        if not hasattr(self, "_client") or self._client is None:
            self._client = WebClient(token=self.slack_token.get_secret_value())
        return self._client
    
    def send_message(self, message: str):
        """
        Sends a message to a specified Slack channel, user, or conversation.
        """
        
        try:

            client = self._get_client()
            response = client.chat_postMessage(channel=self.channel_id, text=message)
            logger.info(f"Message sent to {self.channel_id}: {message}")
            return f"Message sent successfully to {self.channel_id}."
        
        except SlackApiError as e:
            logger.error(f"Failed to send message to {self.channel_id}: {e.response['error']}")
            return f"Received the error :  {e.response['error']}"

    def read_messages(self, limit=10):
        """
        Reads the latest messages from a Slack channel or conversation.
       
        :param limit: int: The number of messages to fetch (default is 10)
        :return: list: Returns a list of messages with metadata.
        """
        try:

            client = self._get_client()
            logger.info(f"auth test: {client.auth_test()}")
            # Fetch conversation history
            response = client.conversations_history(
                channel=self.channel_id,
                limit=limit )
            
            # Extract messages from the response
            messages = self.extract_slack_messages(response.get('messages', []))
            
            return messages
            
        except SlackApiError as e:
            # Handle errors from the Slack API
            logger.error(f"Failed to read message from {self.channel_id}: {e.response['error']}")
            return f"Received the error :  {e.response['error']}"
        
    def create_slack_channel(self,  channel_name: str, is_private=False):
        """
        Creates a new Slack channel.

        :param channel_name: str: Desired name for the channel (e.g., "my-new-channel").
        :param is_private: bool: Whether to make the channel private (default: False).
        :return: dict: Slack API response or error message.
        """

        try:
            client = self._get_client()
            response = client.conversations_create(
                name=channel_name,
                is_private=is_private
            )
            channel_id = response["channel"]["id"]
            print(f"Channel '{channel_name}' created successfully! Channel ID: {channel_id}")
            return {"success": True, "channel_id": channel_id}
        except SlackApiError as e:
            error_message = e.response.get("error", "unknown_error")
            print(f"Failed to create channel '{channel_name}': {error_message}")
            return {"success": False, "error": error_message}
    
    def list_users(self):
        """
        Lists all users in the Slack workspace.

        :return: list: List of users with their IDs and names.
        """
        
        
        try:
            client = self._get_client()
            print(client.auth_test())
            response = client.users_list()
            users = response["members"]
            return [{"id": user["id"], "name": user["name"]} for user in users if not user["is_bot"]]
        
        except SlackApiError as e:
            logger.error(f"Failed to list users: {e.response['error']}")
            return f"Received the error :  {e.response['error']}"
    
    def extract_slack_messages(self, data):
        extracted_info = []

        for item in data:
            # Extract 'user' and 'text'
            user = item.get("user", "Undefined User")
            message = item.get("text", "No message")

            # Extract 'app name'
            app_name = item.get("bot_profile", {}).get("name", "No App Name")
            
            # Append to result
            extracted_info.append({"user": user, "message": message, "app_name": app_name})
        
        return extracted_info
    
    
    def get_available_tools(self):
        return [
            {
                "name": "send_message",
                "description": self.send_message.__doc__ or "Send a message to a Slack channel, user, or conversation.",
                "args_schema": SendMessageModel,
                "ref": self.send_message
                
            },
            {
                "name": "read_messages",
                "description": self.read_messages.__doc__ or "Send a message to a Slack channel, user, or conversation.",
                "args_schema": ReadMessagesModel,
                "ref": self.read_messages
            },
            {
                "name": "create_channel",
                "description": self.create_slack_channel.__doc__ or "Send a message to a Slack channel, user, or conversation.",
                "args_schema": CreateChannelModel,
                "ref": self.create_slack_channel             
            },
            {
                "name": "list_users",
                "description": self.list_users.__doc__ or "List all users in the Slack workspace.",
                "args_schema": ListUsersModel,
                "ref": self.list_users
            }
            
        ]