"""
Script to fetch FAQ documentation from GitHub and create local FAQ files.

Run this script to populate the alita_sdk/tools/docs/faq/ directory with FAQ content
from the official documentation repository.

Usage:
    python fetch_toolkit_faqs.py
"""

import urllib.request
import urllib.error
import re
from pathlib import Path
import sys

# Base URL for toolkit documentation
BASE_URL = "https://raw.githubusercontent.com/ProjectAlita/projectalita.github.io/main/docs/integrations/toolkits"

# All toolkits to fetch FAQ for
TOOLKITS = [
    # Inner
    'artifact',
    # ADO sub-toolkits
    'ado_repos', 'ado_wiki', 'ado_work_item', 'ado_test_plan',
    # Version control
    'github', 'gitlab', 'gitlab_org', 'bitbucket', 'localgit',
    # Issue tracking
    'jira', 'advanced_jira_mining',
    # Test management
    'qtest', 'testrail', 'xray', 'zephyr', 'zephyr_scale', 'zephyr_squad',
    'zephyr_enterprise', 'zephyr_essential', 'testio', 'rally', 'report_portal',
    # Documentation
    'confluence', 'sharepoint',
    # Communication
    'slack', 'gmail', 'yagmail',
    # Enterprise
    'servicenow', 'salesforce',
    # Design
    'figma',
    # API tools
    'postman', 'openapi', 'custom_open_api',
    # Cloud
    'aws', 'azure_ai', 'carrier',
    # Security
    'keycloak',
    # Data
    'elastic', 'google', 'pandas', 'sql',
    # Documents
    'pptx', 'ocr'
]


def fetch_faq(toolkit_name):
    """
    Fetch FAQ section from toolkit documentation on GitHub.

    Args:
        toolkit_name: Name of the toolkit

    Returns:
        FAQ content as string, or None if not found
    """
    doc_url = f"{BASE_URL}/{toolkit_name}_toolkit.md"

    try:
        with urllib.request.urlopen(doc_url, timeout=10) as response:
            if response.status == 200:
                content = response.read().decode('utf-8')

                # Extract FAQ or FAQs section
                # Updated regex to match both "## FAQ" and "## FAQs"
                faq_pattern = r'##\s+FAQs?\s*\n(.*?)(?=\n##\s+|\Z)'
                match = re.search(faq_pattern, content, re.IGNORECASE | re.DOTALL)

                if match:
                    return match.group(1).strip()
                else:
                    return None
            return None

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        else:
            print(f"    HTTP error {e.code}")
            return None
    except Exception as e:
        print(f"    Error: {e}")
        return None


def save_faq(toolkit_name, faq_content, output_dir):
    """
    Save FAQ content to a local markdown file with header and GitHub documentation link.

    Args:
        toolkit_name: Name of the toolkit
        faq_content: FAQ content to save
        output_dir: Directory to save the file in

    Returns:
        True if successful, False otherwise
    """
    try:
        output_file = output_dir / f"{toolkit_name}.md"

        # Build GitHub documentation URL
        github_doc_url = f"https://github.com/ProjectAlita/projectalita.github.io/blob/main/docs/integrations/toolkits/{toolkit_name}_toolkit.md"

        # Format toolkit name for display (capitalize and replace underscores)
        display_name = toolkit_name.replace('_', ' ').title()

        with open(output_file, 'w', encoding='utf-8') as f:
            # Write header with title and GitHub link
            f.write(f"# {display_name} Toolkit FAQ\n\n")
            f.write(f"**Official Documentation**: [{display_name} Toolkit Guide]({github_doc_url})\n\n")
            f.write("---\n\n")
            # Write FAQ content
            f.write(faq_content)

        return True
    except Exception as e:
        print(f"    Error saving: {e}")
        return False


def main():
    """Main execution function."""

    # Use relative path from script location instead of importing alita_sdk
    # This allows the script to work during build when package isn't installed
    # Script is at: alita_sdk/runtime/utils/docs/fetch_toolkit_faqs.py
    # Need to go up to: alita_sdk/
    script_dir = Path(__file__).parent  # alita_sdk/runtime/utils/docs/
    sdk_root = script_dir.parent.parent.parent  # alita_sdk/
    faq_dir = sdk_root / 'docs' / 'faq'

    # Create FAQ directory if it doesn't exist
    faq_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("Fetching FAQ Documentation from GitHub")
    print("=" * 80)
    print(f"Target directory: {faq_dir}")
    print(f"Total toolkits to fetch: {len(TOOLKITS)}")
    print("=" * 80)
    print()

    success_count = 0
    failed_count = 0
    no_faq_count = 0

    for i, toolkit in enumerate(TOOLKITS, 1):
        print(f"[{i}/{len(TOOLKITS)}] {toolkit:30s} ", end='', flush=True)

        faq = fetch_faq(toolkit)

        if faq:
            if save_faq(toolkit, faq, faq_dir):
                print(f"✓ Saved ({len(faq):,} chars)")
                success_count += 1
            else:
                print("✗ Save failed")
                failed_count += 1
        else:
            print("⊘ No FAQ section found")
            no_faq_count += 1

    print()
    print("=" * 80)
    print("Summary:")
    print(f"  ✓ Successfully saved:  {success_count}")
    print(f"  ⊘ No FAQ found:        {no_faq_count}")
    print(f"  ✗ Failed:              {failed_count}")
    print(f"  Total processed:       {len(TOOLKITS)}")
    print("=" * 80)
    print()

    if success_count > 0:
        print(f"FAQ files saved to: {faq_dir}")
        print()
        print("You can now use offline FAQ support!")
        print("The FAQ fetcher will automatically use local files when available.")

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

