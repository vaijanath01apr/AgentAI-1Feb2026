from phi.agent import Agent
from phi.model.openai import OpenAIChat
from phi.tools.duckduckgo import DuckDuckGo
from phi.tools.yfinance import YFinanceTools

from dotenv import load_dotenv

load_dotenv()

def create_agent_team():
    """Creates a agent with web search"""
    web_agent = Agent(
        name="Jarvis",
        model=OpenAIChat(id="gpt-4o"),
        description="You are a research assistant that searches the web for information",
        instructions=[
            "Always search for the most recent information.",
            "Include sources in your responses.",
            "Summarize findings clearly.",
        ],
        show_tool_calls=True,
        markdown=True,
        debug_mode=False,
        tools=[DuckDuckGo()]
    )

    finance_agent = Agent(
        name="Financial Analyst",
        role="Analyze financial data and markets",
        model=OpenAIChat(id="gpt-4o"),
        tools=[YFinanceTools(stock_price=True, analyst_recommendations=True)],
        instructions=["Use tables for data"],
        show_tool_calls=True,
        markdown=True,
    )

    team_leader = Agent(
        name="Team Leader",
        model=OpenAIChat(id="gpt-4o"),
        team=[web_agent, finance_agent],
        description="You are a team leader coordinating research tasks.",
        instructions=[
            "Delegate tasks to appropriate team members.",
            "Synthesize information from multiple sources.",
            "Provide comprehensive answers.",
        ],
        show_tool_calls=True,
        markdown=True,
    )

    return team_leader



if __name__ == "__main__":
    agent = create_agent_team()
    agent.print_response("Analyze Microsoft stock performance.", stream=True)