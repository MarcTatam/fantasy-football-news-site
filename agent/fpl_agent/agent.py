from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm

fpl_agent = Agent(
    model=LiteLlm(model="claude-sonnet-5"),
    name='fpl_agent',
    description='A helpful assistant for solving the user\'s fantasy premier league related questions.',
    instruction='Answer user questions to the best of your knowledge, and using the tools as effectively as possible.',
)
