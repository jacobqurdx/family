from __future__ import annotations
import json
import os
import re
from pathlib import Path

STUB_RESPONSES_DIR = Path(__file__).parent.parent / "stub_responses"


class LLMClient:
    """
    Unified LLM client. Pass stub=True (or set AGENT_STUB_LLM=true) to
    run without an API key using deterministic pre-written responses.
    """

    def __init__(
        self,
        stub: bool = False,
        cache_dir: Path | None = None,
        model: str | None = None,
    ):
        self.stub = stub
        self.cache_dir = cache_dir
        self.model = model
        if stub:
            self._backend: _Backend = StubLLMBackend(STUB_RESPONSES_DIR)
        else:
            self._backend = RealLLMBackend(cache_dir=cache_dir, model=model)

    @classmethod
    def from_env(cls, cache_dir: Path | None = None) -> "LLMClient":
        stub = os.environ.get("AGENT_STUB_LLM", "false").lower() in ("true", "1", "yes")
        return cls(stub=stub, cache_dir=cache_dir)

    def complete(self, prompt: str, step: str) -> str:
        return self._backend.complete(prompt, step)

    def search(self, query: str) -> list[dict]:
        return self._backend.search(query)


class _Backend:
    def complete(self, prompt: str, step: str) -> str:
        raise NotImplementedError

    def search(self, query: str) -> list[dict]:
        raise NotImplementedError


DEFAULT_MODEL = "claude-sonnet-4-6-20250514"


class RealLLMBackend(_Backend):
    def __init__(self, cache_dir: Path | None = None, model: str | None = None):
        import anthropic as _anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set.\n"
                "Either set the environment variable or run in stub mode:\n"
                "  export AGENT_STUB_LLM=true\n"
                "  agent evaluate --stub"
            )
        self._client = _anthropic.Anthropic(api_key=api_key)
        self.cache_dir = cache_dir
        self.model = model or DEFAULT_MODEL

    def complete(self, prompt: str, step: str) -> str:
        import hashlib
        cache_key = hashlib.sha256(f"{self.model}:{step}:{prompt}".encode()).hexdigest()
        if self.cache_dir:
            cache_file = self.cache_dir / f"{cache_key}.json"
            if cache_file.exists():
                return json.loads(cache_file.read_text())["response"]
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
        except Exception as e:
            text = _safe_fallback_json(step, str(e))
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cache_dir / f"{cache_key}.json").write_text(
                json.dumps({"step": step, "response": text})
            )
        return text

    def search(self, query: str) -> list[dict]:
        prompt = (
            f"Search for: {query}\n\n"
            "Return up to 5 recent, relevant results as a JSON array:\n"
            '[{"title": "...", "source_name": "...", "source_url": "https://...", '
            '"published_date": "YYYY-MM-DD", "content": "200-400 word summary"}]\n'
            "Return only the JSON array."
        )
        try:
            response = self._client.messages.create(
                model="claude-sonnet-4-6-20250514",
                max_tokens=4000,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{"role": "user", "content": prompt}],
            )
            text = " ".join(b.text for b in response.content if hasattr(b, "text"))
            return _parse_json_array(text)
        except Exception:
            return []


class StubLLMBackend(_Backend):
    """Returns pre-written responses from stub_responses/. Never touches the network."""

    def __init__(self, stub_dir: Path):
        self.stub_dir = stub_dir
        self._responses = self._load_all_responses()

    def _load_all_responses(self) -> dict[str, dict[str, str]]:
        responses: dict[str, dict[str, str]] = {}
        if not self.stub_dir.exists():
            return responses
        for step_dir in self.stub_dir.iterdir():
            if step_dir.is_dir() and not step_dir.name.startswith("."):
                responses[step_dir.name] = {}
                for f in step_dir.glob("*.json"):
                    responses[step_dir.name][f.stem] = f.read_text()
                for f in step_dir.glob("*.md"):
                    responses[step_dir.name][f.stem] = f.read_text()
        return responses

    def complete(self, prompt: str, step: str) -> str:
        variant = self._select_variant(prompt, step)
        step_responses = self._responses.get(step, {})
        if variant in step_responses:
            response = step_responses[variant]
        elif step_responses:
            response = next(iter(step_responses.values()))
            variant = f"{next(iter(step_responses))} [fallback]"
        else:
            response = _safe_fallback_json(step, "no stub responses found")
            variant = "generated_fallback"
        print(f"  [STUB] {step} → {variant}")
        return response

    def search(self, query: str) -> list[dict]:
        collection_responses = self._responses.get("collection", {})
        if "web_search_results" in collection_responses:
            print("  [STUB] web_search → web_search_results")
            try:
                return json.loads(collection_responses["web_search_results"])
            except Exception:
                pass
        print("  [STUB] web_search → empty (no stub collection responses)")
        return []

    def _select_variant(self, prompt: str, step: str) -> str:
        p = prompt.lower()
        # Extract only the signal content block (after "Content:\n") to avoid
        # matching keywords that appear in the template instructions themselves.
        content_marker = "content:\n"
        content_start = p.find(content_marker)
        signal_content = p[content_start + len(content_marker):] if content_start != -1 else p
        if step == "relevance":
            if any(kw in signal_content for kw in
                   ["semiconductor", "oncology", "mrna", "cold chain",
                    "mckinsey", "generic medicine", "ema quarterly",
                    "series d", "adc therapy", "venture", "biotech fund"]):
                return "relevant_false"
            # Route to parameter-specific stub so process_step populates correctly
            if any(kw in signal_content for kw in ["sdd", "spray dry", "spray-dry"]):
                return "relevant_true_sdd"
            if any(kw in signal_content for kw in ["wuxi", "biosecure", "1260h", "import alert", "form 483"]):
                return "relevant_true_cdmo"
            if any(kw in signal_content for kw in ["tariff", "section 301", "ustr", "federal register", "hatu", "dipea"]):
                return "relevant_true_tariff"
            if any(kw in signal_content for kw in ["sm-a", "starting material", "force majeure", "factory fire", "shortage"]):
                return "relevant_true_raw_materials"
            if any(kw in signal_content for kw in
                   ["fda", "import"]):
                return "relevant_true_cdmo"
            return "relevant_false"
        elif step == "novelty":
            if any(kw in p for kw in
                   ["restating", "repeat", "already known", "no change",
                    "confirms existing", "previously reported"]):
                return "novel_false"
            if any(kw in p for kw in
                   ["confirmed", "announced", "effective", "signed into law",
                    "official action", "chapter 11", "bankruptcy",
                    "force majeure", "oai"]):
                return "novel_true"
            return "novel_true"
        elif step == "severity":
            content_marker = "content:\n"
            content_start = p.find(content_marker)
            sc = p[content_start + len(content_marker):] if content_start != -1 else p
            # Truncate at next section heading so instructions don't pollute sc
            end_pos = sc.find("\n## ")
            if end_pos != -1:
                sc = sc[:end_pos]
            # CRITICAL: definitively confirmed, discontinuous events
            if any(kw in sc for kw in [
                "import alert 99", "total loss", "into law",
                "no license exceptions", "47 pharmaceutical api",
                "detention without physical", "force majeure",
            ]):
                return "severity_critical"
            if "100%" in sc and ("tariff" in sc or "executive order" in sc):
                return "severity_critical"
            # HIGH: confirmed material changes
            if any(kw in sc for kw in [
                "form 483", "38%", "passes senate", "allocation cut",
                "72-21",
            ]):
                return "severity_high_cdmo" if "wuxi" in sc or "fda" in sc else "severity_high_tariff"
            if "55%" in sc and ("final rule" in sc or "federal register" in sc):
                return "severity_high_tariff"
            # ELEVATED: precursor events
            if any(kw in sc for kw in [
                "proposed", "nprm", "public comment", "bookings frozen",
                "output cut", "dipp quota", "march 15, 2026",
            ]):
                return "severity_elevated"
            if "extended" in sc and "lead time" in sc:
                return "severity_elevated"
            if "15% capacity" in sc or "capacity reduction" in sc:
                return "severity_elevated"
            # ROUTINE: stable, positive, or non-actionable
            return "severity_routine"
        elif step == "impact":
            # raw_content is now in the impact prompt under "## Signal".
            # Extract it for routing — it's signal-specific and distinct from MRP boilerplate.
            signal_marker = "## signal\n\n"
            what_changed_marker = "\n\n## what changed"
            sig_start = p.find(signal_marker)
            if sig_start != -1:
                ic = p[sig_start + len(signal_marker):]
                end = ic.find(what_changed_marker)
                if end != -1:
                    ic = ic[:end]
            else:
                ic = p

            # Supply halt — factory fire, embargo, complete loss of supply
            if any(kw in ic for kw in ["factory fire", "building 7", "total loss",
                                        "no license exceptions", "detention without physical",
                                        "embargo", "destroyed", "no commercial batches"]):
                return "impact_supply_halt"
            # HATU — check before generic force-majeure; HATU signals are about benzotriazole/Chemsy
            if any(kw in ic for kw in ["chemsy", "fluorochem", "benzotriazole",
                                        "hatu price", "hatu lead", "hatu supplier",
                                        "hatu shortage", "pharmamaterials"]):
                return "impact_hatu"
            # DIPEA — check before generic force-majeure; DIPEA signals mention DIPP / diisopropylamine
            if "dipea" in ic and any(kw in ic for kw in ["indian chemical", "diisopropylamine",
                                                           "dipp", "n,n-diisopropylethylamine",
                                                           "production cut", "output cut",
                                                           "balaji amines", "alkyl amines"]):
                return "impact_dipea"
            # SM-A force majeure / allocation cut (partial, not total halt)
            if any(kw in ic for kw in ["force majeure", "allocation cut", "40%",
                                        "sole source supply"]):
                return "impact_sm_a_shortage"
            # 100% tariff
            if "100%" in ic and any(kw in ic for kw in ["tariff", "executive order"]):
                return "impact_tariff_100pct"
            # Legislative / proposed — not yet enacted
            if any(kw in ic for kw in ["proposed rulemaking", "comment period",
                                        "proceeds to the president", "passes senate",
                                        "senate passes", "if finalized", "pending compliance"]):
                return "impact_legislative_qualitative"
            # CDMO regulatory pressure (483, capacity reduction — not full removal)
            if any(kw in ic for kw in ["form 483", "capacity reduction", "bookings frozen",
                                        "q1 2026 earnings", "pending review", "working with legal"]):
                return "impact_cdmo_regulatory"
            # 55% or other confirmed tariff
            if any(kw in ic for kw in ["55%", "section 301", "ustr proposes",
                                        "tariff", "federal register"]):
                return "impact_tariff_55pct"
            # Confirmed CDMO enforcement (import alert, warning letter, biosecure signed)
            if any(kw in ic for kw in ["import alert", "warning letter", "into law",
                                        "restriction affecting", "wuxi sta", "wuxi apptec"]):
                return "impact_cdmo_removal"
            return "impact_cdmo_removal"
        elif step == "metacognition":
            # Extract only the signal content block to avoid matching template text.
            content_marker = "content:\n"
            content_start = p.find(content_marker)
            mc = p[content_start + len(content_marker):] if content_start != -1 else p
            end_pos = mc.find("\n## ")
            if end_pos != -1:
                mc = mc[:end_pos]
            if any(kw in mc for kw in [
                # hedged language
                "reportedly", "sources say", "alleged", "unconfirmed",
                "not yet confirmed", "has not been confirmed",
                # proposed / pending — not yet law or confirmed
                "proposed rulemaking", "notice of proposed", "comment period",
                "if finalized", "proposed amendment", "amendment would",
                "bipartisan support but has not",
                # pending actions / awaiting confirmation
                "pending review", "proceeds to the president",
                "will communicate", "pending compliance",
                # capacity/outlook uncertainty
                "bookings frozen", "working with legal counsel",
            ]):
                return "metacognition_uncertain"
            return "metacognition_certain"
        elif step == "briefing":
            return "investigation_report_template"
        variants = list(self._responses.get(step, {}).keys())
        return variants[0] if variants else "fallback"


def _safe_fallback_json(step: str, error_message: str) -> str:
    fallbacks = {
        "relevance": json.dumps({
            "is_relevant": False,
            "relevant_parameters": [],
            "relevance_reasoning": f"Assessment failed: {error_message}. Marked not relevant for safety.",
        }),
        "novelty": json.dumps({
            "is_novel": False,
            "novelty_reasoning": f"Assessment failed: {error_message}. Marked not novel for safety.",
            "updated_parameter_states": [],
        }),
        "severity": json.dumps({
            "severity": "ELEVATED",
            "severity_reasoning": f"Assessment failed: {error_message}. Defaulting to ELEVATED for human review.",
            "risk_vector_type": "unknown",
            "affected_geography": None,
            "affected_cdmo_node_name": None,
        }),
        "impact": json.dumps({
            "estimated_cost_impact_per_kg": None,
            "estimated_cost_impact_reasoning": f"Assessment failed: {error_message}.",
            "estimated_timeline_impact_weeks": None,
            "estimated_timeline_reasoning": "",
            "confidence": "low",
            "caveats": ["Impact estimation failed; manual assessment required."],
        }),
        "metacognition": json.dumps({
            "grade": "CERTAIN",
            "confidence": 0.5,
            "uncertainty_flags": [f"Metacognition failed: {error_message}"],
            "reasoning": "Metacognition assessment failed; defaulting to CERTAIN.",
        }),
    }
    return fallbacks.get(step, json.dumps({"error": error_message}))


def _parse_json_array(text: str) -> list:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE)
    try:
        return json.loads(text)
    except Exception:
        return []


def write_stub_files(base_dir: Path = STUB_RESPONSES_DIR) -> None:
    """Write all stub response files to disk. Safe to re-run — skips existing files."""
    stub_files = _stub_file_contents()
    for rel_path, content in stub_files.items():
        full_path = base_dir / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if not full_path.exists():
            full_path.write_text(content)
            print(f"Created: {rel_path}")
        else:
            print(f"Exists (skipped): {rel_path}")


def _stub_file_contents() -> dict[str, str]:
    return {
        "relevance/relevant_true.json": json.dumps({
            "is_relevant": True,
            "relevant_parameters": ["Starting Material A price", "Amide Coupling"],
            "relevance_reasoning": (
                "The signal directly concerns Wuxi AppTec WuXi STA, which is the "
                "assigned CDMO for Starting Material A and the Amide Coupling step — "
                "both in the top 3 of our sensitivity-weighted parameter list."
            ),
        }, indent=2),
        "relevance/relevant_false.json": json.dumps({
            "is_relevant": False,
            "relevant_parameters": [],
            "relevance_reasoning": (
                "The signal concerns a company, facility, or topic that does not "
                "appear in our monitored parameter list. No action required."
            ),
        }, indent=2),
        "novelty/novel_true.json": json.dumps({
            "is_novel": True,
            "novelty_reasoning": (
                "The current state records no confirmed regulatory action at this facility. "
                "This signal reports a confirmed new development not previously captured."
            ),
            "updated_parameter_states": [{
                "parameter_name": "Starting Material A price",
                "new_state_summary": (
                    "CDMO node Wuxi AppTec WuXi STA has received an FDA enforcement action. "
                    "Supply continuity at risk. Alternative qualification timeline: 18 weeks."
                ),
                "new_baseline_value": None,
                "new_baseline_value_unit": None,
                "change_direction": "disrupted",
            }],
        }, indent=2),
        "novelty/novel_false.json": json.dumps({
            "is_novel": False,
            "novelty_reasoning": (
                "The current state already reflects this information. "
                "The signal restates previously known facts without adding new developments."
            ),
            "updated_parameter_states": [],
        }, indent=2),
        "severity/severity_routine.json": json.dumps({
            "severity": "ROUTINE",
            "severity_reasoning": (
                "The signal provides general market context without reporting a confirmed change "
                "to price, availability, or regulatory status for any monitored parameter."
            ),
            "risk_vector_type": "unknown",
            "affected_geography": None,
            "affected_cdmo_node_name": None,
        }, indent=2),
        "severity/severity_elevated.json": json.dumps({
            "severity": "ELEVATED",
            "severity_reasoning": (
                "The signal reports a precursor event that could escalate to a confirmed disruption. "
                "The event is not yet confirmed but warrants active monitoring."
            ),
            "risk_vector_type": "cdmo_removal",
            "affected_geography": "CN",
            "affected_cdmo_node_name": "Wuxi AppTec — WuXi STA",
        }, indent=2),
        "severity/severity_high_tariff.json": json.dumps({
            "severity": "HIGH",
            "severity_reasoning": (
                "A confirmed tariff rate change has been reported affecting CN-origin materials. "
                "This represents a material cost escalation warranting immediate scenario modelling."
            ),
            "risk_vector_type": "tariff_escalation",
            "affected_geography": "CN",
            "affected_cdmo_node_name": None,
        }, indent=2),
        "severity/severity_high_cdmo.json": json.dumps({
            "severity": "HIGH",
            "severity_reasoning": (
                "An OAI outcome has been reported at Wuxi AppTec WuXi STA. "
                "This CDMO performs the Amide Coupling (sole-source) and Cyclisation steps."
            ),
            "risk_vector_type": "cdmo_removal",
            "affected_geography": "CN",
            "affected_cdmo_node_name": "Wuxi AppTec — WuXi STA",
        }, indent=2),
        "severity/severity_critical.json": json.dumps({
            "severity": "CRITICAL",
            "severity_reasoning": (
                "A discontinuous, confirmed restriction affecting our primary CDMO or supplier "
                "bankruptcy has been reported. Requires immediate senior leadership notification."
            ),
            "risk_vector_type": "cdmo_removal",
            "affected_geography": "CN",
            "affected_cdmo_node_name": "Wuxi AppTec — WuXi STA",
        }, indent=2),
        "impact/impact_tariff.json": json.dumps({
            "estimated_cost_impact_per_kg": 115.84,
            "estimated_cost_impact_reasoning": (
                "At 55% tariff on CN-origin materials (SM-A, HATU, DMF, DCM, 2-Fluorotoluene), "
                "total tariff cost per kg API. Source: MRP sensitivity report tariff_sweep at 55%."
            ),
            "estimated_timeline_impact_weeks": None,
            "estimated_timeline_reasoning": "Tariff escalation does not affect lead times directly.",
            "confidence": "high",
            "caveats": [
                "Assumes all CN-origin materials subject to the full consolidated rate.",
                "Indirect China exposure (DIPEA) not included in this estimate.",
            ],
        }, indent=2),
        "impact/impact_cdmo.json": json.dumps({
            "estimated_cost_impact_per_kg": 620.50,
            "estimated_cost_impact_reasoning": (
                "Emergency sourcing at +50% price premium for SM-A and HATU. "
                "Source: MRP sensitivity report cdmo_removal_scenarios, Wuxi AppTec WuXi STA."
            ),
            "estimated_timeline_impact_weeks": 18.0,
            "estimated_timeline_reasoning": (
                "Alternative supplier qualification lead time: 18 weeks (SM-A). "
                "Source: MRP sensitivity report signal_priority_weights, rank 1."
            ),
            "confidence": "medium",
            "caveats": [
                "Emergency premium of 50% is an estimate; actual premium could be higher.",
                "Timeline assumes an alternative supplier exists and can be qualified.",
            ],
        }, indent=2),
        "briefing/investigation_report_template.md": (
            "# Supply Chain Risk Investigation Report [STUB MODE]\n\n"
            "> This report was generated in stub mode without live LLM calls.\n\n"
            "## 1. Executive Summary\n\n"
            "A HIGH-severity supply chain risk signal has been identified.\n"
            "Estimated cost impact: +$115–620/kg API [MRP sensitivity report].\n\n"
            "## 2. Signal Description\n\nSource: Stub response.\n\n"
            "## 3. Manufacturing Network Impact\n\n"
            "- CN-origin material cost exposure: estimated 86% of total material cost\n"
            "- At 55% tariff: +$115.84/kg API [MRP sensitivity report, tariff_sweep_results]\n"
            "- CDMO removal (Wuxi AppTec): +$620.50/kg, 18-week critical path\n\n"
            "## 4. Recommended Actions\n\n"
            "1. Approve `TRIGGER_SCENARIO_RUN`\n"
            "2. Initiate alternative supplier qualification for SM-A\n\n"
            "## 5. Sources\n\n"
            "1. [MRP sensitivity report] scenario_id: api-001_route_a\n"
        ),
        "metacognition/metacognition_certain.json": json.dumps({
            "grade": "CERTAIN",
            "confidence": 0.92,
            "uncertainty_flags": [],
            "reasoning": (
                "The signal provides direct, unambiguous factual evidence consistent with "
                "the assessed tier. The reasoning traces clearly to the signal content and "
                "no borderline interpretation is required."
            ),
        }, indent=2),
        "metacognition/metacognition_uncertain.json": json.dumps({
            "grade": "UNCERTAIN",
            "confidence": 0.78,
            "uncertainty_flags": [
                "hedged language: signal uses 'reportedly' or 'sources say'",
                "borderline tier: event may be precursor rather than confirmed",
            ],
            "reasoning": (
                "The signal contains hedged language that introduces ambiguity about whether "
                "the reported event is confirmed or merely rumoured. The assessed tier could "
                "reasonably be one level lower if the event is not yet confirmed."
            ),
        }, indent=2),
        "collection/web_search_results.json": json.dumps([
            {
                "title": "USTR Confirms 55% Consolidated Tariff on Chinese Pharmaceutical Imports",
                "source_name": "Federal Register",
                "source_url": "https://www.federalregister.gov/documents/2026/05/01/stub-example",
                "published_date": "2026-05-01",
                "content": (
                    "The United States Trade Representative has confirmed that the consolidated "
                    "Section 301 tariff rate on pharmaceutical imports from China will be "
                    "maintained at 55%, effective June 1, 2026. The ruling applies to HS codes "
                    "covering active pharmaceutical ingredient intermediates and key starting "
                    "materials. Affected importers must apply the 55% rate to all entries "
                    "regardless of the country of export of immediate predecessor materials "
                    "where the beneficial origin is determined to be China."
                ),
            },
            {
                "title": "FDA Issues Warning Letter to Wuxi AppTec WuXi STA Following GMP Inspection",
                "source_name": "FDA Enforcement",
                "source_url": "https://www.fda.gov/inspections-compliance-enforcement/stub-example",
                "published_date": "2026-05-10",
                "content": (
                    "The US Food and Drug Administration has issued a warning letter to Wuxi "
                    "AppTec WuXi STA following a GMP inspection conducted in March 2026. "
                    "The letter cites observations related to data integrity in batch "
                    "manufacturing records. Affected customers manufacturing active "
                    "pharmaceutical ingredients using Wuxi STA as a CDMO should review "
                    "their supply continuity plans."
                ),
            },
            {
                "title": "BioSecure Act Amendment Would Grandfather Existing CDMO Contracts",
                "source_name": "Reuters Pharma",
                "source_url": "https://www.reuters.com/business/healthcare/stub-example-2026",
                "published_date": "2026-05-12",
                "content": (
                    "A proposed amendment to the BioSecure Act would allow pharmaceutical "
                    "manufacturers to continue existing contracts with Chinese CDMOs for up to "
                    "three years after the law takes effect. The amendment has bipartisan "
                    "support but has not yet been voted on."
                ),
            },
        ], indent=2),
    }
