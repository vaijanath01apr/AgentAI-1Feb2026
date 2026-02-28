import os
from typing import Optional, List
from pathlib import Path
from phi.agent import Agent
from phi.model.openai import OpenAIChat
from phi.embedder.openai import OpenAIEmbedder
from phi.knowledge.text import TextKnowledgeBase
from phi.vectordb.lancedb import LanceDb, SearchType
from phi.document.chunking.fixed import FixedSizeChunking

    
from dotenv import load_dotenv
load_dotenv()

def create_csv_analyst():
    """csv analyst"""

    # RAG DB
    knowledge_base = TextKnowledgeBase(
        path="./data/sample_article.txt",
        vector_db= LanceDb(
            table_name="sample_csv_chunked_article",
            uri="./tmp/lancedb",
            search_type=SearchType.vector,
            embedder=OpenAIEmbedder(model="text-embedding-3-small")
        ),
        chunking_strategy=FixedSizeChunking(
            chunk_size=1024,
            overlap=50
        )
    )

    knowledge_base.load(recreate=False)

    agent = Agent(
        name="Jarvis",
        model=OpenAIChat(id="gpt-4o"),
        description="You are a helpful AI assistant.",
        instructions=[
            "You are a data analyst assistant.",
            "Always search the knowledge base for relevant data before answering.",
            "Use tables to display data when appropriate.",
            "Provide insights and analysis based on the CSV data.",
            "If you can't find relevant information, say so clearly.",
        ],
        markdown=True,
        debug_mode=True,  
        search_knowledge=True,
        knowledge_base=knowledge_base
    )
    return agent

if __name__ == "__main__":
    agent = create_csv_analyst()
    agent.print_response("which countries john travelled to?", stream=True)