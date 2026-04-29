from __future__ import annotations


def test_root_serves_web_interface(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "MARA" in response.text
    assert "Prompt Studio" in response.text
    assert "Medical Agent RAG Assistant" in response.text
    assert "Open Swagger" in response.text
    assert "Suggest prompts" in response.text
    assert "Important Note" not in response.text
    assert "Prompt Lab" not in response.text
