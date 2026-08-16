"""
DeepSeek Harness (`dsh`) — read a Harness session-log swarm into PSA.

DeepSeek Harness (github.com/deepseek-ai/deepseek-harness) writes each session as a
JSONL event log and links subagents by a `parentSession` + `delegationDepth` header.
This turns a directory of those logs into a PSA psyche read of the whole swarm:
postures per agent and how they propagate across the delegation tree.

Install:
    pip install psa-sdk

Run:
    PSA_API_KEY=your-key python examples/deepseek_harness.py /path/to/sessions/<swarm>/
"""
import os
import sys

os.environ.setdefault("PSA_BASE_URL", "https://splabs.io")

from psa.adapters.deepseek_harness import import_deepseek_harness_swarm

path = sys.argv[1] if len(sys.argv) > 1 else "./sessions"
result = import_deepseek_harness_swarm(path)

print(f"graph_id  = {result.graph_id}")
print(f"max_alert = {result.alert}")
print(f"cahs      = {result.cahs}")
print("Inspect the full swarm psyche read at https://splabs.io dashboard.")
