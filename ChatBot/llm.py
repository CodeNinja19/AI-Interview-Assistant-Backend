from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from ChatBot.tools.tool_list import tool_list


def get_llm():
    # llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash",temperature=0.5)
    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        temperature=0,
        max_tokens=None,
        reasoning_format="parsed",
        timeout=None,
        max_retries=2,
    )
    return llm.bind_tools(tool_list)
