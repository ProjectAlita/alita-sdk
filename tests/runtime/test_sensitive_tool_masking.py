"""Tests for sensitive tool argument masking (EL-3912).

Validates that _mask_sensitive_tool_args() correctly masks parameter values
for known sensitive field names while NOT masking non-sensitive fields like
file_path, filepath, path, etc.

Root cause: the marker 'pat' (Personal Access Token) was matched via plain
substring search, so 'pat' in 'file_path' -> True, incorrectly masking it.
Fix: switched to word-boundary matching using regex.
"""
import pytest
from alita_sdk.runtime.middleware.sensitive_tool_guard import SensitiveToolGuardMiddleware

mask = SensitiveToolGuardMiddleware._mask_sensitive_tool_args


# ---------------------------------------------------------------------------
# 1. Fields that MUST be masked (true positives)
# ---------------------------------------------------------------------------

class TestTruePositiveMasking:
    """Fields containing known sensitive markers must be masked to '***'."""

    @pytest.mark.parametrize("field_name", [
        'password',
        'user_password',
        'password_hash',
        'db_password',
    ])
    def test_password_fields(self, field_name):
        assert mask('secret123', field_name) == '***'

    @pytest.mark.parametrize("field_name", [
        'secret',
        'client_secret',
        'secret_key',
        'app_secret',
    ])
    def test_secret_fields(self, field_name):
        assert mask('s3cr3t', field_name) == '***'

    @pytest.mark.parametrize("field_name", [
        'token',
        'access_token',
        'auth_token',
        'bearer_token',
        'refresh_token',
        'session_token',
    ])
    def test_token_fields(self, field_name):
        assert mask('tok_abc', field_name) == '***'

    @pytest.mark.parametrize("field_name", [
        'api_key',
        'apikey',
        'api_key_value',
    ])
    def test_api_key_fields(self, field_name):
        assert mask('key-123', field_name) == '***'

    @pytest.mark.parametrize("field_name", [
        'authorization',
        'http_authorization',
    ])
    def test_authorization_fields(self, field_name):
        assert mask('Bearer xxx', field_name) == '***'

    @pytest.mark.parametrize("field_name", [
        'credential',
        'user_credential',
        'credential_data',
    ])
    def test_credential_fields(self, field_name):
        assert mask('cred_val', field_name) == '***'

    @pytest.mark.parametrize("field_name", [
        'private_key',
        'ssh_private_key',
    ])
    def test_private_key_fields(self, field_name):
        assert mask('-----BEGIN', field_name) == '***'

    @pytest.mark.parametrize("field_name", [
        'access_key',
        'aws_access_key',
    ])
    def test_access_key_fields(self, field_name):
        assert mask('AKIA...', field_name) == '***'

    @pytest.mark.parametrize("field_name", [
        'cookie',
        'session_cookie',
        'auth_cookie',
    ])
    def test_cookie_fields(self, field_name):
        assert mask('sid=abc', field_name) == '***'

    @pytest.mark.parametrize("field_name", [
        'pat',           # standalone PAT
        'github_pat',    # suffix
        'pat_token',     # prefix
        'my_pat',        # underscore-delimited
    ])
    def test_pat_fields(self, field_name):
        """PAT (Personal Access Token) fields must still be masked."""
        assert mask('ghp_xxx', field_name) == '***'


# ---------------------------------------------------------------------------
# 2. Fields that MUST NOT be masked (false positives — the bug)
# ---------------------------------------------------------------------------

class TestFalsePositivePrevention:
    """Non-sensitive fields must NOT be masked. These were buggy before the fix."""

    @pytest.mark.parametrize("field_name", [
        'file_path',
        'filepath',
        'path',
        'source_path',
        'target_path',
        'repo_path',
        'dir_path',
        'base_path',
        'output_path',
        'input_path',
    ])
    def test_path_fields_not_masked(self, field_name):
        """file_path, filepath, path etc. must NOT be masked (EL-3912 regression)."""
        value = '/src/main/app.py'
        assert mask(value, field_name) == value

    @pytest.mark.parametrize("field_name", [
        'dispatch',
        'dispatch_id',
        'spatial',
        'spatial_data',
        'compatible',
        'pattern',
        'pattern_name',
    ])
    def test_other_pat_substring_fields_not_masked(self, field_name):
        """Fields containing 'pat' as a substring of a longer word must NOT be masked."""
        value = 'some_value'
        assert mask(value, field_name) == value

    @pytest.mark.parametrize("field_name", [
        'file_contents',
        'file_data',
        'content',
        'body',
        'message',
        'description',
        'title',
        'branch',
        'repo',
        'owner',
        'issue_number',
        'commit_sha',
        'code',
        'query',
        'url',
        'name',
        'email',
    ])
    def test_common_tool_params_not_masked(self, field_name):
        """Common non-sensitive tool parameters must never be masked."""
        value = 'visible_value'
        assert mask(value, field_name) == value


# ---------------------------------------------------------------------------
# 3. Nested structure masking
# ---------------------------------------------------------------------------

class TestNestedMasking:
    """Masking should recurse into dicts, lists, and tuples."""

    def test_dict_masks_sensitive_keys(self):
        result = mask({'file_path': '/a/b.py', 'password': 'secret'})
        assert result['file_path'] == '/a/b.py'
        assert result['password'] == '***'

    def test_dict_preserves_non_sensitive_keys(self):
        result = mask({'content': 'hello', 'title': 'test'})
        assert result == {'content': 'hello', 'title': 'test'}

    def test_list_masked_when_field_sensitive(self):
        """When the field name is sensitive, the entire value (including lists) is masked."""
        result = mask(['val1', 'val2'], 'password')
        assert result == '***'

    def test_list_non_sensitive(self):
        result = mask(['val1', 'val2'], 'items')
        assert result == ['val1', 'val2']

    def test_tuple_masked_when_field_sensitive(self):
        """When the field name is sensitive, the entire value (including tuples) is masked."""
        result = mask(('a', 'b'), 'pat')
        assert result == '***'

    def test_nested_dict_in_dict(self):
        result = mask({
            'config': {
                'api_key': 'key123',
                'timeout': 30,
            },
            'file_path': '/src/app.py',
        })
        assert result['config']['api_key'] == '***'
        assert result['config']['timeout'] == 30
        assert result['file_path'] == '/src/app.py'

    def test_github_create_file_scenario(self):
        """Exact scenario from EL-3912: GitHub create_file tool args."""
        tool_args = {
            'file_path': 'src/utils/helper.py',
            'file_contents': 'def hello():\n    print("hello")',
            'branch': 'fix/issue-42',
            'commit_message': 'Add helper utility',
        }
        result = mask(tool_args)
        assert result['file_path'] == 'src/utils/helper.py', \
            "file_path must NOT be masked (EL-3912)"
        assert result['file_contents'] == 'def hello():\n    print("hello")'
        assert result['branch'] == 'fix/issue-42'
        assert result['commit_message'] == 'Add helper utility'


# ---------------------------------------------------------------------------
# 4. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Boundary conditions for field name matching."""

    def test_none_field_name(self):
        assert mask('value', None) == 'value'

    def test_empty_field_name(self):
        assert mask('value', '') == 'value'

    def test_whitespace_field_name(self):
        assert mask('value', '   ') == 'value'

    def test_case_insensitive_masking(self):
        assert mask('val', 'PASSWORD') == '***'
        assert mask('val', 'Password') == '***'
        assert mask('val', 'API_KEY') == '***'

    def test_no_field_name_dict_root(self):
        """When called on a dict without field_name, recurse into keys."""
        result = mask({'password': '123', 'name': 'test'})
        assert result['password'] == '***'
        assert result['name'] == 'test'

    def test_scalar_without_field_name(self):
        assert mask('hello') == 'hello'
        assert mask(42) == 42
        assert mask(None) is None
