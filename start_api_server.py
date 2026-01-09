"""
Wrapper script to start uvicorn with proper reload exclusions
"""
import sys
import subprocess
import os

if __name__ == "__main__":
    # Change to project root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Determine which server to start based on argument
    if len(sys.argv) > 1 and sys.argv[1] == "8010":
        # Root API on port 8010
        # Use --reload-dir to only watch specific directories (avoids wildcard expansion issues)
        cmd = [
            sys.executable, "-m", "uvicorn",
            "main_api:app",
            "--host", "0.0.0.0",
            "--port", "8010",
            "--reload",
            "--reload-dir", "app",
            "--reload-dir", "infra",
            "--reload-dir", "handlers",
            "--reload-dir", "domain",
            "--reload-dir", "config",
            "--reload-dir", "hub",
            "--reload-dir", "dtms_integration",
            "--reload-dir", "dtms_core"
        ]
    else:
        # App API on port 8000 (default)
        # Use --reload-dir to only watch specific directories (avoids wildcard expansion issues)
        cmd = [
            sys.executable, "-m", "uvicorn",
            "app.main_api:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload",
            "--reload-dir", "app",
            "--reload-dir", "infra",
            "--reload-dir", "handlers",
            "--reload-dir", "domain",
            "--reload-dir", "config",
            "--reload-dir", "hub",
            "--reload-dir", "dtms_integration",
            "--reload-dir", "dtms_core"
        ]
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

