from langchain_openai import ChatOpenAI
import os

model = ChatOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    model="gpt-3.5-turbo-instruct",
    temperature=0.0,
    max_tokens=1000
)