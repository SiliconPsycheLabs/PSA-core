"""
CrewAI + PSA — basic integration example.

Install:
    pip install psa-sdk[crewai] crewai

Run:
    PSA_API_KEY=your-key python examples/crewai_basic.py
"""
import os
os.environ.setdefault("PSA_BASE_URL", "https://splabs.io")

from crewai import Agent, Task, Crew
from psa.adapters.crewai import PSAObserver

researcher = Agent(
    role="Researcher",
    goal="Research the given topic thoroughly",
    backstory="Expert researcher with broad knowledge",
    verbose=False,
)

writer = Agent(
    role="Writer",
    goal="Write clear, concise summaries",
    backstory="Technical writer specializing in AI topics",
    verbose=False,
)

research_task = Task(
    description="Research the current state of AI agent frameworks",
    expected_output="A brief summary of the top 3 frameworks",
    agent=researcher,
)

write_task = Task(
    description="Write a 2-paragraph summary based on the research",
    expected_output="A clear 2-paragraph summary",
    agent=writer,
)

observer = PSAObserver(agent_id="crewai-demo")

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    observers=[observer],
    verbose=False,
)

result = crew.kickoff()
print("Crew output:", result)
print("PSA trace submitted automatically on crew completion.")
