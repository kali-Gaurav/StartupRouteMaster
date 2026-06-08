import os
import sys
import uvicorn
from dotenv import load_dotenv

def main():
    print("Starting NeuralForge OS...")
    
    # Load root .env file for GEMINI_API_KEY
    root_env = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(root_env):
        load_dotenv(root_env)
        print(f"Loaded environment variables from {root_env}")
    else:
        print(f"Warning: Root .env file not found at {root_env}")
        
    # Check if GEMINI_API_KEY is present
    if not os.getenv("GEMINI_API_KEY"):
        print("\n" + "!" * 60)
        print("WARNING: GEMINI_API_KEY is not set in the environment.")
        print("Please add GEMINI_API_KEY=your_key_here to the .env file.")
        print("!" * 60 + "\n")

    # Change working directory to files_agents so relative paths work
    target_dir = os.path.join(os.path.dirname(__file__), "files_agents")
    if os.path.exists(target_dir):
        os.chdir(target_dir)
        # Add to sys.path so imports work correctly
        sys.path.insert(0, os.getcwd())
    else:
        print(f"Error: {target_dir} not found.")
        sys.exit(1)

    print("Launching Web Dashboard at http://localhost:8000 ...")
    # Start the server
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main()
