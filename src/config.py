"""Shared configuration: env loading, Azure OpenAI client, fixtures."""
import json
import os
from functools import lru_cache

from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

REQUIRED = [
    "SLACK_BOT_TOKEN", "SLACK_TEST_CHANNEL_ID",
    "GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_REPO",
    "LINEAR_API_KEY", "LINEAR_TEST_TEAM_ID",
    "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_DEPLOYMENT", "AZURE_OPENAI_API_VERSION",
]


def require(name):
    val = (os.getenv(name) or "").strip()
    if not val:
        raise SystemExit(
            f"MISSING CREDENTIAL: {name} is not set in .env. "
            f"Stopping rather than falling back to a mock."
        )
    return val


@lru_cache(maxsize=1)
def llm_client():
    """Azure OpenAI client. API key auth only - no DefaultAzureCredential."""
    return AzureOpenAI(
        api_version=require("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=require("AZURE_OPENAI_ENDPOINT"),
        api_key=require("AZURE_OPENAI_API_KEY"),
    )


def deployment():
    return require("AZURE_OPENAI_DEPLOYMENT")


@lru_cache(maxsize=1)
def fixtures():
    with open("fixtures.json") as f:
        return json.load(f)
