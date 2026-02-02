# Gitlab Org Toolkit FAQ

**Official Documentation**: [Gitlab Org Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/gitlab_org_toolkit.md)

---

1.  **Q: Can I use my regular GitLab Org password for the ELITEA integration?**
    *   **A:** No, it is **strongly recommended to use a GitLab Personal Access Token** instead of your main account password for security reasons, especially for organizational-level integrations. Personal Access Tokens provide a more secure and controlled way to grant access to external applications like ELITEA, and are essential for secure organizational access.

2.  **Q: What scopes/permissions should I grant to the GitLab Org Personal Access Token?**
    *   **A:** Grant only the **minimum necessary scopes** required for your ELITEA Agent's intended interactions with your GitLab Organization. For typical organizational-level integration, the `api` scope (or granular `read_api`, `read_repository`, `write_repository`) is often necessary to access resources across the organization. Carefully consider the principle of least privilege and avoid granting "sudo" or unnecessary permissions, especially at the organizational level.

3.  **Q: What is the correct format for the GitLab Repository names when specifying multiple repositories for the GitLab Org toolkit?**
    *   **A:** When specifying multiple repositories, use a comma-separated list in the format `group_or_username/repository_name,group_or_username/repository_name,...` (e.g., `my_group/repo1,my_group/repo2,another_group/repo3`). Ensure each repository name is correctly formatted with the group path or username and the repository name separated by a forward slash `/`.

4.  **Q: Why is my Agent getting "Permission Denied" errors when using the GitLab Org toolkit, even though I think I have the right permissions?**
    *   **A:** If you are encountering "Permission Denied" errors with the GitLab Org toolkit, carefully re-examine the following:
        *   **Token Scope Accuracy (Org Level):** Double and triple-check the **scopes/permissions** granted to your GitLab Org Personal Access Token in your GitLab user settings. Ensure that the token possesses the *exact* scopes required for *each* GitLab tool your Agent is attempting to use across the organization. Verify that the scopes are sufficient for organizational-level access if needed.
        *   **Organizational Access Verification:** Explicitly verify that the GitLab Org account associated with the Personal Access Token has the necessary access rights to the *GitLab Organization itself* and to *all target repositories* within the organization. Confirm organizational membership and assigned roles/permissions within GitLab Org settings.
        *   **Token Validity and Revocation:** Double-check that the Personal Access Token is still valid, has not expired, and has not been accidentally revoked in your GitLab settings. Generate a new token as a test if unsure.
        *   **Repository Name Accuracy (Org Level):** Carefully review all repository names in your Agent instructions and toolkit configuration, ensuring they are correctly spelled, capitalized, and formatted with the correct group paths for your GitLab Organization's structure.

If, after meticulously checking all of these points, you still encounter "Permission Denied" errors when using the GitLab Org toolkit, please reach out to ELITEA Support with detailed information for further assistance.

### Support and Contact Information

If you encounter any issues, have questions, or require further assistance beyond what is covered in this guide regarding the GitLab Org integration or ELITEA Agents in general, please do not hesitate to contact our dedicated ELITEA Support Team. We are here to help you resolve any problems quickly and efficiently and ensure you have a smooth and productive experience with ELITEA.

**How to Reach ELITEA Support:**

*   **Email:**  **[SupportAlita@epam.com](mailto:SupportAlita@epam.com)**

**Best Practices for Effective Support Requests:**

To help us understand and resolve your issue as quickly as possible, please ensure you provide the following information in your support email:

*   **ELITEA Environment:** Clearly specify the ELITEA environment you are using (e.g., "Next" or the specific name of your ELITEA instance).


*   **Project Details:**  Indicate the **Project Name** and whether you are working in your **Private** workspace or a **Team** project.
*   **Detailed Issue Description:** Provide a clear, concise, and detailed description of the problem you are encountering. Explain what you were trying to do, what you expected to happen, and what actually occurred.
*   **Relevant Configuration Information:**  To help us diagnose the issue, please include relevant configuration details, such as:
    *   **Agent Instructions (Screenshot or Text):** If the issue is with an Agent, provide a screenshot or copy the text of your Agent's "Instructions" field.
    *   **Toolkit Configurations (Screenshots):** If the issue involves the GitLab Org toolkit or other toolkits, include screenshots of the toolkit configuration settings within your Agent.
*   **Error Messages (Full Error Text):** If you are encountering an error message, please provide the **complete error text**. In the Chat window, expand the error details and copy the full error message. This detailed error information is crucial for diagnosis.
*   **Your Query/Prompt (Exact Text):** If the issue is related to Agent execution, provide the exact query or prompt you used to trigger the issue.

**Before Contacting Support:**

We encourage you to first explore the resources available within this guide and the broader ELITEA documentation. You may find answers to common questions or solutions to known issues in the documentation.