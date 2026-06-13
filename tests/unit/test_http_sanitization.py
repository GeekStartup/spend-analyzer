from app.http import sanitize_query_string


def test_query_values_are_redacted():
    assert sanitize_query_string("page=2") == "page=%5BREDACTED%5D"
