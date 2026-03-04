# Test data management scripts

Scripts to copy or delete apps, configs, toolkits, and MCPs between Alita environments (dev, stage, next). Run from this directory so `alita_api_common` is on the path.

**Dependency:** `pip install requests`

---

## Run order (source → target sync)

To mirror source environment onto target, run in this order:

1. **copy_configs.py** — copy configurations (by `alita_title`)
2. **copy_toolkits.py** — copy toolkits (by `toolkit_name`)
3. **copy_mcps.py** — copy MCPs (by `toolkit_name`)
4. **copy_apps.py** — copy applications (by `name`)
5. **link_tools.py** — link toolkits and MCPs to apps on target
6. **link_apps.py** — link nested apps to parent apps on target

Copy scripts use `--source-env`, `--source-project-id`, `--source-token`, `--target-env`, `--target-project-id`, `--target-token`. See each script's docstring for usage.

---

## Delete scripts (single environment)

To clean an environment, run as needed (order does not matter):

- **delete_configs.py** — delete project configs (except ignored types)
- **delete_toolkits.py** — delete all toolkits
- **delete_mcps.py** — delete all MCPs
- **delete_apps.py** — delete all applications

Each uses `--env`, `--project-id`, `--token`.
