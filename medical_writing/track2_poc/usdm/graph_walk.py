"""
USDM Graph Walk: defines 57 nodes across 9 layers for protocol extraction.
Each layer depends on confirmed values from prior layers.
"""
from __future__ import annotations
from typing import Any, List, Dict, Optional, Set
from pydantic import BaseModel, Field


class USDMNode(BaseModel):
    id: str
    label: str
    data_type: str          # "string" | "list" | "number" | "boolean"
    cardinality: str        # "1" | "0..1" | "1..*" | "0..*"
    extraction_hint: str
    parent_ids: List[str]
    parent_predicates: Dict[str, str] = Field(default_factory=dict)
    # Maps parent_id -> relationship label, e.g. "indication": "ADDRESSES"
    required: bool


# ─────────────────────────────────────────────
# Layer 0 — Protocol Identity & Design Foundations (12 nodes)
# ─────────────────────────────────────────────
layer_0_nodes: List[USDMNode] = [
    USDMNode(
        id="sponsor_name",
        label="Sponsor Name",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the name of the sponsor organisation from the title page or header.",
        parent_ids=[],
        required=True,
    ),
    USDMNode(
        id="protocol_number",
        label="Protocol Number",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the unique protocol identifier (e.g. STR-4021-201) from the title page.",
        parent_ids=[],
        required=True,
    ),
    USDMNode(
        id="protocol_version",
        label="Protocol Version",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the protocol version string (e.g. Version 1.0, Amendment 2) from the title page.",
        parent_ids=[],
        required=True,
    ),
    USDMNode(
        id="protocol_date",
        label="Protocol Date",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the protocol effective date or approval date from the title page.",
        parent_ids=[],
        required=True,
    ),
    USDMNode(
        id="study_title",
        label="Full Study Title",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the complete official study title from the title page.",
        parent_ids=[],
        required=True,
    ),
    USDMNode(
        id="drug_name",
        label="Investigational Drug Name",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the INN or internal code name for the investigational product.",
        parent_ids=[],
        required=True,
    ),
    USDMNode(
        id="indication",
        label="Therapeutic Indication",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the disease or condition being studied (full description including qualifiers).",
        parent_ids=[],
        required=True,
    ),
    USDMNode(
        id="study_phase",
        label="Clinical Phase",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the clinical development phase (Phase 1 / 2 / 3 / 4).",
        parent_ids=[],
        required=True,
    ),
    USDMNode(
        id="design_type",
        label="Study Design Type",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the full study design descriptor (e.g. randomized, double-blind, placebo-controlled, parallel-group).",
        parent_ids=[],
        required=True,
    ),
    USDMNode(
        id="blinding",
        label="Blinding",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the blinding type: open-label, single-blind, or double-blind.",
        parent_ids=[],
        required=True,
    ),
    USDMNode(
        id="randomization_type",
        label="Randomization Type",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the randomization method (e.g. stratified, block, central).",
        parent_ids=[],
        required=True,
    ),
    USDMNode(
        id="intervention_model",
        label="Intervention Model",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the intervention model: parallel group, crossover, factorial, single group.",
        parent_ids=[],
        required=True,
    ),
]

# ─────────────────────────────────────────────
# Layer 1 — Objectives, Arms & Epochs (4 nodes)
# USDM classes: Objective, StudyArm, StudyEpoch
# ─────────────────────────────────────────────
layer_1_nodes: List[USDMNode] = [
    USDMNode(
        id="objectives",
        label="Study Objectives",
        data_type="list",
        cardinality="1..*",
        extraction_hint=(
            "Extract ALL study objectives (primary, secondary, and exploratory) as a list of "
            "USDM Objective objects. Each object must have: "
            "\"text\" (full objective statement beginning with 'To...'), "
            "\"level\" (one of: PRIMARY, SECONDARY, EXPLORATORY)."
        ),
        parent_ids=["indication", "study_phase"],
        parent_predicates={"indication": "ADDRESSES", "study_phase": "CONDUCTED IN"},
        required=True,
    ),
    USDMNode(
        id="study_arms",
        label="Study Arms",
        data_type="list",
        cardinality="1..*",
        extraction_hint=(
            "Extract each treatment arm as a USDM StudyArm object. Each object must have: "
            "\"name\" (arm name, e.g. 'STR-4021 10 mg once daily'), "
            "\"type\" (one of: EXPERIMENTAL, ACTIVE_COMPARATOR, PLACEBO_COMPARATOR, NO_INTERVENTION), "
            "\"description\" (brief description of the arm's treatment)."
        ),
        parent_ids=["design_type", "drug_name"],
        parent_predicates={"design_type": "STRUCTURED AS", "drug_name": "INCLUDES"},
        required=True,
    ),
    USDMNode(
        id="study_epochs",
        label="Study Epochs",
        data_type="list",
        cardinality="1..*",
        extraction_hint=(
            "Extract each study epoch as a USDM StudyEpoch object. Each object must have: "
            "\"name\" (epoch name, e.g. 'Screening'), "
            "\"type\" (one of: SCREENING, RUN_IN, TREATMENT, FOLLOW_UP, WASH_OUT, OTHER), "
            "\"durationWeeks\" (duration of the epoch in weeks as a number)."
        ),
        parent_ids=["design_type"],
        parent_predicates={"design_type": "ORGANIZED BY"},
        required=True,
    ),
    USDMNode(
        id="enrollment_target",
        label="Total Enrollment Target",
        data_type="number",
        cardinality="1",
        extraction_hint="Extract the total planned number of subjects to be randomized.",
        parent_ids=["study_phase"],
        parent_predicates={"study_phase": "SIZED FOR"},
        required=True,
    ),
]

# ─────────────────────────────────────────────
# Layer 2 — Endpoints, Duration & Interventions (5 nodes)
# USDM classes: Endpoint, StudyIntervention
# ─────────────────────────────────────────────
layer_2_nodes: List[USDMNode] = [
    USDMNode(
        id="endpoints",
        label="Study Endpoints",
        data_type="list",
        cardinality="1..*",
        extraction_hint=(
            "Extract ALL study endpoints (primary and secondary) as a list of USDM Endpoint objects. "
            "Each object must have: "
            "\"text\" (full endpoint description), "
            "\"level\" (one of: PRIMARY, SECONDARY, EXPLORATORY), "
            "\"purpose\" (one of: EFFICACY, SAFETY, PHARMACOKINETIC, PHARMACODYNAMIC, BIOMARKER, QUALITY_OF_LIFE, OTHER), "
            "\"timepoint\" (assessment timepoint, e.g. 'Week 24'), "
            "\"instrument\" (measurement instrument or assay, null if not specified)."
        ),
        parent_ids=["objectives", "indication"],
        parent_predicates={"objectives": "OPERATIONALIZE", "indication": "MEASURED IN"},
        required=True,
    ),
    USDMNode(
        id="study_duration_weeks",
        label="Total Study Duration (weeks)",
        data_type="number",
        cardinality="1",
        extraction_hint="Extract the total study duration in weeks from first visit to last visit.",
        parent_ids=["study_epochs"],
        parent_predicates={"study_epochs": "SPANS"},
        required=True,
    ),
    USDMNode(
        id="treatment_duration_weeks",
        label="Treatment Duration (weeks)",
        data_type="number",
        cardinality="1",
        extraction_hint="Extract the length of the treatment period in weeks.",
        parent_ids=["study_epochs"],
        parent_predicates={"study_epochs": "TREATMENT EPOCH OF"},
        required=True,
    ),
    USDMNode(
        id="followup_duration_weeks",
        label="Follow-up Duration (weeks)",
        data_type="number",
        cardinality="0..1",
        extraction_hint="Extract the duration of the follow-up period in weeks. Return 0 if no follow-up.",
        parent_ids=["study_epochs"],
        parent_predicates={"study_epochs": "FOLLOW-UP EPOCH OF"},
        required=False,
    ),
    USDMNode(
        id="study_interventions",
        label="Study Interventions",
        data_type="list",
        cardinality="1..*",
        extraction_hint=(
            "Extract each study intervention as a USDM StudyIntervention object. Each object must have: "
            "\"name\" (intervention name, e.g. 'STR-4021'), "
            "\"type\" (one of: INVESTIGATIONAL, NON_INVESTIGATIONAL), "
            "\"doses\" (list of dose levels as strings, e.g. ['10 mg', '25 mg']), "
            "\"doseUnit\" (unit of dose, e.g. 'mg'), "
            "\"route\" (one of: ORAL, SUBCUTANEOUS, INTRAVENOUS, INTRAMUSCULAR, TOPICAL, INHALED, OTHER), "
            "\"frequency\" (dosing frequency string, e.g. 'ONCE_DAILY', 'TWICE_DAILY', 'WEEKLY'), "
            "\"instructions\" (specific administration instructions, null if none). "
            "Include both the investigational product(s) and any comparator/placebo."
        ),
        parent_ids=["study_arms", "drug_name"],
        parent_predicates={"study_arms": "ADMINISTERED TO", "drug_name": "DEFINES PRODUCT IN"},
        required=True,
    ),
]

# ─────────────────────────────────────────────
# Layer 3 — Population & Eligibility (6 nodes)
# USDM classes: StudyDesignPopulation, EligibilityCriterion
# ─────────────────────────────────────────────
layer_3_nodes: List[USDMNode] = [
    USDMNode(
        id="population_description",
        label="Population Description",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the brief narrative description of the study population.",
        parent_ids=["indication", "study_phase"],
        parent_predicates={"indication": "ELIGIBLE FOR", "study_phase": "SUITABLE FOR"},
        required=True,
    ),
    USDMNode(
        id="population_age_min",
        label="Minimum Age (years)",
        data_type="number",
        cardinality="1",
        extraction_hint="Extract the minimum eligible age in years.",
        parent_ids=["indication"],
        parent_predicates={"indication": "AGE RANGE FOR"},
        required=True,
    ),
    USDMNode(
        id="population_age_max",
        label="Maximum Age (years)",
        data_type="number",
        cardinality="0..1",
        extraction_hint="Extract the maximum eligible age in years. Return None if no upper limit.",
        parent_ids=["indication"],
        parent_predicates={"indication": "AGE RANGE FOR"},
        required=False,
    ),
    USDMNode(
        id="sex_criteria",
        label="Sex/Gender Eligibility",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the sex or gender eligibility (e.g. 'male and female', 'female only').",
        parent_ids=["indication"],
        parent_predicates={"indication": "SEX ELIGIBILITY FOR"},
        required=True,
    ),
    USDMNode(
        id="eligibility_criteria",
        label="Eligibility Criteria",
        data_type="list",
        cardinality="1..*",
        extraction_hint=(
            "Extract ALL eligibility criteria (inclusion and exclusion) as a list of "
            "USDM EligibilityCriterion objects. Each object must have: "
            "\"text\" (full criterion text), "
            "\"category\" (INCLUSION or EXCLUSION), "
            "\"identifier\" (criterion number, e.g. 'IC-1', 'EC-3')."
        ),
        parent_ids=["indication", "population_age_min"],
        parent_predicates={"indication": "QUALIFIES PATIENTS FOR", "population_age_min": "CONSTRAINED BY"},
        required=True,
    ),
    USDMNode(
        id="enrollment_target_per_arm",
        label="Enrollment Target Per Arm",
        data_type="number",
        cardinality="1",
        extraction_hint="Extract the planned number of subjects per treatment arm.",
        parent_ids=["enrollment_target", "study_arms"],
        parent_predicates={"enrollment_target": "DERIVED FROM", "study_arms": "ALLOCATED ACROSS"},
        required=True,
    ),
]

# ─────────────────────────────────────────────
# Layer 4 — Randomization (3 nodes)
# ─────────────────────────────────────────────
layer_4_nodes: List[USDMNode] = [
    USDMNode(
        id="randomization_ratio",
        label="Randomization Ratio",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the randomization ratio between arms (e.g. '1:1', '2:1:1').",
        parent_ids=["study_arms"],
        parent_predicates={"study_arms": "ALLOCATES"},
        required=True,
    ),
    USDMNode(
        id="stratification_factors",
        label="Stratification Factors",
        data_type="list",
        cardinality="0..*",
        extraction_hint="Extract the randomization stratification factors as a list. Return empty list if none.",
        parent_ids=["indication", "randomization_type"],
        parent_predicates={"indication": "BALANCED BY", "randomization_type": "APPLIED WITHIN"},
        required=False,
    ),
    USDMNode(
        id="dose_modifications",
        label="Dose Modifications",
        data_type="list",
        cardinality="0..*",
        extraction_hint="Extract any dose modification rules as a list. Return empty list if none.",
        parent_ids=["study_interventions", "indication"],
        parent_predicates={"study_interventions": "ADJUSTED FROM", "indication": "DRIVEN BY"},
        required=False,
    ),
]

# ─────────────────────────────────────────────
# Layer 5 — Statistical Analysis Plan (6 nodes)
# ─────────────────────────────────────────────
layer_5_nodes: List[USDMNode] = [
    USDMNode(
        id="primary_analysis_type",
        label="Primary Analysis Type",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the primary statistical model or analysis method (e.g. MMRM, ANCOVA, logistic regression).",
        parent_ids=["endpoints", "study_phase"],
        parent_predicates={"endpoints": "ANALYZED BY", "study_phase": "APPROPRIATE FOR"},
        required=True,
    ),
    USDMNode(
        id="statistical_analysis_primary",
        label="Primary Statistical Analysis Description",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the full narrative description of the primary statistical analysis method.",
        parent_ids=["endpoints", "primary_analysis_type"],
        parent_predicates={"endpoints": "ANALYZED VIA", "primary_analysis_type": "IMPLEMENTED AS"},
        required=True,
    ),
    USDMNode(
        id="analysis_populations",
        label="Analysis Populations",
        data_type="list",
        cardinality="1..*",
        extraction_hint="Extract the defined analysis populations as a list (e.g. Full Analysis Set, Per Protocol Set, Safety Population).",
        parent_ids=["enrollment_target", "design_type"],
        parent_predicates={"enrollment_target": "DEFINES SIZE OF", "design_type": "STRATIFIES INTO"},
        required=True,
    ),
    USDMNode(
        id="missing_data_approach",
        label="Missing Data Approach",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the approach to handling missing data (e.g. multiple imputation, LOCF, MMRM handles missing implicitly).",
        parent_ids=["primary_analysis_type", "endpoints"],
        parent_predicates={"primary_analysis_type": "HANDLES MISSINGNESS FOR", "endpoints": "IMPUTES MISSING VALUES FOR"},
        required=True,
    ),
    USDMNode(
        id="multiplicity_adjustments",
        label="Multiplicity Adjustments",
        data_type="string",
        cardinality="0..1",
        extraction_hint="Extract any multiplicity adjustment procedures (e.g. Hochberg, Bonferroni, hierarchical testing). Return None if not specified.",
        parent_ids=["endpoints"],
        parent_predicates={"endpoints": "CONTROLS ERROR RATE FOR"},
        required=False,
    ),
    USDMNode(
        id="estimands",
        label="Estimands",
        data_type="string",
        cardinality="0..1",
        extraction_hint="Extract the estimand framework description per ICH E9(R1) if present. Return None if not specified.",
        parent_ids=["endpoints", "primary_analysis_type"],
        parent_predicates={"endpoints": "DEFINES TARGET FOR", "primary_analysis_type": "SPECIFIED WITHIN"},
        required=False,
    ),
]

# ─────────────────────────────────────────────
# Layer 6 — Schedule of Activities (4 nodes)
# USDM classes: Encounter, Activity, ScheduledActivityInstance
# ─────────────────────────────────────────────
layer_6_nodes: List[USDMNode] = [
    USDMNode(
        id="encounters",
        label="Study Encounters",
        data_type="list",
        cardinality="1..*",
        extraction_hint=(
            "Extract all scheduled study encounters (visits) as USDM Encounter objects. "
            "Each object must have: "
            "\"name\" (visit name, e.g. 'Screening', 'Week 4'), "
            "\"encounterType\" (one of: SCHEDULED, UNSCHEDULED, TELEPHONE, VIRTUAL), "
            "\"timingWeek\" (scheduled week relative to randomisation as a number; negative for pre-randomisation), "
            "\"windowBeforeDays\" (allowable window before scheduled date in days, 0 if not specified), "
            "\"windowAfterDays\" (allowable window after scheduled date in days, 0 if not specified)."
        ),
        parent_ids=["study_epochs", "study_duration_weeks"],
        parent_predicates={"study_epochs": "SCHEDULED WITHIN", "study_duration_weeks": "DISTRIBUTED ACROSS"},
        required=True,
    ),
    USDMNode(
        id="activities",
        label="Study Activities",
        data_type="list",
        cardinality="1..*",
        extraction_hint=(
            "Extract all study activities and assessments as USDM Activity objects. "
            "Each object must have: "
            "\"name\" (activity name, e.g. 'Physical Examination', 'Central Lab HbA1c'), "
            "\"activityType\" (one of: PROCEDURE, BIOLOGICAL_SAMPLE_COLLECTION, QUESTIONNAIRE, "
            "ADMINISTRATIVE, IMAGING, STUDY_DRUG_ADMINISTRATION, OTHER)."
        ),
        parent_ids=["endpoints", "study_interventions"],
        parent_predicates={"endpoints": "ASSESSED THROUGH", "study_interventions": "ADMINISTERED AS"},
        required=True,
    ),
    USDMNode(
        id="scheduled_activity_instances",
        label="Scheduled Activity Instances",
        data_type="list",
        cardinality="1..*",
        extraction_hint=(
            "Extract the Schedule of Activities as a list of USDM ScheduledActivityInstance objects. "
            "Each object represents one activity at one encounter and must have: "
            "\"encounterId\" (encounter name matching an entry from the encounters node), "
            "\"activityId\" (activity name matching an entry from the activities node), "
            "\"epochId\" (epoch name matching an entry from the study_epochs node), "
            "\"mandatory\" (boolean — true if the activity is required at this encounter). "
            "Include ALL activity-encounter combinations from the Schedule of Activities table."
        ),
        parent_ids=["encounters", "activities", "study_epochs"],
        parent_predicates={"encounters": "SCHEDULES", "activities": "INSTANCES OF", "study_epochs": "OCCURS WITHIN"},
        required=True,
    ),
    USDMNode(
        id="sample_size_rationale",
        label="Sample Size Rationale",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the sample size justification narrative including assumptions and power calculation.",
        parent_ids=["endpoints", "primary_analysis_type", "enrollment_target"],
        parent_predicates={"endpoints": "POWERS DETECTION OF", "primary_analysis_type": "ASSUMES MODEL OF", "enrollment_target": "JUSTIFIES"},
        required=True,
    ),
]

# ─────────────────────────────────────────────
# Layer 7 — Safety Monitoring (3 nodes)
# ─────────────────────────────────────────────
layer_7_nodes: List[USDMNode] = [
    USDMNode(
        id="stopping_rules",
        label="Stopping Rules",
        data_type="list",
        cardinality="0..*",
        extraction_hint="Extract any pre-defined stopping rules or safety stopping criteria as a list.",
        parent_ids=["study_phase", "endpoints"],
        parent_predicates={"study_phase": "APPROPRIATE FOR", "endpoints": "TRIGGERED BY"},
        required=False,
    ),
    USDMNode(
        id="dsmb_structure",
        label="DSMB/DMC Structure",
        data_type="string",
        cardinality="0..1",
        extraction_hint="Extract the Data Safety Monitoring Board or Data Monitoring Committee structure description. Return None if no DSMB.",
        parent_ids=["study_phase", "enrollment_target"],
        parent_predicates={"study_phase": "WARRANTED FOR", "enrollment_target": "SCALED TO"},
        required=False,
    ),
    USDMNode(
        id="adverse_event_reporting_period",
        label="Adverse Event Reporting Period",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the adverse event reporting period description (e.g. from first dose through 30 days after last dose).",
        parent_ids=["study_duration_weeks", "followup_duration_weeks"],
        parent_predicates={"study_duration_weeks": "COVERS TREATMENT WITHIN", "followup_duration_weeks": "EXTENDED THROUGH"},
        required=True,
    ),
]

# ─────────────────────────────────────────────
# Layer 8 — Administrative (3 nodes)
# ─────────────────────────────────────────────
layer_8_nodes: List[USDMNode] = [
    USDMNode(
        id="informed_consent_version",
        label="Informed Consent Version",
        data_type="string",
        cardinality="1",
        extraction_hint="Extract the informed consent form version number or date from the administrative section.",
        parent_ids=["protocol_version"],
        parent_predicates={"protocol_version": "ALIGNED WITH"},
        required=True,
    ),
    USDMNode(
        id="regulatory_references",
        label="Regulatory References",
        data_type="list",
        cardinality="1..*",
        extraction_hint="Extract the list of regulatory guidelines referenced (e.g. ICH E6(R2), ICH E9(R1), EMA CHMP guideline for T2DM).",
        parent_ids=["indication", "study_phase"],
        parent_predicates={"indication": "GUIDED BY GUIDELINES FOR", "study_phase": "GOVERNED BY"},
        required=True,
    ),
    USDMNode(
        id="abbreviations_key_terms",
        label="Abbreviations and Key Terms",
        data_type="list",
        cardinality="0..*",
        extraction_hint="Extract the list of abbreviations and key terms with their definitions from the abbreviations section.",
        parent_ids=["drug_name", "indication"],
        parent_predicates={"drug_name": "DEFINES ABBREVIATION FOR", "indication": "PROVIDES CONTEXT FOR"},
        required=False,
    ),
]

# ─────────────────────────────────────────────
# Layer metadata
# ─────────────────────────────────────────────
LAYER_METADATA = [
    {
        "name": "Protocol Identity",
        "description": "Core identifiers and design foundations: sponsor, protocol number/version/date, study title, drug, indication, phase, design, blinding, randomization.",
        "extraction_note": "Extract directly from title page, header, and synopsis. These are foundational facts required before any other layer.",
    },
    {
        "name": "Objectives, Arms & Epochs",
        "description": "USDM Objective objects (with level: PRIMARY/SECONDARY/EXPLORATORY), StudyArm objects (with USDM type codes), StudyEpoch objects (with type and durationWeeks), and total enrollment target.",
        "extraction_note": "Extract from Objectives section and Study Design Overview. Each arm must carry a USDM type code (EXPERIMENTAL, ACTIVE_COMPARATOR, PLACEBO_COMPARATOR). Each epoch must carry an epoch type and duration in weeks.",
    },
    {
        "name": "Endpoints, Duration & Interventions",
        "description": "USDM Endpoint objects (with level, purpose, timepoint, instrument), study duration scalars, and StudyIntervention objects (with dose levels, route, frequency).",
        "extraction_note": "Extract from Endpoints, Study Design, and Treatment sections. Endpoints must carry level (PRIMARY/SECONDARY) and purpose (EFFICACY/SAFETY/etc.). Interventions must cover both investigational product and comparator/placebo.",
    },
    {
        "name": "Population & Eligibility",
        "description": "Population demographics and USDM EligibilityCriterion objects with category (INCLUSION/EXCLUSION) and identifier, plus enrollment target per arm.",
        "extraction_note": "Extract from Eligibility Criteria section. All criteria must carry a category and identifier (IC-1, EC-1, etc.).",
    },
    {
        "name": "Randomization",
        "description": "Randomization ratio, stratification factors, and dose modification rules.",
        "extraction_note": "Extract from Randomization and Treatment sections. Ratio must be consistent with number of study arms.",
    },
    {
        "name": "Statistical Analysis Plan",
        "description": "Analysis types, populations, missing data approach, multiplicity adjustments, estimands.",
        "extraction_note": "Extract from Statistical Methods section. Analysis must align with endpoints.",
    },
    {
        "name": "Schedule of Activities",
        "description": "USDM Encounter objects (visits with timing and windows), Activity objects (with activityType), ScheduledActivityInstance objects linking each activity to an encounter and epoch, plus sample size rationale.",
        "extraction_note": "Extract from Schedule of Activities table. ScheduledActivityInstance is the key USDM entity — each row represents one activity at one encounter. Every cell in the SoA table should produce one instance.",
    },
    {
        "name": "Safety Monitoring",
        "description": "Stopping rules, DSMB structure, adverse event reporting period.",
        "extraction_note": "Extract from Safety Monitoring section. AE reporting period spans treatment plus follow-up.",
    },
    {
        "name": "Administrative",
        "description": "Informed consent version, regulatory references, abbreviations.",
        "extraction_note": "Extract from Administrative / References / Abbreviations sections at end of document.",
    },
]

# ─────────────────────────────────────────────
# Master layer list
# ─────────────────────────────────────────────
ALL_LAYERS: List[List[USDMNode]] = [
    layer_0_nodes,   # 12 nodes — Protocol Identity
    layer_1_nodes,   #  4 nodes — Objectives (Objective), Arms (StudyArm), Epochs (StudyEpoch)
    layer_2_nodes,   #  5 nodes — Endpoints (Endpoint), Duration, Interventions (StudyIntervention)
    layer_3_nodes,   #  6 nodes — Population, Eligibility (EligibilityCriterion)
    layer_4_nodes,   #  3 nodes — Randomization
    layer_5_nodes,   #  6 nodes — Statistical Analysis Plan
    layer_6_nodes,   #  4 nodes — SoA: Encounter, Activity, ScheduledActivityInstance
    layer_7_nodes,   #  3 nodes — Safety Monitoring
    layer_8_nodes,   #  3 nodes — Administrative
]
# Total: 46 nodes


def get_layer_nodes(layer_index: int) -> List[USDMNode]:
    """Return the list of nodes for the given layer index (0-8)."""
    if layer_index < 0 or layer_index >= len(ALL_LAYERS):
        raise IndexError(f"Layer index {layer_index} out of range (0-8)")
    return ALL_LAYERS[layer_index]


def get_extraction_prompt_context(
    layer_index: int, confirmed_values: Dict[str, Any]
) -> Dict[str, str]:
    """
    Returns a mapping of {node_id: constraint_string} for each node in the layer.
    The constraint string is a plain-English note about what parent values constrain
    this extraction, useful for priming the LLM extractor.
    """
    nodes = get_layer_nodes(layer_index)
    context: Dict[str, str] = {}
    for node in nodes:
        constraints = []
        for pid in node.parent_ids:
            if pid in confirmed_values and confirmed_values[pid] is not None:
                val = confirmed_values[pid]
                constraints.append(f"{pid} = {val!r}")
        if constraints:
            context[node.id] = "Constrained by: " + "; ".join(constraints)
        else:
            context[node.id] = "No confirmed parent constraints yet."
    return context


def get_nodes_blocking_layer(
    layer_index: int, confirmed_ids: Set[str]
) -> List[str]:
    """
    Returns the IDs of required parent nodes for this layer that have NOT yet
    been confirmed. These must be resolved before extraction can proceed.
    """
    nodes = get_layer_nodes(layer_index)
    all_required_parents: Set[str] = set()
    for node in nodes:
        # Only blocking if the current node is required
        if node.required:
            for pid in node.parent_ids:
                # Find if parent node is required
                parent_node = _find_node(pid)
                if parent_node and parent_node.required:
                    all_required_parents.add(pid)
    return [pid for pid in all_required_parents if pid not in confirmed_ids]


def _find_node(node_id: str) -> Optional[USDMNode]:
    """Find a node by ID across all layers."""
    for layer in ALL_LAYERS:
        for node in layer:
            if node.id == node_id:
                return node
    return None
