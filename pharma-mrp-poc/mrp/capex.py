from __future__ import annotations
from mrp.domain import (
    Plant, PlantAsset, DepreciationMethod, MaintenanceType,
    DepreciationYear, BoMResult, BoMResultWithCapEx,
)


def depreciation_schedule(
    asset: PlantAsset,
    batches_per_year: int | None = None,
) -> list[DepreciationYear]:
    """
    Compute the full annual depreciation schedule for one asset over its useful life.

    - STRAIGHT_LINE: constant charge each year; book value reaches salvage at end of life.
    - DECLINING_BALANCE: apply db_rate to book value; switch to SL when SL charge > DB.
    - DOUBLE_DECLINING: same as DECLINING_BALANCE but rate = 2 / useful_life_years.
    - UNITS_OF_PRODUCTION: charge = rate_per_batch × batches_per_year (or 0 if not provided).

    Raises ValueError if required config is missing (rate for DB, total_batches for UoP).
    Book value never falls below salvage_value (salvage floor enforced each year).
    """
    n_years = int(asset.useful_life_years)

    if asset.depreciation_method == DepreciationMethod.UNITS_OF_PRODUCTION:
        if asset.total_expected_batches is None:
            raise ValueError(
                f"Asset '{asset.id}': total_expected_batches must be set for "
                "UNITS_OF_PRODUCTION method"
            )
    if asset.depreciation_method == DepreciationMethod.DECLINING_BALANCE:
        if asset.declining_balance_rate is None:
            raise ValueError(
                f"Asset '{asset.id}': declining_balance_rate must be set for "
                "DECLINING_BALANCE method"
            )

    uop_rate_per_batch: float = 0.0
    if asset.depreciation_method == DepreciationMethod.UNITS_OF_PRODUCTION:
        uop_rate_per_batch = (
            (asset.capex_cost - asset.salvage_value) / asset.total_expected_batches
        )

    schedule: list[DepreciationYear] = []
    book_value = asset.capex_cost

    for i in range(n_years):
        opening = book_value
        depreciable = opening - asset.salvage_value

        if depreciable <= 0:
            schedule.append(DepreciationYear(
                year_index=i,
                opening_book_value=opening,
                annual_charge=0.0,
                closing_book_value=opening,
                method=asset.depreciation_method.value,
            ))
            continue

        remaining_life = asset.useful_life_years - i

        if asset.depreciation_method == DepreciationMethod.STRAIGHT_LINE:
            charge = depreciable / remaining_life

        elif asset.depreciation_method == DepreciationMethod.DECLINING_BALANCE:
            sl_charge = depreciable / remaining_life
            db_charge = opening * asset.declining_balance_rate
            charge = max(db_charge, sl_charge)

        elif asset.depreciation_method == DepreciationMethod.DOUBLE_DECLINING:
            ddb_rate = 2.0 / asset.useful_life_years
            sl_charge = depreciable / remaining_life
            ddb_charge = opening * ddb_rate
            charge = max(ddb_charge, sl_charge)

        elif asset.depreciation_method == DepreciationMethod.UNITS_OF_PRODUCTION:
            charge = uop_rate_per_batch * (batches_per_year or 0)

        else:
            raise ValueError(f"Unknown depreciation method: {asset.depreciation_method}")

        # Salvage floor: never depreciate below salvage value
        charge = min(charge, depreciable)

        closing = opening - charge
        schedule.append(DepreciationYear(
            year_index=i,
            opening_book_value=opening,
            annual_charge=charge,
            closing_book_value=closing,
            method=asset.depreciation_method.value,
        ))
        book_value = closing

    return schedule


def annual_depreciation_for_plant(
    plant: Plant,
    year_index: int,
    batches_per_year: int | None = None,
) -> float:
    """
    Sum annual depreciation across all plant assets for a given 0-based year index.
    Returns 0.0 for years beyond an asset's useful life.
    """
    total = 0.0
    for asset in plant.assets:
        n = int(asset.useful_life_years)
        if year_index >= n:
            continue
        schedule = depreciation_schedule(asset, batches_per_year=batches_per_year)
        if year_index < len(schedule):
            total += schedule[year_index].annual_charge
    return total


def annual_maintenance_cost(
    plant: Plant,
    batches_per_year: int | None = None,
) -> float:
    """Sum all maintenance costs across all plant assets for one year."""
    total = 0.0
    for asset in plant.assets:
        for ms in asset.maintenance_schedules:
            if ms.maintenance_type == MaintenanceType.FIXED_ANNUAL:
                total += ms.value
            elif ms.maintenance_type == MaintenanceType.PCT_OF_CAPEX:
                total += asset.capex_cost * ms.value / 100.0
            elif ms.maintenance_type == MaintenanceType.PER_BATCH:
                total += ms.value * (batches_per_year or 0)
    return total


def overlay_capex(
    bom: BoMResult,
    plant: Plant,
    analysis_year: int,
    year_index: int,
) -> BoMResultWithCapEx:
    """
    Overlay the CapEx fixed-cost layer onto a completed BoMResult.

    Two-layer COGS architecture:
      Variable = materials + equipment + (labor × band_multiplier) + (utilities × band_multiplier)
      Fixed    = annual_depreciation + annual_maintenance
      COGS     = Variable + Fixed

    Utilisation band is a step function (§2.8.3) — never interpolated between bands.
    Breakeven = total_fixed / variable_per_kg (kg of variable output needed to cover fixed costs).
    """
    batches = bom.config.num_batches
    batch_size_kg = bom.config.batch_size.to("kg").magnitude
    kg_produced = batches * batch_size_kg

    # Utilisation as % of nameplate capacity
    capacity_kg = plant.effective_annual_capacity_kg()
    utilisation_pct = (kg_produced / capacity_kg * 100.0) if capacity_kg > 0 else 0.0

    # Step-function band selection
    labor_mult, utility_mult = plant.variable_cost_multipliers(utilisation_pct)
    bands = sorted(plant.utilisation_bands, key=lambda b: b.utilisation_lower_pct)
    active_band_label = ""
    for band in bands:
        if band.utilisation_lower_pct <= utilisation_pct < band.utilisation_upper_pct:
            active_band_label = band.label
            break
    if not active_band_label and bands:
        active_band_label = bands[-1].label

    # Variable costs (labour and utilities scaled by band multipliers)
    adjusted_labor = bom.total_labor_cost * labor_mult
    adjusted_utility = bom.total_utility_cost * utility_mult
    total_variable = (
        bom.total_material_cost
        + bom.total_equipment_cost
        + adjusted_labor
        + adjusted_utility
    )

    # Fixed costs (annual; independent of batch count this year)
    total_depreciation = annual_depreciation_for_plant(
        plant, year_index, batches_per_year=batches
    )
    total_maintenance = annual_maintenance_cost(plant, batches_per_year=batches)
    total_fixed = total_depreciation + total_maintenance

    total_cogs = total_variable + total_fixed
    cogs_per_kg = total_cogs / kg_produced if kg_produced > 0 else 0.0
    fixed_per_kg = total_fixed / kg_produced if kg_produced > 0 else 0.0
    variable_per_kg = total_variable / kg_produced if kg_produced > 0 else 0.0

    # Breakeven: kg needed at this variable cost rate to recover fixed costs
    breakeven_kg: float | None = None
    if variable_per_kg > 0:
        breakeven_kg = total_fixed / variable_per_kg

    return BoMResultWithCapEx(
        bom=bom,
        plant_name=plant.name,
        analysis_year=analysis_year,
        batches_produced=batches,
        utilisation_pct=utilisation_pct,
        active_band_label=active_band_label,
        adjusted_labor_cost=adjusted_labor,
        adjusted_utility_cost=adjusted_utility,
        total_depreciation_cost=total_depreciation,
        total_maintenance_cost=total_maintenance,
        total_variable_cost=total_variable,
        total_fixed_cost=total_fixed,
        total_cogs=total_cogs,
        cogs_per_kg_api=cogs_per_kg,
        fixed_cost_per_kg_api=fixed_per_kg,
        variable_cost_per_kg_api=variable_per_kg,
        breakeven_kg_api=breakeven_kg,
        currency=plant.currency,
    )
