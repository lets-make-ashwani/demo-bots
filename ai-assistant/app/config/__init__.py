import os
from dotenv import load_dotenv

# Load dotenv to read ENVIRONMENT
load_dotenv()

env = os.getenv("ENVIRONMENT", "development").lower()

if env == "production":
    from app.config.production import ProductionSettings
    settings = ProductionSettings()
else:
    from app.config.development import DevelopmentSettings
    settings = DevelopmentSettings()
