# TestRail

### Tool configuration

```json
{
    "url": "https://your-custom-domain.testrail.io/",
    "email": "<your_email>",
    "password": "<your_token>"
}
```

### Case Properties
When `add_case` method is used it is possible to pass test case steps. Based on `template ID` (default is 1) which should be also specified there are a few different combinations:
- Template ID 1 - Text
```json
{
    "template_id": 1,
    "custom_preconds": "My preconditions",
    "custom_steps": "My test steps",
    "custom_expected": "My expected final results"
}
```
OR
- Template ID 2 - Steps
```json
{
    "template_id": 2,
    "custom_preconds": "My preconditions",
    "custom_steps_separated": [
        {
            "content": "Step 1",
            "expected": "Expected Result 1"
        },
        {
            "content": "Step 2",
            "expected": "Expected Result 2"
        },
        {
            "shared_step_id": 3
        },
    ]
}
```
