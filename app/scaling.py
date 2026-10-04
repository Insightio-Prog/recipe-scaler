"""Recipe scaling engine: pure Python, no web or AI code in here.

All quantities are stored in base units: grams (g), millilitres (ml) or
counted items ("each"). Display helpers turn 1500 g into "1.5 kg" and so on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# unit -> (base unit, multiplier to base)
UNITS: dict[str, tuple[str, float]] = {
    "g": ("g", 1.0),
    "gram": ("g", 1.0),
    "grams": ("g", 1.0),
    "kg": ("g", 1000.0),
    "kilo": ("g", 1000.0),
    "kilos": ("g", 1000.0),
    "ml": ("ml", 1.0),
    "millilitre": ("ml", 1.0),
    "millilitres": ("ml", 1.0),
    "cl": ("ml", 10.0),
    "l": ("ml", 1000.0),
    "ltr": ("ml", 1000.0),
    "litre": ("ml", 1000.0),
    "litres": ("ml", 1000.0),
    "each": ("each", 1.0),
    "ea": ("each", 1.0),
    "no": ("each", 1.0),
    "x": ("each", 1.0),
}


class ScalingError(ValueError):
    """Raised for input that cannot be scaled (bad unit, zero portions...)."""


def to_base(quantity: float, unit: str) -> tuple[float, str]:
    key = (unit or "").strip().lower().rstrip(".")
    if key not in UNITS:
        raise ScalingError(f"Unknown unit: {unit!r}")
    base, mult = UNITS[key]
    return quantity * mult, base


@dataclass
class Ingredient:
    name: str
    quantity: Optional[float]  # in base units; None = no number ("to taste")
    unit: Optional[str]  # base unit: g, ml, each, or None
    note: str = ""
    uncertain: bool = False  # the AI wasn't sure it read this line right


@dataclass
class Recipe:
    name: str
    portions: float
    portion_weight_g: Optional[float] = None
    ingredients: list[Ingredient] = field(default_factory=list)
    method: list[str] = field(default_factory=list)
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.portions or self.portions <= 0:
            raise ScalingError("Portions must be greater than zero")


def _trim(x: float, dp: int) -> str:
    s = f"{x:.{dp}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def format_quantity(quantity: Optional[float], unit: Optional[str], exact: bool = False) -> str:
    """Kitchen-friendly text: 1500 g -> '1.5 kg', 3.04 g -> '3 g'.

    exact=True skips the round-to-5 step (used for printed portion weights)."""
    if quantity is None or unit is None:
        return ""
    if unit == "g":
        if quantity >= 1000:
            return f"{_trim(quantity / 1000, 2)} kg"
        if quantity >= 100:
            return f"{int(round(quantity)) if exact else int(round(quantity / 5.0) * 5)} g"
        if quantity >= 10:
            return f"{int(round(quantity))} g"
        return f"{_trim(quantity, 1)} g"
    if unit == "ml":
        if quantity >= 1000:
            return f"{_trim(quantity / 1000, 2)} l"
        if quantity >= 100:
            return f"{int(round(quantity / 5.0) * 5)} ml"
        if quantity >= 10:
            return f"{int(round(quantity))} ml"
        return f"{_trim(quantity, 1)} ml"
    # counted items
    return _trim(quantity, 1)


def portions_factor(recipe: Recipe, target_portions: float) -> float:
    if target_portions <= 0:
        raise ScalingError("Target portions must be greater than zero")
    return target_portions / recipe.portions


def ingredient_factor(recipe: Recipe, index: int, amount: float, unit: str) -> float:
    """Factor needed so that ingredient `index` comes to `amount` `unit`."""
    if amount <= 0:
        raise ScalingError("Amount must be greater than zero")
    try:
        ing = recipe.ingredients[index]
    except IndexError:
        raise ScalingError("No such ingredient") from None
    if ing.quantity is None or ing.unit is None or ing.quantity <= 0:
        raise ScalingError(f"'{ing.name}' has no quantity to scale from")
    base_amount, base_unit = to_base(amount, unit)
    if base_unit != ing.unit:
        raise ScalingError(
            f"'{ing.name}' is measured in {ing.unit}, but you gave {unit}"
        )
    return base_amount / ing.quantity


def scale(recipe: Recipe, factor: float, per_portion: bool = False) -> dict:
    """Return the scaled recipe as plain dicts, ready for JSON."""
    if factor <= 0:
        raise ScalingError("Scale factor must be greater than zero")
    portions = recipe.portions * factor
    divisor = portions if per_portion else 1.0
    rows = []
    for ing in recipe.ingredients:
        if ing.quantity is None or ing.unit is None:
            q = None
        else:
            q = ing.quantity * factor / divisor
        rows.append(
            {
                "name": ing.name,
                "quantity": q,
                "unit": ing.unit,
                "display": format_quantity(q, ing.unit),
                "note": ing.note,
            }
        )
    weight = None
    if recipe.portion_weight_g:
        weight = recipe.portion_weight_g if per_portion else recipe.portion_weight_g * portions
    return {
        "name": recipe.name,
        "portions": round(portions, 2),
        "factor": factor,
        "per_portion": per_portion,
        "total_weight": format_quantity(weight, "g", exact=True) if weight else "",
        "ingredients": rows,
    }


def recipe_from_dict(d: dict) -> Recipe:
    """Build a Recipe from client/AI JSON, converting any unit to base units."""
    ings: list[Ingredient] = []
    for raw in d.get("ingredients", []):
        qty, unit = raw.get("quantity"), raw.get("unit")
        if qty is None or unit in (None, ""):
            q, u = None, None
        else:
            q, u = to_base(float(qty), unit)
        ings.append(
            Ingredient(
                name=str(raw.get("name", "")).strip(),
                quantity=q,
                unit=u,
                note=str(raw.get("note", "") or ""),
                uncertain=bool(raw.get("uncertain", False)),
            )
        )
    pw = d.get("portion_weight_g")
    return Recipe(
        name=str(d.get("name", "Untitled")).strip() or "Untitled",
        portions=float(d.get("portions") or 0),
        portion_weight_g=float(pw) if pw else None,
        ingredients=ings,
        method=[str(s) for s in d.get("method", [])],
        notes=str(d.get("notes", "") or ""),
    )
