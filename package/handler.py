from time import sleep
from traceback import format_exc


try:
    from langchain_core.messages import HumanMessage
except Exception as e:
    print(e)
    print(format_exc())

try:
    from alita_sdk.llms import AlitaChatModel
except Exception as e:
    print(e)
    print(format_exc())


def handler(event, context=None):
    try:
        local_settings = {
            "deployment": "https://eye.projectalita.ai",
            "model": "gpt-4o",
            "api_key": event.get("AUTH_TOKEN"),
            "project_id": event.get("PROJECT_ID"),
            "integration_uid": event.get("INTEGRATION_UID"),
            "max_tokens": 2048,
            "temperature": 0.9,
            "stream": True
        }
        llm: AlitaChatModel = AlitaChatModel(**local_settings)
        chat_history = []
        user_message = HumanMessage(content='go').dict()
        user_message['role'] = 'user'
        chat_history.append(user_message)
        #ToDo use prompt_id and prompt_version_id as event parameters
        executor = llm.client.prompt(
            prompt_id=29,
            prompt_version_id=61
        )
        response = executor.invoke(
            {"content": user_message['content'], "chat_history": []},
        )
        print("response:")
        print(response)
        result = {
            'statusCode': 200,
            'body': response
        }
    except Exception as exc:
        result = {
            'statusCode': 500,
            'body': format_exc()
        }
    return result
