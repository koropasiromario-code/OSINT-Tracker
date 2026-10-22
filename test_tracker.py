from tracker import compare_with_previous


def test_first_snapshot():
    result = compare_with_previous({"title": "A"}, None)
    assert result["previous_exists"] is False
    assert result["changed"] is False


def test_detects_change():
    previous = {"content": {"title": "A", "pages_scanned": 1}}
    current = {"title": "B", "pages_scanned": 2}
    result = compare_with_previous(current, previous)
    assert result["changed"] is True
    assert result["differences"]["title"] == {"before": "A", "after": "B"}
