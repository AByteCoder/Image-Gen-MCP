"""Google GenAI client initialization.

Selects between service-account (Vertex AI) and API-key authentication
based on environment configuration from ``config``. The resulting
``client`` singleton is imported by other modules that call the GenAI API.
"""

from google import genai
from google.oauth2 import service_account

from image_gen_mcp.config import GEMINI_API_KEY, SERVICE_ACCOUNT_FILE, VERTEX_LOCATION

if SERVICE_ACCOUNT_FILE:
    _credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    client: genai.Client = genai.Client(
        credentials=_credentials,
        vertexai=True,
        project=_credentials.project_id,
        location=VERTEX_LOCATION,
    )
else:
    client: genai.Client = genai.Client(api_key=GEMINI_API_KEY)
