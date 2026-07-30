"""
CausalCommBench — synthetic gold-fault traces for localization.

- Single-fault traces (binary Y): sanity check for exact CR.
- Multi-fault traces (graded Y): each active FAULT_ costs 0.5 utility so
  single-event soft-null yields partial ΔY and Recall@2 / nDCG are meaningful.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from commscm.schema.events import (
    Channel,
    CommunicationEvent,
    EventDAG,
    RunOutcome,
    RunTrace,
)

FAULT_TEXT = "FAULT_TEXT_AMBIGUITY: unclear conflicting requirements"
FAULT_TOOL = 'FAULT_TOOL_MISSING: {"tool":"search","status":"empty"}'
FAULT_MEMORY = 'FAULT_MEMORY_CORRUPT: {"op":"write","key":"spec","value":"GARBAGE"}'
FAULT_RETRIEVAL = 'FAULT_RETRIEVAL_WRONG: {"docs":["irrelevant outdated API"]}'
FAULT_CODER = "FAULT_CODER_PARTIAL: incomplete solve() body"

CHANNEL_OF = {
    "C0": Channel.TEXT,
    "C1": Channel.TEXT,
    "C2": Channel.TOOL,
    "C3": Channel.MEMORY,
    "C4": Channel.RETRIEVAL,
    "C5": Channel.TEXT,
    "C6": Channel.TEXT,
    "C7": Channel.TOOL,
}


class GoldFaultCase(BaseModel):
    case_id: str
    fault_type: str
    true_event_id: str
    true_event_ids: list[str] = Field(default_factory=list)
    trace: RunTrace

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _sync_ids(self) -> "GoldFaultCase":
        ids = list(self.true_event_ids) or [self.true_event_id]
        self.true_event_ids = ids
        self.true_event_id = ids[0]
        return self


def _empty_msgs() -> dict[str, str]:
    return {
        "C0": "Task: implement add(a,b) returning a+b.",
        "C1": "Plan: implement def add(a,b): return a+b",
        "C2": '{"tool":"docs.search","status":"ok","result":"add(a,b)->sum"}',
        "C3": '{"op":"write","key":"spec","value":"return sum of a and b"}',
        "C4": '{"docs":["PEP guidance: pure function add"]}',
        "C5": "CODE_PLACEHOLDER",
        "C6": "REVIEW_PLACEHOLDER",
        "C7": "EXEC_PLACEHOLDER",
    }


def _derive(msgs: dict[str, str]) -> None:
    msgs["C5"] = (
        f"CODE from plan={msgs['C1']} tool={msgs['C2']} "
        f"mem={msgs['C3']} ret={msgs['C4']}"
    )
    msgs["C6"] = f"REVIEW of {msgs['C5']}"
    msgs["C7"] = f'{{"exec":"{msgs["C6"]}"}}'


def build_pipeline(faults: dict[str, str]) -> EventDAG:
    """
    Build 8-event DAG with zero or more exogenous FAULT_ injections.

    Topology:
      C0 user text (exogenous)
      C1–C4 exogenous channel events
      C5←{C1..C4}, C6←C5, C7←C6 (mechanized descendants)
    """
    msgs = _empty_msgs()
    for eid, fault_msg in faults.items():
        if eid not in msgs:
            raise KeyError(eid)
        msgs[eid] = fault_msg

    # Derive downstream; if a downstream node is itself faulted, keep its fault message
    _derive(msgs)
    for eid, fault_msg in faults.items():
        if eid in {"C5", "C6", "C7"}:
            msgs[eid] = fault_msg
            if eid == "C5":
                msgs["C6"] = f"REVIEW of {fault_msg}"
                msgs["C7"] = f'{{"exec":"REVIEW of {fault_msg}"}}'
            elif eid == "C6":
                msgs["C7"] = f'{{"exec":"{fault_msg}"}}'

    parents = {
        "C0": [],
        "C1": [],
        "C2": [],
        "C3": [],
        "C4": [],
        "C5": ["C1", "C2", "C3", "C4"],
        "C6": ["C5"],
        "C7": ["C6"],
    }
    senders = {
        "C0": "user",
        "C1": "planner",
        "C2": "tool",
        "C3": "memory",
        "C4": "retriever",
        "C5": "coder",
        "C6": "reviewer",
        "C7": "executor",
    }
    receivers = {
        "C0": "planner",
        "C1": "coder",
        "C2": "coder",
        "C3": "coder",
        "C4": "coder",
        "C5": "reviewer",
        "C6": "executor",
        "C7": "user",
    }

    dag = EventDAG()
    for i, eid in enumerate(["C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7"]):
        dag.add(
            CommunicationEvent(
                event_id=eid,
                sender=senders[eid],
                receiver=receivers[eid],
                channel=CHANNEL_OF[eid],
                message=msgs[eid],
                time_index=i,
                parents=list(parents[eid]),
            )
        )
    return dag


def count_fault_markers(dag: EventDAG) -> int:
    """Count primary injected faults (message starts with FAULT_)."""
    return sum(1 for e in dag.events.values() if e.message.startswith("FAULT_"))


def binary_fault_outcome(dag: EventDAG) -> float:
    """Single-fault convention: any primary FAULT_ ⇒ Y=0 else Y=1."""
    return 0.0 if count_fault_markers(dag) else 1.0


def graded_fault_outcome(dag: EventDAG, *, cost_per_fault: float = 0.5) -> float:
    """
    Multi-fault convention: each primary FAULT_ event costs `cost_per_fault`.

    Two faults ⇒ Y=0; nulling one ⇒ Y=0.5; nulling both ⇒ Y=1.
    """
    n = count_fault_markers(dag)
    return max(0.0, min(1.0, 1.0 - cost_per_fault * n))


def make_case(
    *,
    case_id: str,
    fault_type: str,
    fault_event: str,
    fault_message: str,
    fault_channel: Channel,
) -> GoldFaultCase:
    assert CHANNEL_OF[fault_event] == fault_channel
    dag = build_pipeline({fault_event: fault_message})
    y = binary_fault_outcome(dag)
    trace = RunTrace(
        run_id=case_id,
        task_id=f"synth_{fault_type}",
        architecture_id="causal_comm_bench_v0",
        dag=dag,
        outcome=RunOutcome(reward=y, success=y >= 1.0, metrics={"fault_type": fault_type}),
        gold_fault_event_id=fault_event,
        gold_fault_event_ids=[fault_event],
        poison_mode=fault_type,
    )
    return GoldFaultCase(
        case_id=case_id,
        fault_type=fault_type,
        true_event_id=fault_event,
        true_event_ids=[fault_event],
        trace=trace,
    )


def make_multi_fault_case(
    *,
    case_id: str,
    fault_type: str,
    faults: dict[str, str],
) -> GoldFaultCase:
    for eid in faults:
        if eid not in CHANNEL_OF:
            raise KeyError(eid)
    dag = build_pipeline(faults)
    y = graded_fault_outcome(dag)
    ids = sorted(faults.keys())
    trace = RunTrace(
        run_id=case_id,
        task_id=f"synth_multi_{fault_type}",
        architecture_id="causal_comm_bench_v0_multi",
        dag=dag,
        outcome=RunOutcome(
            reward=y,
            success=y >= 1.0,
            metrics={"fault_type": fault_type, "n_faults": len(faults), "graded": True},
        ),
        gold_fault_event_id=ids[0],
        gold_fault_event_ids=ids,
        poison_mode=fault_type,
        extra={"outcome_mode": "graded"},
    )
    return GoldFaultCase(
        case_id=case_id,
        fault_type=fault_type,
        true_event_id=ids[0],
        true_event_ids=ids,
        trace=trace,
    )


def build_gold_fault_dataset() -> list[GoldFaultCase]:
    """Four one-fault-at-a-time traces."""
    return [
        make_case(
            case_id="T1_text",
            fault_type="text_ambiguity",
            fault_event="C1",
            fault_message=FAULT_TEXT,
            fault_channel=Channel.TEXT,
        ),
        make_case(
            case_id="T2_tool",
            fault_type="missing_tool_output",
            fault_event="C2",
            fault_message=FAULT_TOOL,
            fault_channel=Channel.TOOL,
        ),
        make_case(
            case_id="T3_memory",
            fault_type="corrupted_memory_write",
            fault_event="C3",
            fault_message=FAULT_MEMORY,
            fault_channel=Channel.MEMORY,
        ),
        make_case(
            case_id="T4_retrieval",
            fault_type="incorrect_retrieval",
            fault_event="C4",
            fault_message=FAULT_RETRIEVAL,
            fault_channel=Channel.RETRIEVAL,
        ),
    ]


def build_multi_fault_dataset() -> list[GoldFaultCase]:
    """
    Interacting faults among exogenous channel events (graded Y).

    Only C1–C4 are used so soft-null of one fault cannot wipe another via
    mechanized descendant recompute.
    """
    return [
        make_multi_fault_case(
            case_id="M1_tool_memory",
            fault_type="tool_and_memory",
            faults={"C2": FAULT_TOOL, "C3": FAULT_MEMORY},
        ),
        make_multi_fault_case(
            case_id="M2_memory_retrieval",
            fault_type="memory_and_retrieval",
            faults={"C3": FAULT_MEMORY, "C4": FAULT_RETRIEVAL},
        ),
        make_multi_fault_case(
            case_id="M3_text_tool",
            fault_type="text_and_tool",
            faults={"C1": FAULT_TEXT, "C2": FAULT_TOOL},
        ),
    ]
