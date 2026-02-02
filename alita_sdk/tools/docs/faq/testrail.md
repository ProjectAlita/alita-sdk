# Testrail Toolkit FAQ

**Official Documentation**: [Testrail Toolkit Guide](https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/testrail_toolkit.md)

---

1.  **Q: Can I use my regular TestRail password instead of an API Key?**
    *   **A:** No, you must use a TestRail API Key for secure integration. Regular passwords are not supported.

2.  **Q: Where do I find Project IDs, Suite IDs, and Section IDs?**
    *   **A:** These IDs are typically visible in the URL when navigating in TestRail. For example, `/projects/overview/1` shows project ID 1. You can also use TestRail's API to query these IDs.

3.  **Q: What are the priority_id and type_id values for my TestRail instance?**
    *   **A:** These IDs vary by TestRail instance. Check your TestRail configuration or contact your TestRail administrator. Common values: Priority (1=High, 2=Medium, 3=Low), but verify for your instance.

4.  **Q: How do I know which template_id to use when creating test cases?**
    *   **A:** Template IDs depend on your TestRail configuration. Template 1 typically uses simple text steps (`custom_steps`), while template 2 uses separated steps (`custom_steps_separated`). Check your TestRail templates settings.

5.  **Q: Can I index test case attachments?**
    *   **A:** Yes, set `include_attachments: true` in the index_data tool parameters. Note that this requires additional processing time and storage.

6.  **Q: What's the difference between single suite and multiple suite modes?**
    *   **A:** TestRail projects can operate in single suite mode (all test cases in one suite) or multiple suite mode (test cases organized across multiple suites). For multiple suite projects, you must specify `suite_id` when retrieving or creating test cases.

### Support Contact

For issues, questions, or assistance with TestRail integration, contact the ELITEA Support Team:

**Email:** [SupportAlita@epam.com](mailto:SupportAlita@epam.com)

**When contacting support, please include:**
* ELITEA environment name
* Project name and workspace type (Private/Team)
* Detailed description of the issue
* Agent instructions (screenshot or text)
* Toolkit configuration (screenshot)
* Complete error messages
* Exact query or prompt used