# Github Toolkit FAQ

**Official Documentation**: [Github Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/github_toolkit.md)

---

??? question "Can I use my regular GitHub password directly for the ELITEA integration instead of a Personal Access Token?"
    **While ELITEA supports password authentication, using a GitHub Personal Access Token (Classic) is strongly recommended for security.** Personal Access Tokens provide a significantly more secure and controlled method for granting access to external applications like ELITEA, without exposing your primary account credentials. You can configure this in the credential's authentication method selection.
    
    The GitHub toolkit supports three authentication methods:
    
    - **Access Token (Recommended):** Most secure and flexible option with granular permissions
    - **Username/Password:** Supported but less secure, use only if PAT is not an option
    - **GitHub App Private Key:** For GitHub App integrations with enhanced security and higher rate limits

??? question "What scopes/permissions are absolutely necessary and minimally sufficient for the GitHub Personal Access Token to work with ELITEA?"
    The minimum required scopes depend on the specific GitHub tools your ELITEA Agent will be using:
    
    **Read-Only Operations** (`read_file`, `list_files_in_main_branch`, `get_issue`):
    
    - `repo:status` and `public_repo` for public repositories
    - `repo` for private repositories
    
    **Write Operations** (`create_file`, `update_file`, `create_pull_request`):
    
    - `repo` (full repository access)
    - Or granular scopes: `repo:write`, `contents:write`
    
    **Issue & PR Management**:
    
    - `issues` - Create, edit, and manage issues
    - `pull_request` - Create and manage pull requests
    
    **Workflow Operations** (`trigger_workflow`):
    
    - `workflow` - Trigger and manage GitHub Actions workflows
    
    **Project Management** (`create_issue_on_project`, `update_issue_on_project`):
    
    - `project` - Required for GitHub Projects (Classic) operations
    - **Note:** These operations require OAuth App tokens, not regular Personal Access Tokens
    
    **Always adhere to the principle of least privilege and grant only the scopes that are strictly necessary for your Agent's intended functionalities.** Refer to the [GitHub token scopes documentation](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps) for detailed descriptions.

??? question "What is the correct format for specifying the GitHub Repository name in the ELITEA toolkit configuration?"
    The GitHub Repository name must be entered in the format `repository_owner/repository_name`.
    
    **Examples:**
    
    - `MyOrganization/my-project-repo`
    - `username/personal-project`
    - `ProjectAlita/AlitaUI`
    
    **Important:**
    
    - Include both the repository owner (username or organization name) and the repository name
    - Separate them with a forward slash `/`
    - Do NOT include:
        - Full GitHub URL (`https://github.com/owner/repo`)
        - `.git` extension (`owner/repo.git`)
        - Trailing or leading slashes (`/owner/repo/`)
    
    This format is crucial for ELITEA to correctly identify and access your repository on GitHub.

??? question "How do I switch from the old Agent-based configuration to the new Credentials + Toolkit workflow?"
    The new workflow provides better security, reusability, and organization:
    
    **New Workflow Steps:**
    
    1. **Create a GitHub Credential:** Navigate to Credentials menu → Create new credential → Select "GitHub" type → Add your authentication details (PAT, username/password, or App key)
    2. **Create a GitHub Toolkit:** Navigate to Toolkits menu → Create toolkit → Select "GitHub" → Link your credential → Configure repository and branch → Select tools to enable
    3. **Add Toolkit to Workflows:** Add the toolkit to your agents, pipelines, or chat sessions
    
    **Benefits over old approach:**
    
    - Credentials stored securely in one place
    - Reuse same credential across multiple toolkits
    - Easier to update authentication without reconfiguring agents
    - Better audit trail and access control
    - Separate concerns: authentication vs. toolkit configuration

??? question "Can I use the same GitHub credential across multiple toolkits and agents?"
    **Yes!** This is one of the key benefits of the new workflow.
    
    **Credential Reusability:**
    
    - One GitHub credential can be used by multiple GitHub toolkits
    - Each toolkit can be configured for different repositories or with different tool selections
    - Each toolkit can be added to multiple agents, pipelines, and chat sessions
    
    **Example Use Case:**
    
    1. Create one GitHub credential with your Personal Access Token
    2. Create multiple toolkits using the same credential:
        - Toolkit A: Production repository (`company/production-app`)
        - Toolkit B: Development repository (`company/dev-app`)
        - Toolkit C: Documentation repository (`company/docs`)
    3. Add different toolkits to different agents based on their purpose
    
    This promotes better credential management, reduces duplication, and simplifies updates when credentials need to be rotated.

??? question "Can I use GitHub toolkits with private repositories?"
    **Yes**, GitHub toolkits fully support private repositories with proper authentication.
    
    **Requirements:**
    
    - Personal Access Token with `repo` scope (full repository access)
    - Or GitHub App with repository permissions configured
    - Your GitHub account must have appropriate access to the private repository (collaborator, team member, or organization member)
    
    **Note:** The `public_repo` scope only works with public repositories. For private repositories, you must use the full `repo` scope.

??? question "What's the difference between Personal Access Token (Classic) and GitHub OAuth App authentication?"
    Both authentication methods are supported but serve different purposes:
    
    **Personal Access Token (Classic) - Recommended for most use cases:**
    
    - Easy to generate from GitHub Settings
    - Works for all standard repository operations
    - User-specific permissions and rate limits
    - Best for individual users and standard integrations
    
    **GitHub OAuth App - Required for specific operations:**
    
    - **Required** for GitHub Projects (Classic) operations (`create_issue_on_project`, `update_issue_on_project`)
    - Requires OAuth App setup in GitHub Developer Settings
    - Provides `project` scope access that PATs don't support
    - More complex setup requiring authorization flow
    
    **To use OAuth App authentication:**
    
    1. Create OAuth App in GitHub Settings → Developer Settings → OAuth Apps
    2. Use `gh` CLI to login with `project` scope: `gh auth login --scopes "project"`
    3. Get token: `gh auth token`
    4. Use this token in your ELITEA GitHub credential
    
    **Most users should use Personal Access Tokens unless specifically working with GitHub Projects (Classic).**

??? question "Can I use the same toolkit across different workspaces (Private vs. Team Projects)?"
    Credential and toolkit visibility depends on where they're created:
    
    **Private Workspace:**
    
    - Credentials created in Private workspace are only visible to you
    - Toolkits using private credentials are only accessible in your private workspace
    - Cannot be shared with team members
    
    **Team Project Workspace:**
    
    - Credentials created in a team project are visible to all project members
    - Toolkits using project credentials can be used by all project members
    - Ideal for team collaboration
    
    **Best Practice:**
    
    - Use Private workspace credentials for personal repositories or testing
    - Use Team Project credentials for shared repositories and team collaboration
    - Create separate toolkits for different repositories even if using the same credential

??? question "Why am I consistently encountering 'Permission Denied' errors, even though I believe I have configured everything correctly?"
    If you are still facing "Permission Denied" errors despite careful configuration, systematically re-examine the following:
    
    **1. Token Scope Accuracy:**
    
    - Double and triple-check the **scopes/permissions** granted to your GitHub Personal Access Token in your GitHub Developer Settings
    - Ensure that the token possesses the *exact* scopes required for *each* GitHub tool your Agent is attempting to use
    - Pay close attention to write vs. read permissions
    - Remember: `public_repo` only works for public repositories; private repos need full `repo` scope
    
    **2. Repository Access Verification:**
    
    - Explicitly verify that the GitHub account associated with the Personal Access Token has the necessary access rights to the *specific target repository*
    - Confirm repository membership, collaborator status, and assigned roles/permissions within the GitHub repository settings
    - Check if the repository is in an organization with additional access restrictions
    
    **3. Token Validity and Revocation:**
    
    - Double-check that the Personal Access Token is still valid and has not expired
    - Verify the token hasn't been accidentally revoked in your GitHub settings
    - Generate a new token as a test if unsure
    - Check token expiration date in GitHub Settings → Developer Settings → Personal Access Tokens
    
    **4. Credential Configuration:**
    
    - Carefully review the credential configuration in ELITEA
    - Check authentication method selection (Token vs. Password vs. App Key)
    - Look for hidden typographical errors or accidental whitespace in token field
    - Ensure no special characters were added when copying the token
    
    **5. Repository Privacy Settings:**
    
    - If working with organization repositories, check organization-level restrictions
    - Some organizations require OAuth App approval before tokens can access repositories
    - Verify SSO (Single Sign-On) requirements if applicable
    
    **If, after meticulously checking all of these points, you still encounter "Permission Denied" errors, please reach out to ELITEA Support with:**
    
    - Error message details
    - Tool/operation that failed
    - Token scopes granted
    - Repository name and privacy setting (public/private)
    - Organization restrictions (if applicable)

---

!!! reference "Useful ELITEA Resources"
    To further enhance your understanding and skills in using the GitHub toolkit with ELITEA, here are helpful internal resources:

      * **[How to Use Chat Functionality](../../how-tos/chat-conversations/how-to-use-chat-functionality.md)** - *Complete guide to using ELITEA Chat with toolkits for interactive GitHub operations.*
      * **[Create and Edit Agents from Canvas](../../how-tos/chat-conversations/how-to-create-and-edit-agents-from-canvas.md)** - *Learn how to quickly create and edit agents directly from chat canvas for rapid prototyping and workflow automation.*
      * **[Create and Edit Toolkits from Canvas](../../how-tos/chat-conversations/how-to-create-and-edit-toolkits-from-canvas.md)** - *Discover how to create and configure GitHub toolkits directly from chat interface for streamlined workflow setup.*
      * **[Create and Edit Pipelines from Canvas](../../how-tos/chat-conversations/how-to-create-and-edit-pipelines-from-canvas.md)** - *Guide to building and modifying pipelines from chat canvas for automated GitHub workflows.*
      * **[Indexing Overview](../../how-tos/indexing/indexing-overview.md)** - *Comprehensive guide to understanding ELITEA's indexing capabilities and how to leverage them for enhanced search and discovery.*
      * **[Index GitHub Data](../../how-tos/indexing/index-github-data.md)** - *Detailed instructions for indexing GitHub repository data to enable advanced search, analysis, and AI-powered insights across your codebase.*

---

!!! reference "External Resources"
    *   **GitHub Developer Settings:** [https://github.com/settings/developers](https://github.com/settings/developers) - *Navigate to the Developer settings in your GitHub account to manage Personal Access Tokens and other developer-related configurations.*
    *   **GitHub Personal Access Tokens (Classic):** [https://github.com/settings/tokens](https://github.com/settings/tokens) - *Directly access the section in GitHub settings to manage your Personal Access Tokens (Classic) for secure integrations.*
    *   **GitHub API Documentation:** [https://docs.github.com/en/rest](https://docs.github.com/en/rest) - *Explore the official GitHub API documentation for detailed information on GitHub API endpoints, authentication, data structures, and developer guides.*
    *   **GitHub Help Center:** [https://docs.github.com](https://docs.github.com) - *Access the official GitHub documentation for comprehensive articles, FAQs, and troubleshooting guides on all aspects of GitHub usage.*
---