# Sharepoint Toolkit FAQ

**Official Documentation**: [Sharepoint Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/sharepoint_toolkit.md)

---

1.  **Q: Can I use my regular SharePoint username and password for the ELITEA integration?**
    *   **A:** No, it is **strongly recommended to use Azure AD App Registration and Client Secrets** instead of user credentials for secure integration. App registration provides a more secure and controlled way to grant access to external applications like ELITEA without exposing user accounts.
2.  **Q: What permissions should I grant to the Azure AD App Registration for SharePoint integration?**
    *   **A:** Grant only the **minimum necessary scopes** required for your ELITEA Agent's intended interactions with SharePoint. For read-only access, `Sites.Read.All` scope in Microsoft Graph might be sufficient. If your Agent needs to modify SharePoint content, you might need to grant `Sites.ReadWrite.All` in Microsoft Graph or more granular SharePoint-specific permissions via `AppInv.aspx`. Avoid granting "FullControl" or unnecessary permissions.
3.  **Q: What is the correct format for the SharePoint Site URL in the toolkit configuration?**
    *   **A:**  The SharePoint Site URL should be entered in the full format, including `https://` and the complete site URL (e.g., `https://your-tenant.sharepoint.com/sites/YourSiteName`). Ensure there are no typos or missing parts in the URL.
4.  **Q: Why is my Agent getting "Permission Denied" errors even though I think I have configured everything correctly?**
    *   **A:** Double-check the following:
        *   **App Registration Permissions:** Verify that the API permissions granted to your Azure AD App Registration include the necessary scopes for the SharePoint tools your Agent is trying to use (e.g., `Sites.ReadWrite.All` for modifying documents).
        *   **SharePoint Site Collection Permissions:** Ensure that you have granted access to your registered App for the specific SharePoint site collection using `AppInv.aspx` and that the granted permissions are sufficient.
        *   **Client ID and Client Secret Validity:** Double-check that the Client ID and Client Secret are correct, valid, and have not expired or been revoked in Azure AD.

### Support and Contact Information

If you encounter any issues, have questions, or require further assistance beyond what is covered in this guide regarding the SharePoint integration or ELITEA Agents in general, please do not hesitate to contact our dedicated ELITEA Support Team. We are here to help you resolve any problems quickly and efficiently and ensure you have a smooth and productive experience with ELITEA.

**How to Reach ELITEA Support:**

*   **Email:**  **[SupportAlita@epam.com](mailto:SupportAlita@epam.com)**

**Best Practices for Effective Support Requests:**

To help us understand and resolve your issue as quickly as possible, please ensure you provide the following information in your support email:

*   **ELITEA Environment:** Clearly specify the ELITEA environment you are using (e.g., "Next" or the specific name of your ELITEA instance).
*   **Project Details:**  Indicate the **Project Name** and whether you are working in your **Private** workspace or a **Team** project.
*   **Detailed Issue Description:** Provide a clear, concise, and detailed description of the problem you are encountering. Explain what you were trying to do, what you expected to happen, and what actually occurred.
*   **Relevant Configuration Information:**  To help us diagnose the issue, please include relevant configuration details, such as:
    *   **Agent Instructions (Screenshot or Text):** If the issue is with an Agent, provide a screenshot or copy the text of your Agent's "Instructions" field.
    *   **Toolkit Configurations (Screenshots):** If the issue involves the SharePoint toolkit or other toolkits, include screenshots of the toolkit configuration settings within your Agent.
*   **Error Messages (Full Error Text):** If you are encountering an error message, please provide the **complete error text**. In the Chat window, expand the error details and copy the full error message. This detailed error information is crucial for diagnosis.
*   **Your Query/Prompt (Exact Text):** If the issue is related to Agent execution, provide the exact query or prompt you used to trigger the issue.

**Before Contacting Support:**

We encourage you to first explore the resources available within this guide and the broader ELITEA documentation. You may find answers to common questions or solutions to known issues in the documentation.