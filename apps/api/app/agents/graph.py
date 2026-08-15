"""The LangGraph agent graph (section 41).

START -> load_learner_context -> retrieve_relevant_memory -> conversation_agent
      -> error_analysis_agent -> [route] --significant--> learner_model_agent
         -> adaptation_agent -> teaching_strategy_agent -> practice_or_response_agent
         -> generate_response
                                 --routine--> generate_response
      -> persist_learning_event -> update_memory -> update_recommendations -> END

The routing after error_analysis_agent is the cost-optimization step from section 42:
a routine, error-free turn skips four LLM-calling nodes (learner_model needs no LLM
call itself, but adaptation_agent and teaching_strategy_agent do) and goes straight
to response generation, since there is nothing new to adapt to.

Each request builds its own compiled graph bound to that request's AsyncSession via
closures — LangGraph state stays JSON-serializable (TutorState) while DB access is
injected per node, which keeps nodes testable without a running app.
"""
from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes.context import load_learner_context, retrieve_relevant_memory
from app.agents.nodes.conversation import conversation_agent, error_analysis_agent
from app.agents.nodes.modeling import adaptation_agent, learner_model_agent, teaching_strategy_agent
from app.agents.nodes.output import generate_response, practice_or_response_agent
from app.agents.nodes.persistence import persist_learning_event, update_memory_node, update_recommendations_node
from app.agents.state import TutorState


def _route_after_error_analysis(state: TutorState) -> str:
    return "significant" if state.get("is_significant_learning_event") else "routine"


def build_tutor_graph(db: AsyncSession):
    # Small async wrappers (not lambdas) around the DB-bound nodes: a lambda
    # calling an async function returns an unawaited coroutine, which LangGraph
    # rejects as an invalid node return value — these wrappers actually await it.
    async def _load_learner_context(s: TutorState) -> dict:
        return await load_learner_context(s, db)

    async def _retrieve_relevant_memory(s: TutorState) -> dict:
        return await retrieve_relevant_memory(s, db)

    async def _learner_model_agent(s: TutorState) -> dict:
        return await learner_model_agent(s, db)

    async def _persist_learning_event(s: TutorState) -> dict:
        return await persist_learning_event(s, db)

    async def _update_memory_node(s: TutorState) -> dict:
        return await update_memory_node(s, db)

    async def _update_recommendations_node(s: TutorState) -> dict:
        return await update_recommendations_node(s, db)

    graph = StateGraph(TutorState)

    graph.add_node("load_learner_context", _load_learner_context)
    graph.add_node("retrieve_relevant_memory", _retrieve_relevant_memory)
    graph.add_node("conversation_agent", conversation_agent)
    graph.add_node("error_analysis_agent", error_analysis_agent)
    graph.add_node("learner_model_agent", _learner_model_agent)
    graph.add_node("adaptation_agent", adaptation_agent)
    graph.add_node("teaching_strategy_agent", teaching_strategy_agent)
    graph.add_node("practice_or_response_agent", practice_or_response_agent)
    graph.add_node("generate_response", generate_response)
    graph.add_node("persist_learning_event", _persist_learning_event)
    graph.add_node("update_memory", _update_memory_node)
    graph.add_node("update_recommendations", _update_recommendations_node)

    graph.set_entry_point("load_learner_context")
    graph.add_edge("load_learner_context", "retrieve_relevant_memory")
    graph.add_edge("retrieve_relevant_memory", "conversation_agent")
    graph.add_edge("conversation_agent", "error_analysis_agent")

    graph.add_conditional_edges(
        "error_analysis_agent",
        _route_after_error_analysis,
        {"significant": "learner_model_agent", "routine": "generate_response"},
    )
    graph.add_edge("learner_model_agent", "adaptation_agent")
    graph.add_edge("adaptation_agent", "teaching_strategy_agent")
    graph.add_edge("teaching_strategy_agent", "practice_or_response_agent")
    graph.add_edge("practice_or_response_agent", "generate_response")

    graph.add_edge("generate_response", "persist_learning_event")
    graph.add_edge("persist_learning_event", "update_memory")
    graph.add_edge("update_memory", "update_recommendations")
    graph.add_edge("update_recommendations", END)

    return graph.compile()


async def run_tutor_turn(db: AsyncSession, initial_state: TutorState) -> TutorState:
    app = build_tutor_graph(db)
    result = await app.ainvoke(initial_state)
    return result
