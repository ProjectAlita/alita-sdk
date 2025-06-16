import base64
import hashlib
import jwt
import time
from json import dumps
from urllib.parse import urlencode

import requests

try:
    from oauthlib.oauth1.rfc5849 import SIGNATURE_RSA_SHA512 as SIGNATURE_RSA
except ImportError:
    from oauthlib.oauth1 import SIGNATURE_RSA
from requests import HTTPError

from atlassian.request_utils import get_default_logger

log = get_default_logger(__name__)


class ZephyrRestAPI(object):
    response = None

    def __init__(
        self,
        base_url,
        user_name,
        password,
        timeout=75,
    ):
        """
        init function for the AtlassianRestAPI object.

        :param base_url: The url to be used in the request.
        :param access_key: User's access key to be used in the request for authorization.
        :param timeout: Request timeout. Defaults to 75.
        """
        self.base_url = base_url
        self.user_name = user_name
        self.password = password
        self.timeout = int(timeout)
        self._create_token_session()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _create_token_session(self):
        self.headers = {
            "Accept": "application/json",
            "Authorization": 'Basic ' + base64.b64encode(f"{self.user_name}:{self.password}".encode('utf-8')).decode('utf-8')
            }

    def get_request_token(self, relative_path, http_method, jwt_expire_sec):
        canonical_path = (http_method + '&' + relative_path).replace('?', '&')
        payload_token = {
            'sub': self.account_id,
            'qsh': hashlib.sha256(canonical_path.encode('utf-8')).hexdigest(),
            'iss': self.access_key,
            'exp': int(time.time()) + jwt_expire_sec,
            'iat': int(time.time())
        }
        return jwt.encode(payload_token, self.secret_key, algorithm='HS256')

    def _update_header(self, key, value):
        """
        Update header for exist session
        :param key:
        :param value:
        :return:
        """
        self.headers.update({key: value})

    @staticmethod
    def _response_handler(response):
        try:
            return response.json()
        except ValueError:
            log.debug("Received response with no content")
            return None
        except Exception as e:
            log.error(e)
            return None

    @staticmethod
    def url_joiner(url, path, trailing=None):
        url_link = "/".join(str(s).strip("/") for s in [url, path] if s is not None)
        if trailing:
            url_link += "/"
        return url_link

    def close(self):
        return self.close()

    def call(self, json=None):
        return self.request(method=self.method,
                            path=self.relative_path,
                            data=None,
                            json=json,
                            flags=None,
                            params=None,
                            headers=None,
                            files=None,
                            trailing=None,
                            absolute=False)

    def request(
        self,
        method="GET",
        path="/",
        data=None,
        json=None,
        flags=None,
        params=None,
        headers=None,
        files=None,
        trailing=None,
        absolute=False,
    ):
        """
        :param method:
        :param path:
        :param data:
        :param json:
        :param flags:
        :param params:
        :param headers:
        :param files:
        :param trailing: bool - OPTIONAL: Add trailing slash to url
        :param absolute: bool, OPTIONAL: Do not prefix url, url is absolute
        :param advanced_mode: bool, OPTIONAL: Return the raw response
        :return:
        """
        url = self.url_joiner(None if absolute else self.base_url, path, trailing)
        params_already_in_url = True if "?" in url else False
        if params or flags:
            if params_already_in_url:
                url += "&"
            else:
                url += "?"
        if params:
            url += urlencode(params or {})
        if flags:
            url += ("&" if params or params_already_in_url else "") + "&".join(flags or [])
        if files is None:
            data = None if not data else dumps(data)
        headers = headers or self.headers
        response = requests.Session().request(
            method=method,
            url=url,
            headers=headers,
            data=data,
            json=json,
            timeout=self.timeout,
            files=files,
        )
        response.encoding = "utf-8"

        log.debug("HTTP: %s %s -> %s %s", method, path, response.status_code, response.reason)
        log.debug("HTTP: Response text -> %s", response.text)

        self.raise_for_status(response)
        return response

    def raise_for_status(self, response):
        """
        Checks the response for errors and throws an exception if return code >= 400
        Since different tools (Atlassian, Jira, ...) have different formats of returned json,
        this method is intended to be overwritten by a tool specific implementation.
        :param response:
        :return:
        """
        if response.status_code == 401 and response.headers.get("Content-Type") != "application/json;charset=UTF-8":
            raise HTTPError("Unauthorized (401)", response=response)

        if 400 <= response.status_code < 600:
            try:
                j = response.json()
                error_msg_list = j.get("errorMessages", list())
                errors = j.get("errors", dict())
                if isinstance(errors, dict):
                    error_msg_list.append(errors.get("message", ""))
                elif isinstance(errors, list):
                    error_msg_list.extend([v.get("message", "") if isinstance(v, dict) else v for v in errors])
                error_msg = "\n".join(error_msg_list)
            except Exception as e:
                log.error(e)
                response.raise_for_status()
            else:
                raise HTTPError(error_msg, response=response)
        else:
            response.raise_for_status()