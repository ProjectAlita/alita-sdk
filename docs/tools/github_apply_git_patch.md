# GitHub Apply Git Patch Tool

## Overview

The `apply_git_patch` tool allows you to apply git patches in unified diff format directly to a GitHub repository. This is useful for applying changes from patch files, code review suggestions, or programmatically generated diffs.

## Features

- **Parse Unified Diff Format**: Supports standard git patch format
- **Multiple Operations**: Create, modify, delete, and rename files
- **Hunk Processing**: Handles complex multi-hunk patches
- **Batch Changes**: Apply multiple file changes in a single operation
- **Error Handling**: Detailed reporting of successful and failed operations
- **Safety Checks**: Prevents committing to protected branches

## Parameters

- `patch_content` (required): The git patch content in unified diff format
- `commit_message` (optional): Commit message for the patch application (default: "Apply git patch")
- `repo_name` (optional): Repository name in format 'owner/repo' (uses default if not specified)

## Supported Patch Operations

### 1. Create New Files
```diff
diff --git a/new_file.txt b/new_file.txt
new file mode 100644
index 0000000..83db48f
--- /dev/null
+++ b/new_file.txt
@@ -0,0 +1,3 @@
+Line 1
+Line 2
+Line 3
```

### 2. Modify Existing Files
```diff
diff --git a/existing_file.py b/existing_file.py
index abc123..def456 100644
--- a/existing_file.py
+++ b/existing_file.py
@@ -1,4 +1,4 @@
 def hello():
-    print("Hello World")
+    print("Hello GitHub")
     return True
```

### 3. Delete Files
```diff
diff --git a/old_file.txt b/old_file.txt
deleted file mode 100644
index abc123..0000000
--- a/old_file.txt
+++ /dev/null
@@ -1,2 +0,0 @@
-Old content
-To be removed
```

### 4. Rename Files
```diff
diff --git a/old_name.py b/new_name.py
similarity index 88%
rename from old_name.py
rename to new_name.py
index abc123..def456 100644
--- a/old_name.py
+++ b/new_name.py
@@ -1,3 +1,3 @@
 def function():
-    return "old"
+    return "new"
```

## Usage Examples

### Basic Usage
```python
from alita_sdk.tools.github import AlitaGitHubAPIWrapper

# Initialize the wrapper
github_wrapper = AlitaGitHubAPIWrapper(
    github_access_token="your_token",
    github_repository="owner/repo"
)

# Simple patch example
patch = '''diff --git a/README.md b/README.md
index abc123..def456 100644
--- a/README.md
+++ b/README.md
@@ -1,3 +1,3 @@
 # Project Title
 
-Old description
+New description'''

result = github_wrapper.run("apply_git_patch", 
                           patch_content=patch,
                           commit_message="Update README description")
```

### Multi-file Patch
```python
# Apply changes to multiple files
multi_file_patch = '''diff --git a/src/main.py b/src/main.py
index abc123..def456 100644
--- a/src/main.py
+++ b/src/main.py
@@ -10,7 +10,7 @@ def main():
     print("Starting application")
-    version = "1.0.0"
+    version = "1.1.0"
     return True

diff --git a/VERSION b/VERSION
index abc123..def456 100644
--- a/VERSION
+++ b/VERSION
@@ -1 +1 @@
-1.0.0
+1.1.0

diff --git a/CHANGELOG.md b/CHANGELOG.md
new file mode 100644
index 0000000..83db48f
--- /dev/null
+++ b/CHANGELOG.md
@@ -0,0 +1,5 @@
+# Changelog
+
+## v1.1.0
+- Updated version number
+- Added changelog'''

result = github_wrapper.run("apply_git_patch",
                           patch_content=multi_file_patch,
                           commit_message="Version bump to 1.1.0")
```

### Reading Patch from File
```python
# Read patch from file and apply
with open('changes.patch', 'r') as f:
    patch_content = f.read()

result = github_wrapper.run("apply_git_patch",
                           patch_content=patch_content,
                           commit_message="Apply changes from patch file")
```

### Apply to Different Repository
```python
# Apply patch to a different repository
result = github_wrapper.run("apply_git_patch",
                           patch_content=patch,
                           commit_message="Apply cross-repo patch",
                           repo_name="other-owner/other-repo")
```

## Response Format

The tool returns a detailed summary of the patch application:

```json
{
    "success": true,
    "applied_changes": [
        "Created: CHANGELOG.md",
        "Modified: src/main.py", 
        "Modified: VERSION",
        "Deleted: old_file.txt",
        "Renamed: old_config.yml → new_config.yml"
    ],
    "failed_changes": [
        "Failed to modify non_existent.py: file not found"
    ],
    "total_changes": 5,
    "successful_changes": 4,
    "failed_count": 1,
    "message": "Patch partially applied. 4 successful, 1 failed."
}
```

## Error Handling

### Common Error Cases

1. **Protected Branch**
```json
{
    "error": "Cannot apply patch",
    "message": "You're attempting to commit directly to the main branch, which is protected. Please create a new branch and try again."
}
```

2. **Invalid Patch Format**
```json
{
    "error": "No valid changes found", 
    "message": "The patch content does not contain any valid file changes."
}
```

3. **File Not Found**
```json
{
    "success": false,
    "failed_changes": ["Failed to modify missing_file.py: file not found"],
    "message": "Patch application failed for some files."
}
```

## Advanced Features

### Generating Patches

You can generate patches using existing GitHub tools and then apply them:

```python
# Get changes from a commit
commit_changes = github_wrapper.run("get_commit_changes", sha="abc123")

# Extract patch content from the changes
patches = []
for file_change in commit_changes['files']:
    if file_change['patch']:
        patches.append(file_change['patch'])

combined_patch = '\n'.join(patches)

# Apply to another branch or repository
result = github_wrapper.run("apply_git_patch",
                           patch_content=combined_patch,
                           commit_message="Apply changes from commit abc123")
```

### Working with Pull Requests

```python
# Get PR diffs and apply to another branch
pr_diffs = github_wrapper.run("list_pull_request_diffs", pr_number=123)

# Convert PR diffs to patch format (you'd need to format them appropriately)
# Then apply the patch
```

## Best Practices

1. **Always Test on Feature Branches**: Never apply patches directly to main/master branches
2. **Validate Patch Content**: Ensure patch format is correct before applying
3. **Use Descriptive Commit Messages**: Include context about the patch source
4. **Handle Partial Failures**: Check the response for failed changes and handle appropriately
5. **Backup Important Changes**: Consider creating a backup branch before applying large patches

## Integration Examples

### CI/CD Pipeline
```python
# Apply automated patches in CI
def apply_security_patches():
    patches = get_security_patches()  # Your patch source
    for patch in patches:
        result = github_wrapper.run("apply_git_patch",
                                   patch_content=patch['content'],
                                   commit_message=f"Security patch: {patch['id']}")
        if not result['success']:
            notify_team(f"Patch {patch['id']} failed: {result['message']}")
```

### Code Review Automation
```python
# Apply suggested changes from code review
def apply_review_suggestions(suggestions):
    for suggestion in suggestions:
        patch = generate_patch_from_suggestion(suggestion)
        result = github_wrapper.run("apply_git_patch",
                                   patch_content=patch,
                                   commit_message=f"Apply review suggestion: {suggestion['title']}")
```

## Limitations

- Patches must be in unified diff format
- Binary files are not supported
- Complex merge conflicts require manual resolution
- Large patches may hit API rate limits
- Some patch edge cases may not be handled perfectly

## Related Tools

- `get_commit_changes`: Get patch content from existing commits
- `list_pull_request_diffs`: Get changes from pull requests
- `create_branch`: Create branches for patch application
- `create_pull_request`: Create PRs after applying patches
