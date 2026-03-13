// Groovy build script for testing AlitaTextLoader
// Tests loading of Groovy source code as text content

package com.example.test

import groovy.transform.CompileStatic
import java.nio.file.Files
import java.nio.file.Paths

/**
 * Sample Groovy class for text loader testing
 * Contains various Groovy syntax elements
 */
@CompileStatic
class TestBuildScript {
    
    // Properties
    String projectName = "TestProject"
    String version = "1.0.0"
    List<String> dependencies = ['commons-io', 'jackson-databind', 'slf4j-api']
    
    // Configuration closure
    def configure(Closure config) {
        config.delegate = this
        config()
    }
    
    // Method with GString interpolation
    String getProjectInfo() {
        return "Project: ${projectName}, Version: ${version}"
    }
    
    // Closure example
    def processFiles = { String dir ->
        def files = new File(dir).listFiles()
        files?.each { file ->
            println "Processing: ${file.name}"
        }
    }
    
    // Map and collection operations
    def buildConfig = [
        sourceCompatibility: '1.8',
        targetCompatibility: '1.8',
        encoding: 'UTF-8'
    ]
    
    // Test method with assertions
    def runTests() {
        assert projectName != null : "Project name must be set"
        assert version ==~ /\d+\.\d+\.\d+/ : "Version must follow semantic versioning"
        
        dependencies.each { dep ->
            println "Checking dependency: ${dep}"
        }
    }
    
    // Static method
    static void printBanner() {
        println """
        ╔═══════════════════════════════╗
        ║   Groovy Build Script Test   ║
        ║     Version 1.0.0            ║
        ╚═══════════════════════════════╝
        """.stripIndent()
    }
}

// Script execution
def script = new TestBuildScript()
script.configure {
    projectName = "AlitaTextLoaderTest"
    version = "2.0.0-SNAPSHOT"
}

// Unicode and special characters in Groovy
def messages = [
    'English': 'Hello World',
    'Spanish': 'Hola Mundo',
    'French': 'Bonjour le monde',
    'Chinese': '你好世界',
    'Japanese': 'こんにちは世界',
    'Emoji': 'Testing 🚀 with émoji ✨'
]

messages.each { lang, msg ->
    println "${lang}: ${msg}"
}

// File operations
def writeTestFile = { String path, String content ->
    try {
        Files.write(Paths.get(path), content.bytes)
        println "✓ File written successfully"
    } catch (Exception e) {
        println "✗ Error: ${e.message}"
    }
}

// Return statement
return "Groovy script execution completed successfully! 🎉"
