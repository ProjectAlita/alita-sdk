# Xray Toolkit FAQ

**Official Documentation**: [Xray Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/xray_toolkit.md)

---

1.  **Q: Can I use my regular Jira password for the ELITEA integration with Xray Cloud?**
    *   **A:** No, it is **mandatory to use Xray Cloud API Keys (Client ID and Client Secret)** instead of your main Jira account password for secure integration. API Keys provide a more secure and controlled way to grant access to external applications like ELITEA.
2.  **Q: What permissions should I grant to the Xray Cloud API Keys?**
    *   **A:** Xray Cloud API Keys inherit the permissions of the Jira user account they are associated with. Ensure that the Jira user account associated with the API Keys has the necessary permissions within Jira and Xray Cloud to access the specific projects and test assets your Agent will be interacting with. You do not need to configure specific scopes during API Key generation as permissions are managed through Jira user roles and project permissions.
3.  **Q: What is the correct format for the Base URL in the Xray Cloud toolkit configuration?**
    *   **A:**  The Xray Cloud Base URL should be entered as the base URL of your Jira Cloud instance, including `https://` or `http://` and the full workspace URL (e.g., `https://your-workspace.atlassian.net`). For Epam Jira, use `https://jira.epam.com`. **Do not append any API endpoint paths to the Base URL.** The toolkit automatically constructs the API endpoint URL.
4.  **Q: How do I find the Project Key and Test Case Key for my Xray Cloud project and test cases?**
    *   **A:** The Project Key is the standard Jira Project Key, which is typically displayed in Jira project settings and URLs. Test Case Keys (Jira Issue Keys) are the standard Jira Issue Keys assigned to test case issues in your Jira project with Xray Cloud enabled. You can find these keys in Jira issue URLs or by inspecting issue details within Jira.
5.  **Q: Why is my Agent getting "Permission Denied" errors even though I think I have configured everything correctly?**
    *   **A:** Double-check the **API Key Validity**, **Jira User Permissions**, **Project Key Accuracy**, and **Base URL Accuracy** as described in the Troubleshooting section. Ensure all these configurations are correct and that the Jira user account associated with the API Keys has the necessary permissions within Jira and Xray Cloud.

### Support and Contact Information

If you encounter any issues, have questions, or require further assistance beyond what is covered in this guide regarding the Xray Cloud integration or ELITEA Agents in general, please do not hesitate to contact our dedicated ELITEA Support Team. We are here to help you resolve any problems quickly and efficiently and ensure you have a smooth and productive experience with ELITEA.

**How to Reach ELITEA Support:**

*   **Email:**  **[SupportAlita@epam.com](mailto:SupportAlita@epam.com)**

**Best Practices for Effective Support Requests:**

To help us understand and resolve your issue as quickly as possible, please ensure you provide the following information in your support email:

*   **ELITEA Environment:** Clearly specify the ELITEA environment you are using (e.g., "Next" or the specific name of your ELITEA instance).
*   **Project Details:**  Indicate the **Project Name** and whether you are working in your **Private** workspace or a **Team** project.
*   **Detailed Issue Description:** Provide a clear, concise, and detailed description of the problem you are encountering. Explain what you were trying to do, what you expected to happen, and what actually occurred.
*   **Relevant Configuration Information:**  To help us diagnose the issue, please include relevant configuration details, such as:
    *   **Agent Instructions (Screenshot or Text):** If the issue is with an Agent, provide a screenshot or copy the text of your Agent's "Instructions" field.
    *   **Toolkit Configurations (Screenshots):** If the issue involves the Xray Cloud toolkit or other toolkits, include screenshots of the toolkit configuration settings within your Agent.
*   **Error Messages (Full Error Text):** If you are encountering an error message, please provide the **complete error text**. In the Chat window, expand the error details and copy the full error message. This detailed error information is crucial for diagnosis.
*   **Your Query/Prompt (Exact Text):** If the issue is related to Agent execution, provide the exact query or prompt you used to trigger the issue.

**Before Contacting Support:**

We encourage you to first explore the resources available within this guide and the broader ELITEA documentation. You may find answers to common questions or solutions to known issues in the documentation.