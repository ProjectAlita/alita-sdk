"""
Standard ingestion presets for common programming languages and frameworks.

These presets provide sensible defaults for whitelist/blacklist patterns
to efficiently ingest code repositories while excluding unnecessary files.

Usage:
    from alita_sdk.community.inventory.presets import PYTHON_PRESET, JAVASCRIPT_PRESET
    
    result = pipeline.run(
        source='github',
        **PYTHON_PRESET
    )
    
    # Or combine presets
    custom_preset = {
        **PYTHON_PRESET,
        'blacklist': PYTHON_PRESET['blacklist'] + ['**/custom_exclude/**']
    }
"""

# ============================================================================
# PYTHON PRESETS
# ============================================================================

PYTHON_PRESET = {
    'whitelist': [
        '*.py',           # Python source files
        '*.pyi',          # Python stub files
        '*.pyx',          # Cython files
        'requirements.txt',
        'setup.py',
        'pyproject.toml',
        'Pipfile',
    ],
    'blacklist': [
        # Dependencies
        '**/venv/**',
        '**/.venv/**',
        '**/env/**',
        '**/virtualenv/**',
        '**/site-packages/**',
        
        # Build outputs
        '**/build/**',
        '**/dist/**',
        '**/*.egg-info/**',
        
        # Caches
        '**/__pycache__/**',
        '**/.pytest_cache/**',
        '**/.mypy_cache/**',
        '**/.ruff_cache/**',
        '**/.coverage/**',
        '**/htmlcov/**',
        
        # Tests (optional - remove if you want to include tests)
        '**/test_*.py',
        '**/*_test.py',
        '**/tests/**',
        
        # Version control
        '**/.git/**',
        
        # IDE
        '**/.vscode/**',
        '**/.idea/**',
        '**/.pydevproject/**',
    ]
}

PYTHON_PRESET_WITH_TESTS = {
    **PYTHON_PRESET,
    'blacklist': [b for b in PYTHON_PRESET['blacklist'] 
                  if 'test' not in b.lower()]
}

# ============================================================================
# JAVASCRIPT / TYPESCRIPT PRESETS
# ============================================================================

JAVASCRIPT_PRESET = {
    'whitelist': [
        '*.js',
        '*.jsx',
        '*.mjs',
        '*.cjs',
        'package.json',
        'package-lock.json',
        'tsconfig.json',
        'jsconfig.json',
    ],
    'blacklist': [
        # Dependencies
        '**/node_modules/**',
        
        # Build outputs
        '**/dist/**',
        '**/build/**',
        '**/out/**',
        '**/.next/**',
        '**/.nuxt/**',
        '**/.output/**',
        '**/.vercel/**',
        
        # Bundler outputs
        '**/bundle.js',
        '**/bundle.*.js',
        '**/*.min.js',
        
        # Caches
        '**/.cache/**',
        '**/.parcel-cache/**',
        '**/.eslintcache',
        
        # Tests (optional)
        '**/*.test.js',
        '**/*.spec.js',
        '**/__tests__/**',
        '**/tests/**',
        
        # Version control
        '**/.git/**',
        
        # IDE
        '**/.vscode/**',
        '**/.idea/**',
        
        # Config/tooling
        '**/.storybook/**',
    ]
}

TYPESCRIPT_PRESET = {
    'whitelist': [
        '*.ts',
        '*.tsx',
        '*.js',
        '*.jsx',
        '*.mjs',
        '*.cjs',
        'package.json',
        'tsconfig.json',
        '*.d.ts',
    ],
    'blacklist': [
        # Dependencies
        '**/node_modules/**',
        
        # Build outputs
        '**/dist/**',
        '**/build/**',
        '**/out/**',
        '**/lib/**',
        '**/.next/**',
        '**/.nuxt/**',
        
        # TypeScript outputs
        '**/*.js.map',
        '**/*.d.ts.map',
        
        # Caches
        '**/.cache/**',
        '**/.tsbuildinfo',
        '**/.eslintcache',
        
        # Tests (optional)
        '**/*.test.ts',
        '**/*.test.tsx',
        '**/*.spec.ts',
        '**/*.spec.tsx',
        '**/__tests__/**',
        '**/tests/**',
        
        # Version control
        '**/.git/**',
        
        # IDE
        '**/.vscode/**',
        '**/.idea/**',
    ]
}

REACT_PRESET = {
    **TYPESCRIPT_PRESET,
    'blacklist': TYPESCRIPT_PRESET['blacklist'] + [
        '**/public/**',
        '**/static/**',
        '**/*.stories.tsx',
        '**/*.stories.ts',
    ]
}

NEXTJS_PRESET = {
    **TYPESCRIPT_PRESET,
    'blacklist': TYPESCRIPT_PRESET['blacklist'] + [
        '**/.next/**',
        '**/public/**',
    ]
}

# ============================================================================
# JAVA PRESETS
# ============================================================================

JAVA_PRESET = {
    'whitelist': [
        '*.java',
        'pom.xml',
        'build.gradle',
        'settings.gradle',
        'build.gradle.kts',
        'settings.gradle.kts',
    ],
    'blacklist': [
        # Build outputs
        '**/target/**',
        '**/build/**',
        '**/out/**',
        '**/bin/**',
        
        # Dependencies
        '**/.gradle/**',
        '**/.m2/**',
        '**/lib/**',
        
        # IDE
        '**/.idea/**',
        '**/.eclipse/**',
        '**/.settings/**',
        '**/.classpath',
        '**/.project',
        '**/*.iml',
        
        # Tests (optional)
        '**/test/**',
        '**/*Test.java',
        '**/*Tests.java',
        
        # Generated code
        '**/generated/**',
        '**/generated-sources/**',
        '**/generated-test-sources/**',
        
        # Version control
        '**/.git/**',
        
        # Logs
        '**/*.log',
    ]
}

SPRING_BOOT_PRESET = {
    **JAVA_PRESET,
    'whitelist': JAVA_PRESET['whitelist'] + [
        'application.properties',
        'application.yml',
        'application.yaml',
        'application-*.properties',
        'application-*.yml',
    ]
}

MAVEN_PRESET = {
    **JAVA_PRESET,
    'whitelist': JAVA_PRESET['whitelist'] + [
        'pom.xml',
        '**/pom.xml',
    ]
}

GRADLE_PRESET = {
    **JAVA_PRESET,
    'whitelist': JAVA_PRESET['whitelist'] + [
        'build.gradle',
        'build.gradle.kts',
        'settings.gradle',
        'settings.gradle.kts',
        'gradle.properties',
    ]
}

# ============================================================================
# .NET / C# PRESETS
# ============================================================================

DOTNET_PRESET = {
    'whitelist': [
        '*.cs',
        '*.csproj',
        '*.sln',
        '*.vb',
        '*.vbproj',
        '*.fsproj',
        '*.fs',
    ],
    'blacklist': [
        # Build outputs
        '**/bin/**',
        '**/obj/**',
        
        # Dependencies
        '**/packages/**',
        
        # IDE
        '**/.vs/**',
        '**/.vscode/**',
        '**/*.user',
        '**/*.suo',
        
        # Tests (optional)
        '**/*Test.cs',
        '**/*Tests.cs',
        '**/test/**',
        '**/tests/**',
        
        # Version control
        '**/.git/**',
        
        # Logs and temp
        '**/*.log',
        '**/temp/**',
        '**/tmp/**',
    ]
}

CSHARP_PRESET = DOTNET_PRESET

ASPNET_PRESET = {
    **DOTNET_PRESET,
    'whitelist': DOTNET_PRESET['whitelist'] + [
        'appsettings.json',
        'appsettings.*.json',
        'web.config',
        'Program.cs',
        'Startup.cs',
    ]
}

# ============================================================================
# MULTI-LANGUAGE PRESETS
# ============================================================================

FULLSTACK_JS_PRESET = {
    'whitelist': [
        '*.js',
        '*.jsx',
        '*.ts',
        '*.tsx',
        '*.json',
    ],
    'blacklist': [
        '**/node_modules/**',
        '**/dist/**',
        '**/build/**',
        '**/.next/**',
        '**/*.test.js',
        '**/*.test.ts',
        '**/*.spec.js',
        '**/*.spec.ts',
        '**/.git/**',
        '**/.vscode/**',
    ]
}

MONOREPO_PRESET = {
    'whitelist': [
        '*.js',
        '*.jsx',
        '*.ts',
        '*.tsx',
        '*.py',
        '*.java',
        '*.cs',
        'package.json',
        'pom.xml',
        '*.csproj',
    ],
    'blacklist': [
        # Universal excludes
        '**/node_modules/**',
        '**/venv/**',
        '**/.venv/**',
        '**/target/**',
        '**/bin/**',
        '**/obj/**',
        '**/dist/**',
        '**/build/**',
        '**/__pycache__/**',
        '**/.git/**',
        '**/.vscode/**',
        '**/.idea/**',
        
        # Tests
        '**/*test*/**',
        '**/*Test*',
        '**/*test*.*',
    ]
}

# ============================================================================
# DOCUMENTATION PRESETS
# ============================================================================

DOCUMENTATION_PRESET = {
    'whitelist': [
        '*.md',
        '*.mdx',
        '*.rst',
        '*.txt',
        'README*',
        'CHANGELOG*',
        'LICENSE*',
        'CONTRIBUTING*',
    ],
    'blacklist': [
        '**/node_modules/**',
        '**/.git/**',
        '**/build/**',
        '**/dist/**',
    ]
}

# ============================================================================
# PRESET REGISTRY
# ============================================================================

PRESETS = {
    # Python
    'python': PYTHON_PRESET,
    'python-with-tests': PYTHON_PRESET_WITH_TESTS,
    
    # JavaScript/TypeScript
    'javascript': JAVASCRIPT_PRESET,
    'js': JAVASCRIPT_PRESET,
    'typescript': TYPESCRIPT_PRESET,
    'ts': TYPESCRIPT_PRESET,
    'react': REACT_PRESET,
    'nextjs': NEXTJS_PRESET,
    'next': NEXTJS_PRESET,
    
    # Java
    'java': JAVA_PRESET,
    'spring-boot': SPRING_BOOT_PRESET,
    'spring': SPRING_BOOT_PRESET,
    'maven': MAVEN_PRESET,
    'gradle': GRADLE_PRESET,
    
    # .NET
    'dotnet': DOTNET_PRESET,
    'csharp': CSHARP_PRESET,
    'cs': CSHARP_PRESET,
    'aspnet': ASPNET_PRESET,
    
    # Multi-language
    'fullstack-js': FULLSTACK_JS_PRESET,
    'fullstack': FULLSTACK_JS_PRESET,
    'monorepo': MONOREPO_PRESET,
    
    # Documentation
    'docs': DOCUMENTATION_PRESET,
    'documentation': DOCUMENTATION_PRESET,
}


def get_preset(name: str) -> dict:
    """
    Get a preset by name.
    
    Args:
        name: Preset name (e.g., 'python', 'typescript', 'java')
        
    Returns:
        Dictionary with 'whitelist' and 'blacklist' keys
        
    Raises:
        KeyError: If preset name not found
        
    Example:
        preset = get_preset('python')
        result = pipeline.run(source='github', **preset)
    """
    if name not in PRESETS:
        available = ', '.join(sorted(PRESETS.keys()))
        raise KeyError(f"Unknown preset '{name}'. Available presets: {available}")
    return PRESETS[name]


def list_presets() -> list:
    """List all available preset names."""
    return sorted(PRESETS.keys())


def combine_presets(*preset_names: str) -> dict:
    """
    Combine multiple presets into one.
    
    Args:
        *preset_names: Names of presets to combine
        
    Returns:
        Dictionary with merged whitelist and blacklist
        
    Example:
        # Combine Python and JavaScript presets
        preset = combine_presets('python', 'javascript')
        result = pipeline.run(source='github', **preset)
    """
    combined_whitelist = []
    combined_blacklist = []
    
    for name in preset_names:
        preset = get_preset(name)
        combined_whitelist.extend(preset.get('whitelist', []))
        combined_blacklist.extend(preset.get('blacklist', []))
    
    # Remove duplicates while preserving order
    seen_wl = set()
    unique_whitelist = []
    for item in combined_whitelist:
        if item not in seen_wl:
            seen_wl.add(item)
            unique_whitelist.append(item)
    
    seen_bl = set()
    unique_blacklist = []
    for item in combined_blacklist:
        if item not in seen_bl:
            seen_bl.add(item)
            unique_blacklist.append(item)
    
    return {
        'whitelist': unique_whitelist,
        'blacklist': unique_blacklist,
    }
