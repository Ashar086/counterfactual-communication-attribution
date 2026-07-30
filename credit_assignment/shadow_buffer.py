"""Shadow Buffer circuit breaker for safe prompt updates."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from credit_assignment.fault_injection import FaultInjector, PoisonMode
from credit_assignment.graph import run_pipeline


@dataclass
class ShadowTrialResult:
    task: str
    base_reward: float
    shadow_reward: float


@dataclass
class ShadowDecision:
    committed: bool
    base_avg_reward: float
    shadow_avg_reward: float
    target_agent: str
    proposed_prompt: str
    trials: list[ShadowTrialResult] = field(default_factory=list)
    log_message: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ShadowBuffer:
    """
    Circuit breaker for Meta-Agent prompt updates.

    Flow:
      1. Meta-Agent proposes a prompt update for a failing agent.
      2. Instantiate shadow node v'_shadow with the new prompt (via prompt_overrides).
      3. For the next k tasks, run base graph and shadow graph in parallel.
      4. Commit only if mean(shadow rewards) > mean(base rewards); else rollback log.
    """

    def __init__(self, k: int = 5) -> None:
        if k < 1:
            raise ValueError("k must be >= 1")
        self.k = k
        # Live prompt overrides committed to the "main" graph
        self.committed_prompts: dict[str, str] = {}
        self.rollback_log: list[dict[str, Any]] = []
        self.commit_log: list[dict[str, Any]] = []

    def propose_update(self, target_agent: str, new_prompt: str) -> dict[str, str]:
        """Build shadow prompt map: committed overrides + candidate for target_agent."""
        shadow_overrides = dict(self.committed_prompts)
        shadow_overrides[target_agent] = new_prompt
        return shadow_overrides

    def simulate_update_cycle(
        self,
        *,
        target_agent: str,
        proposed_prompt: str,
        tasks: list[str],
        fault_injector: FaultInjector | None = None,
    ) -> ShadowDecision:
        """
        Run k paired base vs shadow evaluations and decide commit vs rollback.

        The shadow graph is the same compiled pipeline with `prompt_overrides`
        swapping the target node for v'_shadow (new prompt). The base graph
        uses currently committed prompts only.
        """
        if len(tasks) < self.k:
            raise ValueError(f"Need at least k={self.k} tasks, got {len(tasks)}")

        injector = fault_injector or FaultInjector(mode=PoisonMode.NONE)
        eval_tasks = tasks[: self.k]
        shadow_overrides = self.propose_update(target_agent, proposed_prompt)

        trials: list[ShadowTrialResult] = []
        for task in eval_tasks:
            base_state = run_pipeline(
                task,
                fault_injector=injector,
                prompt_overrides=dict(self.committed_prompts),
            )
            shadow_state = run_pipeline(
                task,
                fault_injector=injector,
                prompt_overrides=shadow_overrides,
            )
            trials.append(
                ShadowTrialResult(
                    task=task,
                    base_reward=float(base_state.global_reward),
                    shadow_reward=float(shadow_state.global_reward),
                )
            )

        base_avg = statistics.fmean(t.base_reward for t in trials)
        shadow_avg = statistics.fmean(t.shadow_reward for t in trials)

        if shadow_avg > base_avg:
            self.committed_prompts[target_agent] = proposed_prompt
            msg = (
                f"COMMIT: shadow avg {shadow_avg:.4f} > base avg {base_avg:.4f}; "
                f"prompt update applied to '{target_agent}'."
            )
            decision = ShadowDecision(
                committed=True,
                base_avg_reward=base_avg,
                shadow_avg_reward=shadow_avg,
                target_agent=target_agent,
                proposed_prompt=proposed_prompt,
                trials=trials,
                log_message=msg,
            )
            self.commit_log.append(
                {
                    "timestamp": decision.timestamp,
                    "target_agent": target_agent,
                    "proposed_prompt": proposed_prompt,
                    "base_avg": base_avg,
                    "shadow_avg": shadow_avg,
                }
            )
            return decision

        msg = (
            f"ROLLBACK: shadow avg {shadow_avg:.4f} <= base avg {base_avg:.4f}; "
            f"rejecting prompt update for '{target_agent}'."
        )
        decision = ShadowDecision(
            committed=False,
            base_avg_reward=base_avg,
            shadow_avg_reward=shadow_avg,
            target_agent=target_agent,
            proposed_prompt=proposed_prompt,
            trials=trials,
            log_message=msg,
        )
        self.rollback_log.append(
            {
                "timestamp": decision.timestamp,
                "target_agent": target_agent,
                "proposed_prompt": proposed_prompt,
                "base_avg": base_avg,
                "shadow_avg": shadow_avg,
                "reason": "shadow_not_strictly_better",
            }
        )
        return decision
