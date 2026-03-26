# import os
# from dotenv import load_dotenv
# from langchain_openai import ChatOpenAI
# from langchain_core.prompts import ChatPromptTemplate

# from app.prompts.mvp_prompt import SYSTEM_PROMPT

# load_dotenv()

# prompt = ChatPromptTemplate.from_messages([
#     ("system", SYSTEM_PROMPT),
#     ("human", "{user_input}")
# ])

# llm = ChatOpenAI(
#     api_key=os.getenv("OPENAI_API_KEY"),
#     base_url=os.getenv("OPENAI_BASE_URL"),
#     model=os.getenv("MODEL_NAME"),
#     temperature=0.2
# )

# chain = prompt | llm
from pathlib import Path
from dotenv import dotenv_values
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.prompts.mvp_prompt import SYSTEM_PROMPT

# 直接读取项目根目录下的 .env 文件
ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT_DIR / ".env"
config = dotenv_values(ENV_PATH)

api_key = config.get("OPENAI_API_KEY")
base_url = config.get("OPENAI_BASE_URL")
model_name = config.get("MODEL_NAME")

print("ENV_PATH =", ENV_PATH)
print("ENV exists =", ENV_PATH.exists())
print("OPENAI_API_KEY exists =", bool(api_key))
print("OPENAI_BASE_URL =", base_url)
print("MODEL_NAME =", model_name)

if not api_key:
    raise ValueError("没有读取到 OPENAI_API_KEY，请检查 .env")
if not model_name:
    raise ValueError("没有读取到 MODEL_NAME，请检查 .env")

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{user_input}")
])

llm = ChatOpenAI(
    api_key=api_key,
    base_url=base_url,
    model=model_name,
    temperature=0.2
)

chain = prompt | llm