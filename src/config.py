"""
Configuration management for the AgentMail chatbot.
"""
import os
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "config", ".env"))

logger = logging.getLogger(__name__)

@dataclass
class AgentMailConfig:
    """AgentMail API configuration."""
    api_key: str
    inbox_name: str = "GroupTripBot"
    inbox_display_name: str = "Group Trip Coordinator Bot"

@dataclass
class AIConfig:
    """AI API configuration."""
    provider: str = "openai"  # "openai" or "google"
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    openai_model: str = "gpt-3.5-turbo"
    google_model: str = "gemini-pro"
    max_tokens: int = 500
    temperature: float = 0.7

@dataclass
class WebhookConfig:
    """Webhook server configuration."""
    url: str
    port: int = 8000
    host: str = "0.0.0.0"

@dataclass
class AppConfig:
    """Application configuration."""
    debug: bool = False
    log_level: str = "INFO"
    default_itinerary_id: Optional[str] = None

class Settings:
    """Application settings manager."""
    
    def __init__(self):
        """Initialize settings from environment variables."""
        self.agentmail = self._load_agentmail_config()
        self.ai = self._load_ai_config()
        self.webhook = self._load_webhook_config()
        self.app = self._load_app_config()
        
        # Validate required settings
        self._validate_config()
        
        # Configure logging
        self._configure_logging()
    
    def _load_agentmail_config(self) -> AgentMailConfig:
        """Load AgentMail configuration from environment."""
        api_key = os.getenv("AGENTMAIL_API_KEY")
        if not api_key:
            raise ValueError("AGENTMAIL_API_KEY environment variable is required")
        
        return AgentMailConfig(
            api_key=api_key,
            inbox_name=os.getenv("INBOX_NAME", "GroupTripBot"),
            inbox_display_name=os.getenv("INBOX_DISPLAY_NAME", "Group Trip Coordinator Bot")
        )
    
    def _load_ai_config(self) -> AIConfig:
        """Load AI configuration from environment."""
        provider = os.getenv("AI_PROVIDER", "openai").lower()
        
        openai_key = os.getenv("OPENAI_API_KEY")
        google_key = os.getenv("GOOGLE_API_KEY")
        
        if provider == "google" and not google_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required when using Google AI")
        elif provider == "openai" and not openai_key:
            raise ValueError("OPENAI_API_KEY environment variable is required when using OpenAI")
        
        return AIConfig(
            provider=provider,
            openai_api_key=openai_key,
            google_api_key=google_key,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            google_model=os.getenv("GOOGLE_MODEL", "gemini-1.5-flash"),
            max_tokens=int(os.getenv("MAX_TOKENS", "500")),
            temperature=float(os.getenv("TEMPERATURE", "0.7"))
        )
    
    def _load_webhook_config(self) -> WebhookConfig:
        """Load webhook configuration from environment."""
        webhook_url = os.getenv("WEBHOOK_URL")
        if not webhook_url:
            raise ValueError("WEBHOOK_URL environment variable is required")
        
        return WebhookConfig(
            url=webhook_url,
            port=int(os.getenv("WEBHOOK_PORT", "8000")),
            host=os.getenv("WEBHOOK_HOST", "0.0.0.0")
        )
    
    def _load_app_config(self) -> AppConfig:
        """Load application configuration from environment."""
        return AppConfig(
            debug=os.getenv("DEBUG", "False").lower() in ("true", "1", "yes"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            default_itinerary_id=os.getenv("DEFAULT_ITINERARY_ID")
        )
    
    def _validate_config(self):
        """Validate configuration settings."""
        # Validate AI models
        if self.ai.provider == "openai":
            valid_models = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo-preview"]
            if self.ai.openai_model not in valid_models:
                logger.warning(f"OpenAI model {self.ai.openai_model} may not be valid. Valid models: {valid_models}")
        elif self.ai.provider == "google":
            valid_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.5-flash-lite", "gemini-pro", "gemini-pro-vision"]
            if self.ai.google_model not in valid_models:
                logger.warning(f"Google model {self.ai.google_model} may not be valid. Valid models: {valid_models}")
        
        # Validate temperature
        if not 0 <= self.ai.temperature <= 2:
            raise ValueError("AI temperature must be between 0 and 2")
        
        # Validate max tokens
        if self.ai.max_tokens <= 0:
            raise ValueError("AI max_tokens must be positive")
        
        # Validate webhook URL
        if not self.webhook.url.startswith(("http://", "https://")):
            raise ValueError("Webhook URL must start with http:// or https://")
        
        # Validate port
        if not 1 <= self.webhook.port <= 65535:
            raise ValueError("Webhook port must be between 1 and 65535")
    
    def _configure_logging(self):
        """Configure application logging."""
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        
        logging.basicConfig(
            level=getattr(logging, self.app.log_level, logging.INFO),
            format=log_format,
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler("./logs/log.txt")
            ]
        )
        
        # Set specific logger levels
        if self.app.debug:
            logging.getLogger("agentmail").setLevel(logging.DEBUG)
            logging.getLogger("chatbot_engine").setLevel(logging.DEBUG)
            logging.getLogger("webhook_server").setLevel(logging.DEBUG)
    
    def get_env_template(self) -> str:
        """
        Generate environment template for configuration.
        
        Returns:
            Template string for .env file
        """
        return """# AgentMail Configuration
AGENTMAIL_API_KEY=your_agentmail_api_key_here
INBOX_NAME=GroupTripBot
INBOX_DISPLAY_NAME=Group Trip Coordinator Bot

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4
MAX_TOKENS=500
TEMPERATURE=0.7

# Webhook Configuration
WEBHOOK_URL=https://your-backend.com/webhook
WEBHOOK_PORT=8000
WEBHOOK_HOST=0.0.0.0

# Application Settings
DEBUG=False
LOG_LEVEL=INFO
DEFAULT_ITINERARY_ID=your_default_itinerary_id_here
"""

# Global settings instance
settings = None

def get_settings() -> Settings:
    """
    Get global settings instance.
    
    Returns:
        Settings instance
    """
    global settings
    if settings is None:
        settings = Settings()
    return settings

def reload_settings():
    """Reload settings from environment variables."""
    global settings
    settings = Settings()

# Environment validation functions
def check_required_env_vars() -> tuple[bool, list[str]]:
    """
    Check if all required environment variables are set.
    
    Returns:
        Tuple of (all_present, missing_vars)
    """
    base_required_vars = [
        "AGENTMAIL_API_KEY",
        "WEBHOOK_URL"
    ]
    
    ai_provider = os.getenv("AI_PROVIDER", "openai").lower()
    required_vars = base_required_vars.copy()
    
    if ai_provider == "google":
        required_vars.append("GOOGLE_API_KEY")
    else:
        required_vars.append("OPENAI_API_KEY")
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    return len(missing) == 0, missing

def setup_config_file(config_dir: str = None):
    """
    Set up configuration file from template.
    
    Args:
        config_dir: Directory to create config file in
    """
    if config_dir is None:
        config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
    
    env_file_path = os.path.join(config_dir, ".env")
    example_file_path = os.path.join(config_dir, ".env.example")
    
    # Create .env from example if it doesn't exist
    if not os.path.exists(env_file_path) and os.path.exists(example_file_path):
        import shutil
        shutil.copy2(example_file_path, env_file_path)
        logger.info(f"Created {env_file_path} from template")
        logger.warning("Please edit the .env file with your actual API keys and configuration")
    
    # Create example file if it doesn't exist
    if not os.path.exists(example_file_path):
        with open(example_file_path, "w") as f:
            f.write(Settings().get_env_template())
        logger.info(f"Created {example_file_path} template")

# Configuration validation decorators
def require_agentmail_config(func):
    """Decorator to ensure AgentMail configuration is available."""
    def wrapper(*args, **kwargs):
        try:
            settings = get_settings()
            if not settings.agentmail.api_key:
                raise ValueError("AgentMail API key not configured")
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"AgentMail configuration error: {e}")
            raise
    return wrapper

def require_ai_config(func):
    """Decorator to ensure AI configuration is available."""
    def wrapper(*args, **kwargs):
        try:
            settings = get_settings()
            if settings.ai.provider == "openai" and not settings.ai.openai_api_key:
                raise ValueError("OpenAI API key not configured")
            elif settings.ai.provider == "google" and not settings.ai.google_api_key:
                raise ValueError("Google AI API key not configured")
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"AI configuration error: {e}")
            raise
    return wrapper