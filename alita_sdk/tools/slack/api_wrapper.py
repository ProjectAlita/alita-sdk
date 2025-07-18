import logging
from typing import Optional
from pydantic import BaseModel, Field, SecretStr, create_model, model_validator
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from alita_sdk.tools.elitea_base import BaseToolApiWrapper


logger = logging.getLogger(__name__)

SendMessageModel = create_model(
                    "SendMessageModel",
                    channel_id=(Optional[str], Field(default=None,description="Channel ID, user ID, or conversation ID to send the message to. (like C12345678 for public channels, D12345678 for DMs)")),                   
                    message=(str, Field(description="The message text to send."))
                    )

ReadMessagesModel = create_model(
                    "ReadMessagesModel",
                    channel_id=(Optional[str], Field(default=None,description="Channel ID, user ID, or conversation ID to read messages from. (like C12345678 for public channels, D12345678 for DMs)")),                    
                    limit=(int, Field(default=10, description="The number of messages to fetch (default is 10)."))
                    )

CreateChannelModel = create_model(
                    "CreateChannelModel",                     
                    channel_name=(str, Field(description="Channel ID, user ID, or conversation ID to send the message to. (like C12345678 for public channels, D12345678 for DMs)")),
                    is_private=(bool, Field(default=False, description="Whether to make the channel private (default: False)."))
                    )

ListChannelUsersModel = create_model(
                    "ListChannelUsersModel",
                    channel_id=(Optional[str], Field(default=None,description="Channel ID, user ID, or conversation ID to read messages from. (like C12345678 for public channels, D12345678 for DMs)"))                 
                    )

ListWorkspaceUsersModel = create_model(
                    "ListWorkspaceUsersModel"                 
                    )

ListWorkspaceConversationsModel = create_model(
                    "ListWorkspaceConversationsModel"                 
                    )

InviteToConversationModel = create_model(
                    "InviteToConversationModel" ,
                    channel_id=(Optional[str], Field(default=None,description="Conversation ID of the channel.")),
                    user_ids=(list[str], Field(description="List of user IDs to invite."))                  
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
    
    def send_message(self, message: str, channel_id: Optional[str] = None):
        """
        Sends a message to a specified Slack channel, user, or conversation.
        Uses the provided channel_id if given, otherwise falls back to the instance's channel_id.
        """
        
        try:

            client = self._get_client()
            
            # Use the passed channel_id if provided, else use self.channel_id
            channel = channel_id if channel_id else self.channel_id
            response = client.chat_postMessage(channel=channel, text=message)
            logger.info(f"Message sent to {channel}: {message}")
            return f"Message sent successfully to {channel}."
        
        except SlackApiError as e:
            logger.error(f"Failed to send message to {channel}: {e.response['error']}")
            return f"Received the error :  {e.response['error']}"

    def read_messages(self, limit=10, channel_id: Optional[str] = None):
        """
        Reads the latest messages from a Slack channel or conversation.
       
        :param limit: int: The number of messages to fetch (default is 10)
        :return: list: Returns a list of messages with metadata.
        """
        try:

            client = self._get_client()
            logger.info(f"auth test: {client.auth_test()}")
            # Use the passed channel_id if provided, else use self.channel_id
            channel = channel_id if channel_id else self.channel_id
            # Fetch conversation history
            response = client.conversations_history(
                channel=channel,
                limit=limit )
            
            # Extract messages from the response
            messages = self.extract_slack_messages(response.get('messages', []))
            
            return messages
            
        except SlackApiError as e:
            # Handle errors from the Slack API
            logger.error(f"Failed to read message from {channel}: {e.response['error']}")
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
    


    def list_channel_users(self, channel_id: Optional[str] = None):
        """
        Lists all users in the specified Slack channel.

        :param channel_id: Optional[str]: The channel ID to list users from. If not provided, uses self.channel_id.
        :return: list: List of user dictionaries with their IDs and names.
        """
        try:
            client = self._get_client()
            # Use the passed channel_id if provided, else use self.channel_id
            channel = channel_id if channel_id else self.channel_id
            logger.info
            if not channel:
                logger.error("No channel_id provided to list_channel_users.")
                return "Error: channel_id must be provided either as an argument or set on the instance."

            # Get user IDs in the channel
            members_response = client.conversations_members(channel=channel)
            user_ids = members_response.get("members", [])

            # Fetch user info for each user ID
            users = []
            for user_id in user_ids:
                user_info = client.users_info(user=user_id)
                user = user_info.get("user", {})
                users.append({"id": user.get("id"), "name": user.get("name")})

            return users

        except SlackApiError as e:
            logger.error(f"Failed to list users in channel {channel}: {e.response['error']}")
            return f"Received the error :  {e.response['error']}"

    def list_workspace_users(self):
        """
        Fetches and returns a list of all users in the Slack workspace with selected user details.

        :return: list: List of user dictionaries containing id, name, is_bot, email, and team.
        """
        try:
            client = self._get_client()
            response = client.users_list()  # Fetch users
            members = self.extract_required_user_fields(response.get('members', []))
            print(f"Found {len(members)} users.")
            return members  # Return the list of users
        except SlackApiError as e:
            print(f"Error fetching users: {e.response['error']}")
            return []
    
    def list_workspace_conversations(self):
        """
        Retrieves and returns a list of all conversations (channels, groups, and direct messages) in the Slack workspace.

        :return: list: List of conversation/channel dictionaries as returned by the Slack API.
        """
        try:
            client = self._get_client()
            response = client.conversations_list()  # Fetch conversations
            channels = response.get("channels", [])
             # Extract only the required fields
            filtered_channels = [
                {
                    "id": ch.get("id"),
                    "name": ch.get("name"),
                    "is_channel": ch.get("is_channel"),
                    "shared_team_ids": ch.get("shared_team_ids"),
                }
                for ch in channels
            ]
            logger.info(f"Found {len(filtered_channels)} channels.")
            return filtered_channels  # Return the list of channels
        except SlackApiError as e:
            print(f"Error fetching conversations: {e.response['error']}")
            return [] 

    def invite_to_conversation(self, user_ids: list, channel_id: Optional[str] = None ):
        """
        Invite one or more users to a Slack channel.
        :param client: Slack WebClient instance.
        :param channel_id: Conversation ID of the channel.
        :param user_ids: List of user IDs to invite.
        """
        try:
            client = self._get_client()
            # Use the passed channel_id if provided, else use self.channel_id
            channel = channel_id if channel_id else self.channel_id
            response = client.conversations_invite(channel=channel, users=",".join(user_ids))
            print(f"Successfully invited users to {channel}.")
            return response
        except SlackApiError as e:
            print(f"Error inviting users: {e.response['error']}")
            return None
                
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

    # Function to extract required user details
    def extract_required_user_fields(self, user_details):
        extracted_user_data = []
        for entry in user_details:
            extracted_entry = {
                "id": entry.get("id", None),
                "name": entry.get("name", None),
                "is_bot": entry.get("is_bot", None),
                "email": entry.get("profile", {}).get("email", None),
                "team": entry.get("profile", {}).get("team", None)
            }
            extracted_user_data.append(extracted_entry)
        return extracted_user_data   
    
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
                "description": self.read_messages.__doc__ or "Read a message from a Slack channel, user, or conversation.",
                "args_schema": ReadMessagesModel,
                "ref": self.read_messages
            },
            {
                "name": "create_slack_channel",
                "description": self.create_slack_channel.__doc__ or "Create a  Slack channel",
                "args_schema": CreateChannelModel,
                "ref": self.create_slack_channel             
            },
            {
                "name": "list_channel_users",
                "description": self.list_channel_users.__doc__ or "List all users in the Slack channel.",
                "args_schema": ListChannelUsersModel,
                "ref": self.list_channel_users
            },
            {
                "name": "list_workspace_users",
                "description": self.list_workspace_users.__doc__ or "List all users in the Slack workspace.",
                "args_schema": ListWorkspaceUsersModel,
                "ref": self.list_workspace_users
            },
            {
                "name": "invite_to_conversation",
                "description": self.invite_to_conversation.__doc__ or "Invite to a conversation in the Slack workspace.",
                "args_schema": InviteToConversationModel,
                "ref": self.invite_to_conversation
            },
            {
                "name": "list_workspace_conversations",
                "description": self.list_workspace_conversations.__doc__ or "Invite to a conversation in the Slack workspace.",
                "args_schema": ListWorkspaceConversationsModel,
                "ref": self.list_workspace_conversations
            }
            
        ]