def test_health(api):
    client, _, _, _ = api
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_mock_panel_health(api):
    client, _, panel, _ = api
    response = client.get("/health/panel")
    assert response.status_code == 200
    assert response.json() == {"healthy": True}
    panel.health.assert_called_once_with()
