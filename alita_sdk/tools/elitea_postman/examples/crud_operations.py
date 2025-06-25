"""
Example usage of the Elitea Postman Toolkit for CRUD operations.
"""

import json
from alita_sdk.tools.elitea_postman import PostmanToolkit


def collection_management_example():
    """Example of creating, updating, and managing collections."""

    toolkit = PostmanToolkit.get_toolkit(
        api_key="your_postman_api_key_here",
        selected_tools=[
            "create_collection",
            "update_collection",
            "duplicate_collection",
            "get_collections"
        ]
    )

    # Create a new collection
    create_tool = None
    for tool in toolkit.get_tools():
        if "create_collection" in tool.name:
            create_tool = tool
            break

    if create_tool:
        print("Creating new collection...")
        new_collection = create_tool.run({
            "name": "My API Test Collection",
            "description": "A test collection created via the Elitea Postman Toolkit",
            "variables": [
                {
                    "key": "base_url",
                    "value": "https://api.example.com",
                    "type": "string",
                    "description": "Base URL for API requests"
                },
                {
                    "key": "api_version",
                    "value": "v1",
                    "type": "string",
                    "description": "API version"
                }
            ],
            "auth": {
                "type": "bearer",
                "bearer": [
                    {
                        "key": "token",
                        "value": "{{auth_token}}",
                        "type": "string"
                    }
                ]
            }
        })

        result = json.loads(new_collection)
        collection_id = result["collection"]["id"] if "collection" in result else None
        print(f"Created collection with ID: {collection_id}")

        # Update the collection
        if collection_id:
            update_tool = None
            for tool in toolkit.get_tools():
                if "update_collection" in tool.name:
                    update_tool = tool
                    break

            if update_tool:
                print("Updating collection...")
                update_result = update_tool.run({
                    "collection_id": collection_id,
                    "description": "Updated description with more details about the API endpoints",
                    "variables": [
                        {
                            "key": "base_url",
                            "value": "https://api.example.com",
                            "type": "string",
                            "description": "Base URL for API requests"
                        },
                        {
                            "key": "api_version",
                            "value": "v2",
                            "type": "string",
                            "description": "Updated API version"
                        },
                        {
                            "key": "timeout",
                            "value": "30000",
                            "type": "string",
                            "description": "Request timeout in milliseconds"
                        }
                    ]
                })
                print("Collection updated successfully")


def folder_and_request_management_example():
    """Example of creating and managing folders and requests."""

    toolkit = PostmanToolkit.get_toolkit(
        api_key="your_postman_api_key_here",
        collection_id="your_collection_id_here",
        selected_tools=[
            "create_folder",
            "create_request",
            "update_request",
            "move_request",
            "duplicate_request"
        ]
    )

    # Create folders
    create_folder_tool = None
    for tool in toolkit.get_tools():
        if "create_folder" in tool.name:
            create_folder_tool = tool
            break

    if create_folder_tool:
        print("Creating folder structure...")

        # Create main API folder
        create_folder_tool.run({
            "collection_id": "your_collection_id_here",
            "name": "User Management",
            "description": "All user-related API endpoints",
            "auth": {
                "type": "bearer",
                "bearer": [
                    {
                        "key": "token",
                        "value": "{{user_token}}",
                        "type": "string"
                    }
                ]
            }
        })

        # Create nested folder
        create_folder_tool.run({
            "collection_id": "your_collection_id_here",
            "name": "Authentication",
            "description": "User authentication endpoints",
            "parent_path": "User Management"
        })

    # Create requests
    create_request_tool = None
    for tool in toolkit.get_tools():
        if "create_request" in tool.name:
            create_request_tool = tool
            break

    if create_request_tool:
        print("Creating API requests...")

        # Create login request
        create_request_tool.run({
            "collection_id": "your_collection_id_here",
            "folder_path": "User Management/Authentication",
            "name": "User Login",
            "method": "POST",
            "url": "{{base_url}}/{{api_version}}/auth/login",
            "description": "Authenticate user and return access token",
            "headers": [
                {
                    "key": "Content-Type",
                    "value": "application/json",
                    "description": "Request content type"
                },
                {
                    "key": "Accept",
                    "value": "application/json",
                    "description": "Expected response format"
                }
            ],
            "body": {
                "mode": "raw",
                "raw": json.dumps({
                    "email": "user@example.com",
                    "password": "password123"
                }, indent=2),
                "options": {
                    "raw": {
                        "language": "json"
                    }
                }
            },
            "tests": """
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Response has token", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('token');
    pm.expect(jsonData.token).to.be.a('string');
    
    // Set token as environment variable
    pm.environment.set("auth_token", jsonData.token);
});

pm.test("Response time is less than 2000ms", function () {
    pm.expect(pm.response.responseTime).to.be.below(2000);
});
            """.strip(),
            "pre_request_script": """
// Clear any existing auth token
pm.environment.unset("auth_token");

console.log("Attempting to authenticate user...");
            """.strip()
        })

        # Create get user profile request
        create_request_tool.run({
            "collection_id": "your_collection_id_here",
            "folder_path": "User Management",
            "name": "Get User Profile",
            "method": "GET",
            "url": "{{base_url}}/{{api_version}}/users/profile",
            "description": "Retrieve the authenticated user's profile information",
            "headers": [
                {
                    "key": "Authorization",
                    "value": "Bearer {{auth_token}}",
                    "description": "Bearer authentication token"
                },
                {
                    "key": "Accept",
                    "value": "application/json",
                    "description": "Expected response format"
                }
            ],
            "tests": """
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Profile has required fields", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('id');
    pm.expect(jsonData).to.have.property('email');
    pm.expect(jsonData).to.have.property('name');
    pm.expect(jsonData).to.have.property('created_at');
});

pm.test("Response time is less than 1000ms", function () {
    pm.expect(pm.response.responseTime).to.be.below(1000);
});
            """.strip()
        })

        # Create update user request
        create_request_tool.run({
            "collection_id": "your_collection_id_here",
            "folder_path": "User Management",
            "name": "Update User Profile",
            "method": "PUT",
            "url": "{{base_url}}/{{api_version}}/users/profile",
            "description": "Update the authenticated user's profile information",
            "headers": [
                {
                    "key": "Authorization",
                    "value": "Bearer {{auth_token}}",
                    "description": "Bearer authentication token"
                },
                {
                    "key": "Content-Type",
                    "value": "application/json",
                    "description": "Request content type"
                },
                {
                    "key": "Accept",
                    "value": "application/json",
                    "description": "Expected response format"
                }
            ],
            "body": {
                "mode": "raw",
                "raw": json.dumps({
                    "name": "Updated User Name",
                    "bio": "This is my updated bio",
                    "preferences": {
                        "theme": "dark",
                        "notifications": True
                    }
                }, indent=2),
                "options": {
                    "raw": {
                        "language": "json"
                    }
                }
            },
            "tests": """
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Profile was updated", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('updated_at');
    
    // Verify the updated fields
    pm.expect(jsonData.name).to.eql("Updated User Name");
    pm.expect(jsonData.bio).to.eql("This is my updated bio");
});

pm.test("Response time is less than 1500ms", function () {
    pm.expect(pm.response.responseTime).to.be.below(1500);
});
            """.strip()
        })


def search_and_organize_example():
    """Example of searching for requests and organizing collections."""

    toolkit = PostmanToolkit.get_toolkit(
        api_key="your_postman_api_key_here",
        collection_id="your_collection_id_here",
        selected_tools=[
            "search_requests",
            "get_folder_requests",
            "move_request",
            "duplicate_request"
        ]
    )

    # Search for authentication-related requests
    search_tool = None
    for tool in toolkit.get_tools():
        if "search_requests" in tool.name:
            search_tool = tool
            break

    if search_tool:
        print("Searching for authentication requests...")
        search_results = search_tool.run({
            "collection_id": "your_collection_id_here",
            "query": "auth",
            "search_in": "all",
            "method": "POST"
        })

        results = json.loads(search_results)
        print(f"Found {results['results_count']} authentication requests:")

        for result in results['results']:
            print(
                f"- {result['name']} ({result['method']}) at {result['path']}")

    # Get requests from a specific folder
    get_folder_requests_tool = None
    for tool in toolkit.get_tools():
        if "get_folder_requests" in tool.name:
            get_folder_requests_tool = tool
            break

    if get_folder_requests_tool:
        print("\nGetting requests from User Management folder...")
        folder_requests = get_folder_requests_tool.run({
            "collection_id": "your_collection_id_here",
            "folder_path": "User Management",
            "include_details": True
        })

        requests = json.loads(folder_requests)
        print(f"Found {requests['request_count']} requests in folder:")

        for request in requests['requests']:
            print(f"- {request['name']} ({request['method']})")
            if request.get('description'):
                print(f"  Description: {request['description']}")
            print(f"  Headers: {len(request.get('headers', []))}")
            print(f"  Has Tests: {len(request.get('tests', [])) > 0}")


if __name__ == "__main__":
    print("Postman Collection Management Examples")
    print("=====================================")

    # Note: Replace with your actual API key and collection ID
    print("\nRunning collection management example...")
    try:
        collection_management_example()
    except Exception as e:
        print(f"Error in collection management: {e}")
        print("Make sure to replace 'your_postman_api_key_here' with actual API key")

    print("\nRunning folder and request management example...")
    try:
        folder_and_request_management_example()
    except Exception as e:
        print(f"Error in folder/request management: {e}")
        print("Make sure to replace API key and collection ID with actual values")

    print("\nRunning search and organize example...")
    try:
        search_and_organize_example()
    except Exception as e:
        print(f"Error in search and organize: {e}")
        print("Make sure to replace API key and collection ID with actual values")
