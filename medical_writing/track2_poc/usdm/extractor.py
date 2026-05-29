"""
LayerExtractor: uses Claude to extract USDM node values from a parsed document,
one layer at a time. Supports stub mode for testing without an API key.
"""
from __future__ import annotations
import json
from typing import Any, Dict, List, Optional
import datetime

from usdm.graph_walk import ALL_LAYERS, get_layer_nodes, get_extraction_prompt_context
from ingestion.verification import ExtractedItem, LayerExtractionResult
import config

# ─────────────────────────────────────────────
# Full section text for stub mode
# (mirrors the synth_phase2_trial.docx content)
# ─────────────────────────────────────────────
STUB_SECTION_TEXTS: Dict[str, str] = {
    "Title Page": (
        "CLINICAL STUDY PROTOCOL\n\n"
        "Protocol Number: STR-4021-201\n"
        "Version 1.0 | Date: 15 January 2026\n\n"
        "Sponsor: Structure Therapeutics\n\n"
        "Full Title: A Phase 2, Randomized, Double-Blind, Placebo-Controlled, "
        "Parallel-Group Study to Evaluate the Efficacy and Safety of STR-4021 in "
        "Adults with Type 2 Diabetes Mellitus with Inadequate Glycemic Control on "
        "Metformin Monotherapy\n\n"
        "Investigational Product: STR-4021\n\n"
        "IND Number: [REDACTED]\n"
        "EudraCT Number: [REDACTED]\n\n"
        "CONFIDENTIAL — This document is the property of Structure Therapeutics "
        "and is supplied for informational purposes only."
    ),
    "Section 1": (
        "1. INTRODUCTION AND BACKGROUND\n\n"
        "Type 2 diabetes mellitus (T2DM) is a chronic metabolic disorder characterised "
        "by insulin resistance and progressive beta-cell dysfunction, resulting in "
        "persistent hyperglycaemia. Globally, approximately 537 million adults are "
        "living with diabetes, a figure projected to reach 783 million by 2045.\n\n"
        "Metformin remains the first-line pharmacotherapy for T2DM. However, a "
        "substantial proportion of patients fail to achieve adequate glycaemic control "
        "(HbA1c <7.0%) on metformin monotherapy, creating a clinical need for "
        "additional therapeutic options.\n\n"
        "The indication for this study is type 2 diabetes mellitus with inadequate "
        "glycemic control on metformin monotherapy. STR-4021 is a novel, orally "
        "bioavailable small-molecule GLP-1 receptor agonist developed by Structure "
        "Therapeutics. Phase 1 data demonstrate glucose-dependent insulinotropic "
        "activity with a favourable safety and tolerability profile, supporting "
        "evaluation in a Phase 2 efficacy and safety study."
    ),
    "Section 2": (
        "2. STUDY DESIGN\n\n"
        "2.1 Overview\n"
        "This is a Phase 2, randomized, double-blind, placebo-controlled, "
        "parallel-group study to evaluate the efficacy and safety of STR-4021 in "
        "adults with T2DM inadequately controlled on stable metformin monotherapy.\n\n"
        "2.2 Treatment Arms\n"
        "Eligible subjects will be randomised in a 1:1:1 ratio using stratified "
        "block randomization to one of three treatment arms:\n"
        "  • STR-4021 10 mg once daily\n"
        "  • STR-4021 25 mg once daily\n"
        "  • Placebo once daily\n\n"
        "Stratification factors are HbA1c at screening (<8.5% vs ≥8.5%) and "
        "geographic region (North America vs Europe vs Asia-Pacific).\n\n"
        "2.3 Study Periods\n"
        "The study comprises three epochs:\n"
        "  1. Screening Period: 4 weeks (Weeks −4 to 0)\n"
        "  2. Treatment Period: 24 weeks (Weeks 0–24)\n"
        "  3. Follow-up Period: 4 weeks (Weeks 24–28)\n\n"
        "Total study duration is 28 weeks from randomisation to last visit.\n\n"
        "2.4 Blinding\n"
        "The study is double-blind. Subjects, investigators, site staff, and Sponsor "
        "personnel will remain blinded to treatment assignment throughout the study. "
        "STR-4021 tablets and matching placebo tablets are identical in appearance, "
        "size, and packaging."
    ),
    "Section 3": (
        "3. STUDY OBJECTIVES\n\n"
        "3.1 Primary Objective\n"
        "To evaluate the efficacy of STR-4021 compared to placebo on glycaemic control "
        "as measured by change from baseline in HbA1c at Week 24 in adults with type 2 "
        "diabetes mellitus inadequately controlled on metformin monotherapy.\n\n"
        "3.2 Secondary Objectives\n"
        "The secondary objectives of this study are:\n"
        "  1. To evaluate the effect of STR-4021 on fasting plasma glucose (FPG) at "
        "Week 24 compared to placebo.\n"
        "  2. To assess the proportion of patients achieving HbA1c <7.0% at Week 24 "
        "in each STR-4021 dose group versus placebo.\n"
        "  3. To evaluate body weight change from baseline at Week 24 in each "
        "STR-4021 dose group versus placebo.\n"
        "  4. To assess the safety and tolerability of STR-4021 at doses of 10 mg "
        "and 25 mg once daily over 24 weeks of treatment.\n\n"
        "3.3 Exploratory Objectives\n"
        "The exploratory objectives of this study are:\n"
        "  1. To evaluate biomarkers of insulin secretion and beta-cell function "
        "(C-peptide, proinsulin/insulin ratio) following STR-4021 treatment.\n"
        "  2. To explore patient-reported outcomes related to treatment satisfaction "
        "using the Diabetes Treatment Satisfaction Questionnaire (DTSQ)."
    ),
    "Section 4": (
        "4. ENDPOINTS\n\n"
        "4.1 Primary Efficacy Endpoint\n"
        "Change from baseline in HbA1c (%) at Week 24, assessed by a central laboratory "
        "HbA1c assay (NGSP-certified) at the Week 24 visit.\n\n"
        "4.2 Secondary Endpoints\n"
        "  1. Change from baseline in fasting plasma glucose (mmol/L) at Week 24.\n"
        "  2. Proportion of patients achieving HbA1c <7.0% at Week 24.\n"
        "  3. Change from baseline in body weight (kg) at Week 24.\n"
        "  4. Change from baseline in 2-hour postprandial glucose at Week 24 "
        "(measured during a standardised mixed-meal tolerance test).\n\n"
        "4.3 Safety Endpoints\n"
        "  • Incidence and severity of adverse events (AEs) and serious adverse events (SAEs).\n"
        "  • Clinically significant changes in laboratory parameters, vital signs, "
        "physical examination findings, and ECG.\n"
        "  • Incidence of hypoglycaemic episodes (symptomatic and confirmed).\n\n"
        "4.4 Exploratory Endpoints\n"
        "Biomarker and patient-reported outcome assessments as detailed in Section 3.3."
    ),
    "Section 5": (
        "5. SUBJECT SELECTION\n\n"
        "5.1 Population Description\n"
        "Adult patients aged 18 to 75 years with type 2 diabetes mellitus inadequately "
        "controlled on stable metformin monotherapy will be enrolled. Approximately "
        "240 subjects will be randomised across approximately 40 study sites.\n\n"
        "5.2 Inclusion Criteria\n"
        "Subjects must meet ALL of the following criteria to be eligible:\n"
        "  1. Age 18–75 years inclusive at the time of informed consent.\n"
        "  2. Documented diagnosis of type 2 diabetes mellitus for at least 6 months "
        "prior to screening.\n"
        "  3. HbA1c ≥7.5% and ≤10.5% at screening (central lab).\n"
        "  4. On stable metformin monotherapy (≥1000 mg/day) for at least 3 months "
        "prior to screening, with no dose changes anticipated during the study.\n"
        "  5. BMI ≥22 and ≤42 kg/m² at screening.\n"
        "  6. Male and female subjects are eligible. Female subjects of childbearing "
        "potential must use highly effective contraception.\n\n"
        "5.3 Exclusion Criteria\n"
        "Subjects will be excluded if they meet ANY of the following criteria:\n"
        "  1. Type 1 diabetes mellitus or latent autoimmune diabetes in adults (LADA).\n"
        "  2. Use of any antidiabetic agent other than metformin within 3 months of "
        "screening (including insulin, GLP-1 receptor agonists, SGLT2 inhibitors, "
        "DPP-4 inhibitors, sulfonylureas, or thiazolidinediones).\n"
        "  3. eGFR <45 mL/min/1.73m² at screening (CKD-EPI formula).\n"
        "  4. History of severe hypoglycaemia (requiring third-party assistance) "
        "within 6 months of screening.\n"
        "  5. Active or clinically significant cardiovascular disease (myocardial "
        "infarction, stroke, unstable angina, or heart failure NYHA Class III–IV) "
        "within 6 months prior to screening."
    ),
    "Section 6": (
        "6. STUDY TREATMENT\n\n"
        "6.1 Investigational Product\n"
        "STR-4021 is supplied as 10 mg and 25 mg immediate-release oral tablets. "
        "Placebo tablets are matching in appearance.\n\n"
        "6.2 Dose and Administration\n"
        "Subjects will receive STR-4021 10 mg, STR-4021 25 mg, or matching placebo "
        "orally once daily in the morning with or without food for 24 weeks. "
        "Study drug should be taken at approximately the same time each day.\n\n"
        "6.3 Dose Modifications\n"
        "No dose titration is planned. The following rules apply:\n"
        "  • Dose interruption is permitted for SAEs until resolution or medical review.\n"
        "  • Permanent discontinuation is required for confirmed severe hypersensitivity "
        "reactions (e.g., anaphylaxis, angioedema).\n"
        "Investigators may reduce or interrupt dosing for other clinically significant "
        "safety findings at their discretion.\n\n"
        "6.4 Comparator\n"
        "Matching placebo tablet administered orally once daily in the morning, "
        "identical in appearance, size, weight, and packaging to active tablets.\n\n"
        "6.5 Concomitant Medications\n"
        "Background metformin therapy must remain stable throughout the study. "
        "Rescue therapy with open-label antidiabetics (excluding GLP-1 RAs) is "
        "permitted for persistent hyperglycaemia meeting pre-defined criteria."
    ),
    "Section 7": (
        "7. SAMPLE SIZE AND ENROLMENT\n\n"
        "7.1 Enrolment Target\n"
        "Approximately 240 subjects will be randomised across approximately 40 study "
        "sites globally (North America, Europe, and Asia-Pacific).\n\n"
        "7.2 Enrolment Per Arm\n"
        "80 subjects per arm (1:1:1 randomisation across three treatment groups), "
        "for a total of 240 randomised subjects. This sample size accounts for an "
        "anticipated dropout rate of up to 15%.\n\n"
        "7.3 Justification\n"
        "A sample size of 80 subjects per arm provides 90% power to detect a "
        "between-group difference of 0.6% in HbA1c change from baseline, assuming "
        "a standard deviation of 1.1% and using a two-sided test at α=0.05 (see "
        "Section 8 for full statistical rationale)."
    ),
    "Section 8": (
        "8. STATISTICAL METHODS\n\n"
        "8.1 Primary Analysis\n"
        "The primary analysis will use a Mixed Model for Repeated Measures (MMRM) "
        "with change from baseline in HbA1c as the dependent variable. Fixed effects "
        "will include treatment arm, visit, treatment-by-visit interaction, baseline "
        "HbA1c, and stratification factors (HbA1c category, region). An unstructured "
        "covariance matrix will be used; restricted maximum likelihood (REML) "
        "estimation will be applied.\n\n"
        "8.2 Analysis Populations\n"
        "  • Full Analysis Set (FAS): all randomised subjects who received at least "
        "one dose of study drug and have at least one post-baseline HbA1c assessment. "
        "The FAS is the primary analysis population.\n"
        "  • Per Protocol Set (PPS): FAS subjects without major protocol deviations "
        "affecting the primary endpoint.\n"
        "  • Safety Population: all randomised subjects who received at least one "
        "dose of study drug.\n\n"
        "8.3 Missing Data\n"
        "Missing data are handled implicitly by the MMRM model under the missing at "
        "random (MAR) assumption. Sensitivity analyses using pattern mixture models "
        "with control-based imputation will be conducted to assess robustness.\n\n"
        "8.4 Multiplicity\n"
        "A hierarchical testing procedure will be used for secondary endpoints in "
        "order of pre-specified priority to control the family-wise Type I error "
        "rate at 0.05 (two-sided).\n\n"
        "8.5 Estimands\n"
        "The treatment policy estimand (per ICH E9(R1)) is the primary estimand, "
        "targeting the effect of treatment assignment regardless of treatment "
        "discontinuation or use of rescue medication.\n\n"
        "8.6 Sample Size Rationale\n"
        "A sample size of 80 subjects per arm (240 total) provides 90% power to "
        "detect a between-group difference of 0.6% in HbA1c change from baseline, "
        "assuming a pooled standard deviation of 1.1% and a two-sided significance "
        "level of 0.05. The sample size allows for up to 15% dropout rate."
    ),
    "Section 9": (
        "9. SCHEDULE OF ACTIVITIES\n\n"
        "9.1 Visit Schedule\n"
        "Visits are scheduled at: Screening (Week −4), Baseline/Randomisation "
        "(Week 0), Week 4, Week 8, Week 12, Week 16, Week 20, End of Treatment "
        "(Week 24), and Follow-up (Week 28). A ±3 day window is permitted for "
        "all post-baseline visits.\n\n"
        "9.2 Assessments Per Visit\n"
        "The following assessments are performed according to the Schedule of "
        "Activities table:\n"
        "  • Informed Consent (Screening only)\n"
        "  • Eligibility Assessment and Medical History (Screening)\n"
        "  • Physical Examination and Vital Signs (all visits)\n"
        "  • 12-lead ECG (Screening, Baseline, Week 12, Week 24, Follow-up)\n"
        "  • Central Laboratory: HbA1c, FPG, lipid panel, eGFR, LFTs, urinalysis "
        "(Screening, Baseline, Week 12, Week 24, Follow-up)\n"
        "  • OGTT/MMTT (Baseline, Week 12, Week 24)\n"
        "  • Body Weight and Waist Circumference (all visits)\n"
        "  • Study Drug Dispensing and Accountability (all treatment visits)\n"
        "  • Concomitant Medication Review (all visits)\n"
        "  • Adverse Event Assessment (all visits)"
    ),
    "Section 10": (
        "10. SAFETY MONITORING\n\n"
        "10.1 Stopping Rules\n"
        "Individual subject stopping criteria:\n"
        "  • Two consecutive HbA1c values >11.5% while on treatment (persistent "
        "uncontrolled hyperglycaemia): subject will be discontinued and offered "
        "rescue therapy.\n"
        "  • Any confirmed SAE judged by the investigator to be related to study drug.\n\n"
        "Trial-level stopping criteria:\n"
        "  • DSMB recommendation to stop the trial based on a pre-specified "
        "safety signal (e.g., unexpected serious drug-related adverse events).\n\n"
        "10.2 Data Safety Monitoring Board\n"
        "An independent Data Safety Monitoring Board (DSMB) comprising three members "
        "(two experienced clinicians and one independent statistician) will review "
        "unblinded cumulative safety data at pre-specified intervals (after ~60 and "
        "~120 subjects complete at least 12 weeks of treatment). The DSMB charter "
        "defines stopping rules and review procedures.\n\n"
        "10.3 Adverse Event Reporting Period\n"
        "All adverse events will be collected from the time of informed consent "
        "through 30 days after the last dose of study drug (or through the Follow-up "
        "Visit at Week 28, whichever is later). Serious adverse events will be "
        "reported from first dose through 30 days after last dose."
    ),
    "Section 11": (
        "11. ETHICAL CONSIDERATIONS AND REGULATORY COMPLIANCE\n\n"
        "11.1 Informed Consent\n"
        "Written informed consent will be obtained from all subjects prior to any "
        "study-related procedures. The informed consent process will be conducted in "
        "accordance with ICH E6(R2) Good Clinical Practice (GCP) guidelines.\n\n"
        "Informed Consent Form Version: ICF Version 1.0, dated 15 January 2026. "
        "Any future amendments to the ICF will be submitted for IRB/IEC approval "
        "before use and will be assigned a new version number aligned with the "
        "protocol amendment version.\n\n"
        "11.2 Ethics Committee Approval\n"
        "This study will be conducted in accordance with the ethical principles of "
        "the Declaration of Helsinki, applicable ICH guidelines, and local regulatory "
        "requirements. Protocol approval from all relevant Institutional Review "
        "Boards (IRBs) and Independent Ethics Committees (IECs) must be obtained "
        "before site activation.\n\n"
        "11.3 Subject Privacy\n"
        "Subject data will be handled in compliance with applicable privacy regulations "
        "including GDPR (EU) and HIPAA (USA)."
    ),
    "References": (
        "REFERENCES AND REGULATORY GUIDELINES\n\n"
        "This study is conducted in accordance with the following regulatory guidelines "
        "and references:\n\n"
        "  1. ICH E6(R2) Good Clinical Practice: Integrated Addendum to ICH E6(R1). "
        "European Medicines Agency, 2016.\n"
        "  2. ICH E9 Statistical Principles for Clinical Trials. European Medicines "
        "Agency, 1998.\n"
        "  3. ICH E9(R1) Addendum on Estimands and Sensitivity Analysis in Clinical "
        "Trials. European Medicines Agency, 2019.\n"
        "  4. EMA Guideline on Clinical Investigation of Medicinal Products in the "
        "Treatment or Prevention of Diabetes Mellitus (CPMP/EWP/1080/00 Rev. 2).\n"
        "  5. 21 CFR Parts 50, 54, 56, 312 — FDA Regulations for Clinical Investigations "
        "(United States Code of Federal Regulations).\n"
        "  6. International Diabetes Federation. IDF Diabetes Atlas, 10th Edition, 2021."
    ),
    "Abbreviations": (
        "ABBREVIATIONS AND DEFINITION OF TERMS\n\n"
        "AE      Adverse Event\n"
        "BMI     Body Mass Index\n"
        "CKD-EPI Chronic Kidney Disease Epidemiology Collaboration (eGFR formula)\n"
        "DSMB    Data Safety Monitoring Board\n"
        "DTSQ    Diabetes Treatment Satisfaction Questionnaire\n"
        "ECG     Electrocardiogram\n"
        "eGFR    estimated Glomerular Filtration Rate\n"
        "FAS     Full Analysis Set\n"
        "FPG     Fasting Plasma Glucose\n"
        "GCP     Good Clinical Practice\n"
        "GLP-1   Glucagon-Like Peptide-1\n"
        "HbA1c   Glycated Haemoglobin\n"
        "ICF     Informed Consent Form\n"
        "ICH     International Council for Harmonisation\n"
        "IEC     Independent Ethics Committee\n"
        "IRB     Institutional Review Board\n"
        "LADA    Latent Autoimmune Diabetes in Adults\n"
        "LFT     Liver Function Test\n"
        "MMRM    Mixed Model for Repeated Measures\n"
        "MMTT    Mixed-Meal Tolerance Test\n"
        "NGSP    National Glycohemoglobin Standardization Program\n"
        "OGTT    Oral Glucose Tolerance Test\n"
        "PPS     Per Protocol Set\n"
        "REML    Restricted Maximum Likelihood\n"
        "SAE     Serious Adverse Event\n"
        "SGLT2   Sodium-Glucose Co-transporter 2\n"
        "T2DM    Type 2 Diabetes Mellitus"
    ),
}

# ─────────────────────────────────────────────
# Stub data matching synth_phase2_trial.json values
# ─────────────────────────────────────────────
STUB_EXTRACTIONS: Dict[int, List[Dict[str, Any]]] = {
    0: [
        {"node_id": "sponsor_name", "value": "Structure Therapeutics", "confidence": 0.95, "source_section": "Title Page", "source_quote": "Sponsor: Structure Therapeutics"},
        {"node_id": "protocol_number", "value": "STR-4021-201", "confidence": 0.97, "source_section": "Title Page", "source_quote": "Protocol Number: STR-4021-201"},
        {"node_id": "protocol_version", "value": "Version 1.0", "confidence": 0.98, "source_section": "Title Page", "source_quote": "Version 1.0"},
        {"node_id": "protocol_date", "value": "15 January 2026", "confidence": 0.97, "source_section": "Title Page", "source_quote": "Date: 15 January 2026"},
        {"node_id": "study_title", "value": "A Phase 2, Randomized, Double-Blind, Placebo-Controlled, Parallel-Group Study to Evaluate the Efficacy and Safety of STR-4021 in Adults with Type 2 Diabetes Mellitus with Inadequate Glycemic Control on Metformin Monotherapy", "confidence": 0.96, "source_section": "Title Page", "source_quote": "Full Title"},
        {"node_id": "drug_name", "value": "STR-4021", "confidence": 0.99, "source_section": "Title Page", "source_quote": "Investigational Product: STR-4021"},
        {"node_id": "indication", "value": "type 2 diabetes mellitus with inadequate glycemic control on metformin monotherapy", "confidence": 0.98, "source_section": "Section 1", "source_quote": "indication: type 2 diabetes mellitus"},
        {"node_id": "study_phase", "value": "Phase 2", "confidence": 0.99, "source_section": "Title Page", "source_quote": "Phase 2"},
        {"node_id": "design_type", "value": "randomized, double-blind, placebo-controlled, parallel-group", "confidence": 0.97, "source_section": "Section 2", "source_quote": "randomized, double-blind, placebo-controlled"},
        {"node_id": "blinding", "value": "double-blind", "confidence": 0.98, "source_section": "Section 2", "source_quote": "double-blind"},
        {"node_id": "randomization_type", "value": "stratified block randomization", "confidence": 0.92, "source_section": "Section 2", "source_quote": "stratified block randomization"},
        {"node_id": "intervention_model", "value": "parallel group", "confidence": 0.97, "source_section": "Section 2", "source_quote": "parallel-group"},
    ],
    1: [
        {"node_id": "objectives", "value": [
            {"text": "To evaluate the efficacy of STR-4021 compared to placebo on glycaemic control as measured by change from baseline in HbA1c at Week 24 in adults with T2DM inadequately controlled on metformin monotherapy.", "level": "PRIMARY"},
            {"text": "To evaluate the effect of STR-4021 on fasting plasma glucose (FPG) at Week 24 compared to placebo.", "level": "SECONDARY"},
            {"text": "To assess the proportion of patients achieving HbA1c <7.0% at Week 24.", "level": "SECONDARY"},
            {"text": "To evaluate body weight change from baseline at Week 24.", "level": "SECONDARY"},
            {"text": "To assess the safety and tolerability of STR-4021 at doses of 10 mg and 25 mg once daily.", "level": "SECONDARY"},
            {"text": "To evaluate biomarkers of insulin secretion and beta-cell function.", "level": "EXPLORATORY"},
            {"text": "To explore patient-reported outcomes using the Diabetes Treatment Satisfaction Questionnaire (DTSQ).", "level": "EXPLORATORY"},
        ], "confidence": 0.94, "source_section": "Section 3", "source_quote": "3.1 Primary Objective\nTo evaluate the efficacy of STR-4021..."},
        {"node_id": "study_arms", "value": [
            {"name": "STR-4021 10 mg", "type": "EXPERIMENTAL", "description": "STR-4021 10 mg oral tablet once daily for 24 weeks"},
            {"name": "STR-4021 25 mg", "type": "EXPERIMENTAL", "description": "STR-4021 25 mg oral tablet once daily for 24 weeks"},
            {"name": "Placebo", "type": "PLACEBO_COMPARATOR", "description": "Matching placebo oral tablet once daily for 24 weeks"},
        ], "confidence": 0.96, "source_section": "Section 2", "source_quote": "randomised in a 1:1:1 ratio...STR-4021 10 mg once daily, STR-4021 25 mg once daily, Placebo once daily"},
        {"node_id": "study_epochs", "value": [
            {"name": "Screening", "type": "SCREENING", "durationWeeks": 4},
            {"name": "Treatment", "type": "TREATMENT", "durationWeeks": 24},
            {"name": "Follow-up", "type": "FOLLOW_UP", "durationWeeks": 4},
        ], "confidence": 0.97, "source_section": "Section 2", "source_quote": "Screening Period: 4 weeks...Treatment Period: 24 weeks...Follow-up Period: 4 weeks"},
        {"node_id": "enrollment_target", "value": 240, "confidence": 0.97, "source_section": "Section 7", "source_quote": "approximately 240 subjects will be randomised"},
    ],
    2: [
        {"node_id": "endpoints", "value": [
            {"text": "Change from baseline in HbA1c (%)", "level": "PRIMARY", "purpose": "EFFICACY", "timepoint": "Week 24", "instrument": "Central laboratory HbA1c assay (NGSP-certified)"},
            {"text": "Change from baseline in fasting plasma glucose (mmol/L)", "level": "SECONDARY", "purpose": "EFFICACY", "timepoint": "Week 24", "instrument": None},
            {"text": "Proportion of patients achieving HbA1c <7.0%", "level": "SECONDARY", "purpose": "EFFICACY", "timepoint": "Week 24", "instrument": None},
            {"text": "Change from baseline in body weight (kg)", "level": "SECONDARY", "purpose": "EFFICACY", "timepoint": "Week 24", "instrument": None},
            {"text": "Change from baseline in 2-hour postprandial glucose", "level": "SECONDARY", "purpose": "EFFICACY", "timepoint": "Week 24", "instrument": "Standardised mixed-meal tolerance test (MMTT)"},
        ], "confidence": 0.96, "source_section": "Section 4", "source_quote": "4.1 Primary Efficacy Endpoint\nChange from baseline in HbA1c (%) at Week 24"},
        {"node_id": "study_duration_weeks", "value": 28, "confidence": 0.97, "source_section": "Section 2", "source_quote": "Total study duration is 28 weeks"},
        {"node_id": "treatment_duration_weeks", "value": 24, "confidence": 0.98, "source_section": "Section 2", "source_quote": "Treatment Period: 24 weeks (Weeks 0–24)"},
        {"node_id": "followup_duration_weeks", "value": 4, "confidence": 0.95, "source_section": "Section 2", "source_quote": "Follow-up Period: 4 weeks (Weeks 24–28)"},
        {"node_id": "study_interventions", "value": [
            {"name": "STR-4021", "type": "INVESTIGATIONAL", "doses": ["10 mg", "25 mg"], "doseUnit": "mg", "route": "ORAL", "frequency": "ONCE_DAILY", "instructions": "Administer orally once daily in the morning with or without food"},
            {"name": "Placebo", "type": "NON_INVESTIGATIONAL", "doses": ["0 mg"], "doseUnit": "mg", "route": "ORAL", "frequency": "ONCE_DAILY", "instructions": "Administer orally once daily in the morning with or without food"},
        ], "confidence": 0.96, "source_section": "Section 6", "source_quote": "STR-4021 is supplied as 10 mg and 25 mg immediate-release oral tablets...once daily in the morning with or without food"},
    ],
    3: [
        {"node_id": "population_description", "value": "Adult patients aged 18 to 75 years with type 2 diabetes mellitus inadequately controlled on stable metformin monotherapy.", "confidence": 0.95, "source_section": "Section 5", "source_quote": "Adult patients aged 18 to 75 years with type 2 diabetes mellitus"},
        {"node_id": "population_age_min", "value": 18, "confidence": 0.99, "source_section": "Section 5", "source_quote": "Age 18–75 years inclusive at the time of informed consent"},
        {"node_id": "population_age_max", "value": 75, "confidence": 0.99, "source_section": "Section 5", "source_quote": "Age 18–75 years inclusive at the time of informed consent"},
        {"node_id": "sex_criteria", "value": "male and female", "confidence": 0.97, "source_section": "Section 5", "source_quote": "Male and female subjects are eligible"},
        {"node_id": "eligibility_criteria", "value": [
            {"text": "Age 18–75 years inclusive at the time of informed consent", "category": "INCLUSION", "identifier": "IC-1"},
            {"text": "Documented diagnosis of T2DM for at least 6 months prior to screening", "category": "INCLUSION", "identifier": "IC-2"},
            {"text": "HbA1c ≥7.5% and ≤10.5% at screening (central lab)", "category": "INCLUSION", "identifier": "IC-3"},
            {"text": "On stable metformin monotherapy (≥1000 mg/day) for at least 3 months prior to screening", "category": "INCLUSION", "identifier": "IC-4"},
            {"text": "BMI ≥22 and ≤42 kg/m² at screening", "category": "INCLUSION", "identifier": "IC-5"},
            {"text": "Type 1 diabetes mellitus or LADA", "category": "EXCLUSION", "identifier": "EC-1"},
            {"text": "Use of any antidiabetic agent other than metformin within 3 months of screening", "category": "EXCLUSION", "identifier": "EC-2"},
            {"text": "eGFR <45 mL/min/1.73m² at screening (CKD-EPI)", "category": "EXCLUSION", "identifier": "EC-3"},
            {"text": "History of severe hypoglycaemia within 6 months of screening", "category": "EXCLUSION", "identifier": "EC-4"},
            {"text": "Active cardiovascular disease within 6 months of screening", "category": "EXCLUSION", "identifier": "EC-5"},
        ], "confidence": 0.97, "source_section": "Section 5", "source_quote": "5.2 Inclusion Criteria...5.3 Exclusion Criteria"},
        {"node_id": "enrollment_target_per_arm", "value": 80, "confidence": 0.95, "source_section": "Section 7", "source_quote": "80 subjects per arm (1:1:1 randomisation across three treatment groups)"},
    ],
    4: [
        {"node_id": "randomization_ratio", "value": "1:1:1", "confidence": 0.96, "source_section": "Section 2", "source_quote": "randomised in a 1:1:1 ratio using stratified block randomization"},
        {"node_id": "stratification_factors", "value": ["HbA1c at screening (<8.5% vs ≥8.5%)", "Geographic region (North America vs Europe vs Asia-Pacific)"], "confidence": 0.91, "source_section": "Section 2", "source_quote": "Stratification factors are HbA1c at screening (<8.5% vs ≥8.5%) and geographic region"},
        {"node_id": "dose_modifications", "value": ["Dose interruption permitted for SAEs until resolution or medical review", "Permanent discontinuation required for confirmed severe hypersensitivity reactions (e.g. anaphylaxis, angioedema)"], "confidence": 0.88, "source_section": "Section 6", "source_quote": "6.3 Dose Modifications\nNo dose titration is planned"},
    ],
    5: [
        {"node_id": "primary_analysis_type", "value": "Mixed Model for Repeated Measures (MMRM)", "confidence": 0.98, "source_section": "Section 8", "source_quote": "MMRM"},
        {"node_id": "statistical_analysis_primary", "value": "The primary analysis will use a Mixed Model for Repeated Measures (MMRM) with change from baseline in HbA1c as the dependent variable, treatment arm, visit, treatment-by-visit interaction, baseline HbA1c, and stratification factors as covariates. Restricted maximum likelihood (REML) estimation will be used.", "confidence": 0.93, "source_section": "Section 8", "source_quote": "MMRM analysis"},
        {"node_id": "analysis_populations", "value": ["Full Analysis Set (FAS): all randomized subjects who received at least one dose", "Per Protocol Set (PPS): FAS subjects without major protocol deviations", "Safety Population: all randomized subjects who received at least one dose of study drug"], "confidence": 0.95, "source_section": "Section 8", "source_quote": "analysis populations"},
        {"node_id": "missing_data_approach", "value": "Missing data are handled implicitly by the MMRM model under the missing at random (MAR) assumption. Sensitivity analyses using pattern mixture models will be conducted.", "confidence": 0.91, "source_section": "Section 8", "source_quote": "missing data"},
        {"node_id": "multiplicity_adjustments", "value": "A hierarchical testing procedure will be used for secondary endpoints in order of pre-specified priority.", "confidence": 0.89, "source_section": "Section 8", "source_quote": "hierarchical testing"},
        {"node_id": "estimands", "value": "The treatment policy estimand (per ICH E9(R1)) is the primary estimand, targeting the effect of treatment assignment regardless of treatment discontinuation.", "confidence": 0.88, "source_section": "Section 8", "source_quote": "estimand"},
    ],
    6: [
        {"node_id": "encounters", "value": [
            {"name": "Screening",              "encounterType": "SCHEDULED", "timingWeek": -4, "windowBeforeDays": 0, "windowAfterDays": 0},
            {"name": "Baseline/Randomisation", "encounterType": "SCHEDULED", "timingWeek":  0, "windowBeforeDays": 0, "windowAfterDays": 0},
            {"name": "Week 4",                 "encounterType": "SCHEDULED", "timingWeek":  4, "windowBeforeDays": 3, "windowAfterDays": 3},
            {"name": "Week 8",                 "encounterType": "SCHEDULED", "timingWeek":  8, "windowBeforeDays": 3, "windowAfterDays": 3},
            {"name": "Week 12",                "encounterType": "SCHEDULED", "timingWeek": 12, "windowBeforeDays": 3, "windowAfterDays": 3},
            {"name": "Week 16",                "encounterType": "SCHEDULED", "timingWeek": 16, "windowBeforeDays": 3, "windowAfterDays": 3},
            {"name": "Week 20",                "encounterType": "SCHEDULED", "timingWeek": 20, "windowBeforeDays": 3, "windowAfterDays": 3},
            {"name": "End of Treatment",       "encounterType": "SCHEDULED", "timingWeek": 24, "windowBeforeDays": 3, "windowAfterDays": 3},
            {"name": "Follow-up",              "encounterType": "SCHEDULED", "timingWeek": 28, "windowBeforeDays": 3, "windowAfterDays": 3},
        ], "confidence": 0.96, "source_section": "Section 9", "source_quote": "Visits are scheduled at: Screening (Week −4), Baseline/Randomisation (Week 0)...±3 day window is permitted"},
        {"node_id": "activities", "value": [
            {"name": "Informed Consent",                           "activityType": "ADMINISTRATIVE"},
            {"name": "Eligibility Assessment",                     "activityType": "ADMINISTRATIVE"},
            {"name": "Medical History",                            "activityType": "ADMINISTRATIVE"},
            {"name": "Physical Examination",                       "activityType": "PROCEDURE"},
            {"name": "Vital Signs",                                "activityType": "PROCEDURE"},
            {"name": "12-lead ECG",                                "activityType": "PROCEDURE"},
            {"name": "Central Lab (HbA1c, FPG, lipids, eGFR)",    "activityType": "BIOLOGICAL_SAMPLE_COLLECTION"},
            {"name": "OGTT/MMTT",                                  "activityType": "PROCEDURE"},
            {"name": "Study Drug Dispensing",                      "activityType": "STUDY_DRUG_ADMINISTRATION"},
            {"name": "Concomitant Medications Review",             "activityType": "ADMINISTRATIVE"},
            {"name": "Adverse Event Assessment",                   "activityType": "ADMINISTRATIVE"},
            {"name": "Body Weight",                                "activityType": "PROCEDURE"},
            {"name": "Waist Circumference",                        "activityType": "PROCEDURE"},
        ], "confidence": 0.93, "source_section": "Section 9", "source_quote": "9.2 Assessments Per Visit\nInformed Consent...Physical Examination...Central Laboratory"},
        {"node_id": "scheduled_activity_instances", "value": [
            # Screening
            {"encounterId": "Screening", "activityId": "Informed Consent",                        "epochId": "Screening", "mandatory": True},
            {"encounterId": "Screening", "activityId": "Eligibility Assessment",                  "epochId": "Screening", "mandatory": True},
            {"encounterId": "Screening", "activityId": "Medical History",                         "epochId": "Screening", "mandatory": True},
            {"encounterId": "Screening", "activityId": "Physical Examination",                    "epochId": "Screening", "mandatory": True},
            {"encounterId": "Screening", "activityId": "Vital Signs",                             "epochId": "Screening", "mandatory": True},
            {"encounterId": "Screening", "activityId": "12-lead ECG",                             "epochId": "Screening", "mandatory": True},
            {"encounterId": "Screening", "activityId": "Central Lab (HbA1c, FPG, lipids, eGFR)", "epochId": "Screening", "mandatory": True},
            {"encounterId": "Screening", "activityId": "Body Weight",                             "epochId": "Screening", "mandatory": True},
            {"encounterId": "Screening", "activityId": "Waist Circumference",                     "epochId": "Screening", "mandatory": True},
            # Baseline/Randomisation
            {"encounterId": "Baseline/Randomisation", "activityId": "Physical Examination",                    "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Baseline/Randomisation", "activityId": "Vital Signs",                             "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Baseline/Randomisation", "activityId": "12-lead ECG",                             "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Baseline/Randomisation", "activityId": "Central Lab (HbA1c, FPG, lipids, eGFR)", "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Baseline/Randomisation", "activityId": "OGTT/MMTT",                              "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Baseline/Randomisation", "activityId": "Study Drug Dispensing",                   "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Baseline/Randomisation", "activityId": "Body Weight",                             "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Baseline/Randomisation", "activityId": "Waist Circumference",                     "epochId": "Treatment", "mandatory": True},
            # Week 4
            {"encounterId": "Week 4", "activityId": "Vital Signs",                  "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 4", "activityId": "Study Drug Dispensing",         "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 4", "activityId": "Concomitant Medications Review","epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 4", "activityId": "Adverse Event Assessment",      "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 4", "activityId": "Body Weight",                   "epochId": "Treatment", "mandatory": True},
            # Week 8
            {"encounterId": "Week 8", "activityId": "Vital Signs",                  "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 8", "activityId": "Study Drug Dispensing",         "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 8", "activityId": "Concomitant Medications Review","epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 8", "activityId": "Adverse Event Assessment",      "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 8", "activityId": "Body Weight",                   "epochId": "Treatment", "mandatory": True},
            # Week 12
            {"encounterId": "Week 12", "activityId": "Physical Examination",                    "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 12", "activityId": "Vital Signs",                             "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 12", "activityId": "12-lead ECG",                             "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 12", "activityId": "Central Lab (HbA1c, FPG, lipids, eGFR)", "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 12", "activityId": "OGTT/MMTT",                              "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 12", "activityId": "Study Drug Dispensing",                   "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 12", "activityId": "Concomitant Medications Review",          "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 12", "activityId": "Adverse Event Assessment",                "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 12", "activityId": "Body Weight",                             "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 12", "activityId": "Waist Circumference",                     "epochId": "Treatment", "mandatory": True},
            # Week 16
            {"encounterId": "Week 16", "activityId": "Vital Signs",                  "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 16", "activityId": "Study Drug Dispensing",         "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 16", "activityId": "Concomitant Medications Review","epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 16", "activityId": "Adverse Event Assessment",      "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 16", "activityId": "Body Weight",                   "epochId": "Treatment", "mandatory": True},
            # Week 20
            {"encounterId": "Week 20", "activityId": "Vital Signs",                  "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 20", "activityId": "Study Drug Dispensing",         "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 20", "activityId": "Concomitant Medications Review","epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 20", "activityId": "Adverse Event Assessment",      "epochId": "Treatment", "mandatory": True},
            {"encounterId": "Week 20", "activityId": "Body Weight",                   "epochId": "Treatment", "mandatory": True},
            # End of Treatment
            {"encounterId": "End of Treatment", "activityId": "Physical Examination",                    "epochId": "Treatment", "mandatory": True},
            {"encounterId": "End of Treatment", "activityId": "Vital Signs",                             "epochId": "Treatment", "mandatory": True},
            {"encounterId": "End of Treatment", "activityId": "12-lead ECG",                             "epochId": "Treatment", "mandatory": True},
            {"encounterId": "End of Treatment", "activityId": "Central Lab (HbA1c, FPG, lipids, eGFR)", "epochId": "Treatment", "mandatory": True},
            {"encounterId": "End of Treatment", "activityId": "OGTT/MMTT",                              "epochId": "Treatment", "mandatory": True},
            {"encounterId": "End of Treatment", "activityId": "Study Drug Dispensing",                   "epochId": "Treatment", "mandatory": True},
            {"encounterId": "End of Treatment", "activityId": "Concomitant Medications Review",          "epochId": "Treatment", "mandatory": True},
            {"encounterId": "End of Treatment", "activityId": "Adverse Event Assessment",                "epochId": "Treatment", "mandatory": True},
            {"encounterId": "End of Treatment", "activityId": "Body Weight",                             "epochId": "Treatment", "mandatory": True},
            {"encounterId": "End of Treatment", "activityId": "Waist Circumference",                     "epochId": "Treatment", "mandatory": True},
            # Follow-up
            {"encounterId": "Follow-up", "activityId": "Physical Examination",                    "epochId": "Follow-up", "mandatory": True},
            {"encounterId": "Follow-up", "activityId": "Vital Signs",                             "epochId": "Follow-up", "mandatory": True},
            {"encounterId": "Follow-up", "activityId": "12-lead ECG",                             "epochId": "Follow-up", "mandatory": True},
            {"encounterId": "Follow-up", "activityId": "Central Lab (HbA1c, FPG, lipids, eGFR)", "epochId": "Follow-up", "mandatory": True},
            {"encounterId": "Follow-up", "activityId": "Concomitant Medications Review",          "epochId": "Follow-up", "mandatory": True},
            {"encounterId": "Follow-up", "activityId": "Adverse Event Assessment",                "epochId": "Follow-up", "mandatory": True},
            {"encounterId": "Follow-up", "activityId": "Body Weight",                             "epochId": "Follow-up", "mandatory": True},
        ], "confidence": 0.94, "source_section": "Section 9", "source_quote": "9.1 Visit Schedule\n9.2 Assessments Per Visit"},
        {"node_id": "sample_size_rationale", "value": "A sample size of 80 subjects per arm (240 total) provides 90% power to detect a difference of 0.6% in HbA1c between STR-4021 25 mg and placebo, assuming a standard deviation of 1.1% and using a two-sided t-test at alpha=0.05. The sample size allows for up to 15% dropout.", "confidence": 0.94, "source_section": "Section 8", "source_quote": "A sample size of 80 subjects per arm (240 total) provides 90% power"},
    ],
    7: [
        {"node_id": "stopping_rules", "value": ["Individual subject stopping: two consecutive HbA1c values >11.5% while on treatment", "Trial-level stopping: DSMB recommendation based on safety signal"], "confidence": 0.91, "source_section": "Section 10", "source_quote": "stopping rules"},
        {"node_id": "dsmb_structure", "value": "An independent Data Safety Monitoring Board (DSMB) of three members (two clinicians, one statistician) will review unblinded safety data at pre-specified intervals.", "confidence": 0.90, "source_section": "Section 10", "source_quote": "DSMB"},
        {"node_id": "adverse_event_reporting_period", "value": "From first dose of study drug through 30 days after last dose (or 30 days after follow-up visit for serious adverse events).", "confidence": 0.94, "source_section": "Section 10", "source_quote": "AE reporting period"},
    ],
    8: [
        {"node_id": "informed_consent_version", "value": "ICF Version 1.0, dated 15 January 2026", "confidence": 0.96, "source_section": "Section 11", "source_quote": "ICF Version 1.0"},
        {"node_id": "regulatory_references", "value": ["ICH E6(R2) Good Clinical Practice", "ICH E9 Statistical Principles for Clinical Trials", "ICH E9(R1) Addendum on Estimands", "EMA Guideline on Clinical Investigation of Medicinal Products in the Treatment of Diabetes Mellitus", "21 CFR Parts 50, 54, 56, 312"], "confidence": 0.93, "source_section": "References", "source_quote": "regulatory references"},
        {"node_id": "abbreviations_key_terms", "value": ["AE: Adverse Event", "BMI: Body Mass Index", "DSMB: Data Safety Monitoring Board", "eGFR: estimated Glomerular Filtration Rate", "FAS: Full Analysis Set", "FPG: Fasting Plasma Glucose", "GLP-1: Glucagon-Like Peptide-1", "HbA1c: Glycated Haemoglobin", "ICF: Informed Consent Form", "MMRM: Mixed Model for Repeated Measures", "SAE: Serious Adverse Event", "T2DM: Type 2 Diabetes Mellitus"], "confidence": 0.91, "source_section": "Abbreviations", "source_quote": "abbreviations"},
    ],
}


class LayerExtractor:
    """
    Extracts USDM node values from a parsed document for a given layer.
    Uses Claude API when available, falls back to stub data otherwise.
    """

    def __init__(self, use_stub: bool = False):
        self._use_stub = use_stub or not config.ANTHROPIC_API_KEY
        if not self._use_stub:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            except ImportError:
                self._use_stub = True

    def extract_layer(
        self,
        layer_index: int,
        document: Any,
        confirmed_values: Dict[str, Any],
    ) -> LayerExtractionResult:
        """Extract all nodes for the given layer from the document."""
        if self._use_stub:
            return self._stub_extract(layer_index)
        return self._real_extract(layer_index, document, confirmed_values)

    def _stub_extract(self, layer_index: int) -> LayerExtractionResult:
        nodes = get_layer_nodes(layer_index)
        stub_data = STUB_EXTRACTIONS.get(layer_index, [])
        stub_map: Dict[str, Dict] = {d["node_id"]: d for d in stub_data}

        items: List[ExtractedItem] = []
        for i, node in enumerate(nodes):
            stub = stub_map.get(node.id, {})
            section_name = stub.get("source_section")
            item = ExtractedItem(
                item_index=i,
                value=stub.get("value"),
                confidence=stub.get("confidence", 0.75),
                source_section=section_name,
                source_section_text=STUB_SECTION_TEXTS.get(section_name) if section_name else None,
                source_quote=stub.get("source_quote"),
                extraction_notes=f"Stub extraction for {node.id}",
            )
            items.append(item)

        layer_meta = _get_layer_meta(layer_index)
        return LayerExtractionResult(
            layer_index=layer_index,
            layer_name=layer_meta,
            extracted_nodes=items,
            model_used="stub",
            prompt_version="stub-1.0",
            extraction_timestamp=datetime.datetime.utcnow(),
            raw_llm_response=None,
        )

    def _real_extract(
        self,
        layer_index: int,
        document: Any,
        confirmed_values: Dict[str, Any],
    ) -> LayerExtractionResult:
        """Real extraction via Claude API."""
        import anthropic

        nodes = get_layer_nodes(layer_index)
        context = get_extraction_prompt_context(layer_index, confirmed_values)

        # Build document text
        doc_text = _document_to_text(document)

        # Build extraction prompt
        node_specs = []
        for node in nodes:
            spec = (
                f"- id: {node.id}\n"
                f"  label: {node.label}\n"
                f"  data_type: {node.data_type}\n"
                f"  cardinality: {node.cardinality}\n"
                f"  hint: {node.extraction_hint}\n"
                f"  context: {context.get(node.id, '')}"
            )
            node_specs.append(spec)

        prompt = f"""You are a clinical document extraction specialist. Extract structured data from the protocol document below.

Extract the following fields (Layer {layer_index}):
{chr(10).join(node_specs)}

For each field, respond with a JSON object with this structure:
{{
  "extractions": [
    {{
      "node_id": "<id>",
      "value": <extracted value or null>,
      "confidence": <0.0-1.0>,
      "source_section": "<section name>",
      "source_quote": "<brief quote>",
      "extraction_notes": "<any notes>"
    }},
    ...
  ]
}}

DOCUMENT:
{doc_text[:8000]}
"""
        response = self._client.messages.create(
            model=config.MODEL,
            max_tokens=config.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text

        # Parse JSON response
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            data = json.loads(raw[start:end])
            extractions_data = data.get("extractions", [])
        except Exception:
            extractions_data = []

        # Build a lookup from section heading -> section full text
        section_text_map: Dict[str, str] = {}
        if document is not None and hasattr(document, "sections"):
            for sec in document.sections:
                section_text_map[sec.heading] = f"{sec.heading}\n\n{sec.content}"

        # Map to ExtractedItem
        extraction_map: Dict[str, Dict] = {e["node_id"]: e for e in extractions_data}
        items: List[ExtractedItem] = []
        for i, node in enumerate(nodes):
            e = extraction_map.get(node.id, {})
            section_name = e.get("source_section")
            # Try exact match first, then fuzzy (first section whose heading contains the name)
            section_full_text: Optional[str] = section_text_map.get(section_name)
            if section_full_text is None and section_name:
                for heading, text in section_text_map.items():
                    if section_name.lower() in heading.lower() or heading.lower() in section_name.lower():
                        section_full_text = text
                        break
            item = ExtractedItem(
                item_index=i,
                value=e.get("value"),
                confidence=e.get("confidence", 0.0),
                source_section=section_name,
                source_section_text=section_full_text,
                source_quote=e.get("source_quote"),
                extraction_notes=e.get("extraction_notes"),
            )
            items.append(item)

        layer_meta = _get_layer_meta(layer_index)
        return LayerExtractionResult(
            layer_index=layer_index,
            layer_name=layer_meta,
            extracted_nodes=items,
            model_used=config.MODEL,
            prompt_version="v1.0",
            extraction_timestamp=datetime.datetime.utcnow(),
            raw_llm_response=raw,
        )

    def build_prompt_context(
        self,
        layer_index: int,
        confirmed_values: Dict[str, Any],
    ) -> str:
        """Returns the prompt context string for testing."""
        context = get_extraction_prompt_context(layer_index, confirmed_values)
        lines = [f"{k}: {v}" for k, v in context.items()]
        return "\n".join(lines)


def _get_layer_meta(layer_index: int) -> str:
    from usdm.graph_walk import LAYER_METADATA
    if layer_index < len(LAYER_METADATA):
        return LAYER_METADATA[layer_index]["name"]
    return f"Layer {layer_index}"


def _document_to_text(document: Any) -> str:
    """Convert parsed document object to a flat text string."""
    if document is None:
        return ""
    if isinstance(document, str):
        return document
    # If it's a ParsedDocument (from document_parser)
    if hasattr(document, "sections"):
        parts = []
        if hasattr(document, "full_text"):
            return document.full_text
        for section in document.sections:
            if hasattr(section, "heading"):
                parts.append(f"\n## {section.heading}\n")
            if hasattr(section, "content"):
                parts.append(section.content)
        return "\n".join(parts)
    return str(document)
