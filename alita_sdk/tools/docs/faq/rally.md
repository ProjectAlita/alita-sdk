# Rally Toolkit FAQ

**Official Documentation**: [Rally Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/rally_toolkit.md)

---

1.  **Q: Can I use my regular Rally username and password for the ELITEA integration?**
    *   **A:** No, it is **mandatory to use a Rally API Key** instead of your main account password for secure integration with ELITEA. Direct password authentication is not supported. API Keys provide a more secure and controlled way to grant access to external applications like ELITEA.
2.  **Q: What permissions should I grant to the Rally API Key?**
    *   **A:** Rally API Keys, when generated through the user profile, inherently provide access based on the user's permissions within Rally. Ensure that the Rally user account associated with the API Key has the necessary permissions within Rally to access and modify the workspaces and projects your Agent will be interacting with. You do not need to configure specific scopes during API Key generation as permissions are managed through Rally user roles and project access control.
3.  **Q: What is the correct format for the Rally Server URL in the toolkit configuration?**
    *   **A:**  The Rally Server URL should be entered in the full format, including `https://` or `http://` and the complete workspace URL (e.g., `https://rally1.rallydev.com` or `https://rally.epam.com`). Ensure there are no typos or missing parts in the URL.
4.  **Q: How do I find the Workspace Name and Project Name for my Rally project?**
    *   **A:** The Workspace Name and Project Name are typically displayed in the Rally web interface when you are logged in and viewing your Rally project. The Workspace Name is usually visible in the top navigation bar, and the Project Name is displayed on the project dashboard or project selection menus. You can also find these names in the URL when you are within your Rally workspace or project.
5.  **Q: Why is my Agent getting "Permission Denied" errors even though I think I have configured everything correctly?**
    *   **A:** Double-check the following:
        *   **API Key Validity:** Ensure that the API Key is valid and has not been revoked in your Rally user settings.
        *   **Rally Account Permissions:** Verify that the Rally account associated with the API Key has the necessary permissions to access the specific workspaces and projects your Agent is trying to interact with.
        *   **Workspace and Project Names Accuracy:** Double-check that you have entered the correct Workspace Name and Project Name in the toolkit configuration and that they correspond to the Rally workspace and project you intend to access.
        *   **Server URL Accuracy:** Ensure that the Server URL is correctly entered and points to the base URL of your Rally instance.

### Support and Contact Information

If you encounter any issues, have questions, or require further assistance beyond what is covered in this guide regarding the Rally integration or ELITEA Agents in general, please do not hesitate to contact our dedicated ELITEA Support Team. We are here to help you resolve any problems quickly and efficiently and ensure you have a smooth and productive experience with ELITEA.

**How to Reach ELITEA Support:**

*   **Email:**  **[SupportAlita@epam.com](mailto:SupportAlita@epam.com)**

**Best Practices for Effective Support Requests:**

To help us understand and resolve your issue as quickly as possible, please ensure you provide the following information in your support email:

*   **ELITEA Environment:** Clearly specify the ELITEA environment you are using (e.g., "Next" or the specific name of your ELITEA instance).
*   **Project Details:**  Indicate the **Project Name** and whether you are working in your **Private** workspace or a **Team** project.
*   **Detailed Issue Description:** Provide a clear, concise, and detailed description of the problem you are encountering. Explain what you were trying to do, what you expected to happen, and what actually occurred.
*   **Relevant Configuration Information:**  To help us diagnose the issue, please include relevant configuration details, such as:
    *   **Agent Instructions (Screenshot or Text):** If the issue is with an Agent, provide a screenshot or copy the text of your Agent's "Instructions" field.
    *   **Toolkit Configurations (Screenshots):** If the issue involves the Rally toolkit or other toolkits, include screenshots of the toolkit configuration settings within your Agent.
*   **Error Messages (Full Error Text):** If you are encountering an error message, please provide the **complete error text**. In the Chat window, expand the error details and copy the full error message. This detailed error information is crucial for diagnosis.
*   **Your Query/Prompt (Exact Text):** If the issue is related to Agent execution, provide the exact query or prompt you used to trigger the issue.

**Before Contacting Support:**

We encourage you to first explore the resources available within this guide and the broader ELITEA documentation. You may find answers to common questions or solutions to known issues in the documentation.