# Sql Toolkit FAQ

**Official Documentation**: [Sql Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/sql_toolkit.md)

---

1.  **Q: Can I use this toolkit with other SQL databases besides MySQL and PostgreSQL?**
    *   **A:** Currently, the ELITEA SQL toolkit officially supports **MySQL** and **PostgreSQL** dialects. Support for other SQL databases might be added in future updates. If you require integration with a different SQL database, please contact ELITEA support to discuss your needs.
2.  **Q: Why can't Elitea connect to my SQL server?**
    *   **A:** Elitea requires direct access to your SQL server. If you're experiencing connectivity issues, check the following:
        1.  **Public IP:** Ensure that your local-hosted SQL server has a Public IP address if it needs to be accessed from outside your local network. Without this, ELITEA cannot initiate a connection to your database.
        2.  **Network Environment:** If your SQL server operates within a closed network or a VPN-restricted environment, deploy ELITEA within the same network. This ensures that ELITEA can reach the SQL server without external network barriers.

3. **Q: Can I use my locally deployed SQL server to connect ELITEA to it?**  
    * **A:** No, your SQL server must be accessible from the web. This means the server should be hosted in a way that allows ELITEA to connect to it over the internet. If your SQL server is only available on your local network, ELITEA will not be able to access it unless you configure public accessibility or set up a secure connection such as a VPN.

### Support Contact

For any issues, questions, or further assistance with the SQL integration or ELITEA Agents, please reach out to our dedicated ELITEA Support Team. We are committed to providing prompt and effective support to ensure your success with ELITEA.

**Contact ELITEA Support:**

*   **Email:**  **[SupportAlita@epam.com](mailto:SupportAlita@epam.com)**

**Best Practices for Effective Support Requests:**

To help us understand and resolve your issue as quickly as possible, please ensure you provide the following information in your support email:

*   **ELITEA Environment:** Clearly specify the ELITEA environment you are using (e.g., "Next" or the specific name of your ELITEA instance).
*   **Project Details:**  Indicate the **Project Name** and whether you are working in your **Private** workspace or a **Team** project.
*   **Detailed Issue Description:** Provide a clear, concise, and detailed description of the problem you are encountering. Explain what you were trying to do, what you expected to happen, and what actually occurred.
*   **Relevant Configuration Information:**  To help us diagnose the issue, please include relevant configuration details, such as:
    *   **Agent Instructions (Screenshot or Text):** If the issue is with an Agent, provide a screenshot or copy the text of your Agent's "Instructions" field.
    *   **Toolkit Configurations (Screenshots):** If the issue involves the SQL toolkit or other toolkits, include screenshots of the toolkit configuration settings within your Agent.
*   **Error Messages (Full Error Text):** If you are encountering an error message, please provide the **complete error text**. In the Chat window, expand the error details and copy the full error message. This detailed error information is crucial for diagnosis.
*   **Your Query/Prompt (Exact Text):** If the issue is related to Agent execution, provide the exact query or prompt you used to trigger the issue.

**Before Contacting Support:**

We encourage you to first explore the resources available within this guide and the broader ELITEA documentation. You may find answers to common questions or solutions to known issues in the documentation.