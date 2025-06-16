from datetime import datetime, timezone

import jwt
import requests

class SharepointAuthorizationHelper:

    def __init__(self, tenant, client_id, client_secret, scope, token_json):
        self.tenant = tenant
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.auth_code = None
        self.access_token = None
        self.token_json = token_json
        self.state = "12345"  # Static state for this example
        self.redirect_url = None

    def refresh_access_token(self) -> str:
        url = f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/token"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.token_json,
            'scope': self.scope
        }
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            return None

    def get_access_token(self) -> str:
        if (self.is_token_valid(self.token_json)):
            return self.token_json['access_token']
        else:
            return self.refresh_access_token()


    def is_token_valid(self, access_token) -> bool:
        try:
            decoded_token = jwt.decode(access_token, options={"verify_signature": False})
            exp_timestamp = decoded_token.get("exp")
            if exp_timestamp is None:
                return False
            expiration_time = datetime.fromtimestamp(exp_timestamp, timezone.utc)
            return expiration_time > datetime.now(timezone.utc)
        except jwt.ExpiredSignatureError:
            return False
        except jwt.InvalidTokenError:
            return False