"""
Shared Gemini client via Vertex AI, so LLM calls bill against your GCP project's
Cloud Billing (and therefore your existing credits) using the SAME service account
already granted access to the Google Sheet -- just add it the "Vertex AI User" IAM
role in Cloud Console (IAM & Admin -> your service account -> Add Role).
"""
import json
import os
import tempfile
from google import genai
from src.config import env

_client = None


def get_client() -> genai.Client:
    global _client
    if _client is not None:
        return _client

    # GOOGLE_SERVICE_ACCOUNT_JSON is the same secret used for Sheets access.
    creds_json = env("GOOGLE_SERVICE_ACCOUNT_JSON")
    creds_dict = json.loads(creds_json)
    project_id = env("GOOGLE_CLOUD_PROJECT", required=False, default=creds_dict.get("project_id"))
    location = env("GOOGLE_CLOUD_LOCATION", required=False, default="us-central1")

    # google-genai's Vertex mode reads credentials via GOOGLE_APPLICATION_CREDENTIALS
    # (a file path), so write the service account JSON to a temp file once per process.
    if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write(creds_json)
        tmp.close()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name

    _client = genai.Client(vertexai=True, project=project_id, location=location)
    return _client


MODEL_NAME = "publishers/google/models/gemini-3.6-flash"  # check ai.google.dev/gemini-api/docs/models for current default before relying on this long-term
