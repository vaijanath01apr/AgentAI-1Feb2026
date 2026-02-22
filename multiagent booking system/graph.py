from langgraph.graph import StateGraph, END
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import os

from models.state import TravelAgentState, ConversationMessage, CustomerInfo, TravelBooking
from utils.graph_utils import create_initial_state, resume_state, add_message_to_state, update_state_field


class TravelMultiAgentGraph:
    """Main graph class for the travel customer management multi-agent system"""

    def __init__(self, openai_api_key: str = None):
        if openai_api_key is None:
            openai_api_key = os.getenv("OPENAI_API_KEY")

        if not openai_api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass it directly.")

        # Import agents here to avoid circular imports
        from agents import RouterAgent, BookingAgent, ComplaintAgent, InformationAgent

        # ── Pinecone RAG store (optional — degrades gracefully if not configured) ──
        rag_store = None
        pinecone_api_key = os.getenv("PINECONE_API_KEY")
        pinecone_index   = os.getenv("PINECONE_INDEX_NAME", "travel-knowledge")
        if pinecone_api_key:
            try:
                from rag import TravelKnowledgeStore
                rag_store = TravelKnowledgeStore(
                    openai_api_key=openai_api_key,
                    pinecone_api_key=pinecone_api_key,
                    index_name=pinecone_index,
                )
                rag_store.connect()
                print(f"[RAG] Pinecone store connected (index: {pinecone_index})")
            except Exception as e:
                print(f"[RAG] Pinecone unavailable — information agent will use LLM only. Error: {e}")
                rag_store = None
        else:
            print("[RAG] PINECONE_API_KEY not set — information agent will use LLM only")

        # Initialize agents
        self.router_agent      = RouterAgent(openai_api_key)
        self.booking_agent     = BookingAgent(openai_api_key)
        self.complaint_agent   = ComplaintAgent(openai_api_key)
        self.information_agent = InformationAgent(openai_api_key, rag_store=rag_store)

        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(TravelAgentState)

        workflow.add_node("router",           self._router_agent)
        workflow.add_node("booking_agent",    self._booking_agent)
        workflow.add_node("complaint_agent",  self._complaint_agent)
        workflow.add_node("information_agent", self._information_agent)
        workflow.add_node("final_response",   self._final_response_agent)

        workflow.set_entry_point("router")

        workflow.add_conditional_edges(
            "router",
            self._route_to_agent,
            {
                "booking":     "booking_agent",
                "complaint":   "complaint_agent",
                "information": "information_agent",
                "complete":    "final_response",
            },
        )

        for agent_node in ("booking_agent", "complaint_agent", "information_agent"):
            workflow.add_conditional_edges(
                agent_node,
                self._agent_continue_or_complete,
                {"continue": "router", "complete": "final_response"},
            )

        workflow.add_edge("final_response", END)
        return workflow.compile()

    # ── Node wrappers ──────────────────────────────────────────────────────

    def _router_agent(self, state: TravelAgentState) -> TravelAgentState:
        return self.router_agent.route_query(state)

    def _booking_agent(self, state: TravelAgentState) -> TravelAgentState:
        return self.booking_agent.process_booking_request(state)

    def _complaint_agent(self, state: TravelAgentState) -> TravelAgentState:
        return self.complaint_agent.handle_complaint(state)

    def _information_agent(self, state: TravelAgentState) -> TravelAgentState:
        return self.information_agent.provide_information(state)

    def _final_response_agent(self, state: TravelAgentState) -> TravelAgentState:
        """Pass through — booking agent already wrote the final message."""
        return update_state_field(state, "is_complete", True)

    # ── Routing helpers ────────────────────────────────────────────────────

    def _route_to_agent(self, state: TravelAgentState) -> str:
        query = state["current_query"].lower()
        stage = state["booking_info"].get("booking_stage", "collecting_info")

        # If we're mid-booking flow, keep routing to booking agent
        if stage in ("collecting_info", "showing_options"):
            return "booking"

        if any(w in query for w in ["book", "reserve", "flight", "hotel", "ticket", "fly"]):
            return "booking"
        if any(w in query for w in ["complaint", "problem", "issue", "cancel", "refund"]):
            return "complaint"
        if any(w in query for w in ["information", "recommend", "suggest", "where", "how", "tell me"]):
            return "information"
        return "complete"

    def _agent_continue_or_complete(self, state: TravelAgentState) -> str:
        return "complete"

    # ── Main entry point ───────────────────────────────────────────────────

    def process_query(
        self,
        query: str,
        session_id: str = None,
        previous_session: Optional[dict] = None,
    ) -> TravelAgentState:
        """
        Process a customer query through the multi-agent system.

        Args:
            query           : The user's latest message.
            session_id      : Session identifier.
            previous_session: Dict returned by session_store.load_session().
                              When provided, booking_info and message history
                              are carried forward so follow-up questions work.
        """
        if previous_session:
            # Continue an existing conversation — carry state forward from SQLite
            state = resume_state(query, previous_session)
        else:
            state = create_initial_state(query, session_id)

        state_with_msg = add_message_to_state(state, "user", query)
        return self.graph.invoke(state_with_msg)
