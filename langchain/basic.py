import os

from langchain_openai import ChatOpenAI

# from langchain_anthropic import ChatAnthropic
# from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
# from langchain_core.runnables import RunnablePassthrough

from dotenv import load_dotenv


load_dotenv()

# temperature 0-1 0 Strict, 1 Creative
llm = ChatOpenAI(temperature=0.3, model="gpt-5.1")

# llm = ChatAnthropic(temperature=0.3, model="")
# llm = ChatGoogleGenerativeAI(temperature=0.3, model="")

def demo_basic_prompt():

    template = """
    You are a helpful assistant who always replies cheerfully and with emojis 😄🎉
    Question: {question}
    Answer:
    """

    prompt = PromptTemplate(
        input_variables=["question"],
        template=template
    )

    chain = prompt | llm | StrOutputParser()

    result = chain.invoke({"question": "What is Agentic AI?"})
    print(result)

if __name__ == "__main__":
    demo_basic_prompt()