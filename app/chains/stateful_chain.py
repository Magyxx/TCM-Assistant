import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.prompts.stateful_prompt import SYSTEM_PROMPT

load_dotenv()

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "当前已有问诊状态如下：\n{current_state}\n\n用户本轮输入：\n{user_input}")
])

llm = ChatOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
    model=os.getenv("MODEL_NAME"),
    temperature=0.2,
    model_kwargs={"response_format": {"type": "json_object"}}
)

chain = prompt | llm