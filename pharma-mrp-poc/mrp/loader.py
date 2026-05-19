import yaml
import sys
from datetime import date
from pathlib import Path
from mrp.domain import (
    Material, MaterialType, CanonicalUnit, StepMaterial, StepMaterialRole,
    EquipmentCost, LaborCost, UtilityCost, Step, Edge, ProcessGraph,
    PriceEntry, PriceList, ProcessConfig, SweepParameter, SweepDefinition,
    SweepMode, ParameterType, DistributionSpec, DistributionType,
    CorrelationPair, MCDefinition,
    Plant, PlantAsset, DepreciationMethod, MaintenanceSchedule, MaintenanceType,
    StepAssetAssignment, CapacityUtilisationBand,
    PlantNetwork, NetworkPlantMembership, VolumeTarget,
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


def _parse_date(s: str | None) -> date | None:
    if s is None:
        return None
    return date.fromisoformat(str(s))


def load_plant(path: Path) -> Plant:
    """
    Load a plant YAML file → Plant domain object.

    YAML maintenance frequency strings map to MaintenanceType:
      "annual"    → FIXED_ANNUAL
      "per_batch" → PER_BATCH
      "pct_capex" → PCT_OF_CAPEX (value field = percentage)
    """
    data = yaml.safe_load(path.read_text())
    p = data["plant"]

    bands = []
    for b in data.get("utilisation_bands", []):
        bands.append(CapacityUtilisationBand(
            label=b["label"],
            utilisation_lower_pct=float(b["utilisation_lower_pct"]),
            utilisation_upper_pct=float(b["utilisation_upper_pct"]),
            labor_cost_multiplier=float(b.get("labor_cost_multiplier", 1.0)),
            utility_cost_multiplier=float(b.get("utility_cost_multiplier", 1.0)),
        ))

    plant_id = p.get("id", path.stem)
    assets = []
    for a in data.get("assets", []):
        step_assignments = []
        for sid, pct in (a.get("step_assignments") or {}).items():
            step_assignments.append(StepAssetAssignment(
                step_id=str(sid),
                allocation_pct=float(pct) * 100.0,
            ))

        maintenance_schedules = []
        for m in a.get("maintenance", []):
            freq = m.get("frequency", "annual")
            if freq == "annual":
                mtype = MaintenanceType.FIXED_ANNUAL
                value = float(m.get("estimated_cost", 0.0))
            elif freq == "per_batch":
                mtype = MaintenanceType.PER_BATCH
                value = float(m.get("estimated_cost", 0.0))
            elif freq == "pct_capex":
                mtype = MaintenanceType.PCT_OF_CAPEX
                value = float(m.get("value", 0.0))
            else:
                mtype = MaintenanceType.FIXED_ANNUAL
                value = float(m.get("estimated_cost", 0.0))
            maintenance_schedules.append(MaintenanceSchedule(
                maintenance_type=mtype,
                value=value,
                description=m.get("description", ""),
            ))

        raw_method = a["depreciation_method"]
        method = DepreciationMethod(raw_method)

        assets.append(PlantAsset(
            id=a["id"],
            plant_id=plant_id,
            name=a["name"],
            asset_class=a.get("asset_class", ""),
            capex_cost=float(a["capex_cost"]),
            useful_life_years=float(a["useful_life_years"]),
            salvage_value=float(a.get("salvage_value", 0.0)),
            depreciation_method=method,
            gmp_qualified=bool(a.get("gmp_qualified", False)),
            purchase_date=_parse_date(a.get("purchase_date")),
            declining_balance_rate=float(a["declining_balance_rate"])
            if "declining_balance_rate" in a else None,
            total_expected_batches=int(a["total_expected_batches"])
            if "total_expected_batches" in a else None,
            step_assignments=step_assignments,
            maintenance_schedules=maintenance_schedules,
        ))

    return Plant(
        id=plant_id,
        name=p["name"],
        currency=p.get("currency", "USD"),
        annual_capacity_kg_api=float(p["annual_capacity_kg_api"]),
        gmp_facility=bool(p.get("gmp_facility", False)),
        location=p.get("location"),
        commissioned_date=_parse_date(p.get("commissioned_date")),
        decommission_date=_parse_date(p.get("decommission_date")),
        assets=assets,
        utilisation_bands=bands,
    )


def load_risk_profile(
    path: Path,
    graph: "ProcessGraph",
    prices: "PriceList",
) -> "RiskProfile":
    """Load risk profile YAML → RiskProfile."""
    from mrp.domain import (
        CDMONode, RiskVector, RiskVectorType, MaterialRiskMetadata,
        StepRiskMetadata, StepCriticality, RiskProfile,
    )

    data = yaml.safe_load(path.read_text())

    # 1. Build cdmo_nodes dict
    cdmo_nodes: dict = {}
    for node_data in data.get("cdmo_nodes", []):
        node = CDMONode(
            id=node_data["id"],
            name=node_data["name"],
            country=node_data["country"],
            city=node_data.get("city"),
            biosecure_act_listed=bool(node_data.get("biosecure_act_listed", False)),
            pentagon_1260h_listed=bool(node_data.get("pentagon_1260h_listed", False)),
            regulatory_watch_flags=list(node_data.get("regulatory_watch_flags", [])),
            notes=node_data.get("notes"),
        )
        cdmo_nodes[node.id] = node

    # 2. Build material_risk dict (lower-cased name → MaterialRiskMetadata)
    material_risk: dict = {}
    for m in data.get("materials", []):
        cdmo_node_ref = m.get("cdmo_node")
        if cdmo_node_ref and cdmo_node_ref not in cdmo_nodes:
            print(f"WARNING: cdmo_node '{cdmo_node_ref}' referenced by material '{m['name']}' not found")
        key = m["name"].lower()
        material_risk[key] = MaterialRiskMetadata(
            material_name=m["name"],
            country_of_origin=m.get("country_of_origin"),
            cdmo_node_id=cdmo_node_ref if cdmo_node_ref in cdmo_nodes else None,
            single_source=bool(m.get("single_source", False)),
            alternative_supplier_lead_time_weeks=m.get("alternative_supplier_lead_time_weeks"),
            indirect_china_exposure=bool(m.get("indirect_china_exposure", False)),
            indirect_china_exposure_notes=m.get("indirect_china_exposure_notes"),
            tariff_hs_code=m.get("tariff_hs_code"),
        )

    # 3. Build step_risk dict (lower-cased name → StepRiskMetadata)
    step_risk: dict = {}
    for s in data.get("steps", []):
        cdmo_node_ref = s.get("cdmo_node")
        if cdmo_node_ref and cdmo_node_ref not in cdmo_nodes:
            print(f"WARNING: cdmo_node '{cdmo_node_ref}' referenced by step '{s['name']}' not found")
        criticality_raw = s.get("step_criticality", "standard")
        try:
            criticality = StepCriticality(criticality_raw)
        except ValueError:
            criticality = StepCriticality.STANDARD
        key = s["name"].lower()
        step_risk[key] = StepRiskMetadata(
            step_name=s["name"],
            cdmo_node_id=cdmo_node_ref if cdmo_node_ref in cdmo_nodes else None,
            step_criticality=criticality,
        )

    # 4. Build risk_vectors list
    risk_vectors: list = []
    for rv in data.get("risk_vectors", []):
        rv_type_raw = rv.get("type", "")
        try:
            rv_type = RiskVectorType(rv_type_raw)
        except ValueError:
            print(f"WARNING: unknown risk_vector type '{rv_type_raw}' for '{rv.get('id')}' — skipping")
            continue
        cdmo_node_ref = rv.get("cdmo_node")
        if cdmo_node_ref and cdmo_node_ref not in cdmo_nodes:
            print(f"WARNING: cdmo_node '{cdmo_node_ref}' referenced by risk_vector '{rv.get('id')}' not found")
        risk_vectors.append(RiskVector(
            id=rv["id"],
            name=rv["name"],
            risk_vector_type=rv_type,
            tariff_rate_pct=float(rv["tariff_rate_pct"]) if "tariff_rate_pct" in rv else None,
            geography=rv.get("geography"),
            include_indirect=bool(rv.get("include_indirect", False)),
            cdmo_node_id=cdmo_node_ref if cdmo_node_ref in cdmo_nodes else None,
            emergency_premium_pct=float(rv.get("emergency_premium_pct", 50.0)),
        ))

    # 5. Tariff sweep config
    sweep = data.get("tariff_sweep", {})
    tariff_sweep_rates = [float(r) for r in sweep.get("rates", [])]
    tariff_sweep_geography = sweep.get("geography")
    tariff_sweep_include_indirect = bool(sweep.get("include_indirect", False))

    # 6. Warn about materials in graph without country_of_origin
    if graph is not None:
        for step in graph.steps.values():
            for sm in step.materials:
                key = sm.material.name.lower()
                mat_meta = material_risk.get(key)
                if mat_meta is None or mat_meta.country_of_origin is None:
                    print(
                        f"WARNING: Material '{sm.material.name}' in step '{step.name}' "
                        "has no country_of_origin tag in risk profile"
                    )

    profile_data = data.get("risk_profile", {})
    return RiskProfile(
        name=profile_data.get("name", path.stem),
        cdmo_nodes=cdmo_nodes,
        material_risk=material_risk,
        step_risk=step_risk,
        risk_vectors=risk_vectors,
        tariff_sweep_rates=tariff_sweep_rates,
        tariff_sweep_geography=tariff_sweep_geography,
        tariff_sweep_include_indirect=tariff_sweep_include_indirect,
    )


def load_network(path: Path, plant_base_dir: Path | None = None) -> tuple[PlantNetwork, dict]:
    """
    Load a network YAML → (PlantNetwork, plant_map).

    plant_map: dict[plant_id → Plant] for all plants in the network.
    Plant files are resolved relative to plant_base_dir (defaults to path.parent).
    """
    base = plant_base_dir or path.parent
    data = yaml.safe_load(path.read_text())
    n = data["network"]

    volume_targets = [
        VolumeTarget(year=int(vt["year"]), volume_kg_api=float(vt["target_kg"]))
        for vt in data.get("volume_targets", [])
    ]

    memberships = []
    plant_map: dict[str, Plant] = {}
    for pm in data.get("plants", []):
        plant_file = base / pm["plant_file"]
        plant = load_plant(plant_file)
        plant_map[plant.id] = plant
        commissioned = _parse_date(pm.get("commissioned_date"))
        memberships.append(NetworkPlantMembership(
            plant_id=plant.id,
            volume_allocation_kg=float(pm.get("volume_allocation_kg", 0.0)),
            start_year=commissioned.year if commissioned else None,
        ))

    network = PlantNetwork(
        id=n.get("id", path.stem),
        name=n["name"],
        currency=n.get("currency", "USD"),
        plants=memberships,
        volume_targets=volume_targets,
    )
    return network, plant_map
