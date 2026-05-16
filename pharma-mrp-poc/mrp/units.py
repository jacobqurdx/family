from pint import UnitRegistry, Quantity, DimensionalityError

ureg = UnitRegistry()

MASS_UNITS   = {"kg", "g", "mg", "tonne", "lb"}
VOLUME_UNITS = {"L", "mL", "gal", "fl_oz"}
MOLE_UNITS   = {"mol", "mmol", "kmol"}
RATIO_UNITS  = {"L/kg"}

def parse_mass(value: float, unit: str) -> Quantity:
    if unit not in MASS_UNITS:
        raise ValueError(f"'{unit}' is not a recognised mass unit. Valid: {MASS_UNITS}")
    return ureg.Quantity(value, unit).to("kg")

def parse_volume(value: float, unit: str) -> Quantity:
    if unit not in VOLUME_UNITS:
        raise ValueError(f"'{unit}' is not a recognised volume unit. Valid: {VOLUME_UNITS}")
    return ureg.Quantity(value, unit).to("L")

def parse_molar_mass(value: float) -> Quantity:
    return ureg.Quantity(value, "g/mol")

def parse_volume_ratio(value: float) -> Quantity:
    return ureg.Quantity(value, "L/kg")

def parse_quantity_from_yaml(value: float, unit: str) -> Quantity:
    if unit in MASS_UNITS:
        return parse_mass(value, unit)
    if unit in VOLUME_UNITS:
        return parse_volume(value, unit)
    if unit in MOLE_UNITS:
        return ureg.Quantity(value, unit).to("mol")
    if unit == "L/kg":
        return parse_volume_ratio(value)
    if unit == "g/mol":
        return parse_molar_mass(value)
    raise ValueError(f"Unrecognised unit '{unit}'")

def to_float(q: Quantity, target_unit: str) -> float:
    return q.to(target_unit).magnitude
