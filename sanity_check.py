# sanity_check.py
import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from tavily import TavilyClient

load_dotenv()

llm = ChatAnthropic(model="claude-sonnet-4-6", api_key=os.getenv("ANTHROPIC_API_KEY"))
print(llm.invoke("Say hello in one sentence.").content)

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
results = tavily.search(query="latest AI Engineering hiring trends Germany")
print(results["results"][0]["title"])