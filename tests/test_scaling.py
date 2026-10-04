import pytest

from app.scaling import (
    ScalingError,
    format_quantity,
    ingredient_factor,
    portions_factor,
    recipe_from_dict,
    scale,
)

CHILLI = {
    "name": "Veg chilli",
    "portions": 10,
    "portion_weight_g": 424,
    "ingredients": [
        {"name": "Onion", "quantity": 200, "unit": "g"},
        {"name": "Red kidney beans", "quantity": 1, "unit": "kg"},
        {"name": "Rapeseed oil", "quantity": 30, "unit": "ml"},
        {"name": "Bay leaf", "quantity": 2, "unit": "each"},
        {"name": "Salt", "quantity": None, "unit": None, "note": "to taste"},
    ],
}


def test_units_convert_to_base():
    r = recipe_from_dict(CHILLI)
    beans = r.ingredients[1]
    assert (beans.quantity, beans.unit) == (1000, "g")


def test_scale_by_portions():
    r = recipe_from_dict(CHILLI)
    out = scale(r, portions_factor(r, 100))
    assert out["portions"] == 100
    assert out["ingredients"][0]["display"] == "2 kg"
    assert out["ingredients"][1]["display"] == "10 kg"
    assert out["ingredients"][2]["display"] == "300 ml"
    assert out["ingredients"][4]["display"] == ""  # to taste stays unnumbered


def test_scale_by_ingredient():
    r = recipe_from_dict(CHILLI)
    f = ingredient_factor(r, 1, 5, "kg")  # have 5 kg beans
    assert f == 5
    out = scale(r, f)
    assert out["portions"] == 50
    assert out["ingredients"][0]["display"] == "1 kg"


def test_per_portion():
    r = recipe_from_dict(CHILLI)
    out = scale(r, 1, per_portion=True)
    assert out["ingredients"][1]["display"] == "100 g"
    assert out["ingredients"][2]["display"] == "3 ml"


def test_wrong_unit_type_rejected():
    r = recipe_from_dict(CHILLI)
    with pytest.raises(ScalingError):
        ingredient_factor(r, 0, 500, "ml")  # onion is grams


def test_no_quantity_cannot_be_anchor():
    r = recipe_from_dict(CHILLI)
    with pytest.raises(ScalingError):
        ingredient_factor(r, 4, 5, "g")


def test_bad_inputs():
    with pytest.raises(ScalingError):
        recipe_from_dict({"name": "x", "portions": 0, "ingredients": []})
    r = recipe_from_dict(CHILLI)
    with pytest.raises(ScalingError):
        portions_factor(r, 0)
    with pytest.raises(ScalingError):
        scale(r, -1)
    with pytest.raises(ScalingError):
        recipe_from_dict({"name": "x", "portions": 1, "ingredients": [{"name": "a", "quantity": 1, "unit": "cups"}]})


@pytest.mark.parametrize(
    "q,u,expected",
    [
        (1500, "g", "1.5 kg"),
        (1000, "g", "1 kg"),
        (1234, "g", "1.23 kg"),
        (237, "g", "235 g"),
        (47.4, "g", "47 g"),
        (3.04, "g", "3 g"),
        (2500, "ml", "2.5 l"),
        (2.5, "each", "2.5"),
        (None, "g", ""),
    ],
)
def test_format(q, u, expected):
    assert format_quantity(q, u) == expected


def test_printed_portion_weight_not_rounded():
    r = recipe_from_dict(CHILLI)
    assert scale(r, 1, per_portion=True)["total_weight"] == "424 g"
