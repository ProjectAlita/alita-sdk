# Ado Repos Toolkit FAQ

**Official Documentation**: [Ado Repos Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/ado_repos_toolkit.md)

---

1.  **Q: Can I use my regular Azure DevOps password directly for the ELITEA integration instead of a Personal Access Token?**
    *   **A:** **No, using an Azure DevOps Personal Access Token is mandatory and strongly recommended for security.** Direct password authentication is not supported for ELITEA's Azure Repos toolkit integration. Personal Access Tokens provide a significantly more secure and controlled method for granting access to external applications like ELITEA, without exposing your primary account credentials.

2.  **Q: What scopes/permissions are absolutely necessary and minimally sufficient for the Azure DevOps Personal Access Token to work with ELITEA?**
    *   **A:** The minimum required scopes depend on the specific Azure Repos tools your ELITEA Agent will be using. For basic read-only access to repositories (e.g., using `read_file`, `list_files`), the `vso.code_read` scope might suffice. However, for most common integration scenarios involving modifications (e.g., `create_file`, `update_file`, `create_pull_request`), you will need the `vso.code_full` scope. For work item (issue) management, include `vso.work_full` scope. **Always adhere to the principle of least privilege and grant only the scopes that are strictly necessary for your Agent's tasks.** Refer to the Azure DevOps documentation for detailed scope descriptions.

3.  **Q: What is the correct format for specifying the Azure DevOps Organization URL in the ELITEA toolkit configuration?**
    *   **A:**  The Azure DevOps Organization URL must be entered in the format `https://dev.azure.com/{YourOrganizationName}`. Replace `{YourOrganizationName}` with your actual Azure DevOps organization name. Ensure you include `https://dev.azure.com/` and your organization name.

4.  **Q: How do I find the Repository ID for my Azure Repos repository?**
    *   **A:**  You need to use the `curl` command provided in the "Integration Steps" section of this guide to retrieve the Repository ID from the Azure DevOps API. Follow the detailed steps in section 3.2 "Integration Steps: Configuring the Azure Repos (ADO Repo) Toolkit in ELITEA" to correctly obtain the Repository ID. Pay close attention to replacing the placeholders with your actual PAT, organization name, and project name in the `curl` command.

5.  **Q: Why am I consistently getting "Permission Denied" errors, even though I think I have configured everything correctly and granted the right permissions?**
    *   **A:** If you are still facing "Permission Denied" errors despite careful configuration, systematically re-examine the following:
        *   **Token Scope Accuracy:** Double and triple-check the **scopes/permissions** granted to your Azure DevOps Personal Access Token in your Azure DevOps user settings. Ensure that the token possesses the *exact* scopes required for *each* Azure Repos tool your Agent is attempting to use. Pay close attention to write vs. read permissions and ensure you have granted sufficient scopes.
        *   **Project and Repository Access Verification:** Explicitly verify that the Azure DevOps account associated with the Personal Access Token has the necessary access rights to the *specific target project and repository* within Azure DevOps itself. Confirm project membership, assigned roles, and repository permissions within the Azure DevOps project settings.
        *   **Token Validity and Revocation:** Double-check that the Personal Access Token is still valid, has not expired, and has not been accidentally revoked in your Azure DevOps settings. Generate a new token as a test if unsure.
        *   **Typographical Errors:** Carefully review all configuration fields in ELITEA, especially the Azure DevOps URL, Organization Name, Project Name, Repository ID, and the Personal Access Token itself for any hidden typographical errors or accidental whitespace.

If, after meticulously checking all of these points, you still encounter "Permission Denied" errors, please reach out to ELITEA Support with detailed information for further assistance.


### Support and Contact Information

If you encounter any issues, have questions, or require further assistance beyond what is covered in this guide regarding the Azure Repos integration or ELITEA Agents in general, please do not hesitate to contact our dedicated ELITEA Support Team. We are here to help you resolve any problems quickly and efficiently and ensure you have a smooth and productive experience with ELITEA.

**How to Reach ELITEA Support:**

*   **Email:**  **[SupportAlita@epam.com](mailto:SupportAlita@epam.com)**

**Best Practices for Effective Support Requests:**

To help us understand and resolve your issue as quickly as possible, please ensure you provide the following information in your support email:

*   **ELITEA Environment:** Clearly specify the ELITEA environment you are using (e.g., "Next" ).
*   **Project Details:**  Indicate the **Project Name** and whether you are working in your **Private** workspace or a **Team** project.
*   **Detailed Issue Description:** Provide a clear, concise, and detailed description of the problem you are encountering. Explain what you were trying to do, what you expected to happen, and what actually occurred.
*   **Relevant Configuration Information:**  To help us diagnose the issue, please include relevant configuration details, such as:
    *   **Agent Instructions (Screenshot or Text):** If the issue is with an Agent, provide a screenshot or copy the text of your Agent's "Instructions" field.
    *   **Toolkit Configurations (Screenshots):** If the issue involves the Azure Repos toolkit or other toolkits, include screenshots of the toolkit configuration settings within your Agent.
*   **Error Messages (Full Error Text):** If you are encountering an error message, please provide the **complete error text**. In the Chat window, expand the error details and copy the full error message. This detailed error information is crucial for diagnosis.
*   **Your Query/Prompt (Exact Text):** If the issue is related to Agent execution, provide the exact query or prompt you used to trigger the issue.

**Before Contacting Support:**

We encourage you to first explore the resources available within this guide and the broader ELITEA documentation. You may find answers to common questions or solutions to known issues in the documentation.