# Qtest Toolkit FAQ

**Official Documentation**: [Qtest Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/qtest_toolkit.md)

---

??? question "How do I create a qTest toolkit in ELITEA?"
    Toolkit creation requires a **two-step process**: 
    
    1. First create qTest credentials in the Credentials menu with your API token and Base URL
    2. Then create the toolkit by selecting those credentials and configuring the Project ID and DQL search limit

??? question "What is the 'No Of Tests Shown In DQL Search' field and why is it required?"
    This is a **mandatory field** that controls the maximum number of test cases retrieved in DQL queries. It's essential for preventing context overflow and ensuring optimal performance. Set it to 100-200 for most use cases, or lower (20-50) when extracting images.

??? question "Can I use my regular qTest username and password for the ELITEA integration?"
    No, you **must use a qTest API token** (Bearer Token) for secure integration. API tokens provide secure, controlled access specifically designed for external applications like ELITEA. Password authentication is not supported for qTest integration.

??? question "Where do I find the Project ID for my qTest project?"
    The Project ID is a numerical identifier found in your qTest project settings, project URL, or in the browser address bar when inside your qTest project. You can typically find it in the URL as a number (e.g., `https://yourcompany.qtestnet.com/p/12345`).

??? question "Why am I getting 'Permission Denied' errors?"
    Check these items:
    
    - **API Token Validity:** Ensure the token hasn't been revoked in qTest
    - **qTest Account Permissions:** Verify your account has proper permissions for the target project
    - **Correct Project ID:** Ensure the Project ID in toolkit configuration matches your target project
    - **Proper Credential Selection:** Confirm you've selected the correct credential in the toolkit

??? question "My DQL queries return no results, but I know test cases exist. What's wrong?"
    Most commonly this is due to the "No Of Tests Shown In DQL Search" field being empty, set to 0, or set too low. Ensure it's set to an appropriate value (e.g., 100-200 for text-only queries, 20-50 when extracting images).

??? question "Can I use the same qTest credential across multiple toolkits and agents?"
    Yes! This is one of the key benefits of the new workflow. Once you create a qTest credential, you can reuse it across multiple qTest toolkits, and each toolkit can be used by multiple agents, pipelines, and chat sessions. This promotes better credential management and reduces duplication.

??? question "What are some best practices for using the qTest toolkit effectively?"
    **Test Integration Thoroughly:**
    
    - After setting up the qTest toolkit, thoroughly test each tool you intend to use to ensure seamless connectivity, correct authentication, and accurate execution
    
    **Monitor Agent Performance:**
    
    - Regularly monitor the performance of Agents utilizing qTest toolkits to identify any potential issues or areas for optimization
    
    **Follow Security Best Practices:**
    
    - Use API Tokens for integrations
    - Grant only the minimum necessary permissions (principle of least privilege)
    - Securely Store Credentials using ELITEA's Secrets Management feature
    
    **Provide Clear Instructions:**
    
    - Craft clear and unambiguous instructions within your ELITEA Agents to guide them in using the qTest toolkit effectively
    
    **Start Simple:**
    
    - Begin with simpler automation tasks and gradually progress to more complex workflows as you gain experience

??? question "What are common use cases for qTest toolkit integration?"
    **Automated Test Case Retrieval:**
    
    - Quickly retrieve detailed test case steps and expected results for test execution guidance
    
    **Dynamic Test Case Creation:**
    
    - Automatically generate test cases from requirements or user stories to ensure comprehensive test coverage
    
    **Automated Test Case Updates:**
    
    - Automatically update test cases based on changing requirements, test feedback, or workflow progress
    
    **Reporting and Analytics:**
    
    - Generate custom reports on test case coverage, execution status, and quality metrics using DQL queries
    
    **Requirements Traceability:**
    
    - Link test cases to Jira requirements for complete traceability between testing and requirements
    
    **Visual Analysis:**
    
    - Analyze test cases with embedded images to understand visual requirements and expected UI behaviors

---

!!! reference "Documentation and Guides"
    - **[How to Use Chat Functionality](../../how-tos/chat-conversations/how-to-use-chat-functionality.md)** - *Complete guide to using ELITEA Chat with toolkits for interactive qTest operations.*
    - **[Create and Edit Agents from Canvas](../../how-tos/chat-conversations/how-to-create-and-edit-agents-from-canvas.md)** - *Learn how to quickly create and edit agents directly from chat canvas for rapid prototyping and workflow automation.*
    - **[Create and Edit Toolkits from Canvas](../../how-tos/chat-conversations/how-to-create-and-edit-toolkits-from-canvas.md)** - *Discover how to create and configure qTest toolkits directly from chat interface for streamlined workflow setup.*
    - **[Create and Edit Pipelines from Canvas](../../how-tos/chat-conversations/how-to-create-and-edit-pipelines-from-canvas.md)** - *Guide to building and modifying pipelines from chat canvas for automated qTest workflows.*
    - **[How to Test Toolkit Tools](../../how-tos/credentials-toolkits/how-to-test-toolkit-tools.md)** - *Detailed instructions on testing toolkit tools before deploying to production workflows.*
    - **[Secrets Management](../../menus/settings/secrets.md)** - *Best practices for securely storing API tokens and sensitive credentials.*
    - **[Credentials Documentation](../../menus/credentials.md)** - *Comprehensive guide to creating and managing credentials in ELITEA.*
    - **[Toolkits Documentation](../../menus/toolkits.md)** - *Complete reference for toolkit configuration and management.*

!!! reference "External qTest Resources"
    - **[Tricentis qTest Website](https://www.tricentis.com/software/test-management/qtest/)** - *Main product website for qTest information and documentation.*
    - **[qTest Documentation](https://support.tricentis.com/community/manuals_qtest.do)** - *Official qTest documentation for features, functionalities, and API.*
    - **[qTest API Documentation](https://api.qasymphony.com/)** - *Official API documentation for developers.*
    - **[Tricentis Support](https://support.tricentis.com/)** - *Community support, articles, FAQs, and troubleshooting guides.*

---