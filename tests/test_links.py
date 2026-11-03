def test_shorten_creates_link(client):
    response = client.post("/shorten", json={"url": "https://example.com"})
    assert response.status_code == 201
    data = response.json()
    assert len(data["short_code"]) == 7
    assert data["original_url"] == "https://example.com/"


def test_shorten_rejects_invalid_url(client):
    response = client.post("/shorten", json={"url": "hello"})
    assert response.status_code == 422


def test_redirect_goes_to_original_url(client):
    created = client.post("/shorten", json={"url": "https://example.com"})
    code = created.json()["short_code"]

    response = client.get(f"/{code}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/"


def test_unknown_code_returns_404(client):
    response = client.get("/doesnotexist", follow_redirects=False)
    assert response.status_code == 404