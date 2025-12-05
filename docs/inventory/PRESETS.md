# Inventory Ingestion Presets

This document provides a reference for all available ingestion presets. Presets automatically configure whitelist/blacklist patterns for common programming languages and project types.

## Usage

### List Available Presets

```bash
alita inventory presets
```

### Use a Preset

```bash
# Basic usage
alita inventory ingest --dir ./my-project -g ./graph.json --preset python

# Combine preset with custom patterns
alita inventory ingest --dir ./src -g ./graph.json -p typescript -w "*.json" -x "*backup*"
```

### How Presets Work

1. **Preset patterns are loaded first** from the selected preset
2. **User-provided patterns are appended** (more specific overrides)
3. **Final patterns are passed to the pipeline**

This means you can use a preset as a starting point and customize it with additional patterns.

## Available Presets

### Python

#### `python`
Standard Python project configuration.

- **Whitelist:** `*.py`, `*.pyi`, `requirements.txt`, `setup.py`, `pyproject.toml`
- **Blacklist:** `venv/*`, `env/*`, `.venv/*`, `__pycache__/*`, `*.pyc`, `*.pyo`, `.pytest_cache/*`, `.tox/*`, `dist/*`, `build/*`, `*.egg-info/*`

#### `python-with-tests`
Python project including test files.

- **Whitelist:** Same as `python` + `test_*.py`, `*_test.py`, `conftest.py`
- **Blacklist:** Same as `python`

### JavaScript/TypeScript

#### `javascript`
JavaScript project (Node.js, web apps).

- **Whitelist:** `*.js`, `*.jsx`, `package.json`, `*.json`
- **Blacklist:** `node_modules/*`, `dist/*`, `build/*`, `*.min.js`, `.next/*`, `.nuxt/*`

#### `typescript`
TypeScript project configuration.

- **Whitelist:** `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `tsconfig.json`, `package.json`
- **Blacklist:** `node_modules/*`, `dist/*`, `build/*`, `*.d.ts`, `*.js.map`, `.next/*`

#### `react`
React application (TypeScript/JavaScript).

- **Whitelist:** `*.tsx`, `*.ts`, `*.jsx`, `*.js`, `*.css`, `package.json`
- **Blacklist:** `node_modules/*`, `dist/*`, `build/*`, `public/*`, `.next/*`

#### `nextjs`
Next.js application configuration.

- **Whitelist:** `*.tsx`, `*.ts`, `*.jsx`, `*.js`, `next.config.js`, `package.json`, `app/*`, `pages/*`, `components/*`
- **Blacklist:** `node_modules/*`, `.next/*`, `out/*`, `*.d.ts`, `public/*`

### Java

#### `java`
Standard Java project.

- **Whitelist:** `*.java`, `pom.xml`, `build.gradle`, `*.xml`
- **Blacklist:** `target/*`, `build/*`, `.gradle/*`, `*.class`, `bin/*`

#### `spring-boot`
Spring Boot application.

- **Whitelist:** `*.java`, `application.properties`, `application.yml`, `pom.xml`, `build.gradle`
- **Blacklist:** `target/*`, `build/*`, `.gradle/*`, `*.class`, `bin/*`, `logs/*`

#### `maven`
Maven-based Java project.

- **Whitelist:** `*.java`, `pom.xml`, `*.xml`
- **Blacklist:** `target/*`, `*.class`, `.m2/*`

#### `gradle`
Gradle-based Java project.

- **Whitelist:** `*.java`, `build.gradle`, `build.gradle.kts`, `settings.gradle`, `*.gradle`
- **Blacklist:** `build/*`, `.gradle/*`, `*.class`, `bin/*`

### .NET/C#

#### `dotnet`
.NET project (any language).

- **Whitelist:** `*.cs`, `*.csproj`, `*.sln`, `*.config`, `appsettings.json`
- **Blacklist:** `bin/*`, `obj/*`, `*.dll`, `*.exe`, `.vs/*`, `packages/*`

#### `csharp`
C# project configuration.

- **Whitelist:** `*.cs`, `*.csproj`, `*.sln`
- **Blacklist:** `bin/*`, `obj/*`, `*.dll`, `*.exe`, `.vs/*`

#### `aspnet`
ASP.NET application.

- **Whitelist:** `*.cs`, `*.cshtml`, `*.razor`, `*.csproj`, `appsettings.json`, `Program.cs`, `Startup.cs`
- **Blacklist:** `bin/*`, `obj/*`, `wwwroot/lib/*`, `.vs/*`, `*.dll`

### Multi-Language

#### `fullstack-js`
Full-stack JavaScript/TypeScript (Node.js backend + React/Next.js frontend).

- **Whitelist:** `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `package.json`, `tsconfig.json`, `next.config.js`
- **Blacklist:** `node_modules/*`, `dist/*`, `build/*`, `.next/*`, `public/*`, `*.d.ts`

#### `monorepo`
Monorepo with multiple language support (Python, JS/TS, Java, .NET).

- **Whitelist:** `*.py`, `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `*.java`, `*.cs`, `*.csproj`, `*.sln`, `package.json`, `pom.xml`, `build.gradle`, `pyproject.toml`, `requirements.txt`, `tsconfig.json`
- **Blacklist:** `node_modules/*`, `venv/*`, `target/*`, `dist/*`, `build/*`, `bin/*`, `obj/*`, `__pycache__/*`

#### `documentation`
Documentation files only.

- **Whitelist:** `*.md`, `*.rst`, `*.txt`, `*.html`, `docs/*`, `README*`, `CHANGELOG*`
- **Blacklist:** `node_modules/*`, `venv/*`, `build/*`, `dist/*`

## Combining Presets

You can combine multiple presets programmatically:

```python
from alita_sdk.community.inventory import combine_presets

# Combine Python and documentation presets
config = combine_presets('python', 'documentation')
```

## Creating Custom Presets

If you need a custom preset, you can:

1. **Use the base preset and add patterns:**
   ```bash
   alita inventory ingest --dir ./src -g ./graph.json \
     --preset python \
     -w "*.yaml" \
     -x "*_backup*"
   ```

2. **Create a preset in your project** (for programmatic use):
   ```python
   from alita_sdk.community.inventory import IngestionPipeline
   
   custom_preset = {
       'whitelist': ['*.py', '*.yaml', '*.json'],
       'blacklist': ['test_*', '*_backup*']
   }
   
   pipeline.run(
       source='my-source',
       whitelist=custom_preset['whitelist'],
       blacklist=custom_preset['blacklist']
   )
   ```

## Pattern Syntax

Patterns use glob syntax:

- `*.py` - Match all Python files
- `**/*.py` - Match Python files in any subdirectory
- `test_*` - Match files starting with "test_"
- `*_test.py` - Match files ending with "_test.py"
- `node_modules/*` - Match everything in node_modules directory
- `*.{js,ts}` - Match both .js and .ts files

## Best Practices

1. **Start with a preset** - Use language-specific presets as a baseline
2. **Add custom patterns** - Extend presets with project-specific needs
3. **Test incrementally** - Use `--limit 10` to test patterns on small batches
4. **Check stats** - Run `alita inventory stats` to verify ingestion results
5. **Use blacklist liberally** - Exclude build artifacts, dependencies, and generated files

## Examples

### Python Django Project
```bash
alita inventory ingest \
  --dir ./django-project \
  -g ./graph.json \
  --preset python \
  -w "*.html" \
  -w "*.css" \
  -x "*migrations/*"
```

### TypeScript Monorepo
```bash
alita inventory ingest \
  --dir ./monorepo \
  -g ./graph.json \
  --preset monorepo \
  -x "packages/*/dist/*" \
  -x "apps/*/build/*"
```

### Java Spring Boot with Docs
```bash
alita inventory ingest \
  --dir ./spring-app \
  -g ./graph.json \
  --preset spring-boot \
  -w "*.md" \
  -w "docs/**/*.md"
```

### React + Node.js Full Stack
```bash
alita inventory ingest \
  --dir ./fullstack-app \
  -g ./graph.json \
  --preset fullstack-js \
  -x "frontend/build/*" \
  -x "backend/uploads/*"
```
