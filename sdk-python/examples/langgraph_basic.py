"""
LangGraph + PSA — basic integration example.

Install:
    pip install psa-sdk[langgraph] langgraph

Run:
    PSA_API_KEY=your-key python examples/langgraph_basic.py
"""
import os
from typing import TypedDict, Annotated
import operator

os.environ.setdefault("PSA_BASE_URL", "https://splabs.io")

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from psa.adapters.langgraph import PSACallbackHandler


class AgentState(TypedDict):
    messages: Annotated[list, operator.add]


def call_model(state: AgentState) -> AgentState:
    messages = state["messages"]
    # replace with your actual LLM call
    response = AIMessage(content=f"Processed: {messages[-1].content}")
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    return END


workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue)
graph = workflow.compile()

handler = PSACallbackHandler(agent_id="langgraph-demo", agent_role="orchestrator")

result = graph.invoke(
    {"messages": [HumanMessage(content="Hello, what can you do?")]},
    config={"callbacks": [handler]},
)

print("Agent response:", result["messages"][-1].content)
print("PSA trace submitted automatically on graph completion.")
