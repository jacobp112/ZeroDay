import sys
import os
import uvicorn

# Add src to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

if __name__ == "__main__":
    print("Starting API on 8001...")
    try:
        from brokerage_parser.api import app
        uvicorn.run(app, host="127.0.0.1", port=8001, log_level="info")
    except Exception as e:
        print(f"FAILED TO START: {e}")
        import traceback
        traceback.print_exc()
