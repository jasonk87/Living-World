from game.stockpile import Stockpile


def test_stockpile_map_char_prefers_inventory_dominance():
    stockpile = Stockpile("Yard", 1, 1, 2, 2, allowed_resources=["Wood", "Stone"])
    stockpile.inventory["Stone"] = 4
    stockpile.inventory["Wood"] = 9

    assert stockpile.get_map_char() == "W"


def test_stockpile_map_char_uses_allowed_resource_when_empty():
    stockpile = Stockpile("Mason Yard", 0, 0, 1, 1, allowed_resources=["Stone"])

    assert stockpile.get_map_char() == "R"


def test_stockpile_to_dict_includes_map_char():
    stockpile = Stockpile("General", 0, 0, 1, 1, allowed_resources=None)
    stockpile.inventory["Tools"] = 3

    snapshot = stockpile.to_dict()

    assert snapshot["map_char"] == stockpile.get_map_char()
