@bitbucket @file @update @functional
Feature: Update file content in Bitbucket repository
  The system must allow users to modify existing files so that code can be maintained and improved.

  # Original Input Context (preserved)
  # Test name: Tool - Update File
  # Test type: functional
  # Test Data:
  #   Branch: "{{branch_name}}"
  #   File Path: "{{file_path}}"
  #   Updated Content: Enhanced authentication module with error handling

  Background:
    Given I am an authenticated Bitbucket user with repository write access
    And the file "{{file_path}}" exists in branch "{{branch_name}}"

  Scenario: Successfully update file content
    When I update the file "{{file_path}}" in branch "{{branch_name}}" with new content:
      """
      // User Authentication Login Module with Error Handling
      class LoginManager {
        constructor() {
          this.isAuthenticated = false;
          this.lastError = null;
        }
        
        async authenticate(username, password) {
          try {
            if (!username || !password) {
              throw new Error('Username and password are required');
            }
            return this.validateCredentials(username, password);
          } catch (error) {
            this.lastError = error.message;
            return false;
          }
        }
        
        validateCredentials(username, password) {
          // Enhanced validation implementation
          return username && password && username.length > 0 && password.length >= 8;
        }
        
        getLastError() {
          return this.lastError;
        }
      }
      
      module.exports = LoginManager;
      """
    Then the file should be updated successfully
    And I can read the updated file content
    And the updated content should include "getLastError()" method

  # EXPECTED OUTPUT (preserved):
  # A confirmation message stating the file was updated successfully.
  # The agent should verify this by reading the updated file content and confirming changes.