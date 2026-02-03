# Jira Toolkit FAQ

**Official Documentation**: [Jira Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/jira_toolkit.md)

---

??? question "Can I use my regular Jira password for the ELITEA integration?"
    **While ELITEA supports password authentication, using a Jira API token is strongly recommended for security.** API tokens provide a significantly more secure and controlled method for granting access to external applications like ELITEA, without exposing your primary account credentials. You can configure this in the credential's authentication method selection.

??? question "What permissions are absolutely necessary for the Jira API token to work with ELITEA?"
    Jira API tokens have a fixed scope and provide access to the Jira REST API. The specific permissions depend on what your ELITEA Agent will be doing:
    
    - For basic read-only access (e.g., using `search_using_jql`, `list_projects`), standard API access is sufficient.
    - For modifications (e.g., `create_issue`, `update_issue`), ensure your Jira account has write permissions to the target projects.
    
    **Always adhere to the principle of least privilege and grant only the permissions that are strictly necessary for your Agent's intended functionalities.**

??? question "What is the correct format for the Jira URL in the ELITEA credential configuration?"
    The Jira URL should be entered as the base URL without the `/jira` suffix:
    
    - For Jira Cloud: `https://yourcompany.atlassian.net`
    - For Jira Server: `https://jira.epam.com`
    
    Ensure there are no typos or missing parts in the URL.

??? question "How do I switch from the old Agent-based configuration to the new Credentials + Toolkit workflow?"
    The new workflow is:
    
    1. Create a Jira credential with your authentication details
    2. Create a Jira toolkit that uses this credential
    3. Add the toolkit to your agents, pipelines, or chat
    
    This provides better security, reusability, and organization compared to configuring authentication directly in agents.

??? question "Can I use the same Jira credential across multiple toolkits and agents?"
    Yes! This is one of the key benefits of the new workflow. Once you create a Jira credential, you can reuse it across multiple Jira toolkits, and each toolkit can be used by multiple agents, pipelines, and chat sessions. This promotes better credential management and reduces duplication.

??? question "Why am I consistently encountering 'Permission Denied' errors, even though I believe I have configured everything correctly?"
    If you are still facing "Permission Denied" errors despite careful configuration, systematically re-examine the following:
    
    - **API Token Validity:** Double-check that the API token is still valid and has not been revoked in your Atlassian account settings.
    - **Jira Account Permissions:** Explicitly verify that the Jira account associated with the API token has the necessary access rights to the specific target projects within Jira itself. Confirm project membership, permissions, and assigned roles within the Jira project settings.
    - **Hosting Option Match:** Double-check that you have selected the correct "Hosting option" (Cloud or Server) in the toolkit configuration, especially for self-hosted or enterprise Jira instances.
    - **Credential Configuration:** Carefully review the credential configuration in ELITEA, especially the authentication method selection and token/password fields for any hidden typographical errors or accidental whitespace.
    
    If, after meticulously checking all of these points, you still encounter "Permission Denied" errors, please reach out to ELITEA Support with detailed information for further assistance.

??? question "What are some best practices for using the Jira toolkit effectively?"
    **Test Integration Thoroughly:**
    
    - After setting up the Jira toolkit and incorporating it into your Agents, thoroughly test each tool you intend to use to ensure seamless connectivity, correct authentication, and accurate execution of Jira actions.
    
    **Monitor Agent Performance:**
    
    - Regularly monitor the performance of Agents utilizing Jira toolkits. Track metrics such as task completion success rate, execution time, and error rates to identify any potential issues or areas for optimization.
    
    **Follow Security Best Practices:**
    
    - Use API Tokens instead of your main account password for integrations
    - Grant only the minimum necessary permissions (principle of least privilege)
    - Securely Store Credentials using ELITEA's Secrets Management feature
    
    **Provide Clear Instructions:**
    
    - Craft clear and unambiguous instructions within your ELITEA Agents to guide them in using the Jira toolkit effectively. Use the prompt examples provided in this guide as a starting point.
    
    **Start Simple:**
    
    - Begin by implementing Jira integration for simpler automation tasks, such as retrieving issue lists or updating issue statuses, and gradually progress to more complex workflows as you gain experience.
    
    **Leverage Advanced Settings:**
    
    - Utilize the "Advanced Settings" in the toolkit configuration, specifically the "Additional Fields" option, to ensure your Agent can interact with and manage custom fields specific to your Jira projects.

??? question "What are common use cases for Jira toolkit integration?"
    **Automated Issue Reporting:**
    
    - When automated tests detect bugs, automatically create Jira issues pre-populated with error information, logs, and environment details.
    
    **Dynamic Task Prioritization:**
    
    - Dynamically reprioritize Jira issues based on real-time data from monitoring systems, customer feedback, or changing business priorities.
    
    **Automated Status Updates:**
    
    - As tasks progress through ELITEA workflows, automatically update the status of linked Jira issues to reflect current progress in real-time.
    
    **Intelligent Commenting:**
    
    - Automatically add comments to Jira issues to provide status updates, notify assignees of new tasks, or request clarification.
    
    **Dependency Management:**
    
    - When creating new Jira issues for sub-tasks or related features, automatically link them to parent issues or related user stories to establish clear dependencies.

---

!!! reference "Documentation and Guides"
    - **[How to Use Chat Functionality](../../how-tos/chat-conversations/how-to-use-chat-functionality.md)** - *Complete guide to using ELITEA Chat with toolkits for interactive GitHub operations.*
    - **[Create and Edit Agents from Canvas](../../how-tos/chat-conversations/how-to-create-and-edit-agents-from-canvas.md)** - *Learn how to quickly create and edit agents directly from chat canvas for rapid prototyping and workflow automation.*
    - **[Create and Edit Toolkits from Canvas](../../how-tos/chat-conversations/how-to-create-and-edit-toolkits-from-canvas.md)** - *Discover how to create and configure GitHub toolkits directly from chat interface for streamlined workflow setup.*
    - **[Create and Edit Pipelines from Canvas](../../how-tos/chat-conversations/how-to-create-and-edit-pipelines-from-canvas.md)** - *Guide to building and modifying pipelines from chat canvas for automated GitHub workflows.*
    - **[Indexing Overview](../../how-tos/indexing/indexing-overview.md)** - *Comprehensive guide to understanding ELITEA's indexing capabilities and how to leverage them for enhanced search and discovery.*
    - **[How to Index Jira Data](../../how-tos/indexing/index-jira-data.md)** - *Complete guide for indexing your Jira projects and issues to enable advanced search and AI-powered analysis capabilities.*
    - **[Secrets Management](../../menus/settings/secrets.md)** - *Best practices for securely storing API tokens and sensitive credentials.*
    - **[AI Configuration](../../menus/settings/ai-configuration.md)** - *Essential settings and configurations for optimizing AI performance with integrations.*

!!! reference "External Jira Resources"
    - **[Atlassian Account Settings](https://id.atlassian.com/manage-profile/security)** - *Manage API tokens and security configurations.*
    - **[Jira API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)** - *Create and manage API tokens for secure integrations.*
    - **[Jira REST API Documentation](https://developer.atlassian.com/cloud/jira/platform/rest/v2/)** - *Official API documentation for developers.*
    - **[JQL Documentation](https://confluence.atlassian.com/jirasoftwareserver/advanced-searching-jql-reference-765593971.html)** - *Learn advanced search queries with Jira Query Language.*
    - **[Atlassian Community](https://community.atlassian.com/t5/Jira/ct-p/jira)** - *Community support, articles, FAQs, and troubleshooting guides.*