# Fetcher — ADO Feature Data Extraction Skill

Fetches a complete structured snapshot of an Azure DevOps feature and its full dependency tree, saves it as a JSON artifact, and confirms the filename in a conversational response.

**Use when:** you need structured feature data (fields, description, links, all child work items) for downstream pipelines (readiness, gap analysis, etc.).

## Input

```json
{"id": 1053702}
```

| Parameter            | Default   | Purpose                                 |
|----------------------|-----------|-----------------------------------------|
| `id`                 | required  | ADO work item ID                        |
| `force_reinit`       | `false`   | Re-fetch from ADO                       |
| `load_attachments`   | `true`    | `false` = skip attachments              |
| `load_dependent_items`| `false`  | `true` = fetch child work items         |

## Output

Conversational confirmation, e.g.: *"The data has been fetched and saved to artifact: `1053702_feature.json`"*

## Artifact structure (`{id}_feature.json`)

| Key              | Contents                                                                 |
|------------------|-------------------------------------------------------------------------|
| `feature`        | id, title, state, type, url, description, assigned_to, dates, relations |
| `dependent_items`| All descendants keyed by ID — parent_id, level, title, state, type, description, dates, url (empty if `load_dependent_items: false`) |
| `dependent_links`| URLs from feature description categorised as `wiki`, `item`, `figma`, `other` |

## Usage patterns

| Pattern                        | Input                                                      |
|--------------------------------|------------------------------------------------------------|
| Feature only (default)         | `{"id": 123}`                                             |
| Full fetch with dependencies   | `{"id": 123, "load_dependent_items": true}`              |
| Refresh fields, no attachments | `{"id": 123, "force_reinit": true, "load_attachments": false}` |
| Full refresh with dependencies | `{"id": 123, "force_reinit": true, "load_dependent_items": true}` |
