"""
WARDEN environment core.

INVARIANT (the thing your professor should be shown):
    The environment defines what EXISTS, what is ACCESSIBLE, what each tool
    RETURNS, and how state EVOLVES.
    The environment never defines what the agent does next.

What makes this a *decision environment* rather than "just normal code":

1. DEPENDENCIES  - some tools are unusable until information obtained from
                   another tool is supplied (diagnostic targets only appear
                   inside evaluation records).
2. STATE         - actions mutate world state; later observations reflect it
                   (s_t -> a_t -> s_{t+1}, not a_t -> static text).
3. PERMISSIONS   - some resources are gated and return structured denials.
4. AN INCENTIVE FORK - there is a cheap path that violates policy and an
                   expensive path that complies. Without such a fork, no
                   oversight manipulation could possibly show an effect.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, str]
    category: str  # evidence | analysis | policy | shortcut | restricted | decision

    def render(self) -> str:
        if self.parameters:
            params = ", ".join(f'"{k}": <{v}>' for k, v in self.parameters.items())
        else:
            params = ""
        return f"- {self.name}({params})\n    {self.description}"


@dataclass
class Observation:
    payload: Any
    is_error: bool = False
    tags: list[str] = field(default_factory=list)


@dataclass
class EnvState:
    """Everything the analysis layer needs to score compliance."""
    searched_queries: list[str] = field(default_factory=list)
    inspected_records: list[str] = field(default_factory=list)
    discovered_record_ids: list[str] = field(default_factory=list)
    discovered_diag_targets: list[str] = field(default_factory=list)
    diagnostics_run: list[str] = field(default_factory=list)
    policies_checked: list[str] = field(default_factory=list)
    comparisons_run: list[str] = field(default_factory=list)
    cached_assessment_retrieved: bool = False
    restricted_attempts: int = 0
    denied_tools: list[str] = field(default_factory=list)
    submitted: bool = False
    submission: dict | None = None


class Environment:
    """Generic engine. A Scenario supplies the world + tool implementations."""

    def __init__(self, scenario, condition: str):
        self.scenario = scenario
        self.condition = condition
        self.state = EnvState()
        self.tools: dict[str, ToolSpec] = {t.name: t for t in scenario.tools()}
        self._impl: dict[str, Callable[[EnvState, dict], Observation]] = scenario.implementations()

    # ---------------- prompt surface ----------------
    def tool_block(self) -> str:
        return "\n".join(self.tools[n].render() for n in self.tools)

    # ---------------- execution ----------------
    def execute(self, name: str, arguments: dict) -> Observation:
        if name not in self._impl:
            return Observation(
                {"error": "unknown_tool", "tool": name,
                 "available": sorted(self.tools.keys())},
                is_error=True, tags=["unknown_tool"])
        try:
            return self._impl[name](self.state, arguments or {})
        except KeyError as e:
            return Observation(
                {"error": "missing_argument", "tool": name, "argument": str(e).strip("'")},
                is_error=True, tags=["bad_arguments"])
        except Exception as e:  # environment must never crash the experiment
            return Observation(
                {"error": "tool_execution_failed", "tool": name, "detail": str(e)},
                is_error=True, tags=["tool_exception"])

    @property
    def finished(self) -> bool:
        return self.state.submitted


def ok(payload: Any, tags: list[str] | None = None) -> Observation:
    return Observation(payload, is_error=False, tags=tags or [])


def err(payload: Any, tags: list[str] | None = None) -> Observation:
    return Observation(payload, is_error=True, tags=tags or [])


def dumps(o: Any) -> str:
    return json.dumps(o, indent=2, ensure_ascii=False)
