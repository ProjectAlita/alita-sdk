"""
Example usage of the Elitea Postman Toolkit for collection analysis.
"""

import json
from alita_sdk.tools.elitea_postman import PostmanToolkit


def analyze_collection_example():
    """Example of analyzing a Postman collection for quality and best practices."""

    # Initialize toolkit
    toolkit = PostmanToolkit.get_toolkit(
        api_key="your_postman_api_key_here",
        collection_id="your_collection_id_here",
        selected_tools=[
            "get_collections",
            "get_collection",
            "analyze_collection",
            "get_improvement_suggestions"
        ]
    )

    # Get the analysis tool
    analyze_tool = None
    for tool in toolkit.get_tools():
        if "analyze_collection" in tool.name:
            analyze_tool = tool
            break

    if not analyze_tool:
        print("Analysis tool not found")
        return

    # Analyze the collection
    print("Analyzing collection...")
    analysis_result = analyze_tool.run({
        "collection_id": "your_collection_id_here"
    })

    # Parse and display results
    analysis = json.loads(analysis_result)

    print(f"\n=== Collection Analysis Report ===")
    print(f"Collection: {analysis['collection_name']}")
    print(f"Total Requests: {analysis['total_requests']}")
    print(f"Quality Score: {analysis['score']}/100")
    print(f"Security Score: {analysis['overall_security_score']}/100")
    print(f"Performance Score: {analysis['overall_performance_score']}/100")
    print(
        f"Documentation Score: {analysis['overall_documentation_score']}/100")

    print(f"\n=== Issues Found ({len(analysis['issues'])}) ===")
    for issue in analysis['issues']:
        print(f"- [{issue['severity'].upper()}] {issue['message']}")
        print(f"  Location: {issue['location']}")
        if issue.get('suggestion'):
            print(f"  Suggestion: {issue['suggestion']}")
        print()

    print(f"=== Recommendations ===")
    for recommendation in analysis['recommendations']:
        print(f"- {recommendation}")

    # Get improvement suggestions
    print("\n=== Getting Improvement Suggestions ===")
    improvement_tool = None
    for tool in toolkit.get_tools():
        if "get_improvement_suggestions" in tool.name:
            improvement_tool = tool
            break

    if improvement_tool:
        improvements_result = improvement_tool.run({
            "collection_id": "your_collection_id_here"
        })

        improvements = json.loads(improvements_result)

        print(
            f"Found {improvements['improvement_count']} improvement suggestions:")
        for improvement in improvements['improvements']:
            print(f"\n[{improvement['priority'].upper()}] {improvement['title']}")
            print(f"Category: {improvement['category']}")
            print(f"Description: {improvement['description']}")
            print(f"Impact: {improvement['impact']}")


def folder_analysis_example():
    """Example of analyzing a specific folder within a collection."""

    toolkit = PostmanToolkit.get_toolkit(
        api_key="your_postman_api_key_here",
        selected_tools=["analyze_folder", "get_folder_requests"]
    )

    # Analyze a specific folder
    analyze_folder_tool = None
    for tool in toolkit.get_tools():
        if "analyze_folder" in tool.name:
            analyze_folder_tool = tool
            break

    if analyze_folder_tool:
        print("Analyzing folder 'Authentication'...")
        folder_analysis = analyze_folder_tool.run({
            "collection_id": "your_collection_id_here",
            "folder_path": "Authentication"
        })

        analysis = json.loads(folder_analysis)

        for folder in analysis:
            print(f"\n=== Folder Analysis: {folder['name']} ===")
            print(f"Path: {folder['path']}")
            print(f"Request Count: {folder['request_count']}")
            print(f"Consistent Naming: {folder['has_consistent_naming']}")
            print(f"Proper Structure: {folder['has_proper_structure']}")
            print(f"Auth Consistency: {folder['auth_consistency']}")
            print(
                f"Avg Documentation Quality: {folder['avg_documentation_quality']}/100")
            print(f"Avg Security Score: {folder['avg_security_score']}/100")
            print(
                f"Avg Performance Score: {folder['avg_performance_score']}/100")

            if folder['issues']:
                print(f"\nFolder Issues:")
                for issue in folder['issues']:
                    print(f"- [{issue['severity'].upper()}] {issue['message']}")

            print(f"\nRequest Analysis:")
            for request in folder['requests']:
                print(f"  - {request['name']} ({request['method']})")
                print(
                    f"    Auth: {request['has_auth']}, Tests: {request['has_tests']}")
                print(f"    Security: {request['security_score']}/100")
                print(f"    Documentation: {request['documentation_quality']}")
                if request['issues']:
                    print(f"    Issues: {len(request['issues'])}")


if __name__ == "__main__":
    print("Postman Collection Analysis Examples")
    print("====================================")

    # Note: Replace with your actual API key and collection ID
    print("\nRunning collection analysis example...")
    try:
        analyze_collection_example()
    except Exception as e:
        print(f"Error in collection analysis: {e}")
        print("Make sure to replace 'your_postman_api_key_here' and 'your_collection_id_here' with actual values")

    print("\nRunning folder analysis example...")
    try:
        folder_analysis_example()
    except Exception as e:
        print(f"Error in folder analysis: {e}")
        print("Make sure to replace 'your_postman_api_key_here' and 'your_collection_id_here' with actual values")
