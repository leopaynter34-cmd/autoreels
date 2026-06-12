"""Run the AutoReels web server."""
import uvicorn

if __name__ == "__main__":
    print("\n🚀 AutoReels server starting...")
    print("   Open http://localhost:8000 in your browser\n")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
