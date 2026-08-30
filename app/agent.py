"""Google ADK advisory fleet entrypoint.

The ADK fleet has no material executor tools. It delegates analysis among specialist
sub-agents and returns proposals only. Authorization and execution remain outside the
model in the deterministic GOC control plane.
"""

from google.adk.apps import App

from poiex_runtime.adk_planner import build_root_agent

root_agent = build_root_agent()

app = App(
    root_agent=root_agent,
    name="app",
)


__all__ = ["app"]
