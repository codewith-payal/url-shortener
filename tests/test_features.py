def make_link(client, url="https://example.com"):
    response = client.post("/shorten", json={"url": url})
    assert response.status_code == 201
    return response.json()["short_code"]


def test_rate_limit_blocks_after_five_requests(client):
    codes = [
        client.post("/shorten", json={"url": "https://example.com"}).status_code
        for _ in range(7)
    ]
    assert codes == [201] * 5 + [429] * 2


def test_second_redirect_is_served_from_cache(client):
    code = make_link(client)

    first = client.get(f"/{code}", follow_redirects=False)
    second = client.get(f"/{code}", follow_redirects=False)

    assert first.headers["x-cache"] == "MISS"
    assert second.headers["x-cache"] == "HIT"


def test_click_is_recorded_with_device(client):
    code = make_link(client)

    client.get(
        f"/{code}",
        follow_redirects=False,
        headers={"user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17)"},
    )

    stats = client.get(f"/links/{code}/stats").json()
    assert stats["total_clicks"] == 1
    assert stats["by_device"] == {"mobile": 1}


def test_clicks_are_recorded_on_cache_hits_too(client):
    code = make_link(client)

    for _ in range(3):
        client.get(f"/{code}", follow_redirects=False)

    stats = client.get(f"/links/{code}/stats").json()
    assert stats["total_clicks"] == 3


def test_list_links_is_paginated(client):
    for _ in range(3):
        make_link(client)

    page = client.get("/links?limit=2").json()

    assert page["total"] == 3
    assert len(page["items"]) == 2