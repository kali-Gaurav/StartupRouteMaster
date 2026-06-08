"""
Development server runner
"""
import uvicorn
import os
import sys

if __name__ == "__main__":
    # Set environment variables for development
    os.environ["ENVIRONMENT"] = "development"
    os.environ["LOG_LEVEL"] = "INFO"
    
    # Run the server
    print("🚀 Starting RouteMaster development server...")
    print("📡 API: http://localhost:8000")
    print("📊 Health: http://localhost:8000/health")
    print("📚 Docs: http://localhost:8000/docs")
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info"
    )
