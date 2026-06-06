import asyncio
from agent_system.mcp_server import mcp
from agent_system.agents.orchestrator import Orchestrator
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # In a real setup, we would run the MCP server as a separate process
    # and the agents would connect to it via stdio or SSE.
    # For this demo, we'll just show the Orchestrator.
    
    orchestrator = Orchestrator()
    task = "Find the latest articles about AI and analyze them."
    
    print(f"User Request: {task}")
    response = await orchestrator.run(task)
    print(f"Orchestrator Response: {response}")

if __name__ == "__main__":
    asyncio.run(main())
