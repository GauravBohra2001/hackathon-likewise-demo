"""Step 0D: verify Azure OpenAI (Foundry) auth with API key only, incl. structured output."""
import json
import os
import sys

from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

api_version = os.environ["AZURE_OPENAI_API_VERSION"]
endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]

print(f"endpoint    = {endpoint}")
print(f"deployment  = {deployment}")
print(f"api_version = {api_version}   (loaded from .env, not hardcoded)")
print()

client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=endpoint,
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
)

print("--- Test 1: plain chat completion ---")
r = client.chat.completions.create(
    model=deployment,
    messages=[{"role": "user", "content": "Reply with exactly the word: CONNECTED"}],
)
print(f"model returned : {r.model}")
print(f"content        : {r.choices[0].message.content!r}")
print(f"finish_reason  : {r.choices[0].finish_reason}")
print(f"usage          : {r.usage}")
print()

print("--- Test 2: structured output (json_schema), used by the extraction node ---")
schema = {
    "type": "object",
    "properties": {
        "operation": {"type": "string",
                      "enum": ["close", "assign", "comment", "bump_priority",
                               "update_status", "delete", "reopen",
                               "tell_customer", "relabel", "status_check"]},
        "destructive": {"type": "boolean"},
        "reversible": {"type": "boolean"},
        "customer_facing": {"type": "boolean"},
        "evidence_of_resolution": {"type": "boolean"},
        "urgency": {"type": "boolean"},
    },
    "required": ["operation", "destructive", "reversible", "customer_facing",
                 "evidence_of_resolution", "urgency"],
    "additionalProperties": False,
}
r2 = client.chat.completions.create(
    model=deployment,
    messages=[
        {"role": "system", "content": "Extract the devops operation described by the Slack message."},
        {"role": "user", "content": "can you close out GH #2, it's a dupe of #1"},
    ],
    response_format={
        "type": "json_schema",
        "json_schema": {"name": "extraction", "schema": schema, "strict": True},
    },
)
raw = r2.choices[0].message.content
print(f"raw content    : {raw}")
print(f"parsed         : {json.dumps(json.loads(raw), indent=2)}")
print(f"finish_reason  : {r2.choices[0].finish_reason}")
print()
print(f"SUCCESS: api_version {api_version} works for both plain and structured output.")
