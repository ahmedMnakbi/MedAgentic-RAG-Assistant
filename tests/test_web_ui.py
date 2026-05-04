from __future__ import annotations

from pathlib import Path


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


def test_prompt_enhancer_send_to_assistant_uses_original_task_not_prompt_package():
    script = Path("app/web/static/app.js").read_text(encoding="utf-8")

    assert "shell.dataset.originalInput = payload.original_input || \"\";" in script
    assert "setAssistantModeFromEnhancement(resultShell.dataset.inferredMode || \"auto\");" in script
    assert "resultShell.dataset.originalInput || resultShell.dataset.optimizedPrompt || \"\"" in script
