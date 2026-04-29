from __future__ import annotations


def test_root_serves_web_interface(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "MedAgentic RAG Assistant" in response.text
    assert "Prompt Lab" in response.text
    assert "Open Swagger" in response.text
