"""Message catalogs: same keys, Polish fallback."""

from app.ui.catalog import CATALOGS, translate


def test_polish_and_english_have_the_same_keys():
    assert set(CATALOGS) == {"pl", "en"}
    assert set(CATALOGS["pl"]) == set(CATALOGS["en"])
    assert CATALOGS["pl"].keys() != []
    for key, value in CATALOGS["pl"].items():
        assert value.strip()
        assert CATALOGS["en"][key].strip()


def test_required_phrases_are_in_the_catalogs():
    assert CATALOGS["pl"]["missing"] == "brak danych"
    assert CATALOGS["en"]["missing"] == "no data"
    assert CATALOGS["pl"]["badge.synthetic"] == "dane syntetyczne"
    assert CATALOGS["en"]["badge.synthetic"] == "synthetic data"
    assert "poradą inwestycyjną" in CATALOGS["pl"]["disclaimer"]
    assert "not financial advice" in CATALOGS["en"]["disclaimer"].casefold()


def test_missing_key_falls_back_to_polish_then_to_the_key():
    catalogs = {
        "pl": {"only_pl": "polski", "both": "po polsku"},
        "en": {"both": "in english"},
    }
    assert translate("en", "both", catalogs) == "in english"
    assert translate("en", "only_pl", catalogs) == "polski"
    assert translate("fr", "both", catalogs) == "po polsku"
    assert translate("en", "missing", catalogs) == "missing"
    assert translate("pl", "disclaimer") == CATALOGS["pl"]["disclaimer"]
    assert translate("en", "disclaimer") == CATALOGS["en"]["disclaimer"]
