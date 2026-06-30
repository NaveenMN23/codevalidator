import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from services.compile_validator import compile_validator, CompileValidationError

files_java = {
    "pom.xml": """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>demo</artifactId>
    <version>0.0.1-SNAPSHOT</version>
    
    <properties>
        <maven.compiler.source>21</maven.compiler.source>
        <maven.compiler.target>21</maven.compiler.target>
    </properties>
</project>
""",
    "src/main/java/com/example/Main.java": """
package com.example;

public class Main {
    public static void main(String[] args) {
        System.out.println("Hello World!");
        // Syntax error below
        invalid_code()
    }
}
"""
}

def test_java():
    print("Testing Java Compile Validation...")
    try:
        compile_validator.validate_compilation(files_java, "java")
        print("FAIL: Should have raised CompileValidationError")
    except CompileValidationError as e:
        print("PASS: Caught expected CompileValidationError")
        print(e)

if __name__ == "__main__":
    test_java()
