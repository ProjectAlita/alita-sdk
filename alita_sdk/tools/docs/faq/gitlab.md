# Gitlab Toolkit FAQ

**Official Documentation**: [Gitlab Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/gitlab_toolkit.md)

---

1.  **Q: What scopes/permissions are absolutely necessary and minimally sufficient for the GitLab Personal Access Token to work with ELITEA?**
    *   **A:** The minimum required scopes depend on the specific GitLab tools your ELITEA Agent will be using. For basic read-only access to repositories (e.g., using `read_file`, `list_files`), the `read_api` and `read_repository` scopes might suffice. However, for most common integration scenarios involving modifications (e.g., `create_file`, `update_file`, `create_pull_request`), you will need the broader `api` scope or more granular write scopes like `write_repository`. For issue management, include `read_issue` and `write_issue` scopes. For merge request management, include `read_merge_requests` and `write_merge_requests` scopes. **Always adhere to the principle of least privilege and grant only the scopes that are strictly necessary for your Agent's intended functionalities.**

2.  **Q: What is the correct format for specifying the GitLab Repository name in the ELITEA toolkit configuration?**
    *   **A:** The GitLab Repository name must be entered in the format `namespace/repository_name` (e.g., `MyGroup/my-project-repo`). Ensure you include both the namespace (user or group name) and the repository name, separated by a forward slash `/`. This format is crucial for ELITEA to correctly identify and access your repository on GitLab.

3.  **Q: How do I switch from the old Agent-based configuration to the new Credentials + Toolkit workflow?**
    *   **A:** The new workflow is: (1) Create a GitLab credential with your authentication details, (2) Create a GitLab toolkit that uses this credential, and (3) Add the toolkit to your agents, pipelines, or chat. This provides better security, reusability, and organization compared to configuring authentication directly in agents.

4.  **Q: Can I use the same GitLab credential across multiple toolkits and agents?**
    *   **A:** Yes! This is one of the key benefits of the new workflow. Once you create a GitLab credential, you can reuse it across multiple GitLab toolkits, and each toolkit can be used by multiple agents, pipelines, and chat sessions. This promotes better credential management and reduces duplication.

5.  **Q: Can I use both GitLab.com and self-hosted GitLab instances with ELITEA?**
    *   **A:** Yes! ELITEA supports both GitLab.com and self-hosted GitLab instances. Simply configure the correct URL in your credential settings: `https://gitlab.com` for GitLab.com or `https://gitlab.yourcompany.com` for your self-hosted instance.

6.  **Q: Why am I consistently encountering "Permission Denied" errors, even though I believe I have configured everything correctly and granted the necessary permissions?**
    *   **A:** If you are still facing "Permission Denied" errors despite careful configuration, systematically re-examine the following:
        *   **Token Scope Accuracy:** Double and triple-check the **scopes/permissions** granted to your GitLab Personal Access Token in your GitLab User Settings. Ensure that the token possesses the *exact* scopes required for *each* GitLab tool your Agent is attempting to use. Pay close attention to write vs. read permissions.
        *   **Repository Access Verification:** Explicitly verify that the GitLab account associated with the Personal Access Token has the necessary access rights to the *specific target repository* within GitLab itself. Confirm project membership and assigned roles/permissions within the GitLab project settings.
        *   **Token Validity and Revocation:** Double-check that the Personal Access Token is still valid, has not expired, and has not been accidentally revoked in your GitLab settings. Generate a new token as a test if unsure.
        *   **Credential Configuration:** Carefully review the credential configuration in ELITEA, especially the URL and token fields for any hidden typographical errors or accidental whitespace.

If, after meticulously checking all of these points, you still encounter "Permission Denied" errors, please reach out to ELITEA Support with detailed information for further assistance.

### Support and Contact Information

If you encounter any persistent issues, have further questions, or require additional assistance beyond the scope of this guide regarding the GitLab integration or ELITEA Agents in general, please do not hesitate to contact our dedicated ELITEA Support Team. We are committed to providing timely and effective support to ensure you have a seamless and productive experience with ELITEA.

**How to Reach ELITEA Support:**

*   **Email:**  **[SupportAlita@epam.com](mailto:SupportAlita@epam.com)**

**Best Practices for Submitting Effective Support Requests:**

To enable our support team to understand and resolve your issue as efficiently as possible, please include the following critical information in your support email:

*   **ELITEA Environment Details:** Clearly specify the ELITEA environment you are currently using (e.g., "Next" or the specific name of your ELITEA instance).
*   **Project Context:**  Indicate the **Project Name** within ELITEA where you are experiencing the issue and specify whether you are working in your **Private** workspace or a **Team** project.
*   **Detailed Issue Description:** Provide a clear, concise, and comprehensive description of the problem you are encountering. Articulate precisely what you were attempting to do, what behavior you expected to observe, and what actually occurred (the unexpected behavior or error). Step-by-step descriptions are highly valuable.
*   **Relevant Configuration Information (Screenshots Preferred):** To facilitate efficient diagnosis, please include relevant configuration details, ideally as screenshots:
    *   **Agent Instructions (Screenshot or Text Export):** If the issue is related to a specific Agent's behavior, provide a screenshot of the Agent's "Instructions" field or export the instructions as text.
    *   **Toolkit Configurations (Screenshots):** If the issue involves the GitLab toolkit or any other toolkits, include clear screenshots of the toolkit configuration settings as they appear within your Agent's configuration in ELITEA.
*   **Complete Error Messages (Full Text):** If you are encountering any error messages, please provide the **complete and unabridged error text**. In the ELITEA Chat window, expand the error details section (if available) and copy the entire error message text. Detailed error information is often crucial for accurate diagnosis.
*   **Your Query/Prompt (Exact Text):** If the issue is related to Agent execution or an unexpected response, provide the exact query or prompt you used to trigger the Agent's action that led to the problem.

**Pre-Support Request Actions (Self-Help):**

Before contacting support, we strongly encourage you to first thoroughly explore the resources available within this comprehensive guide and the broader ELITEA documentation. You may find readily available answers to common questions, solutions to known issues, or configuration guidance within these resources, potentially resolving your issue more quickly.


!!! reference "External Resources"
    *   **GitLab Website:** [https://gitlab.com](https://gitlab.com) - *Access the main GitLab platform to create an account or log in.*
    *   **GitLab Access Tokens:** [https://gitlab.com/-/profile/personal_access_tokens](https://gitlab.com/-/profile/personal_access_tokens) - *Directly access the section in GitLab settings to manage your Personal Access Tokens for secure integrations.*
    *   **GitLab API Documentation:** [https://docs.gitlab.com/ee/api/](https://docs.gitlab.com/ee/api/) - *Explore the official GitLab API documentation for detailed information on GitLab API endpoints, authentication, data structures, and developer guides.*
    *   **GitLab Help Center:** [https://docs.gitlab.com](https://docs.gitlab.com) - *Access the official GitLab documentation for comprehensive articles, FAQs, and troubleshooting guides on all aspects of GitLab usage.*
    *   **GitLab Support:** [https://about.gitlab.com/support/](https://about.gitlab.com/support/) - *Access GitLab's official support resources and contact information.*