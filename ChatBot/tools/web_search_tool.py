from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.tools import tool
from dotenv import load_dotenv
import os
load_dotenv()

TAVILY_API_KEY=os.getenv("TAVILY_API_KEY")

@tool
def web_search(query: str) -> dict | str:
    """
    Perform a web search using Tavily and return the top results.
    Use this tool when you don't have any information about the query.
    Args:
        query (str): The search query.

    Returns:
        str: The top search result.
    """
    tavily_search = TavilySearchResults(max_results=3)
    search_docs = tavily_search.invoke(query)
    # print("Web search results:", search_docs)
    return search_docs if search_docs else "No results found."