from typing import Dict, Any, Optional, List

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from models.state import TravelAgentState
from graph import add_message_to_state


class InformationAgent:
    """Information agent for providing travel information, recommendations,
    and destination details — powered by Pinecone RAG when available."""

    def __init__(self, openai_api_key: str, rag_store=None):
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model="gpt-4o-mini",
            temperature=0.3,
        )
        # Optional Pinecone-backed knowledge store (injected from outside)
        self.rag_store = rag_store

        self.query_analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a travel information specialist. Analyse the \
customer's query to understand what type of information they need.

Query types:
- destination_info: Information about a specific place
- travel_tips: Advice on travelling to/from a place
- recommendations: Suggestions for activities, restaurants, hotels
- requirements: Visa, vaccine, or documentation requirements
- general_travel: General travel questions and tips
- weather_seasonal: Weather or best time to visit

Extract:
- destination: The place they are asking about
- query_type: The type of information needed
- timeframe: When they plan to travel
- interests: What they are interested in (beaches, culture, adventure …)

Return a JSON response with these fields."""),
            ("user", "{query}"),
        ])

        self.rag_answer_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a knowledgeable travel guide. \
Use the following retrieved travel knowledge to answer the user's question \
accurately and helpfully. If the retrieved context does not cover the topic \
fully, supplement with your own knowledge but stay factual.

--- Retrieved Knowledge ---
{context}
--- End of Retrieved Knowledge ---

Destination: {destination}
Query type: {query_type}
Travel timeframe: {timeframe}
Interests: {interests}

Give a comprehensive, engaging answer."""),
            ("user", "{query}"),
        ])

        self.recommendation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a travel recommendation expert. \
Use the retrieved travel knowledge below as primary context. \
Provide 3-5 specific, personalised recommendations with brief explanations.

--- Retrieved Knowledge ---
{context}
--- End of Retrieved Knowledge ---

Destination: {destination}
Interests: {interests}
Budget: {budget}
Group: {group}"""),
            ("user", "What do you recommend in {destination}?"),
        ])

        self.travel_tips_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a practical travel advisor. \
Use the retrieved travel knowledge below as primary context and cover:

1. Transportation from airport to city centre
2. Local transport options
3. Money / currency information
4. Communication (SIM cards, WiFi)
5. Cultural etiquette and customs
6. Safety tips
7. Emergency contacts
8. Useful phrases in local language

--- Retrieved Knowledge ---
{context}
--- End of Retrieved Knowledge ---

Destination: {destination}
Travel duration: {duration}"""),
            ("user", "What are the travel tips for {destination}?"),
        ])

        self.output_parser = JsonOutputParser()

    # ------------------------------------------------------------------
    # RAG helper
    # ------------------------------------------------------------------

    def _retrieve_context(self, query: str, top_k: int = 4) -> str:
        """Return a formatted context string from Pinecone (empty if unavailable)."""
        if not self.rag_store:
            return ""
        try:
            docs = self.rag_store.retrieve(query, top_k=top_k)
            if not docs:
                return ""
            return "\n\n---\n\n".join(doc.page_content for doc in docs)
        except Exception as e:
            print(f"[RAG] Retrieval error: {e}")
            return ""

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def provide_information(self, state: TravelAgentState) -> TravelAgentState:
        """Provide travel information based on the customer's query."""
        try:
            analysis_chain = self.query_analysis_prompt | self.llm | self.output_parser
            analysis_result = analysis_chain.invoke({"query": state["current_query"]})

            query_type  = analysis_result.get("query_type", "general_travel")
            destination = analysis_result.get("destination")
            timeframe   = analysis_result.get("timeframe")
            interests   = analysis_result.get("interests", [])

            if query_type == "destination_info":
                return self._provide_destination_info(state, destination, timeframe, interests)
            elif query_type == "recommendations":
                return self._provide_recommendations(state, destination, interests)
            elif query_type == "travel_tips":
                return self._provide_travel_tips(state, destination)
            elif query_type == "requirements":
                return self._provide_requirements_info(state, destination)
            elif query_type == "weather_seasonal":
                return self._provide_weather_info(state, destination, timeframe)
            else:
                return self._provide_general_travel_info(state)

        except Exception as e:
            print(f"Information agent error: {e}")
            return add_message_to_state(
                state,
                "agent",
                "I apologise, but I'm having trouble retrieving that travel "
                "information right now. Could you please rephrase your question "
                "or ask about a specific destination?",
                "information_agent",
            )

    # ------------------------------------------------------------------
    # Private handlers (each now uses RAG context)
    # ------------------------------------------------------------------

    def _provide_destination_info(
        self,
        state: TravelAgentState,
        destination: str,
        timeframe: str,
        interests: List[str],
    ) -> TravelAgentState:
        context = self._retrieve_context(
            f"travel guide {destination} attractions tips culture"
        )

        chain = self.rag_answer_prompt | self.llm
        response = chain.invoke({
            "context":     context,
            "destination": destination or "the location",
            "query_type":  "destination information",
            "timeframe":   timeframe or "unspecified",
            "interests":   ", ".join(interests) if interests else "general tourism",
            "query":       state["current_query"],
        })

        prefix = "📍 " if not context else "📍 [RAG] "
        return add_message_to_state(
            state,
            "agent",
            f"Information Agent: Here's what I know about {destination}:\n\n{response.content}",
            "information_agent",
        )

    def _provide_recommendations(
        self,
        state: TravelAgentState,
        destination: str,
        interests: List[str],
    ) -> TravelAgentState:
        budget = "moderate"
        group  = "general"
        for msg in [m["content"] for m in state["messages"][-5:]]:
            ml = msg.lower()
            if any(w in ml for w in ["luxury", "expensive", "high-end"]):
                budget = "luxury"
            elif any(w in ml for w in ["budget", "cheap", "affordable"]):
                budget = "budget"
            if any(w in ml for w in ["family", "kids", "children"]):
                group = "family"
            elif any(w in ml for w in ["solo", "alone"]):
                group = "solo"

        context = self._retrieve_context(
            f"recommendations activities restaurants things to do {destination}"
        )

        chain = self.recommendation_prompt | self.llm
        response = chain.invoke({
            "context":     context,
            "destination": destination or "your destination",
            "interests":   ", ".join(interests) if interests else "general tourism",
            "budget":      budget,
            "group":       group,
        })

        return add_message_to_state(
            state,
            "agent",
            f"Information Agent: Based on your interests, here are my recommendations "
            f"for {destination}:\n\n{response.content}",
            "information_agent",
        )

    def _provide_travel_tips(
        self,
        state: TravelAgentState,
        destination: str,
    ) -> TravelAgentState:
        context = self._retrieve_context(
            f"travel tips transportation money safety {destination}"
        )

        chain = self.travel_tips_prompt | self.llm
        response = chain.invoke({
            "context":     context,
            "destination": destination or "your destination",
            "duration":    "your trip",
        })

        return add_message_to_state(
            state,
            "agent",
            f"Information Agent: Here are some practical travel tips for {destination}:\n\n{response.content}",
            "information_agent",
        )

    def _provide_requirements_info(
        self,
        state: TravelAgentState,
        destination: str,
    ) -> TravelAgentState:
        context = self._retrieve_context(
            f"visa requirements entry documents health vaccinations {destination}"
        )

        if context:
            chain = self.rag_answer_prompt | self.llm
            response = chain.invoke({
                "context":     context,
                "destination": destination or "your destination",
                "query_type":  "visa and entry requirements",
                "timeframe":   "your travel dates",
                "interests":   "entry requirements",
                "query":       state["current_query"],
            })
            message = (
                f"Information Agent: Here are the requirements for travelling to "
                f"{destination}:\n\n{response.content}"
            )
        else:
            message = f"""Information Agent: Here's requirements information for {destination}:

**Visa Requirements:**
- Check the latest visa requirements on your government's travel website
- Many countries offer visa on arrival or e-visas
- Processing time varies by nationality

**Health Requirements:**
- COVID-19: Check current entry requirements before travel
- Vaccinations: Consult CDC or WHO guidelines for your destination
- Travel insurance is highly recommended

**Documentation:**
- Valid passport (usually 6 months beyond your travel dates)
- Return flight itinerary and hotel booking confirmation
- Proof of sufficient funds

For the most up-to-date information, check:
- Your country's foreign affairs website
- The destination country's embassy website
- IATA Travel Centre (iatatravelcentre.com)"""

        return add_message_to_state(state, "agent", message, "information_agent")

    def _provide_weather_info(
        self,
        state: TravelAgentState,
        destination: str,
        timeframe: str,
    ) -> TravelAgentState:
        context = self._retrieve_context(
            f"weather best time to visit seasons climate {destination}"
        )

        if context:
            chain = self.rag_answer_prompt | self.llm
            response = chain.invoke({
                "context":     context,
                "destination": destination or "your destination",
                "query_type":  "weather and best time to visit",
                "timeframe":   timeframe or "unspecified",
                "interests":   "seasonal weather",
                "query":       state["current_query"],
            })
            message = (
                f"Information Agent: Here's the weather and seasonal information "
                f"for {destination}:\n\n{response.content}"
            )
        else:
            message = f"""Information Agent: Here's weather information for {destination}:

**General Weather Tips:**
- Weather patterns vary significantly by location and season
- Pack layers regardless of destination
- Check weather apps (Weather.com, AccuWeather) for real-time updates
- Consider seasonal events and festivals when planning

For specific forecasts and best visiting times, check:
- Local tourism board websites
- Travel forums for real traveller experiences

Would you like recommendations for the best time to visit {destination} based on your interests?"""

        return add_message_to_state(state, "agent", message, "information_agent")

    def _provide_general_travel_info(self, state: TravelAgentState) -> TravelAgentState:
        context = self._retrieve_context(state["current_query"])

        if context:
            chain = self.rag_answer_prompt | self.llm
            response = chain.invoke({
                "context":     context,
                "destination": "various destinations",
                "query_type":  "general travel",
                "timeframe":   "unspecified",
                "interests":   "general travel advice",
                "query":       state["current_query"],
            })
            return add_message_to_state(
                state,
                "agent",
                f"Information Agent: {response.content}",
                "information_agent",
            )

        return add_message_to_state(
            state,
            "agent",
            """Information Agent: I'd be happy to help with your travel questions! I can provide information about:

**Destinations:** Attractions, culture, practical tips, and recommendations
**Planning:** Visa requirements, best times to visit, transportation options
**Activities:** Tours, experiences, and local highlights
**Practical Advice:** Packing tips, safety information, and local customs

Could you please tell me:
- Which destination you're interested in?
- What type of information you need?
- When you're planning to travel?

This will help me give you the most relevant and useful information!""",
            "information_agent",
        )
