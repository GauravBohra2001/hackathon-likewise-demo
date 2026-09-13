"""Step 0C part 1: simplest possible Linear query to verify auth + discover team id."""
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

KEY = os.environ["LINEAR_API_KEY"]
URL = "https://api.linear.app/graphql"

resp = requests.post(
    URL,
    headers={"Authorization": KEY, "Content-Type": "application/json"},
    json={"query": "{ teams { nodes { id name key } } }"},
    timeout=30,
)
print(f"--- POST https://api.linear.app/graphql -> HTTP {resp.status_code} ---")
print(json.dumps(resp.json(), indent=2))
