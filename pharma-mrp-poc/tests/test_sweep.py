import pytest
from pathlib import Path
from mrp.domain import (
    SweepDefinition, SweepMode, SweepParameter, ParameterType, ProcessConfig,
)
from mrp.sweep import expand_sweep, run_sweep
from mrp.units import ureg
from mrp.loader import load_process, load_price_list


EXAMPLES = Path(__file__).parent.parent / "examples"


def _make_config():
    return ProcessConfig(batch_size=ureg.Quantity(50.0, "kg"), num_batches=1)


def test_cartesian_2x3_produces_6_scenarios():
    defn = SweepDefinition(
        name="test",
        mode=SweepMode.CARTESIAN,
        base_config=_make_config(),
        parameters=[
            SweepParameter(
                param_type=ParameterType.STEP_YIELD,
                target_id="step_1",
                label="Yield A",
                values=[70.0, 80.0],
                baseline=75.0,
                unit="%",
            ),
            SweepParameter(
                param_type=ParameterType.STEP_YIELD,
                target_id="step_2",
                label="Yield B",
                values=[80.0, 90.0, 95.0],
                baseline=90.0,
                unit="%",
            ),
        ],
    )
    combos = expand_sweep(defn)
    assert len(combos) == 6


def test_one_at_a_time_produces_correct_scenarios():
    defn = SweepDefinition(
        name="oat",
        mode=SweepMode.ONE_AT_A_TIME,
        base_config=_make_config(),
        parameters=[
            SweepParameter(
                param_type=ParameterType.STEP_YIELD,
                target_id="step_1",
                label="Yield A",
                values=[70.0, 80.0, 90.0],
                baseline=80.0,
                unit="%",
            ),
            SweepParameter(
                param_type=ParameterType.STEP_YIELD,
                target_id="step_2",
                label="Yield B",
                values=[75.0, 85.0, 95.0],
                baseline=85.0,
                unit="%",
            ),
        ],
    )
    combos = expand_sweep(defn)
    # Non-baseline scenarios only (baseline is excluded from each param's sweep)
    assert len(combos) <= 8  # max 4 non-baseline each (2 params × 2 non-baseline each)
    assert len(combos) >= 4  # at minimum 2+2


def test_sweep_125_scenarios_all_succeed():
    """3-parameter × 5-value Cartesian produces 125 scenarios, all successful."""
    graph  = load_process(EXAMPLES / "linear_5step.yaml")
    prices = load_price_list(EXAMPLES / "prices_q2_2026.yaml")
    config = _make_config()

    defn = SweepDefinition(
        name="125-sweep",
        mode=SweepMode.CARTESIAN,
        base_config=config,
        parameters=[
            SweepParameter(
                param_type=ParameterType.STEP_YIELD,
                target_id="step_3",
                label="Step 3 Yield (%)",
                values=[65.0, 70.0, 74.0, 78.0, 82.0],
                baseline=74.0,
                unit="%",
            ),
            SweepParameter(
                param_type=ParameterType.STEP_YIELD,
                target_id="step_4",
                label="Step 4 Yield (%)",
                values=[75.0, 79.0, 82.0, 85.0, 88.0],
                baseline=82.0,
                unit="%",
            ),
            SweepParameter(
                param_type=ParameterType.MATERIAL_PRICE,
                target_id="Starting Material A",
                label="SM-A Price (USD/kg)",
                values=[500.0, 650.0, 820.0, 1000.0, 1250.0],
                baseline=820.0,
                unit="USD/kg",
            ),
        ],
    )

    combos = expand_sweep(defn)
    assert len(combos) == 125

    results, elapsed = run_sweep(graph, config, prices, defn, workers=None)
    successful = [r for r in results if r.status == "success"]
    assert len(successful) == 125
