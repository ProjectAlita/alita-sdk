from datetime import datetime, timezone
from urllib.parse import unquote, urlparse, quote
import base64

import jwt
import requests
from botocore.response import get_response


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
    
    def _extract_tenant_from_token(self) -> str:
        """Extract tenant ID from access token if available."""
        if self.tenant:
            return self.tenant
        
        # Try to extract from token_json or access_token
        if self.access_token:
            try:
                # Decode JWT without verification to extract tenant
                decoded = jwt.decode(self.access_token, options={"verify_signature": False})
                return decoded.get('tid', 'common')
            except Exception:
                pass
        
        return 'common'

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

    def _validate_response(self, response, required_field, error_prefix=None):
        if response.status_code != 200:
            raise RuntimeError(f"{error_prefix or 'Request'} failed: {response.status_code} {response.text}")
        json_data = response.json()
        if required_field not in json_data:
            raise KeyError(f"'{required_field}' missing in response")
        return json_data[required_field]

    def generate_token_and_site_id(self, site_url: str) -> tuple[str, str]:
        try:
            parsed = urlparse(site_url)
            domain = parsed.hostname
            site_path = parsed.path.strip('/')
            if not domain or not site_path:
                raise ValueError(f"site_url missing domain or site path: {site_url}")
            app_name = domain.split('.')[0]
            openid_config_url = f"https://login.microsoftonline.com/{app_name}.onmicrosoft.com/v2.0/.well-known/openid-configuration"
            response = requests.get(openid_config_url)
            token_url = self._validate_response(response, required_field="token_endpoint", error_prefix="OpenID config")
            token_data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default"
            }
            token_response = requests.post(token_url, data=token_data)
            access_token = self._validate_response(token_response, required_field="access_token", error_prefix="Token request")
            graph_site_url = f"https://graph.microsoft.com/v1.0/sites/{domain}:/{site_path}"
            headers = {"Authorization": f"Bearer {access_token}"}
            site_response = requests.get(graph_site_url, headers=headers)
            site_id = self._validate_response(site_response, required_field="id", error_prefix="Site info")
            return access_token, site_id
        except Exception as e:
            raise RuntimeError(f"Error while obtaining access_token and site_id: {e}")

    def get_files_list(self, site_url: str, folder_name: str = None, limit_files: int = 100):
        if not site_url or not site_url.startswith("https://"):
            raise ValueError(f"Invalid site_url format: {site_url}")
        if limit_files is not None and (not isinstance(limit_files, int) or limit_files <= 0):
            raise ValueError(f"limit_files must be a positive integer, got: {limit_files}")
        try:
            access_token, site_id = self.generate_token_and_site_id(site_url)
            headers = {"Authorization": f"Bearer {access_token}"}
            drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
            drives_response = requests.get(drives_url, headers=headers)
            drives = self._validate_response(drives_response, required_field="value", error_prefix="Drives request")
            result = []
            def _recurse_drive(drive_id, drive_path, parent_folder, limit_files):
                # Escape folder_name for URL safety if present
                if parent_folder:
                    safe_folder_name = quote(parent_folder.strip('/'), safe="/")
                    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root:/{safe_folder_name}:/children?$top={limit_files}"
                else:
                    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root/children?$top={limit_files}"
                response = requests.get(url, headers=headers)
                if response.status_code != 200:
                    return []
                files_json = response.json()
                if "value" not in files_json:
                    return []
                files = []
                for file in files_json["value"]:
                    file_name = file.get('name', '')
                    # Build full path reflecting nested folders
                    if parent_folder:
                        full_path = '/' + '/'.join([drive_path.strip('/'), parent_folder.strip('/'), file_name.strip('/')])
                    else:
                        full_path = '/' + '/'.join([drive_path.strip('/'), file_name.strip('/')])
                    temp_props = {
                        'Name': file_name,
                        'Path': full_path,
                        'Created': file.get('createdDateTime'),
                        'Modified': file.get('lastModifiedDateTime'),
                        'Link': file.get('webUrl'),
                        'id': file.get('id')
                    }
                    if not all([temp_props['Name'], temp_props['Path'], temp_props['id']]):
                        continue  # skip files with missing required fields
                    if 'folder' in file:
                        # Recursively extract files from this folder
                        inner_folder = parent_folder + '/' + file_name if parent_folder else file_name
                        inner_files = _recurse_drive(drive_id, drive_path, inner_folder, limit_files)
                        files.extend(inner_files)
                    else:
                        files.append(temp_props)
                    if limit_files is not None and len(result) + len(files) >= limit_files:
                        return files[:limit_files - len(result)]
                return files
            #
            site_segments = [seg for seg in site_url.strip('/').split('/') if seg][-2:]
            full_path_prefix = '/'.join(site_segments)
            #
            for drive in drives:
                drive_id = drive.get("id")
                drive_path = unquote(urlparse(drive.get("webUrl")).path) if drive.get("webUrl") else ""
                if not drive_id:
                    continue  # skip drives without id
                #
                sub_folder = folder_name
                if folder_name:
                    folder_path = folder_name.strip('/')
                    expected_prefix = drive_path.strip('/')#f'{full_path_prefix}/{library_type}'
                    if folder_path.startswith(full_path_prefix):
                        if folder_path.startswith(expected_prefix):
                            sub_folder = folder_path.removeprefix(f'{expected_prefix}').strip('/')#target_folder_url = folder_path.removeprefix(f'{full_path_prefix}/')
                        else:
                            # ignore full path folder which is not targeted to current drive
                            continue
                #
                files = _recurse_drive(drive_id, drive_path, sub_folder, limit_files)
                result.extend(files)
                if limit_files is not None and len(result) >= limit_files:
                    return result[:limit_files]
            return result
        except Exception as e:
            raise RuntimeError(f"Error in get_files_list: {e}")

    def get_file_content(self, site_url: str, path: str):
        try:
            access_token, site_id = self.generate_token_and_site_id(site_url)
            headers = {"Authorization": f"Bearer {access_token}"}
            drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
            drives_response = requests.get(drives_url, headers=headers)
            drives = self._validate_response(drives_response, required_field="value", error_prefix="Drives request")
            path = path.strip('/')
            #
            for drive in drives:
                drive_path = unquote(urlparse(drive.get("webUrl")).path).strip('/')
                if not drive_path or not path.startswith(drive_path):
                    continue
                drive_id = drive.get("id")
                if not drive_id:
                    continue
                path = path.replace(drive_path, '').strip('/')
                safe_path = quote(path, safe="")
                url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{safe_path}:/content"
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    return response.content
            raise RuntimeError(f"File '{path}' not found in any private or shared documents.")
        except Exception as e:
            raise RuntimeError(f"Error in get_file_content: {e}")

    def get_lists(self, site_url: str):
        """Get all SharePoint lists on a site using Graph API.
        
        Returns a list of dictionaries with list metadata (Title, Id, Description, ItemCount).
        """
        if not site_url or not site_url.startswith("https://"):
            raise ValueError(f"Invalid site_url format: {site_url}")
        try:
            access_token, site_id = self.generate_token_and_site_id(site_url)
            headers = {"Authorization": f"Bearer {access_token}"}
            lists_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists"
            response = requests.get(lists_url, headers=headers)
            
            if response.status_code != 200:
                raise RuntimeError(f"Lists request failed: {response.status_code} {response.text}")
            
            lists_json = response.json()
            lists = lists_json.get("value", [])
            
            result = []
            for lst in lists:
                # Skip hidden system lists
                if lst.get('list', {}).get('hidden', False):
                    continue
                    
                result.append({
                    'Title': lst.get('displayName', lst.get('name', '')),
                    'Id': lst.get('id', ''),
                    'Description': lst.get('description', ''),
                    'ItemCount': lst.get('list', {}).get('itemCount', 0),
                    'BaseTemplate': lst.get('list', {}).get('template', '')
                })
            
            return result
        except Exception as e:
            raise RuntimeError(f"Error getting lists: {e}")

    def get_list_columns(self, site_url: str, list_title: str):
        """Get column metadata for a SharePoint list using Graph API.
        
        Returns array of column objects with name, displayName, columnType, required, and choice metadata.
        Lookup columns are excluded.
        """
        if not site_url or not site_url.startswith("https://"):
            raise ValueError(f"Invalid site_url format: {site_url}")
        if not list_title:
            raise ValueError("list_title is required")
        
        try:
            access_token, site_id = self.generate_token_and_site_id(site_url)
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # First, get the list ID
            lists_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists"
            lists_response = requests.get(lists_url, headers=headers)
            
            if lists_response.status_code != 200:
                raise RuntimeError(f"Lists request failed: {lists_response.status_code} {lists_response.text}")
            
            lists_json = lists_response.json()
            lists = lists_json.get("value", [])
            
            list_id = None
            for lst in lists:
                if lst.get('displayName', '').lower() == list_title.lower() or lst.get('name', '').lower() == list_title.lower():
                    list_id = lst.get('id')
                    break
            
            if not list_id:
                raise RuntimeError(f"List '{list_title}' not found on site")
            
            # Get columns for the list
            columns_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/columns"
            columns_response = requests.get(columns_url, headers=headers)
            
            if columns_response.status_code != 200:
                raise RuntimeError(f"Columns request failed: {columns_response.status_code} {columns_response.text}")
            
            columns_json = columns_response.json()
            columns = columns_json.get("value", [])
            
            result = []
            for col in columns:
                # Skip hidden columns
                if col.get('hidden', False):
                    continue
                
                # Skip read-only columns (system fields like Created, Modified)
                if col.get('readOnly', False):
                    continue
                
                # Skip lookup columns (too complex for now)
                if 'lookup' in col:
                    continue
                
                column_info = {
                    'name': col.get('name', ''),
                    'displayName': col.get('displayName', col.get('name', '')),
                    'columnType': col.get('text', col.get('number', col.get('boolean', col.get('dateTime', col.get('choice', {}))))).get('__type__', 'text') if isinstance(col.get('text', col.get('number', col.get('boolean', col.get('dateTime', col.get('choice', {}))))), dict) else 'text',
                    'required': col.get('required', False)
                }
                
                # Extract column type from the column definition
                if 'text' in col:
                    column_info['columnType'] = 'text'
                elif 'number' in col:
                    column_info['columnType'] = 'number'
                elif 'boolean' in col:
                    column_info['columnType'] = 'boolean'
                elif 'dateTime' in col:
                    column_info['columnType'] = 'dateTime'
                elif 'choice' in col:
                    column_info['columnType'] = 'choice'
                    choice_info = col.get('choice', {})
                    if 'choices' in choice_info:
                        column_info['choice'] = {
                            'choices': choice_info.get('choices', [])
                        }
                
                result.append(column_info)
            
            return result
        except Exception as e:
            raise RuntimeError(f"Error getting list columns: {e}")

    def create_list_item(self, site_url: str, list_title: str, fields: dict):
        """Create a new item in a SharePoint list using Graph API.
        
        Args:
            site_url: SharePoint site URL
            list_title: Title of the list
            fields: Dictionary of field name -> value pairs
            
        Returns:
            Dictionary with created item metadata (id, fields, webUrl)
        """
        if not site_url or not site_url.startswith("https://"):
            raise ValueError(f"Invalid site_url format: {site_url}")
        if not list_title:
            raise ValueError("list_title is required")
        if not fields or not isinstance(fields, dict):
            raise ValueError("fields must be a non-empty dictionary")
        
        try:
            access_token, site_id = self.generate_token_and_site_id(site_url)
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # First, get the list ID
            lists_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists"
            lists_response = requests.get(lists_url, headers=headers)
            
            if lists_response.status_code != 200:
                raise RuntimeError(f"Lists request failed: {lists_response.status_code} {lists_response.text}")
            
            lists_json = lists_response.json()
            lists = lists_json.get("value", [])
            
            list_id = None
            for lst in lists:
                if lst.get('displayName', '').lower() == list_title.lower() or lst.get('name', '').lower() == list_title.lower():
                    list_id = lst.get('id')
                    break
            
            if not list_id:
                raise RuntimeError(f"List '{list_title}' not found on site")
            
            # Create the list item
            items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items"
            payload = {
                "fields": fields
            }
            
            items_response = requests.post(items_url, headers=headers, json=payload)
            
            if items_response.status_code not in [200, 201]:
                raise RuntimeError(f"Create item failed: {items_response.status_code} {items_response.text}")
            
            item_data = items_response.json()
            
            # TODO: Filter out internal/system fields (@odata.etag, AuthorLookupId, _ComplianceFlags, etc.)
            # to reduce LLM context pollution. Return only id, user-defined fields, and essential metadata.
            return {
                'id': item_data.get('id', ''),
                'fields': item_data.get('fields', {}),
                'webUrl': item_data.get('webUrl', '')
            }
        except Exception as e:
            raise RuntimeError(f"Error creating list item: {e}")

    def get_list_items(self, site_url: str, list_title: str, limit: int = 1000):
        """Fallback Graph API method to read SharePoint list items by list title.

        Returns a list of dictionaries representing list item fields.
        """
        if not site_url or not site_url.startswith("https://"):
            raise ValueError(f"Invalid site_url format: {site_url}")
        try:
            access_token, site_id = self.generate_token_and_site_id(site_url)
            headers = {"Authorization": f"Bearer {access_token}"}
            lists_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists"
            response = requests.get(lists_url, headers=headers)
            if response.status_code != 200:
                raise RuntimeError(f"Lists request failed: {response.status_code} {response.text}")
            lists_json = response.json()
            lists = lists_json.get("value", [])
            target_list = None
            normalized_title = list_title.strip().lower()
            for lst in lists:
                # displayName is the user-visible title. name can differ (internal name)
                display_name = (lst.get("displayName") or lst.get("name") or '').strip().lower()
                if display_name == normalized_title:
                    target_list = lst
                    break
            if not target_list:
                raise RuntimeError(f"List '{list_title}' not found via Graph API.")
            list_id = target_list.get('id')
            if not list_id:
                raise RuntimeError(f"List '{list_title}' missing id field.")
            items_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields&$top={limit}"
            items_response = requests.get(items_url, headers=headers)
            if items_response.status_code != 200:
                raise RuntimeError(f"List items request failed: {items_response.status_code} {items_response.text}")
            items_json = items_response.json()
            values = items_json.get('value', [])
            result = []
            for item in values:
                fields = item.get('fields', {})
                if fields:
                    # TODO: Filter out internal/system fields (@odata.etag, AuthorLookupId, _ComplianceFlags, etc.)
                    # to reduce LLM context pollution. Return only user-defined fields and essential metadata.
                    result.append(fields)
            return result
        except Exception as e:
            raise RuntimeError(f"Error in get_list_items: {e}")

    def upload_file_to_library(self, site_url: str, folder_path: str, filename: str, file_bytes: bytes, replace: bool = True) -> dict:
        """Upload file to SharePoint document library via Microsoft Graph API.
        
        Supports both small files (≤4MB) via simple PUT and large files via chunked upload session.
        
        Args:
            site_url: SharePoint site URL
            folder_path: Server-relative folder path (e.g., '/sites/MySite/Shared Documents/folder')
            filename: Target filename
            file_bytes: File content as bytes
            replace: If True, overwrite existing file. If False, raise error on conflict
            
        Returns:
            dict with file metadata: {id, webUrl, path, size, mime_type}
            
        Raises:
            RuntimeError: If upload fails or file exists when replace=False
        """
        SIZE_THRESHOLD = 4 * 1024 * 1024  # 4 MB
        CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB (must be multiple of 320 KB for Graph API)
        
        try:
            # Get access token and site ID
            access_token, site_id = self.generate_token_and_site_id(site_url)
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Get drives for the site
            drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
            drives_response = requests.get(drives_url, headers=headers)
            drives = self._validate_response(drives_response, required_field="value", error_prefix="Drives request")
            
            # Find matching drive for the folder path
            for drive in drives:
                drive_path = unquote(urlparse(drive.get("webUrl")).path).strip('/') if drive.get("webUrl") else ""
                folder_path_clean = folder_path.strip('/')
                
                if folder_path_clean.startswith(drive_path):
                    drive_id = drive.get("id")
                    if not drive_id:
                        continue
                    
                    # Calculate relative path within drive
                    relative_path = folder_path_clean.replace(drive_path, '').strip('/')
                    item_path = f"{relative_path}/{filename}".strip('/')
                    safe_item_path = quote(item_path, safe="/")
                    
                    # Check if file exists (for replace=False handling)
                    if not replace:
                        check_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{safe_item_path}"
                        check_response = requests.get(check_url, headers=headers)
                        if check_response.status_code == 200:
                            raise RuntimeError(
                                f"File '{filename}' already exists at '{folder_path}'. "
                                f"Set replace=True to overwrite."
                            )
                    
                    file_size = len(file_bytes)
                    
                    # Small file: simple PUT
                    if file_size <= SIZE_THRESHOLD:
                        upload_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{safe_item_path}:/content"
                        upload_response = requests.put(upload_url, headers=headers, data=file_bytes)
                        
                        if upload_response.status_code not in (200, 201):
                            raise RuntimeError(
                                f"File upload failed: HTTP {upload_response.status_code} - {upload_response.text}"
                            )
                        
                        result = upload_response.json()
                        return {
                            'id': result.get('id'),
                            'webUrl': result.get('webUrl'),
                            'path': result.get('parentReference', {}).get('path', '') + '/' + result.get('name', filename),
                            'size': result.get('size', file_size),  # SharePoint's reported storage size (includes metadata overhead)
                            'original_size': file_size,  # Actual uploaded file size in bytes
                            'mime_type': result.get('file', {}).get('mimeType', 'application/octet-stream')
                        }
                    
                    # Large file: chunked upload session
                    else:
                        # Create upload session
                        session_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{safe_item_path}:/createUploadSession"
                        session_body = {
                            "item": {
                                "@microsoft.graph.conflictBehavior": "replace" if replace else "fail"
                            }
                        }
                        session_response = requests.post(session_url, headers=headers, json=session_body)
                        
                        if session_response.status_code not in (200, 201):
                            raise RuntimeError(
                                f"Failed to create upload session: HTTP {session_response.status_code} - {session_response.text}"
                            )
                        
                        upload_url = session_response.json().get('uploadUrl')
                        if not upload_url:
                            raise RuntimeError("Failed to create upload session: No uploadUrl returned")
                        
                        # Upload chunks
                        offset = 0
                        
                        while offset < file_size:
                            chunk_end = min(offset + CHUNK_SIZE, file_size)
                            chunk = file_bytes[offset:chunk_end]
                            
                            chunk_headers = {
                                "Content-Length": str(len(chunk)),
                                "Content-Range": f"bytes {offset}-{chunk_end - 1}/{file_size}"
                            }
                            
                            chunk_response = requests.put(upload_url, headers=chunk_headers, data=chunk)
                            
                            # Final chunk returns 201/200 with file metadata
                            if chunk_response.status_code in (200, 201):
                                result = chunk_response.json()
                                return {
                                    'id': result.get('id'),
                                    'webUrl': result.get('webUrl'),
                                    'path': result.get('parentReference', {}).get('path', '') + '/' + result.get('name', filename),
                                    'size': result.get('size', file_size),  # SharePoint's reported storage size (includes metadata overhead)
                                    'original_size': file_size,  # Actual uploaded file size in bytes
                                    'mime_type': result.get('file', {}).get('mimeType', 'application/octet-stream')
                                }
                            # Intermediate chunks return 202
                            elif chunk_response.status_code != 202:
                                raise RuntimeError(
                                    f"Chunk upload failed: HTTP {chunk_response.status_code} - {chunk_response.text}"
                                )
                            
                            offset = chunk_end
                        
                        raise RuntimeError("Chunked upload completed but no final response received")
            
            raise RuntimeError(f"Could not find drive for folder path: {folder_path}")
            
        except Exception as e:
            raise RuntimeError(f"Error uploading file to library: {e}")

    def add_attachment_to_list_item(self, site_url: str, list_title: str, item_id: int, filename: str, file_bytes: bytes, replace: bool = True) -> dict:
        """Add attachment to SharePoint list item via Microsoft Graph API.
        
        Args:
            site_url: SharePoint site URL
            list_title: Name of the SharePoint list
            item_id: Internal item ID (not the display ID)
            filename: Attachment filename
            file_bytes: File content as bytes
            replace: If True, delete existing attachment with same name first. If False, raise error on conflict
            
        Returns:
            dict with attachment metadata: {id, name, size}
            
        Raises:
            RuntimeError: If attachment fails or file exists when replace=False
        """
        try:
            # Get access token and site ID
            access_token, site_id = self.generate_token_and_site_id(site_url)
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Get lists for the site
            lists_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists"
            lists_response = requests.get(lists_url, headers=headers)
            if lists_response.status_code != 200:
                raise RuntimeError(f"Lists request failed: {lists_response.status_code} {lists_response.text}")
            
            lists = lists_response.json().get("value", [])
            
            # Find target list
            target_list = None
            normalized_title = list_title.strip().lower()
            for lst in lists:
                display_name = (lst.get("displayName") or lst.get("name") or '').strip().lower()
                if display_name == normalized_title:
                    target_list = lst
                    break
            
            if not target_list:
                raise RuntimeError(f"List '{list_title}' not found")
            
            list_id = target_list.get('id')
            if not list_id:
                raise RuntimeError(f"List '{list_title}' missing id field")
            
            # Check for existing attachment (for replace=False or replace=True with deletion)
            attachments_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items/{item_id}/attachments"
            attachments_response = requests.get(attachments_url, headers=headers)
            
            if attachments_response.status_code == 200:
                existing_attachments = attachments_response.json().get("value", [])
                existing_attachment = next(
                    (att for att in existing_attachments if att.get("name", "").lower() == filename.lower()),
                    None
                )
                
                if existing_attachment:
                    if not replace:
                        raise RuntimeError(
                            f"Attachment '{filename}' already exists on list item {item_id}. "
                            f"Set replace=True to overwrite."
                        )
                    # Delete existing attachment
                    attachment_id = existing_attachment.get('id')
                    if attachment_id:
                        delete_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items/{item_id}/attachments/{attachment_id}"
                        delete_response = requests.delete(delete_url, headers=headers)
                        if delete_response.status_code not in (200, 204):
                            raise RuntimeError(
                                f"Failed to delete existing attachment: HTTP {delete_response.status_code} - {delete_response.text}"
                            )
            
            # Add new attachment
            file_base64 = base64.b64encode(file_bytes).decode('utf-8')
            
            attachment_data = {
                "name": filename,
                "contentBytes": file_base64
            }
            
            add_headers = headers.copy()
            add_headers["Content-Type"] = "application/json"
            
            add_response = requests.post(attachments_url, headers=add_headers, json=attachment_data)
            
            if add_response.status_code not in (200, 201):
                raise RuntimeError(
                    f"Failed to add attachment: HTTP {add_response.status_code} - {add_response.text}"
                )
            
            result = add_response.json()
            return {
                'id': result.get('id'),
                'name': result.get('name', filename),
                'size': len(file_bytes)
            }
                
        except Exception as e:
            raise RuntimeError(f"Error adding attachment to list item: {e}")
