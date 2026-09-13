.PHONY: headline eval reset demo

# Reproduces the exact headline numbers reported in the reliability brief:
# cautious 88.9% disagreement / 1 unsafe-act, trusting 77.8% / 1, overall 78.3%.
# Runs against the preserved 23-example, 5-field extraction cache. No git checkout needed.
headline:
	./.venv/bin/python -m eval.loo --config data/extracted_headline_config.json

# Runs the gate against the CURRENT cache (26 examples, 7-field schema).
eval:
	./.venv/bin/python -m eval.loo

# Restores the seeded Slack/GitHub/Linear sandbox to its Step 0 state.
reset:
	./.venv/bin/python -m scripts.reset_sandbox
