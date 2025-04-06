"""
Demo of File Path Support in Flock Serialization

This example demonstrates:
1. Creating a custom component class
2. Creating a Flock with that component
3. Serializing it to YAML with file paths
4. Loading it back using file path fallback

Usage:
    python file_path_demo.py
"""



from flock.core import (
    Flock,
)



def deserialization():
    """Run the deserialization demo."""
    
  
    try:
        # Attempt to load the Flock
        loaded_flock = Flock.load_from_file("file_path_demo.flock.yaml")
        
        # Test the loaded Flock
        print("\nTesting loaded Flock:")
        result = loaded_flock.run(
            start_agent="greeter",
            input={"name": "File Path User"}
        )
        print(f"Greeting result by the greeting module: {result}")
        
        # Test the person agent
        person_result = loaded_flock.run(
            start_agent="person_creator",
            input={
                "name": "File Path Person",
                "age": 30,
                "languages": ["en", "es"]
            }
        )
        print(f"Person result as Person type: {person_result.person}")
        
        print("\nSuccessfully loaded and executed Flock using file path fallback!")
        
    except Exception as e:
        print(f"Error loading Flock: {e}")
    


if __name__ == "__main__":
    deserialization() 