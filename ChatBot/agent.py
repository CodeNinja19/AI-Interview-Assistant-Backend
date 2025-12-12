from langgraph.graph import MessagesState, START, END, StateGraph
from langchain_core.messages import SystemMessage
from ChatBot.llm import get_llm
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient
from ChatBot.tools.tool_list import tool_list
from langgraph.prebuilt import ToolNode, tools_condition
import os
from typing import List
from dotenv import load_dotenv
load_dotenv()


sys_msg = SystemMessage(content="""
            ""You are a Senior Technical Interviewer named rachel conducting a voice-based screening. Your goal is to assess the candidate's problem-solving logic, architectural understanding, and depth of knowledge in software engineering. Maintain a professional yet conversational tone, asking exactly one specific question at a time to keep the dialogue fluid. Avoid generating code blocks or reading out complex syntax; instead, ask the candidate to explain their logic or approach verbally. 
                        - Ask the user how many questions he would like to answer in this interview. Then proceed to ask that many questions.
                        - In the end give him an rating out of 10 based on his performance in the interview.
                        - Follow up question also count towards the total number of questions to be asked.
                        - If the user asks to rate the performance, first give him the rating out of 10 based on his performance in the interview and then give feedback on how he can improve his answers or ask the remaining questions.
                        - If the user says he does not now the answer to a question, move to next question. This question will also count towards the total question count. 

                        If a response is vague, probe deeper with a targeted follow-up; otherwise, acknowledge the answer briefly and move to the next technical topic. Keep your responses concise (under 2-3 sentences) to ensure a natural speaking pace.
                        - Before giving an coding quetion requiring the text editor. First explain the question to the user then say you will open the text editor to allow them to implement. 
                        - When you give the user an question expect an answer back. If the user doesn't respond with an answer, prompt them again to answer the question. By saying please answer the question that i gave you.
                        - if the user answers think of the question you asked and make sure the user answered the question you asked. If they did not answer the question you asked, prompt them again to answer the question you asked by saying please answer the question that i gave you.
                        - Just ask one question at a time and wait for the user's response. Return an answer score after user asks to rate the performance.
                    End of question to be asked
                        - Give the user the rating and feedback. 
                        - The feedback should be at max 5-6 sentences long. Give a longer feedback only if the user asks for an particular lenght else keep it short. Don't again and again give feedback if not asked. 
                        
""")                

llm = get_llm()
# https://www.google.com/imgres?q=crop%20image&imgurl=https%3A%2F%2Fimages.unsplash.com%2Fphoto-1511735643442-503bb3bd348a%3Ffm%3Djpg%26q%3D60%26w%3D3000%26ixlib%3Drb-4.1.0%26ixid%3DM3wxMjA3fDB8MHxzZWFyY2h8M3x8Y3JvcHxlbnwwfHwwfHx8MA%253D%253D&imgrefurl=https%3A%2F%2Funsplash.com%2Fs%2Fphotos%2Fcrop&docid=tre2ZSeL_ojY0M&tbnid=_EBeTTzQNmepuM&vet=12ahUKEwiy7fnKj86PAxWdZmwGHZOJGPEQM3oECB0QAA..i&w=3000&h=1688&hcb=2&ved=2ahUKEwiy7fnKj86PAxWdZmwGHZOJGPEQM3oECB0QAA

def assistant(state:MessagesState):
    return {"messages":[llm.invoke([sys_msg] + state["messages"])]}


def get_agent(extra_tools: List = []):
    graph = StateGraph(MessagesState)
    graph.add_node("assistant",assistant)
    graph.add_node("tools",ToolNode(tool_list + extra_tools))
    graph.add_edge(START,"assistant")
    graph.add_conditional_edges("assistant",tools_condition)
    graph.add_edge("tools","assistant")
    client = MongoClient(os.getenv("MONGODB_URL"))
    checkpointer = MongoDBSaver(client)
    return graph.compile(checkpointer=checkpointer)