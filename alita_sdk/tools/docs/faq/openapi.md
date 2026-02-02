# Openapi Toolkit FAQ

**Official Documentation**: [Openapi Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/openapi_toolkit.md)

---

??? question "Can I use multiple OpenAPI toolkits in the same agent?"
    Yes, you can add multiple OpenAPI toolkits to a single agent, each configured with different APIs and specifications.

??? question "Does the toolkit support OpenAPI 2.0 (Swagger) specifications?"
    Yes, both OpenAPI 2.0 (Swagger) and OpenAPI 3.x specifications are supported.

??? question "Can I use YAML instead of JSON for my OpenAPI specification?"
    Yes, both JSON and YAML formats are fully supported. The toolkit will automatically parse either format.

??? question "What happens if my API specification is very large (hundreds of endpoints)?"
    The toolkit supports large specifications with no hard endpoint limit. However, providing many endpoints may impact LLM performance. Use the `selected_tools` feature to limit available tools to only those your agent needs.

??? question "Can I update my OpenAPI specification after creating the toolkit?"
    Yes, edit your toolkit configuration and update the Schema field with the new specification, then save the changes.

??? question "How do I handle APIs that require multiple authentication methods?"
    Create separate OpenAPI Configuration credentials for each authentication method, then create separate toolkits for each, or use the `headers` parameter to add additional authentication headers per request.

??? question "Can I use the toolkit with internal/private APIs?"
    Yes, as long as your ELITEA instance can reach the API's network endpoint. Ensure proper network routing, VPNs, and firewall rules are configured.

??? question "What if my API uses custom authentication not supported by standard methods?"
    Use the Custom authentication type with `custom_header_name` to specify any header name your API requires. For complex authentication, you may need to handle token generation externally.

??? question "How do I test if my OpenAPI toolkit is configured correctly?"
    After saving your toolkit, open the toolkit detail page to access the TOOLS section. Select any tool from the list and use the TEST SETTINGS panel on the right side to configure parameters and execute the tool. This allows you to verify authentication, endpoint connectivity, and parameter configurations before using the toolkit in agents or chat.

??? question "Can I use the same OpenAPI Configuration credential across multiple toolkits?"
    Yes, that's the recommended approach! Create one credential and reuse it across all toolkits that access the same API.

??? question "How do I find the OpenAPI specification for an API?"
    Most API providers publish OpenAPI specifications in their developer documentation:
    
    1. **Check API Documentation**: Look for "API Reference", "Developer Documentation", "Integration Guides", or "OpenAPI Specification"
    2. **Common Locations**: `/swagger.json`, `/openapi.json`, or `/api-docs` endpoints
    3. **File Names**: `swagger.json`, `openapi.json`, `swagger.yaml`, `openapi.yaml`, `api-spec.json`
    4. **Request from Provider**: Contact the API provider if not publicly available
    5. **Generate from Code**: Use tools like Swagger Codegen, FastAPI (Python), or Springdoc (Java Spring Boot)

??? question "How do I determine which tool name to use in agent instructions?"
    Tool names come directly from the `operationId` field in your OpenAPI specification. After uploading your specification, check the "Api Endpoints" accordion in the toolkit configuration to see all available tool names. Use the exact operationId in your agent instructions.

??? question "What's the difference between OpenAPI Configuration and direct toolkit authentication?"
    **OpenAPI Configuration** (Recommended): Reusable credentials stored separately that can be shared across multiple toolkits with centralized management and Secrets integration.
    
    **Direct Toolkit Authentication**: Authentication configured within each toolkit, less reusable but simpler for single-use cases.

??? question "How do I pass request bodies to POST/PUT/PATCH operations?"
    Use the `body_json` parameter with a valid JSON string. The JSON must use double quotes, have no trailing commas, and be passed as a string (not an object). The toolkit parses and sends it as the request body.

??? question "How can I add custom headers to specific API calls?"
    Use the `headers` parameter available on all generated tools. Authentication headers from OpenAPI Configuration are automatically added; the `headers` parameter is for additional per-call headers.

??? question "How do I handle APIs with pagination?"
    Guide the agent in instructions to make multiple calls. Specify the pagination parameters (page, pageSize), check response indicators (hasMore, totalPages), and instruct the agent to repeat calls until all data is retrieved.

??? question "Why aren't all my API endpoints showing up?"
    Common causes: Missing `operationId` (operations are skipped without it), invalid specification (validate at [Swagger Editor](https://editor.swagger.io/)), or missing descriptions. Add both `operationId` and `description` fields to all operations.

??? question "Is there a limit on the number of API endpoints I can use?"
    No hard limit, but large specifications (100+ endpoints) may impact LLM performance. Consider using `selected_tools` to enable only needed operations or break very large APIs into focused specifications per use case.

### Support Contact

For issues, questions, or assistance with OpenAPI integration, please refer to **[Contact Support](../../support/contact-support.md)** for detailed information on how to reach the ELITEA Support Team.


!!! info "Useful Links"
    *   **[OpenAPI Initiative](https://www.openapis.org/)**: Official OpenAPI home and community resources
    *   **[OpenAPI Specification](https://spec.openapis.org/oas/latest.html)**: Complete specification documentation and schema reference
    *   **[Swagger Editor](https://editor.swagger.io/)**: Online editor for creating, editing, and validating OpenAPI specifications
    *   **[JSONLint](https://jsonlint.com/)**: JSON validation tool for checking syntax errors
    *   **[YAML Lint](http://www.yamllint.com/)**: YAML validation tool for checking syntax errors