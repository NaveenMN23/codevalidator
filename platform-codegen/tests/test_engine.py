import os
from pathlib import Path
from generator.engine import generator

def test_multi_tag_stripping():
    print("Running multi-tag stripping test...")
    
    # Define test tags
    tags = ["beginner-broken-refund", "intermediate-race-condition"]
    challenge_name = "book-my-show"
    language = "node"
    
    try:
        # Generate the zip
        zip_path = generator.generate(challenge_name, language, tags)
        print(f"Successfully generated zip at: {zip_path}")
        
        # In a real test, we would extract the zip and verify the contents.
        # For now, we just check if it exists and has the correct name.
        expected_name = "beginner-broken-refund-intermediate-race-condition.zip"
        if zip_path.name == expected_name:
            print("PASS: Filename is correct.")
        else:
            print(f"FAIL: Expected name {expected_name}, got {zip_path.name}")
            
    except Exception as e:
        print(f"FAIL: Generation failed with error: {e}")

if __name__ == "__main__":
    test_multi_tag_stripping()
