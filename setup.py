"""
Setup script for alita-sdk with custom build hooks.

This setup.py complements pyproject.toml by adding custom build commands
that automatically generate documentation before building the package.
"""

import subprocess
import sys
from pathlib import Path
from setuptools import setup, Command
from setuptools.command.build_py import build_py as _build_py


class GenerateDocsCommand(Command):
    """Custom command to generate documentation files."""

    description = 'Generate tool code and FAQ documentation'
    user_options = []

    def initialize_options(self):
        """Set default values for options."""
        pass

    def finalize_options(self):
        """Post-process options."""
        pass

    def run(self):
        """Run the documentation generation scripts."""
        scripts = [
            'alita_sdk/runtime/utils/docs/generate_tool_code_docs.py',
            'alita_sdk/runtime/utils/docs/fetch_toolkit_faqs.py',
        ]

        for script in scripts:
            script_path = Path(script)
            if not script_path.exists():
                self.warn(f"Script not found: {script}")
                continue

            self.announce(f"Running {script}...", level=2)
            try:
                result = subprocess.run(
                    [sys.executable, str(script_path)],
                    capture_output=True,
                    text=True,
                    check=False
                )

                if result.returncode != 0:
                    self.warn(f"Script {script} returned non-zero exit code: {result.returncode}")
                    if result.stderr:
                        self.warn(f"Error output:\n{result.stderr}")
                    # Don't fail the build, just warn
                else:
                    if result.stdout:
                        self.announce(result.stdout, level=2)
                    self.announce(f"✓ Successfully ran {script}", level=2)

            except Exception as e:
                self.warn(f"Failed to run script {script}: {e}")
                # Don't fail the build, just warn


class CustomBuildPy(_build_py):
    """Custom build command that generates docs before building."""

    def run(self):
        """Run doc generation first, then proceed with normal build."""
        # Run doc generation first
        self.run_command('generate_docs')
        # Then proceed with normal build
        super().run()


setup(
    cmdclass={
        'generate_docs': GenerateDocsCommand,
        'build_py': CustomBuildPy,
    }
)

