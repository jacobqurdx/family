import yaml
import sys
from pathlib import Path
from mrp.domain import (
    Material, MaterialType, CanonicalUnit, StepMaterial, StepMaterialRole,
    EquipmentCost, LaborCost, UtilityCost, Step, Edge, ProcessGraph,
    PriceEntry, PriceList, ProcessConfig, SweepParameter, SweepDefinition,
    SweepMode, ParameterType, DistributionSpec, DistributionType,
    CorrelationPair, MCDefinition,
)
from mrp.units import parse_molar_mass, parse_volume_ratio, ureg


def load_process(path: Path) -> ProcessGraph:
    data = yaml.safe_load(path.read_text())
    proc_data = data["process"]
    steps = {}

    for s in data["steps"]:
        step_materials = []
        for m in s.get("materials", []):
            material = Material(
                name=m["name"],
                cas_number=m.get("cas"),
                material_type=MaterialType(m["type"]),
                canonical_unit=CanonicalUnit(m["canonical_unit"]),
                molecular_weight=parse_molar_mass(m["mw_g_mol"]) if m.get("mw_g_mol") else None,
            )
            sm_kwargs = dict(
                material=material,
                role=StepMaterialRole(m["role"]),
                excess_pct=m.get("excess_pct", 0.0),
            )
            if "equivalents" in m:
                sm_kwargs["equivalents"] = float(m["equivalents"])
            elif "volume_ratio_l_per_kg" in m:
                sm_kwargs["volume_ratio"] = parse_volume_ratio(m["volume_ratio_l_per_kg"])
            elif "catalyst_mol_pct" in m:
                sm_kwargs["catalyst_mol_pct"] = float(m["catalyst_mol_pct"])
            step_materials.append(StepMaterial(**sm_kwargs))

        costs_data = s.get("costs", {})

        equipment_costs = []
        for e in costs_data.get("equipment", []):
            equipment_costs.append(EquipmentCost(
                name=e["name"],
                cost_per_batch=float(e["cost_per_batch"]),
                currency=e.get("currency", "USD"),
            ))

        labor_costs = []
        for l in costs_data.get("labor", []):
            labor_costs.append(LaborCost(
                role=l["role"],
                hours_per_batch=float(l["hours_per_batch"]),
                rate_per_hour=float(l["rate_per_hour"]),
                currency=l.get("currency", "USD"),
            ))

        utility_costs = []
        for u in costs_data.get("utilities", []):
            utility_costs.append(UtilityCost(
                utility_type=u["type"],
                quantity_per_batch=float(u["quantity_per_batch"]),
                unit=u["unit"],
                cost_per_unit=float(u["cost_per_unit"]),
                currency=u.get("currency", "USD"),
            ))

        steps[s["id"]] = Step(
            id=s["id"],
            name=s["name"],
            step_yield_pct=float(s["yield_pct"]),
            theoretical_yield_pct=float(s.get("theoretical_yield_pct", 100.0)),
            output_name=s["output"]["name"],
            output_mw=parse_molar_mass(s["output"]["mw_g_mol"]) if s["output"].get("mw_g_mol") else None,
            gmp_step=bool(s.get("gmp", False)),
            reaction_type=s.get("reaction_type"),
            materials=step_materials,
            equipment_costs=equipment_costs,
            labor_costs=labor_costs,
            utility_costs=utility_costs,
        )

    edges = [
        Edge(
            from_step_id=e.get("from"),
            to_step_id=e.get("to"),
            intermediate_name=e.get("intermediate", ""),
            is_terminal=bool(e.get("terminal", False)),
        )
        for e in data["edges"]
    ]

    graph = ProcessGraph(
        name=proc_data["name"],
        target_api_name=proc_data["target_api"]["name"],
        target_api_cas=proc_data["target_api"].get("cas"),
        description=proc_data.get("description"),
        steps=steps,
        edges=edges,
    )

    errors = graph.validate()
    if errors:
        print("ERROR: Process graph validation failed:")
        for err in errors:
            print(f"  • {err}")
        sys.exit(1)

    return graph


def load_price_list(path: Path) -> PriceList:
    data = yaml.safe_load(path.read_text())
    pl = data["price_list"]
    material_prices = {}
    for m in data.get("materials", []):
        key = m["name"].lower()
        if "price_per_kg" in m:
            price, unit = m["price_per_kg"], "kg"
        elif "price_per_L" in m:
            price, unit = m["price_per_L"], "L"
        else:
            raise ValueError(f"Material '{m['name']}' has neither price_per_kg nor price_per_L")
        material_prices[key] = PriceEntry(
            name=m["name"],
            price_per_unit=float(price),
            unit=unit,
            currency=pl.get("currency", "USD"),
            vendor=m.get("vendor"),
            lead_time_days=m.get("lead_time_days"),
            min_order_qty=m.get(f"min_order_{unit}"),
        )
    return PriceList(
        name=pl["name"],
        currency=pl.get("currency", "USD"),
        material_prices=material_prices,
        labor_rates=data.get("labor_rates", {}),
        utility_rates=data.get("utility_rates", {}),
    )


def load_sweep(path: Path, base_config: ProcessConfig) -> SweepDefinition:
    data = yaml.safe_load(path.read_text())
    sw = data["sweep"]
    params = []
    for p in sw["parameters"]:
        params.append(SweepParameter(
            param_type=ParameterType(p["type"]),
            target_id=p.get("target_step") or p.get("target_material", ""),
            label=p["label"],
            values=[float(v) for v in p["values"]],
            baseline=float(p["baseline"]),
            unit=p["unit"],
        ))
    cfg_data = sw.get("base_config", {})
    config = ProcessConfig(
        batch_size=ureg.Quantity(float(cfg_data.get("batch_size_kg", 50.0)), "kg"),
        num_batches=int(cfg_data.get("num_batches", 1)),
    ) if cfg_data else base_config
    return SweepDefinition(
        name=sw["name"],
        mode=SweepMode(sw.get("mode", "cartesian")),
        parameters=params,
        base_config=config,
    )


def load_mc_definition(path: Path) -> MCDefinition:
    data = yaml.safe_load(path.read_text())
    mc = data["monte_carlo"]
    dists = []
    for p in mc["parameters"]:
        raw_params = {k: v for k, v in p.items()
                      if k not in ("type", "target_step", "target_material",
                                   "label", "distribution", "unit",
                                   "clip_low", "clip_high")}
        dists.append(DistributionSpec(
            param_type=ParameterType(p["type"]),
            target_id=p.get("target_step") or p.get("target_material", ""),
            label=p["label"],
            distribution=DistributionType(p["distribution"]),
            unit=p["unit"],
            params={k: float(v) for k, v in raw_params.items()},
            clip_low=p.get("clip_low"),
            clip_high=p.get("clip_high"),
        ))
    cfg_data = mc.get("base_config", {})
    corrs = [
        CorrelationPair(label_a=c[0], label_b=c[1], pearson_r=float(c[2]))
        for c in mc.get("correlations", [])
    ]
    return MCDefinition(
        name=mc["name"],
        n_iterations=int(mc["n_iterations"]),
        distributions=dists,
        base_config=ProcessConfig(
            batch_size=ureg.Quantity(float(cfg_data.get("batch_size_kg", 50.0)), "kg"),
            num_batches=int(cfg_data.get("num_batches", 1)),
        ),
        correlations=corrs,
        random_seed=mc.get("random_seed"),
    )
