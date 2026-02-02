# Report Portal Toolkit FAQ

**Official Documentation**: [Report Portal Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/report_portal_toolkit.md)

---

1.  **Q: What type of API Key should I use for integration?**
    *   **A:** It is recommended to use a personal API key generated within your ReportPortal profile settings. Ensure this key has sufficient permissions to access the relevant projects and data. Using a personal API key is generally preferred over account passwords for security and manageability.

2.  **Q: Can I use different ReportPortal URLs for different Agents?**
    *   **A:** Yes, you can configure different ReportPortal URLs for different ELITEA Agents. This is useful if you need to connect to multiple ReportPortal instances or projects from different Agents. Simply configure a separate ReportPortal toolkit in each Agent with the respective URL and credentials.

3.  **Q: What happens if the ReportPortal connection is lost?**
    *   **A:** If the connection is lost, ELITEA Agents will not be able to retrieve data from ReportPortal. Agent executions that rely on the ReportPortal toolkit will likely fail and log error messages indicating connection failures. You will need to troubleshoot the connection issues (network, URL, API Key validity, ReportPortal service status) and re-establish the connection to resume data retrieval.

4.  **Q: How often is data synchronized between ELITEA and ReportPortal?**
    *   **A:** Data synchronization is typically initiated on-demand when an ELITEA Agent uses a ReportPortal toolkit tool. There is no automatic background synchronization. When an Agent executes a tool like `get_launch_details`, it makes a real-time API request to ReportPortal to fetch the latest data. Real-time synchronization depends on the responsiveness of the ReportPortal API and network conditions.

### Support Contact

For any issues, questions, or further assistance with the ReportPortal integration or ELITEA Agents, please reach out to our dedicated ELITEA Support Team. We are committed to providing prompt and effective support to ensure your success with ELITEA.

**Contact ELITEA Support:**

*   **Email:**  [SupportAlita@epam.com](mailto:SupportAlita@epam.com)

**Best Practices for Effective Support Requests:**

To help us understand and resolve your issue as quickly as possible, please ensure you provide the following information in your support email:

*   **ELITEA Environment:** Clearly specify the ELITEA environment you are using (e.g., "Next" or the specific name of your ELITEA instance).
*   **Project Details:**  Indicate the **Project Name** and whether you are working in your **Private** workspace or a **Team** project.
*   **Detailed Issue Description:** Provide a clear, concise, and detailed description of the problem you are encountering. Explain what you were trying to do, what you expected to happen, and what actually occurred.
*   **Relevant Configuration Information:**  To help us diagnose the issue, please include relevant configuration details, such as:
    *   **Agent Instructions (Screenshot or Text):** If the issue is with an Agent, provide a screenshot or copy the text of your Agent's "Instructions" field.
    *   **Toolkit Configurations (Screenshots):** If the issue involves the ReportPortal toolkit or other toolkits, include screenshots of the toolkit configuration settings within your Agent.
*   **Error Messages (Full Error Text):** If you are encountering an error message, please provide the **complete error text**. In the Chat window, expand the error details and copy the full error message. This detailed error information is crucial for diagnosis.
*   **Your Query/Prompt (Exact Text):** If the issue is related to Agent execution, provide the exact query or prompt you used to trigger the issue.

**Before Contacting Support:**

We encourage you to first explore the resources available within this guide and the broader ELITEA documentation. You may find answers to common questions or solutions to known issues in the documentation.