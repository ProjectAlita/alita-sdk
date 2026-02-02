# Slack Toolkit FAQ

**Official Documentation**: [Slack Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/slack_toolkit.md)

---

1. **Q: Can I use my regular Slack password instead of a Bot/User OAuth Token?**
    * **A:** No, for secure integration with ELITEA, you **must use a Slack Bot/User OAuth Token**. Using your regular password directly is not supported and is a security risk.
2. **Q: Where do I find Channel and Workspace IDs in Slack?**
    * **A:** Channel and Workspace IDs are typically visible in the URL when you navigate to a specific channel or workspace within Slack. You can also find these IDs through the Slack API.
3. **Q: What if I don't know the exact permissions needed for the OAuth Token?**
    * **A:** Slack allows you to set scopes/permissions when creating an app. For ELITEA integration, ensure the token has access to the channels and actions you want to manage. Contact your Slack administrator if you are unsure about these permissions.

### Support Contact

For any issues, questions, or further assistance with the Slack integration or ELITEA Agents, please reach out to our dedicated ELITEA Support Team. We are committed to providing prompt and effective support to ensure your success with ELITEA.

**Contact ELITEA Support:**

* **Email:**  **[SupportAlita@epam.com](mailto:SupportAlita@epam.com)**

**Best Practices for Effective Support Requests:**

To help us understand and resolve your issue as quickly as possible, please ensure you provide the following information in your support email:

* **ELITEA Environment:** Clearly specify the ELITEA environment you are using (e.g., "Next" or the specific name of your ELITEA instance).
* **Project Details:**  Indicate the **Project Name** and whether you are working in your **Private** workspace or a **Team** project.
* **Detailed Issue Description:** Provide a clear, concise, and detailed description of the problem you are encountering. Explain what you were trying to do, what you expected to happen, and what actually occurred.
* **Relevant Configuration Information:**  To help us diagnose the issue, please include relevant configuration details, such as:
    * **Agent Instructions (Screenshot or Text):** If the issue is with an Agent, provide a screenshot or copy the text of your Agent's "Instructions" field.
    * **Toolkit Configurations (Screenshots):** If the issue involves the Slack toolkit or other toolkits, include screenshots of the toolkit configuration settings within your Agent.
* **Error Messages (Full Error Text):** If you are encountering an error message, please provide the **complete error text**. In the Chat window, expand the error details and copy the full error message. This detailed error information is crucial for diagnosis.
* **Your Query/Prompt (Exact Text):** If the issue is related to Agent execution, provide the exact query or prompt you used to trigger the issue.

**Before Contacting Support:**

We encourage you to first explore the resources available within this guide and the broader ELITEA documentation. You may find answers to common questions or solutions to known issues in the documentation.