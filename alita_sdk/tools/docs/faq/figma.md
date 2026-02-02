# Figma Toolkit FAQ

**Official Documentation**: [Figma Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/figma_toolkit.md)

---

??? question "Can I use multiple Figma toolkits in the same agent?"
    Yes, you can add multiple Figma toolkits to a single agent, each configured with different files or credentials.

??? question "Does the toolkit support Figma Community files?"
    Yes, as long as your Personal Access Token has permission to access the file. Note that some community files may be read-only.

??? question "Can I use YAML for the Global Regexp filter?"
    No, the Global Regexp field accepts standard regular expression syntax only. Use tools like [regex101.com](https://regex101.com/) to test your patterns.

??? question "What happens if my Figma file is very large (hundreds of frames)?"
    The toolkit supports large files, but you may encounter response size limits. Use the "Global Limit" setting and "Global Regexp" filter to focus on specific data, or use `max_frames` parameter in the Analyze file tool to limit frames analyzed per page.

??? question "Can I update my Figma credentials after creating the toolkit?"
    Yes, edit your credential in the Credentials menu, then the toolkit will automatically use the updated credentials for all subsequent API calls.

??? question "How do I handle multiple Figma teams or organizations?"
    Create separate credentials for each Figma organization/team, then create separate toolkits referencing the appropriate credential for each.

??? question "Can I use the toolkit with Figma files that require OAuth 2.0?"
    Currently, the toolkit supports Personal Access Token authentication. OAuth 2.0 support may be added in future releases.

??? question "What if my Figma file uses custom plugins or extensions?"
    The toolkit accesses Figma's standard REST API and retrieves the rendered design data. Custom plugin data may not be available unless exposed through the standard API.

??? question "How do I test if my Figma toolkit is configured correctly?"
    Use the Test Connection button when creating credentials to verify authentication. After creating the toolkit, test it in a chat conversation with a simple query like "Get file details for [file_key]".

??? question "Can I use the same Figma credential across multiple toolkits?"
    Yes, that's the recommended approach! Create one credential and reuse it across all toolkits that access the same Figma account.

??? question "How do I find my Figma file key?"
    The file key is in the URL when viewing a file in Figma. For example, in `https://www.figma.com/file/ABC123DEF456/My-Design`, the file key is `ABC123DEF456`. See the [How to Find Figma File Key](#how-to-find-figma-file-key) section for detailed instructions.

??? question "Can I restrict which Figma tools are available to an agent?"
    Currently, all tools enabled in the toolkit configuration are available to agents. You can control tool usage through agent instructions by explicitly specifying which tools to use for specific scenarios.
  
### Support Contact

If you encounter issues not covered in this guide or need additional assistance with Figma integration, please refer to **[Contact Support](../../support/contact-support.md)** for detailed information on how to reach the ELITEA Support Team.

---


!!! reference "Useful ELITEA Resources"
    To further enhance your understanding and skills in using the Figma toolkit with ELITEA, here are helpful internal resources:

      * **[ELITEA Credentials Management](../../how-tos/credentials-toolkits/how-to-use-credentials.md)** - *Learn how to securely store your Figma API Token using ELITEA's Credentials management feature for enhanced security within ELITEA.*
      * **[Indexing Overview](../../how-tos/indexing/indexing-overview.md)** - *Comprehensive guide to understanding ELITEA's indexing capabilities and how to leverage them for enhanced search and discovery.*
      * **[Index Figma Data](../../how-tos/indexing/index-figma-data.md)** - *Detailed instructions for indexing Figma design files to enable advanced search, analysis, and AI-powered insights across your design assets.*

!!! reference "External Resources"
    *   **Figma Website:** [https://www.figma.com/](https://www.figma.com/) - *Access the main Figma product website for product information, documentation, tutorials, and community resources.*
    *   **Figma for Developers Documentation:** [https://www.figma.com/developers/api](https://www.figma.com/developers/api) - *Explore the official Figma API documentation for detailed information on Figma API endpoints, authentication, data structures, and developer guides.*
    *   **Figma OAuth 2.0 Documentation:** [https://www.figma.com/plugin-docs/oauth-with-plugins/](https://www.figma.com/plugin-docs/oauth-with-plugins/) - *Learn more about implementing OAuth 2.0 authentication for Figma applications and integrations.*
    *   **Figma Help Center:** [https://help.figma.com/hc/en-us](https://help.figma.com/hc/en-us) - *Access the official Figma Help Center for comprehensive articles, FAQs, and troubleshooting guides on all aspects of Figma usage.*