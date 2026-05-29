import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
from llm.testbed import LLMTestBed

st.title("LLM Testbed")
st.caption("Evaluate accuracy and calibration against ground truth pairs")

use_real = st.sidebar.toggle("Use Real LLM", value=False)

if st.button("Run Evaluation"):
    with st.spinner("Running all ground truth pairs..."):
        testbed = LLMTestBed(use_real_llm=use_real)
        results = testbed.run_accuracy_eval()
        cal = testbed.run_calibration_eval(results)
        df = testbed.to_dataframe(results)

    st.subheader("Results by Pair")
    st.dataframe(df[["pair_id", "section_id", "auto_score", "confidence", "notes"]])

    col1, col2, col3 = st.columns(3)
    col1.metric("Avg Auto-Score", f"{df['auto_score'].mean():.3f}")
    col2.metric("Calibration Delta", f"{cal['calibration_delta']:.3f}")
    col3.metric("Calibration", "PASSED ✓" if cal['calibration_passed'] else "FAILED ✗")

    st.subheader("Expert Rating")
    st.caption("Fill in expert ratings below to complete the evaluation.")
    for _, row in df.iterrows():
        with st.expander(f"{row['pair_id']} — {row['section_id']}"):
            st.write("**Generated:**")
            st.write(row['generated_prose'])
            st.write("**Gold:**")
            st.write(row['gold_prose'])
            st.selectbox(
                "Rating",
                ["— select —", "minor_revision", "major_revision", "unacceptable"],
                key=f"rating_{row['pair_id']}"
            )
