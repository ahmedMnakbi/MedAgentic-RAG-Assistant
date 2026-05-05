from __future__ import annotations

from pathlib import Path


def test_root_serves_web_interface(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "MARA" in response.text
    assert "MARA Prompt Builder" in response.text
    assert "/static/app.js?v=" in response.text
    assert "Turn a rough medical-learning request into a safe, grounded execution plan." in response.text
    assert "Medical Agent RAG Assistant" in response.text
    assert "Open Swagger" in response.text
    assert "Build prompt plan" in response.text
    assert "Suggest prompts" not in response.text
    assert "Suggest first, refine second" not in response.text
    assert "Inspect a library recipe" not in response.text
    assert "Refine your own prompt" not in response.text
    assert "Important Note" not in response.text
    assert "Prompt Lab" not in response.text
    assert "Enhance prompt before execution" not in response.text
    assert "enhance-prompt-toggle" not in response.text


def test_prompt_enhancer_send_to_assistant_uses_optimized_task_not_raw_or_package():
    script = Path("app/web/static/app.js").read_text(encoding="utf-8")

    assert "latestPromptEnhanceV2: null" in script
    assert "state.latestPromptEnhanceV2 = payload;" in script
    assert "shell.dataset.optimizedTask = optimizedTask;" in script
    assert "shell.dataset.originalInput = payload.original_input || \"\";" in script
    assert "setAssistantModeFromEnhancement(resultShell.dataset.inferredMode || \"auto\");" in script
    assert "promptEnhancementHandoffTask(state.latestPromptEnhanceV2, resultShell)" in script
    assert "function promptEnhancementHandoffTask(payload, resultShell)" in script
    assert "const fromPayload = cleanOptimizedTask(payload || {});" in script
    assert "function cleanTaskText(value)" in script
    assert "Audience|Route|Source scope|Output format|Instructions" in script
    assert "return document.getElementById(\"prompt-enhance-v2-input\").value.trim();" in script
    assert "const taskMatch = optimizedPrompt.match(/^Task:\\s*(.+)$/im);" in script
    assert "open_article: \"auto\"" in script
    assert "data-enhanced-to-open-literature" in script
    assert "data-enhanced-to-open-article" in script
    assert "cleanOpenLiteratureQuery(payload)" in script
    assert "fullTextInput.checked = resultShell.dataset.fullTextRequired === \"true\";" in script
    assert "formatIndexingStatus(doc.indexing_status)" in script
    assert "Vector indexed" in script
    assert "Text fallback" in script
    assert "danger-outline-button" in script
    assert "enhance_prompt: false" in script
    assert "enhance-prompt-toggle" not in script
