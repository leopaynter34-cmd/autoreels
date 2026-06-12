"""Entry point for Railway deployment."""
import uvicorn
import os
import sys

# Make sure pipeline is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"Starting AutoReels on port {port}")
    uvicorn.run("website.app:app", host="0.0.0.0", port=port)
