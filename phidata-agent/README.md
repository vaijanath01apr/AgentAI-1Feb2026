# Phidata Agent

A collection of AI agents built with [Phidata](https://github.com/phidatahq/phidata) and OpenAI's GPT-4o model.

## Overview

This project contains multiple AI agents named **Jarvis** built using the Phidata framework. Each agent demonstrates a different capability, from basic conversational AI to web-search-powered research assistants.

## Prerequisites

- Python 3.8+
- An OpenAI API key

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd phidata-agent
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the `phidata-agent` directory:

```bash
touch .env
```

Add your OpenAI API key:

```
OPENAI_API_KEY=your_openai_api_key_here
```

## Running the Project

### Run the basic agent

```bash
python basic.py
```

Sends the prompt `"What is the capital of France?"` to the agent and prints the response.

### Run the web search agent

```bash
python websearch_agent.py
```

Runs a research-focused agent that searches the web via DuckDuckGo. It streams the response to the terminal for the query `"What are the latest AI developments?"`, with sources included in the output.

## Project Structure

```
phidata-agent/
├── basic.py              # Basic conversational agent
├── websearch_agent.py    # Web search agent using DuckDuckGo
├── requirements.txt      # Python dependencies
└── .env                  # Environment variables (not committed)
```

## Dependencies

| Package           | Purpose                        |
|-------------------|--------------------------------|
| `phidata`         | Agent framework                |
| `openai`          | GPT-4o model integration       |
| `duckduckgo-search` | Web search tool              |
| `yfinance`        | Financial data tool            |
| `newspaper4k`     | News article extraction tool   |
| `python-dotenv`   | Load environment variables     |
| `lancedb`         | Vector database                |
| `sqlalchemy`      | SQL database ORM               |
