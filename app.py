"""
OpenHands Backend optimized for Hugging Face Spaces deployment
Final fixed version that handles all import issues
"""
import os
import sys
import logging
import uvicorn
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_hf_environment():
    """Setup environment variables for Hugging Face Spaces"""
    
    # Core HF Spaces configuration
    os.environ.setdefault("PORT", "7860")
    os.environ.setdefault("HOST", "0.0.0.0")
    os.environ.setdefault("OPENHANDS_RUNTIME", "local")  # Use local runtime, not docker
    os.environ.setdefault("CORS_ALLOWED_ORIGINS", "*")
    
    # Use memory-based storage to avoid file permission issues
    os.environ["SETTINGS_STORE_TYPE"] = "memory"
    os.environ["SECRETS_STORE_TYPE"] = "memory"
    os.environ["CONVERSATION_STORE_TYPE"] = "memory"
    os.environ["FILE_STORE"] = "memory"
    os.environ["SESSION_STORE_TYPE"] = "memory"
    
    # Disable security and auth for public API
    os.environ["DISABLE_SECURITY"] = "true"
    os.environ["OPENHANDS_DISABLE_AUTH"] = "true"
    os.environ["SECURITY_CONFIRMATION_MODE"] = "false"
    
    # Disable file-based features that might cause issues
    os.environ["DISABLE_FILE_LOGGING"] = "true"
    os.environ["DISABLE_PERSISTENT_SESSIONS"] = "true"
    os.environ["SERVE_FRONTEND"] = "false"
    
    # Set reasonable defaults for public usage
    os.environ.setdefault("MAX_ITERATIONS", "30")
    os.environ.setdefault("DEFAULT_AGENT", "CodeActAgent")
    
    # LLM configuration - use OpenRouter by default
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("⚠️  LLM_API_KEY or OPENROUTER_API_KEY not set. Please set it in HF Spaces environment variables.")
        logger.warning("⚠️  Without API key, the backend will start but LLM calls will fail.")
    else:
        logger.info("✅ LLM API key found")
    
    # Fixed model name format for OpenRouter (remove openrouter/ prefix)
    os.environ.setdefault("LLM_MODEL", "anthropic/claude-3.5-sonnet")
    os.environ.setdefault("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    
    # Create directories if they don't exist
    directories = ["/tmp/openhands", "/tmp/cache", "/tmp/workspace", "/tmp/file_store"]
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    logger.info("✅ Environment configured for Hugging Face Spaces")

def check_dependencies():
    """Check if critical dependencies are available"""
    missing_deps = []
    
    try:
        import fastapi
        logger.info("✅ FastAPI available")
    except ImportError:
        missing_deps.append("fastapi")
    
    try:
        import uvicorn
        logger.info("✅ Uvicorn available")
    except ImportError:
        missing_deps.append("uvicorn")
    
    try:
        import litellm
        logger.info("✅ LiteLLM available")
    except ImportError:
        missing_deps.append("litellm")
    
    # Check optional dependencies
    try:
        import docker
        logger.info("⚠️  Docker available (not needed for HF Spaces)")
    except ImportError:
        logger.info("✅ Docker not available (expected for HF Spaces)")
    
    # Google Cloud is COMPLETELY OPTIONAL - no login required, no API key needed
    # This is just for informational purposes only
    try:
        import google.api_core
        logger.info("⚠️  Google Cloud available (OPTIONAL - not needed for basic functionality)")
    except ImportError:
        logger.info("✅ Google Cloud not available (PERFECTLY FINE - no login/API key required)")
    
    if missing_deps:
        logger.error(f"❌ Missing critical dependencies: {missing_deps}")
        return False
    
    return True

if __name__ == "__main__":
    try:
        logger.info("🔧 Setting up Hugging Face environment...")
        setup_hf_environment()
        
        logger.info("🔍 Checking dependencies...")
        if not check_dependencies():
            logger.error("❌ Critical dependencies missing. Cannot start server.")
            sys.exit(1)
        
        logger.info("📦 Importing OpenHands app...")
        from openhands.server.app import app
        
        # Get configuration
        port = int(os.getenv("PORT", 7860))
        host = os.getenv("HOST", "0.0.0.0")
        
        # Startup information
        print("\n" + "="*50)
        print("🤗 OpenHands Backend for Hugging Face Spaces")
        print("="*50)
        print(f"🚀 Server: {host}:{port}")
        print(f"🔑 LLM API Key: {'✅ Set' if os.getenv('LLM_API_KEY') else '❌ Missing'}")
        print(f"🤖 LLM Model: {os.getenv('LLM_MODEL', 'Not configured')}")
        print(f"🏃 Runtime: {os.getenv('OPENHANDS_RUNTIME', 'local')}")
        print("📡 API Endpoints available at /docs")
        print("="*50 + "\n")
        
        logger.info("🚀 Starting uvicorn server...")
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=True
        )
        
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.error("💡 This usually means a required dependency is missing.")
        logger.error("💡 Check that all dependencies in requirements.txt are installed.")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)