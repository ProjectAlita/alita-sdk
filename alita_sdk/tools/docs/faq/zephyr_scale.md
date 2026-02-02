# Zephyr Scale Toolkit FAQ

**Official Documentation**: [Zephyr Scale Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/zephyr_scale_toolkit.md)

---

*   **Q: Can I use my regular Jira password for the ELITEA integration with Zephyr Scale?**
    *   **A:** No, it is **mandatory to use a Zephyr Scale API token** for secure integration with ELITEA. Direct password authentication is not supported. API tokens provide a more secure and controlled way to grant access to external applications like ELITEA.
*   **Q: What permissions should I grant to the Zephyr Scale API Token?**
    *   **A:** Zephyr Scale API tokens inherit the permissions of the Jira user account they are associated with. Ensure that the Jira user account associated with the API token has the necessary permissions within Jira and Zephyr Scale to access and modify the specific projects and test assets your Agent will be interacting with. You do not need to configure specific scopes during token generation as permissions are managed through Jira user roles and project permissions.
*   **Q: What is the correct format for the Zephyr Scale Base URL in the toolkit configuration?**
    *   **A:**  The Zephyr Scale Base URL should be entered as the base URL of your Jira instance, including `https://` or `http://` and the full workspace URL (e.g., `https://your-workspace.atlassian.net/jira` or `https://your-company.atlassian.net`). For Epam Jira, use `https://jira.epam.com/jira/`. **Do not append `/api/v1` or any other API endpoint path to the Base URL.** The toolkit automatically constructs the API endpoint URL.
*   **Q: How do I find the Project Key for my Zephyr Scale project?**
    *   **A:** The Project Key is a unique identifier for your Jira project where Zephyr Scale is enabled. You can typically find the Project Key in your Jira project settings or in the URL when you are within your Jira project. It is usually a short string of uppercase letters (e.g., "PA", "PROJECTX").
*   **Q: Why is my Agent getting "Permission Denied" errors even though I think I have configured everything correctly?**
    *   **A:** Double-check the following:
        *   **API Token Validity:** Ensure that the API token is valid and has not been revoked.
        *   **Jira User Permissions:** Verify that the Jira user account associated with the API token has the necessary permissions within Jira and Zephyr Scale to access the specific projects and test assets your Agent is trying to use.
        *   **Project Key Accuracy:** Double-check that you have entered the correct Project Key in the toolkit configuration and that it corresponds to the Zephyr Scale project you intend to access.
        *   **Base URL Accuracy:** Ensure that the Base URL is correctly entered and points to the base URL of your Jira instance.
        *   **Hosting Option:** Double-check that you have selected the correct "Hosting option" (Cloud or Server) in the Jira toolkit configuration, especially for self-hosted or Epam Jira instances.

### Support and Contact Information

If you encounter any issues, have questions, or require further assistance beyond what is covered in this guide regarding the Zephyr Scale integration or ELITEA Agents in general, please do not hesitate to contact our dedicated ELITEA Support Team. We are here to help you resolve any problems quickly and efficiently and ensure you have a smooth and productive experience with ELITEA.

**How to Reach ELITEA Support:**

*   **Email:**  **[SupportAlita@epam.com](mailto:SupportAlita@epam.com)**

**Best Practices for Effective Support Requests:**

To help us understand and resolve your issue as quickly as possible, please ensure you provide the following information in your support email:

*   **ELITEA Environment:** Clearly specify the ELITEA environment you are using (e.g., "Next" or the specific name of your ELITEA instance).
*   **Project Details:**  Indicate the **Project Name** and whether you are working in your **Private** workspace or a **Team** project.
*   **Detailed Issue Description:** Provide a clear, concise, and detailed description of the problem you are encountering. Explain what you were trying to do, what you expected to happen, and what actually occurred.
*   **Relevant Configuration Information:**  To help us diagnose the issue, please include relevant configuration details, such as:
    *   **Agent Instructions (Screenshot or Text):** If the issue is with an Agent, provide a screenshot or copy the text of your Agent's "Instructions" field.
    *   **Toolkit Configurations (Screenshots):** If the issue involves the Zephyr Scale toolkit or other toolkits, include screenshots of the toolkit configuration settings within your Agent.
*   **Error Messages (Full Error Text):** If you are encountering an error message, please provide the **complete error text**. In the Chat window, expand the error details and copy the full error message. This detailed error information is crucial for diagnosis.
*   **Your Query/Prompt (Exact Text):** If the issue is related to Agent execution, provide the exact query or prompt you used to trigger the issue.

**Before Contacting Support:**

We encourage you to first explore the resources available within this guide and the broader ELITEA documentation. You may find answers to common questions or solutions to known issues in the documentation.