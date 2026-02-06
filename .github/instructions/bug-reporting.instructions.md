---
description: Instructions for bug reporting to ELITEA Board
applyTo: "**"
---

# Bug Reporting Guidelines

## General Instructions
- **Objective**: Create a comprehensive, actionable bug report.
- **Audience**: Assume the report will be read by developers, QA, and project managers.
- **Clarity**: Be specific, concise, and unambiguous. Avoid jargon where possible.
- **Completeness**: Fill out all applicable sections of the template. If a section is not applicable, mark it as `N/A`.
- **Verification**: Before submitting, review the report to ensure all details are correct and steps are reproducible.

---

# Bug Report Template Structure

## 1. Title
- **Format**: `[BUG] <Brief, informative title>`
- **Rule**: The title must clearly and concisely summarize the issue.
- **Good**: `[BUG] Save button is disabled after entering valid credit card information`
- **Bad**: `[BUG] Button not working`

## 2. Description
- **Rule**: Provide a brief, to-the-point description of what is wrong and why it matters. Explain the impact from a user's perspective.
- **Example**: "When a user enters valid payment details, the 'Save' button remains disabled, preventing them from completing their purchase. This directly impacts conversion rates."

## 3. Preconditions (optional)
- **Rule**: List any specific setup or state required for the bug to occur. This includes user roles, specific data, or system configurations.
- **Example**:
    - `User must be logged in with a 'Premium' account type.`
    - `The shopping cart must contain at least one item from the 'Electronics' category.`

## 4. Steps to Reproduce
- **Rule**: Provide a clear, numbered list of steps required to trigger the bug. Start from a known baseline (e.g., "From the home page...").
- **Rule**: Each step should be a single, clear action.
- **Example**:
    1. `Navigate to the checkout page.`
    2. `Enter valid shipping information.`
    3. `Select 'Credit Card' as the payment method.`
    4. `Fill in all required credit card fields with valid data.`
    5. `Observe the 'Save' button.`

## 5. Test Data
- **Rule**: Provide all relevant data used during testing. This helps developers reproduce the exact scenario.
- **Rule**: Mask or use placeholder data for sensitive information like passwords or API keys.
- **Sections**:
    - **Account**: User account/role used (e.g., `qa_user_1 (role: Admin)`).
    - **Environment**: `DEV`, `STAGE`, or `PROD`.
    - **Links**: Direct links to the agent, pipeline, UI page, etc., where the bug occurred.

## 6. Actual Result
- **Rule**: Describe exactly what happened after executing the steps. Be objective and factual.
- **Example**: `The 'Save' button remains greyed out and is not clickable.`

## 7. Expected Result
- **Rule**: Describe what should have happened if the bug did not exist.
- **Example**: `The 'Save' button should become active and clickable once all required fields are filled with valid data.`

## 8. Attachments
- **Rule**: Always include screenshots or videos. Visual evidence is critical.
- **Screenshots**: Annotate screenshots to highlight the specific UI element or error message.
- **Logs**: If applicable, attach relevant log files or paste snippets. Use code blocks for formatting.

## 9. Notes (optional)
- **Rule**: Include any other relevant information, such as:
    - `Frequency of occurrence (e.g., "Reproduced 5/5 times").`
    - `Potential workarounds.`
    - `Related issues or context.`
    - `Hypotheses about the cause.`

## 10. Labels
- **Rule**: Add appropriate labels to categorize the bug report.
- **Required Labels** (for ALL bug reports):
    - `Type:Bug` - **REQUIRED** for all bug reports to mark the issue as a bug
- **Required Labels** (for SDK toolkit-related bugs):
    - `feat:toolkits` - Indicates this is related to toolkits functionality
    - `eng:sdk` - Indicates this requires SDK engineering work
- **Optional Labels**:
    - `int:{toolkit_name}` - If the bug is specific to a toolkit, add this label with the toolkit name. Examples: `int:github`, `int:jira`, `int:confluence`, `int:gitlab`, etc.
- **Examples**:
    - Bug in GitHub toolkit: Labels should include `Type:Bug`, `feat:toolkits`, `eng:sdk`, `int:github`
    - Bug in JIRA toolkit: Labels should include `Type:Bug`, `feat:toolkits`, `eng:sdk`, `int:jira`
    - General toolkit bug (not specific to one toolkit): Labels should include `Type:Bug`, `feat:toolkits`, `eng:sdk`
    - Non-toolkit bug: Labels should include `Type:Bug` at minimum
---

# Example Bug Reports

*The examples below demonstrate how to apply these guidelines.*

## Example 1 — UI Bug
- **Title**: `[BUG] Pipeline flow does not display selected toolkit after saving`
- **Description**: When a user selects a toolkit for an MCP node and saves the pipeline, the toolkit selection is not displayed in the visual pipeline flow. This causes confusion and can lead to incorrect pipeline edits because the UI does not reflect the stored configuration.
- ... *(continue with the full example as provided in the original template)* ...

## Example 2 — Backend/API Bug
- **Title**: `[BUG] Summarization fails silently when conversation exceeds token threshold`
- **Description**: Summarization triggers successfully but the summary is not created when conversation token count is high. The UI indicates “summarizing” but the final summary is missing, causing users to lose expected output.
- ... *(continue with the full example as provided in the original template)* ...

## Example 3 — Integration/Tooling Bug
- **Title**: `[BUG] Repo update_file tool returns confusing error when target file is missing`
- **Description**: When the automation tool attempts to update a file that does not exist in the target branch, the error message does not explain the root cause or remediation steps, which slows down troubleshooting and reduces automation reliability.
- ... *(continue with the full example as provided in the original template)* ...

