import os
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
from scraper import fetch_website_contents   # reuse Class 1's scraper

load_dotenv()

# ① a reusable prompt with a {website} blank
prompt = ChatPromptTemplate.from_template(
    "Give a short, friendly summary of this website:\n\n{website}")

# ② the same model from Class 1, wrapped for LangChain
model = ChatGroq(model="openai/gpt-oss-20b", temperature=0.3)
parser = StrOutputParser()
chain = prompt | model | parser

def summarize(url):
    # ⑤ run it; the dict fills the {website} blank by name
    return chain.invoke({"website": fetch_website_contents(url)})

if __name__ == "__main__":
    print(summarize("https://anthropic.com"))
