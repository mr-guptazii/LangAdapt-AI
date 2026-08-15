"""Graph-shape tests that don't require a database: verifies the LangGraph
tutor graph compiles and the routing function makes the expected cost-optimization
decision (section 42) without invoking any node."""
from app.agents.graph import _route_after_error_analysis, build_tutor_graph


class _FakeSession:
    """Minimal stand-in so build_tutor_graph's node closures can be created
    without a real AsyncSession — the nodes are never invoked in this test."""


def test_graph_compiles():
    compiled = build_tutor_graph(_FakeSession())
    assert compiled is not None


def test_routes_to_full_pipeline_when_errors_detected():
    assert _route_after_error_analysis({"is_significant_learning_event": True}) == "significant"


def test_routes_to_fast_path_when_no_errors():
    assert _route_after_error_analysis({"is_significant_learning_event": False}) == "routine"
    assert _route_after_error_analysis({}) == "routine"
