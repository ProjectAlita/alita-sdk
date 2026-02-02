# Servicenow Toolkit FAQ

**Official Documentation**: [Servicenow Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/servicenow_toolkit.md)

---

1.  **Q: Can I use this toolkit to work with other ticket types like Problems, Changes, or Service Requests?**
    *   **A:** For now, the ServiceNow toolkit is specifically designed to work with **incidents** only. Support for other ServiceNow tables and applications may be added in the future.

2.  **Q: Where do I find the "Field ID" for a field in ServiceNow?**
    *   **A:** The "Field ID" is the column name in the database table. The easiest way to find it is to ask your ServiceNow administrator. If you have admin access to your PDI, you can navigate to a form (e.g., an incident form), right-click the field's label (e.g., "Category"), and select **"Configure Dictionary"**. The value in the **"Column name"** field is the Field ID you need (e.g., `category`).Also it can be found in url's and browser dev tools section.

3.  **Q: Why am I getting an "Authentication failed" error?**
    *   **A:** This error is almost always due to incorrect credentials.
        *   Verify that the **Username** and **Password** in the toolkit configuration exactly match the user credentials for your **ServiceNow instance**, not your ServiceNow Developer Portal account.
        *   If you recently reset your instance password, ensure you have updated it in the toolkit configuration or the ELITEA Secret.
        *   Check for any extra spaces or typos in the URL, username, or password fields.

### Support and Contact Information

If you encounter any persistent issues, have further questions, or require additional assistance beyond the scope of this guide, please do not hesitate to contact our dedicated ELITEA Support Team.

*   **Email:**  **[SupportAlita@epam.com](mailto:SupportAlita@epam.com)**

To help us resolve your issue efficiently, please include the following in your support request:
*   **ELITEA Environment Details** (e.g., "Next" or the specific name of your ELITEA instance).
*   **Project Name** and workspace type (**Private** or **Team**)
*   A **detailed description** of the problem, including the steps to reproduce it.
*   **Screenshots** of your Agent instructions and toolkit configuration.
*   The **full text of any error messages** you received.