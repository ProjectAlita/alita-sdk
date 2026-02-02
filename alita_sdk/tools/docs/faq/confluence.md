# Confluence Toolkit FAQ

**Official Documentation**: [Confluence Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/confluence_toolkit.md)

---

??? question "Can I use my regular Confluence password for the ELITEA integration?"
    **While ELITEA supports password authentication, using a Confluence API token is strongly recommended for security.** API tokens provide a significantly more secure and controlled method for granting access to external applications like ELITEA, without exposing your primary account credentials. You can configure this in the credential's authentication method selection.

??? question "What permissions are absolutely necessary for the Confluence API token to work with ELITEA?"
    Confluence API tokens have a fixed scope and provide access to the Confluence REST API. The specific permissions depend on what your ELITEA Agent will be doing:
    
    - For basic read-only access (e.g., using `read_page_by_id`, `site_search`), standard API access is sufficient.
    - For modifications (e.g., `create_page`, `update_page_by_id`), ensure your Confluence account has write permissions to the target spaces.
    
    **Always adhere to the principle of least privilege and grant only the permissions that are strictly necessary for your Agent's intended functionalities.**

??? question "What is the correct format for specifying the Confluence Space key in the ELITEA toolkit configuration?"
    The Confluence Space key must be entered as the short alphanumeric code assigned to the space (e.g., "DOCS", "TEAM", "DEV"). Do not use the full space name or special characters. You can find the space key in your Confluence space settings or in the URL when viewing the space.

??? question "How do I switch from the old Agent-based configuration to the new Credentials + Toolkit workflow?"
    The new workflow is:
    
    1. Create a Confluence credential with your authentication details
    2. Create a Confluence toolkit that uses this credential
    3. Add the toolkit to your agents, pipelines, or chat
    
    This provides better security, reusability, and organization compared to configuring authentication directly in agents.

??? question "Can I use the same Confluence credential across multiple toolkits and agents?"
    Yes! This is one of the key benefits of the new workflow. Once you create a Confluence credential, you can reuse it across multiple Confluence toolkits, and each toolkit can be used by multiple agents, pipelines, and chat sessions. This promotes better credential management and reduces duplication.

??? question "Why am I consistently encountering 'Permission Denied' errors, even though I believe I have configured everything correctly?"
    If you are still facing "Permission Denied" errors despite careful configuration, systematically re-examine the following:
    
    - **API Token Validity:** Double-check that the API token is still valid and has not been revoked in your Atlassian account settings.
    - **Space Access Verification:** Explicitly verify that the Confluence account associated with the API token has the necessary access rights to the specific target space within Confluence itself. Confirm space membership, permissions, and assigned roles within the Confluence space settings.
    - **Hosting Option Match:** Double-check that you have selected the correct "Hosting option" (Cloud or Server) in the toolkit configuration, especially for self-hosted or enterprise Confluence instances.
    - **Credential Configuration:** Carefully review the credential configuration in ELITEA, especially the authentication method selection and token/password fields for any hidden typographical errors or accidental whitespace.
    
    If, after meticulously checking all of these points, you still encounter "Permission Denied" errors, please reach out to ELITEA Support with detailed information for further assistance.

??? question "What are some best practices for using the Confluence toolkit effectively?"
    **Test Integration Thoroughly:**
    
    - After setting up the Confluence toolkit and incorporating it into your Agents, thoroughly test each tool you intend to use to ensure seamless connectivity, correct authentication, and accurate execution of Confluence actions.
    
    **Monitor Agent Performance:**
    
    - Regularly monitor the performance of Agents utilizing Confluence toolkits. Track metrics such as task completion success rate, execution time, and error rates to identify any potential issues or areas for optimization.
    
    **Follow Security Best Practices:**
    
    - Use API Tokens instead of your main account password for integrations
    - Grant only the minimum necessary permissions (principle of least privilege)
    - Securely Store Credentials using ELITEA's Secrets Management feature
    
    **Provide Clear Instructions:**
    
    - Craft clear and unambiguous instructions within your ELITEA Agents to guide them in using the Confluence toolkit effectively. Use the prompt examples provided in this guide as a starting point.
    
    **Start Simple:**
    
    - Begin by implementing Confluence integration for simpler automation tasks, such as retrieving page content or searching spaces, and gradually progress to more complex workflows as you gain experience.
    
    **Leverage Vector Search:**
    
    - Configure PgVector and embedding models to enable advanced semantic search capabilities across your Confluence spaces, making information discovery more intelligent and efficient.

??? question "What are common use cases for Confluence toolkit integration?"
    The Confluence toolkit enables a wide range of automation and AI-powered knowledge management scenarios. Here are the most common and impactful use cases:
    
    **1. Intelligent Knowledge Discovery & Q&A**
    - Create AI assistants that answer questions by searching and analyzing Confluence documentation
    - Enable natural language queries like "How do we handle customer refunds?" that automatically search spaces and retrieve relevant content
    - Build chatbots that provide instant access to onboarding guides, policies, and procedures
    
    **2. Automated Documentation Management**
    - Auto-generate meeting notes pages from calendar events or meeting transcripts
    - Create standardized documentation pages based on templates (project plans, technical specs, retrospectives)
    - Bulk update pages with consistent formatting, headers, or updated information
    - Automatically archive or label outdated content based on age or relevance
    
    **3. Content Monitoring & Notifications**
    - Set up agents to monitor specific pages or spaces for changes and send notifications
    - Track documentation updates and create summaries of changes
    - Alert teams when critical documentation is modified or created
    
    **4. Knowledge Base Indexing & Semantic Search**
    - Index entire Confluence spaces to enable advanced semantic search capabilities
    - Create searchable knowledge bases that understand context and meaning, not just keywords
    - Build recommendation systems that suggest related documentation based on user queries
    
    **5. Cross-Platform Integration**
    - Sync information between Confluence and other tools (Jira, Slack, GitHub, etc.)
    - Create Confluence pages from Jira tickets, GitHub issues, or other data sources
    - Update Confluence documentation automatically when external systems change
    
    **6. Compliance & Audit Support**
    - Generate compliance reports by extracting and analyzing content from specific spaces
    - Create audit trails by tracking page creation, updates, and access patterns
    - Ensure documentation standards are met across all spaces
    
    **7. Onboarding & Training Automation**
    - Build interactive onboarding assistants that guide new employees through documentation
    - Create personalized learning paths based on role or department
    - Generate training materials and quizzes from existing documentation
    
    **8. Content Analytics & Insights**
    - Analyze documentation gaps by identifying topics with insufficient coverage
    - Generate summaries and insights from large documentation sets
    - Track content freshness and identify stale or outdated pages
    
    These use cases can be implemented individually or combined to create sophisticated knowledge management workflows that significantly reduce manual effort and improve information accessibility across your organization.
    
!!! reference "Elitea Documentation and Guides"    
    - **[How to Use Chat Functionality](../../how-tos/chat-conversations/how-to-use-chat-functionality.md)** - *Complete guide to using ELITEA Chat with toolkits for interactive Confluence operations.*
    - **[Create and Edit Agents from Canvas](../../how-tos/chat-conversations/how-to-create-and-edit-agents-from-canvas.md)** - *Learn how to quickly create and edit agents directly from chat canvas for rapid prototyping and workflow automation.*
    - **[Create and Edit Toolkits from Canvas](../../how-tos/chat-conversations/how-to-create-and-edit-toolkits-from-canvas.md)** - *Discover how to create and configure Confluence toolkits directly from chat interface for streamlined workflow setup.*
    - **[Create and Edit Pipelines from Canvas](../../how-tos/chat-conversations/how-to-create-and-edit-pipelines-from-canvas.md)** - *Guide to building and modifying pipelines from chat canvas for automated Confluence workflows.*
    - **[Indexing Overview](../../how-tos/indexing/indexing-overview.md)** - *Comprehensive guide to understanding ELITEA's indexing capabilities and how to leverage them for enhanced search and discovery.*
    - **[How to Index Confluence Data](../../how-tos/indexing/index-confluence-data.md)** - *Complete guide for indexing your Confluence spaces and pages to enable advanced search and AI-powered analysis capabilities.*
    - **[Secrets Management](../../menus/settings/secrets.md)** - *Best practices for securely storing API tokens and sensitive credentials.*
    - **[AI Configuration](../../menus/settings/ai-configuration.md)** - *Essential settings and configurations for optimizing AI performance with integrations.*

!!! reference "External Confluence Resources"
    - **[Atlassian Account Settings](https://id.atlassian.com/manage-profile/security)** - *Navigate to your Atlassian account settings to manage API tokens and other security configurations.*
    - **[Confluence API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)** - *Directly access the section in Atlassian settings to manage your API tokens for secure integrations.*
    - **[Confluence REST API Documentation](https://developer.atlassian.com/cloud/confluence/rest/v1/)** - *Explore the official Confluence API documentation for detailed information on API endpoints, authentication, data structures, and developer guides.*
    - **[Atlassian Community](https://community.atlassian.com/t5/Confluence/ct-p/confluence)** - *Access the official Atlassian Community for comprehensive articles, FAQs, best practices, and troubleshooting guides on all aspects of Confluence usage.*