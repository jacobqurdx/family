from __future__ import annotations
import sys
import json
from typing import Optional

from agent.domain import (
    Signal, SeverityResult, ImpactResult, MetacognitionResult,
    SeverityTier, RiskVectorType,
)


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def adjudicate_severity(
    severity: SeverityResult,
    meta: MetacognitionResult,
    signal: Signal,
) -> tuple[SeverityResult, MetacognitionResult]:
    """
    Present the severity assessment and metacognition grade to a human adjudicator.
    Returns (possibly-corrected SeverityResult, updated MetacognitionResult).
    """
    print("\n" + "=" * 70)
    print("HUMAN ADJUDICATION REQUIRED — SEVERITY (uncertain assessment)")
    print("=" * 70)
    print(f"\nSignal: {signal.id}")
    print(f"Source: {signal.source_name}  ({signal.collected_at[:10]})")
    print(f"\n--- Content (first 600 chars) ---")
    print(signal.raw_content[:600])
    print("..." if len(signal.raw_content) > 600 else "")
    print(f"\n--- Primary Assessment ---")
    print(f"  Severity: {severity.severity.value.upper()}")
    print(f"  Reasoning: {severity.severity_reasoning}")
    print(f"  Risk vector: {severity.risk_vector_type.value}")
    if severity.affected_cdmo_node_name:
        print(f"  CDMO: {severity.affected_cdmo_node_name}")
    print(f"\n--- Metacognition Grade: UNCERTAIN ---")
    print(f"  Confidence: {meta.confidence:.2f}")
    if meta.uncertainty_flags:
        print("  Flags:")
        for flag in meta.uncertainty_flags:
            print(f"    • {flag}")
    print(f"  Reasoning: {meta.reasoning}")

    tiers = [t for t in SeverityTier]
    print("\n--- Choose Severity Tier ---")
    for i, tier in enumerate(tiers, 1):
        marker = " <-- current" if tier == severity.severity else ""
        print(f"  {i}. {tier.value.upper()}{marker}")
    print("  Press Enter to accept current assessment, or type a number to override.")

    try:
        raw = input("\nYour choice: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n[Adjudication skipped — keeping original assessment]")
        return severity, _mark_skipped(meta)

    if raw == "":
        print("[Accepted original assessment]")
        updated_meta = MetacognitionResult(
            grade=meta.grade,
            confidence=meta.confidence,
            uncertainty_flags=meta.uncertainty_flags,
            reasoning=meta.reasoning,
            step=meta.step,
            adjudicated=True,
            adjudicated_by="human:accepted",
            prompt_version=meta.prompt_version,
        )
        return severity, updated_meta

    try:
        choice = int(raw)
        if 1 <= choice <= len(tiers):
            new_tier = tiers[choice - 1]
            if new_tier == severity.severity:
                print(f"[Same tier selected — accepted original]")
                updated_meta = MetacognitionResult(
                    grade=meta.grade,
                    confidence=meta.confidence,
                    uncertainty_flags=meta.uncertainty_flags,
                    reasoning=meta.reasoning,
                    step=meta.step,
                    adjudicated=True,
                    adjudicated_by="human:accepted",
                    prompt_version=meta.prompt_version,
                )
                return severity, updated_meta
            print(f"[Overriding: {severity.severity.value.upper()} → {new_tier.value.upper()}]")
            corrected = SeverityResult(
                severity=new_tier,
                severity_reasoning=(
                    f"{severity.severity_reasoning} "
                    f"[Human adjudicator overrode {severity.severity.value.upper()} "
                    f"→ {new_tier.value.upper()}]"
                ),
                risk_vector_type=severity.risk_vector_type,
                affected_geography=severity.affected_geography,
                affected_cdmo_node_name=severity.affected_cdmo_node_name,
                prompt_version=severity.prompt_version,
            )
            updated_meta = MetacognitionResult(
                grade="UNCERTAIN",
                confidence=meta.confidence,
                uncertainty_flags=meta.uncertainty_flags,
                reasoning=meta.reasoning,
                step=meta.step,
                adjudicated=True,
                adjudicated_by=f"human:overridden:{severity.severity.value}->{new_tier.value}",
                prompt_version=meta.prompt_version,
            )
            return corrected, updated_meta
    except ValueError:
        pass

    print("[Invalid input — keeping original assessment]")
    return severity, _mark_skipped(meta)


def adjudicate_impact(
    impact: ImpactResult,
    meta: MetacognitionResult,
    signal: Signal,
) -> tuple[ImpactResult, MetacognitionResult]:
    """
    Present the impact assessment and metacognition grade to a human adjudicator.
    Returns (possibly-corrected ImpactResult, updated MetacognitionResult).
    """
    print("\n" + "=" * 70)
    print("HUMAN ADJUDICATION REQUIRED — IMPACT (uncertain assessment)")
    print("=" * 70)
    print(f"\nSignal: {signal.id}")
    print(f"Source: {signal.source_name}  ({signal.collected_at[:10]})")
    print(f"\n--- Impact Assessment ---")
    cost = (
        f"${impact.estimated_cost_impact_per_kg:,.2f}/kg"
        if impact.estimated_cost_impact_per_kg is not None
        else "N/A"
    )
    timeline = (
        f"{impact.estimated_timeline_impact_weeks:.0f} weeks"
        if impact.estimated_timeline_impact_weeks is not None
        else "N/A"
    )
    print(f"  Cost impact:     {cost}")
    print(f"  Timeline impact: {timeline}")
    print(f"  Confidence:      {impact.confidence}")
    print(f"  Reasoning:       {impact.estimated_cost_impact_reasoning}")
    if impact.caveats:
        print("  Caveats:")
        for c in impact.caveats:
            print(f"    • {c}")
    print(f"\n--- Metacognition Grade: UNCERTAIN ---")
    print(f"  Confidence: {meta.confidence:.2f}")
    if meta.uncertainty_flags:
        print("  Flags:")
        for flag in meta.uncertainty_flags:
            print(f"    • {flag}")
    print(f"  Reasoning: {meta.reasoning}")

    print("\n--- Options ---")
    print("  Enter  Accept current impact assessment")
    print("  c      Override cost impact ($/kg)")
    print("  t      Override timeline impact (weeks)")
    print("  b      Override both cost and timeline")
    print("  x      Skip adjudication")

    try:
        raw = input("\nYour choice: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n[Adjudication skipped — keeping original assessment]")
        return impact, _mark_skipped(meta)

    if raw == "" or raw == "x":
        if raw == "":
            print("[Accepted original impact assessment]")
        else:
            print("[Skipped — keeping original assessment]")
        updated_meta = MetacognitionResult(
            grade=meta.grade,
            confidence=meta.confidence,
            uncertainty_flags=meta.uncertainty_flags,
            reasoning=meta.reasoning,
            step=meta.step,
            adjudicated=True,
            adjudicated_by="human:accepted" if raw == "" else "human:skipped",
            prompt_version=meta.prompt_version,
        )
        return impact, updated_meta

    new_cost = impact.estimated_cost_impact_per_kg
    new_timeline = impact.estimated_timeline_impact_weeks

    if raw in ("c", "b"):
        try:
            val = input("  New cost impact ($/kg, or blank to keep): ").strip()
            if val:
                new_cost = float(val)
        except (ValueError, EOFError):
            print("  [Invalid input — keeping original cost]")

    if raw in ("t", "b"):
        try:
            val = input("  New timeline impact (weeks, or blank to keep): ").strip()
            if val:
                new_timeline = float(val)
        except (ValueError, EOFError):
            print("  [Invalid input — keeping original timeline]")

    changes = []
    if new_cost != impact.estimated_cost_impact_per_kg:
        changes.append(
            f"cost ${impact.estimated_cost_impact_per_kg} → ${new_cost}"
        )
    if new_timeline != impact.estimated_timeline_impact_weeks:
        changes.append(
            f"timeline {impact.estimated_timeline_impact_weeks} → {new_timeline} weeks"
        )

    if not changes:
        print("[No changes made — keeping original]")
        updated_meta = MetacognitionResult(
            grade=meta.grade,
            confidence=meta.confidence,
            uncertainty_flags=meta.uncertainty_flags,
            reasoning=meta.reasoning,
            step=meta.step,
            adjudicated=True,
            adjudicated_by="human:accepted",
            prompt_version=meta.prompt_version,
        )
        return impact, updated_meta

    override_note = f" [Human override: {', '.join(changes)}]"
    corrected = ImpactResult(
        estimated_cost_impact_per_kg=new_cost,
        estimated_cost_impact_reasoning=impact.estimated_cost_impact_reasoning + override_note,
        estimated_timeline_impact_weeks=new_timeline,
        estimated_timeline_reasoning=impact.estimated_timeline_reasoning + override_note,
        confidence="medium",
        caveats=impact.caveats + [f"Human-adjudicated: {', '.join(changes)}"],
        prompt_version=impact.prompt_version,
    )
    print(f"[Overriding: {', '.join(changes)}]")
    updated_meta = MetacognitionResult(
        grade="UNCERTAIN",
        confidence=meta.confidence,
        uncertainty_flags=meta.uncertainty_flags,
        reasoning=meta.reasoning,
        step=meta.step,
        adjudicated=True,
        adjudicated_by=f"human:overridden:{'+'.join(changes)}",
        prompt_version=meta.prompt_version,
    )
    return corrected, updated_meta


def _mark_skipped(meta: MetacognitionResult) -> MetacognitionResult:
    return MetacognitionResult(
        grade=meta.grade,
        confidence=meta.confidence,
        uncertainty_flags=meta.uncertainty_flags,
        reasoning=meta.reasoning,
        step=meta.step,
        adjudicated=False,
        adjudicated_by=None,
        prompt_version=meta.prompt_version,
    )
