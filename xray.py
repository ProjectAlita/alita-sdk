import os

from alita_sdk.runtime.llms.alita import AlitaChatModel
from alita_sdk.tools.xray import XrayApiWrapper

deployment = os.getenv('DEPLOYMENT_URL')
api_key = os.getenv('API_KEY')
project_id = '18'

settings = {
    'base_url':  'https://eu.xray.cloud.getxray.app/',
    'client_id': '24176FEA2E0E44D99A51AE0904CA1ED6',
    'client_secret': 'fe4348422b267ba815ef3b445473a1ca6658d30a956eb179aedeb0eab7ac7b97',
    'limit': 100,
    'collection_name': 'xray_collection',
    'vectorstore_type': "Chroma",
    'llm': AlitaChatModel(**{
        "deployment": deployment,
        "api_token": api_key,
        "project_id": project_id,
    })
}

wrapper = XrayApiWrapper(**settings)
wrapper.index_data(jql="project = EL AND issuetype = Test")
print(wrapper.search_index(query='order history page', max_results=3))