# WI Fetcher — ADO Work Item Data Extraction Skill

Fetches a single Azure DevOps work item with its parent, predecessors, categorized links, and comments, saves it as a JSON artifact, and returns a structured summary report.

**Use when:** you need detailed work item data including relational context (parent, predecessors) and comments for analysis, reporting, or downstream processing.

## Input

```json
{"id": 123456}
```

| Parameter            | Type   | Default                                                                                           | Purpose                                    |
|----------------------|--------|---------------------------------------------------------------------------------------------------|--------------------------------------------|
| `id`                 | int    | required                                                                                          | ADO work item ID (positive integer)        |
| `relations_include`  | list   | `[]`                                                                                              | Specific relation types to include         |
| `relations_exclude`  | list   | `["System.LinkTypes.Hierarchy-Forward", "System.LinkTypes.Dependency-Forward", "System.LinkTypes.Related"]` | Relation types to exclude                  |

### Relation Types

**Default behavior** (when `relations_include` is empty):
- ✅ **Include:** Parent (`System.LinkTypes.Hierarchy-Reverse`), Predecessors (`System.LinkTypes.Dependency-Reverse`)
- ❌ **Exclude:** Children (`Hierarchy-Forward`), Successors (`Dependency-Forward`), Related items

**Custom filtering:**
- Set `relations_include` to override defaults and fetch only specified types
- Set `relations_exclude` to block specific types (applied after include filter)

## Output

Conversational summary report with extraction statistics:

```markdown
✅ Successfully fetched work item and saved to artifact: **123456_work_item.json**

## Work Item Summary

**ID:** 123456
**Title:** Implement user authentication
**State:** Active
**Type:** User Story

## Extracted Data

✓ **Parent:** Found (ID: 123400)
✓ **Predecessors:** 2 found
✓ **Comments:** 5 found

## Links Found
  - Wiki: 3
  - Work Items: 2
  - Figma: 1
  - Other: 1
```

## Artifact Structure

File: `{id}_work_item.json`

```json
{
  "work_item": {
    "id": 123456,
    "url": "https://...",
    "title": "Implement user authentication",
    "state": "Active",
    "work_item_type": "User Story",
    "description": "Clean text (HTML stripped)",
    "acceptance_criteria": "Clean text (HTML stripped)",
    "assigned_to": {
      "name": "John Doe",
      "email": "john.doe@example.com"
    },
    "created_by": {
      "name": "Jane Smith",
      "email": "jane.smith@example.com"
    },
    "changed_by": {
      "name": "John Doe",
      "email": "john.doe@example.com"
    },
    "created_date": "2025-01-15T10:30:00Z",
    "changed_date": "2025-03-20T14:45:00Z",
    "comment_count": 5
  },
  "parent": {
    "id": 123400,
    "title": "Authentication Module",
    "state": "Active",
    "work_item_type": "Feature",
    "description": "...",
    "url": "https://...",
    "assigned_to": {...},
    "created_date": "...",
    "changed_date": "...",
    "comment_count": 2,
    "comments": [
      {
        "id": 1,
        "text": "Comment text",
        "created_by": {"name": "...", "email": "..."},
        "created_date": "..."
      }
    ]
  },
  "predecessors": [
    {
      "id": 123450,
      "title": "Design authentication flow",
      "state": "Closed",
      "work_item_type": "Task",
      "description": "...",
      "url": "https://...",
      "assigned_to": {...},
      "created_date": "...",
      "changed_date": "...",
      "comment_count": 0,
      "comments": []
    }
  ],
  "links": {
    "wiki": [
      "https://dev.azure.com/org/project/_wiki/wikis/auth-design"
    ],
    "item": [
      "https://dev.azure.com/org/project/_workitems/edit/123400"
    ],
    "figma": [
      "https://figma.com/file/abc123/auth-mockups"
    ],
    "other": [
      "https://example.com/api-spec"
    ]
  },
  "comments": [
    {
      "id": 1,
      "text": "Updated acceptance criteria based on security review",
      "created_by": {
        "name": "John Doe",
        "email": "john.doe@example.com"
      },
      "created_date": "2025-03-18T09:15:00Z"
    }
  ]
}
```

### Artifact Field Reference

| Section       | Description                                                                                  |
|---------------|----------------------------------------------------------------------------------------------|
| `work_item`   | Requested work item with all core fields, HTML stripped from description/acceptance criteria |
| `parent`      | Parent work item data (same structure as `work_item`, includes comments if any exist)        |
| `predecessors`| Array of predecessor work items (each with same structure, includes comments if any)         |
| `other_relations` | Array of other relation types if `relations_include` specifies additional types      |
| `links`       | Links from work item description, categorized by type (wiki, work item, figma, other)        |
| `comments`    | Top-level work item comments (array of {id, text, created_by, created_date})                 |

**Note:** Empty arrays and null values are omitted from the output for cleaner JSON.

## Usage Examples

### Example 1: Standard fetch (parent + predecessors)
```json
{"id": 123456}
```
**Fetches:** Work item + parent + predecessors + comments + categorized links  
**Artifact:** `123456_work_item.json`

### Example 2: Work item only (no relations)
```json
{
  "id": 123456,
  "relations_exclude": [
    "System.LinkTypes.Hierarchy-Forward",
    "System.LinkTypes.Hierarchy-Reverse",
    "System.LinkTypes.Dependency-Forward",
    "System.LinkTypes.Dependency-Reverse",
    "System.LinkTypes.Related"
  ]
}
```
**Fetches:** Work item + comments + links only (no parent, no predecessors)

### Example 3: Include specific relations
```json
{
  "id": 123456,
  "relations_include": ["System.LinkTypes.Hierarchy-Reverse", "System.LinkTypes.Related"]
}
```
**Fetches:** Work item + parent + related items (no predecessors)

### Example 4: Custom exclude filter
```json
{
  "id": 123456,
  "relations_exclude": ["System.LinkTypes.Dependency-Reverse"]
}
```
**Fetches:** Work item + parent (predecessors excluded, but parent included by default)

## Link Categorization

Links extracted from `System.Description` are automatically categorized:

| Category | Pattern Match                                           |
|----------|---------------------------------------------------------|
| `wiki`   | Contains `/_wiki/` or `/wiki/`                          |
| `item`   | Contains `workitem=`, `/_workitems/`, or `/workItems/`  |
| `figma`  | Contains `figma.com`                                    |
| `other`  | All other HTTP/HTTPS/FTP URLs                           |

HTML tags are stripped from description and acceptance criteria text for cleaner output.

## Error Handling

**Validation errors** return a formatted error message without execution:

| Error Condition           | Message Example                                                   |
|---------------------------|-------------------------------------------------------------------|
| Missing `id` parameter    | `Missing required field 'id'. Expected: {"id": 123}`              |
| Invalid `id` type/value   | `Invalid ID: "abc". Must be a positive integer.`                  |
| Malformed JSON            | `Invalid JSON. Expected: {"id": 123}\nReceived: "{id: 123}"`      |
| Empty input               | `Input required. Provide JSON: {"id": 123}`                       |

## Technical Details

- **Toolkits used:** `LFAADOBoardReader` (get_work_item, get_comments), `ADOartifactstorage` (createFile)
- **Processing:** Pure code nodes (no LLM inference) for speed and cost efficiency
- **HTML handling:** All HTML content stripped using regex, entities unescaped
- **User data:** Only name and email extracted from ADO user objects
- **Performance:** Optimized with conditional comment fetching (only when `comment_count > 0`)
