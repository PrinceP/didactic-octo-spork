import json

SERVICE_NAME=""
AI_APP_VERSION=""
API_VERSION=""
with open("config.json") as fp:
    version = json.load(fp)
    SERVICE_NAME = version["service_name"]
    AI_APP_VERSION = version["ai_app_version"]
    API_VERSION = version["api_version"]