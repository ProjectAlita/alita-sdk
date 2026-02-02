# Bitbucket Toolkit FAQ

**Official Documentation**: [Bitbucket Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/bitbucket_toolkit.md)

---

1.  **Q: Can I use my regular Bitbucket password instead of an API Token?**
    *   **A:** No, **you must use an API Token for security and authentication**. API Tokens are more secure and allow you to limit permissions through scopes.

2.  **Q: What are the minimum scopes needed for the API Token?**
    *   **A:** For read-only operations: account:read, project:read, and repository:read. For full functionality including writes: add repository:write and pullrequest:write.

3.  **Q: What happened to App Passwords?**
    *   **A:** As of September 9, 2025, Bitbucket deprecated App Passwords in favor of API Tokens with scopes. All existing app passwords will be disabled on June 9, 2026.

4.  **Q: Can I use this toolkit with Bitbucket Server?**
    *   **A:** Yes, the toolkit supports both Bitbucket Cloud and Bitbucket Server. Set the correct URL and uncheck the "Cloud" option for Server instances.

5.  **Q: How do I know which branch is currently active?**
    *   **A:** The active branch is either the one you set in the toolkit configuration or the last branch set using the "set_active_branch" tool.

6.  **Q: Why can't my Agent create pull requests?**
    *   **A:** Ensure your API Token has "pullrequest:write" scope and verify the source and target branches exist.

7.  **Q: Can I use this toolkit with multiple repositories?**
    *   **A:** Each toolkit instance is configured for one repository. Create multiple toolkit configurations to work with multiple repositories.

### Support Contact

For assistance with the Bitbucket integration or ELITEA, contact the ELITEA Support Team at **[SupportAlita@epam.com](mailto:SupportAlita@epam.com)**.