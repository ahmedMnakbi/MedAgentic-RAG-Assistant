const state = {
  documents: [],
  selectedPromptId: null,
  promptResults: [],
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setHealth(ok, label) {
  const pill = document.getElementById("health-pill");
  const text = document.getElementById("health-text");
  pill.classList.toggle("ok", ok);
  pill.classList.toggle("error", !ok);
  text.textContent = label;
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const text = await response.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!response.ok) {
    const message = data?.error || response.statusText || "Request failed";
    throw new Error(message);
  }
  return data;
}

async function loadHealth() {
  try {
    const payload = await api("/health");
    setHealth(payload.status === "ok", "API healthy");
  } catch (error) {
    setHealth(false, error.message);
  }
}

function renderDocuments() {
  const list = document.getElementById("documents-list");
  const picker = document.getElementById("doc-picker");
  if (!state.documents.length) {
    list.className = "document-list empty-state";
    list.textContent = "No documents indexed yet.";
    picker.innerHTML = "";
    return;
  }

  list.className = "document-list";
  picker.innerHTML = "";
  list.innerHTML = state.documents
    .map(
      (doc) => `
        <article class="document-card">
          <strong>${escapeHtml(doc.filename)}</strong>
          <div class="meta-line">
            <span>ID: <span class="mono">${escapeHtml(doc.document_id)}</span></span>
            <span>${doc.page_count} pages</span>
            <span>${doc.chunk_count} chunks</span>
          </div>
          <p class="microcopy">Uploaded ${new Date(doc.uploaded_at).toLocaleString()}</p>
        </article>
      `,
    )
    .join("");

  picker.innerHTML = state.documents
    .map(
      (doc) => `
        <article class="document-card">
          <label>
            <span>
              <input type="checkbox" name="document_ids" value="${escapeHtml(doc.document_id)}" />
              <strong>${escapeHtml(doc.filename)}</strong>
            </span>
            <span class="microcopy mono">${escapeHtml(doc.document_id)}</span>
          </label>
        </article>
      `,
    )
    .join("");
}

async function loadDocuments() {
  const docs = await api("/api/documents");
  state.documents = docs;
  renderDocuments();
}

function renderResult(payload) {
  const shell = document.getElementById("result-shell");
  const warnings = (payload.warnings || [])
    .map((warning) => `<span class="warning-chip">${escapeHtml(warning)}</span>`)
    .join("");
  const sources = (payload.sources || [])
    .map(
      (source) => `
        <article class="source-card">
          <strong>${escapeHtml(source.filename)}</strong>
          <div class="meta-line">
            <span>Page ${source.page}</span>
            <span>Score ${source.score}</span>
          </div>
          <p class="microcopy mono">${escapeHtml(source.document_id)}</p>
          <p>${escapeHtml(source.excerpt)}</p>
        </article>
      `,
    )
    .join("");
  const quizItems = (payload.quiz_items || [])
    .map(
      (item) => `
        <article class="quiz-card">
          <strong>${escapeHtml(item.question)}</strong>
          <ul>
            ${(item.options || []).map((option) => `<li>${escapeHtml(option)}</li>`).join("")}
          </ul>
          <p><strong>Correct:</strong> ${escapeHtml(item.correct_answer)}</p>
          <p>${escapeHtml(item.explanation)}</p>
          <p class="microcopy">Source pages: ${(item.source_pages || []).join(", ")}</p>
        </article>
      `,
    )
    .join("");
  const pubmedResults = (payload.pubmed_results || [])
    .map(
      (item) => `
        <article class="pubmed-card">
          <strong>${escapeHtml(item.title)}</strong>
          <p class="microcopy">${escapeHtml(item.journal)} &middot; ${escapeHtml(item.publication_date)}</p>
          <p>${escapeHtml((item.authors || []).join(", "))}</p>
          <a class="ghost-link" href="${escapeHtml(item.pubmed_url)}" target="_blank" rel="noreferrer">
            View PMID ${escapeHtml(item.pmid)}
          </a>
        </article>
      `,
    )
    .join("");

  shell.className = "result-shell";
  shell.innerHTML = `
    <article class="result-card">
      <div class="result-topline">
        <span class="status-badge ${escapeHtml(payload.status)}">${escapeHtml(payload.status)}</span>
        <span class="mode-badge">${escapeHtml(payload.mode_used)}</span>
        <span class="mode-badge">Safety: ${escapeHtml(payload.safety.category)}</span>
      </div>
      <div class="answer-body">${escapeHtml(payload.answer || "")}</div>
      ${warnings ? `<div class="result-topline">${warnings}</div>` : ""}
    </article>

    ${
      payload.enhanced_prompt
        ? `<article class="result-card">
            <h3>Enhanced prompt</h3>
            <div class="prompt-template mono">${escapeHtml(payload.enhanced_prompt)}</div>
          </article>`
        : ""
    }

    ${
      sources
        ? `<article class="result-card">
            <h3>Sources</h3>
            <div class="document-list">${sources}</div>
          </article>`
        : ""
    }

    ${
      quizItems
        ? `<article class="result-card">
            <h3>Quiz items</h3>
            <div class="document-list">${quizItems}</div>
          </article>`
        : ""
    }

    ${
      pubmedResults
        ? `<article class="result-card">
            <h3>PubMed results</h3>
            <div class="document-list">${pubmedResults}</div>
          </article>`
        : ""
    }
  `;
}

function serializeChatPayload() {
  const allDocs = document.getElementById("all-docs-toggle").checked;
  const documentIds = allDocs
    ? null
    : Array.from(document.querySelectorAll('#doc-picker input[name="document_ids"]:checked')).map(
        (input) => input.value,
      );

  return {
    question: document.getElementById("chat-question").value.trim(),
    mode: document.getElementById("chat-mode").value,
    document_ids: documentIds,
    enhance_prompt: document.getElementById("enhance-prompt-toggle").checked,
    top_k: Number(document.getElementById("chat-top-k").value),
  };
}

function renderPromptResults(results) {
  const shell = document.getElementById("prompt-search-results");
  state.promptResults = results;
  if (!results.length) {
    shell.className = "prompt-results empty-state";
    shell.textContent = "No prompt matches found.";
    return;
  }
  shell.className = "prompt-results";
  shell.innerHTML = results
    .map(
      (item) => `
        <article class="prompt-card ${state.selectedPromptId === item.id ? "active" : ""}" data-prompt-id="${escapeHtml(item.id)}">
          <strong>${escapeHtml(item.title)}</strong>
          <p>${escapeHtml(item.description)}</p>
          <div class="meta-line">
            <span>${escapeHtml(item.category)}</span>
            <span>${escapeHtml(item.prompt_type)}</span>
          </div>
          <div class="tag-row">
            ${(item.tags || []).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}
          </div>
        </article>
      `,
    )
    .join("");
}

function renderPromptDetail(prompt) {
  const shell = document.getElementById("prompt-detail");
  if (!prompt) {
    shell.className = "prompt-detail empty-state";
    shell.textContent = "No prompt selected yet.";
    return;
  }

  const variables = (prompt.variables || []).length
    ? `
      <div class="variables-list">
        ${prompt.variables
          .map(
            (variable) => `
              <div class="variable-pill">
                <strong>\${${escapeHtml(variable.name)}}</strong>
                ${variable.required ? "required" : "optional"}
                ${variable.default_value ? ` &middot; default: ${escapeHtml(variable.default_value)}` : ""}
              </div>
            `,
          )
          .join("")}
      </div>
    `
    : `<p class="microcopy">This prompt has no variables.</p>`;

  shell.className = "prompt-detail";
  shell.innerHTML = `
    <article class="result-card">
      <div class="result-topline">
        <span class="mode-badge">${escapeHtml(prompt.category)}</span>
        <span class="mode-badge">${escapeHtml(prompt.prompt_type)}</span>
        <span class="mode-badge">Author: ${escapeHtml(prompt.author_name)}</span>
      </div>
      <h3>${escapeHtml(prompt.title)}</h3>
      <p>${escapeHtml(prompt.description)}</p>
      ${variables}
      <div class="inline-actions">
        <button class="secondary-button" type="button" id="load-prompt-into-improver">Load into improver</button>
      </div>
      <div class="prompt-template mono">${escapeHtml(prompt.template)}</div>
    </article>
  `;

  document
    .getElementById("load-prompt-into-improver")
    .addEventListener("click", () => {
      document.getElementById("prompt-improve-input").value = prompt.template;
      document.getElementById("prompt-improve-input").focus();
    });
}

function renderPromptImprovement(payload) {
  const shell = document.getElementById("prompt-improve-result");
  shell.className = "prompt-improve-result";
  shell.innerHTML = `
    <article class="result-card">
      <h3>Improved prompt</h3>
      <div class="prompt-improved-body mono">${escapeHtml(payload.improved_prompt)}</div>
    </article>
    <article class="result-card">
      <h3>What changed</h3>
      <ul>
        ${(payload.changes || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    </article>
  `;
}

async function loadPromptDetail(promptId) {
  state.selectedPromptId = promptId;
  renderPromptResults(state.promptResults);
  const payload = await api(`/api/prompts/${encodeURIComponent(promptId)}`);
  renderPromptDetail(payload);
}

async function searchPrompts(event) {
  if (event) {
    event.preventDefault();
  }
  const params = new URLSearchParams();
  const query = document.getElementById("prompt-search-query").value.trim();
  const type = document.getElementById("prompt-search-type").value;
  const category = document.getElementById("prompt-search-category").value;
  params.set("limit", "8");
  if (query) params.set("query", query);
  if (type) params.set("type", type);
  if (category) params.set("category", category);
  const payload = await api(`/api/prompts/search?${params.toString()}`);
  renderPromptResults(payload);
  if (payload.length) {
    await loadPromptDetail(payload[0].id);
  } else {
    renderPromptDetail(null);
  }
}

function bindStaticInteractions() {
  document.getElementById("refresh-docs").addEventListener("click", async () => {
    await loadDocuments();
  });

  document.getElementById("all-docs-toggle").addEventListener("change", (event) => {
    document.getElementById("doc-picker-wrap").classList.toggle("hidden", event.target.checked);
  });

  document.querySelectorAll(".chip-button").forEach((button) => {
    button.addEventListener("click", () => {
      document.getElementById("chat-question").value = button.dataset.query || "";
      document.getElementById("chat-question").focus();
    });
  });

  document.getElementById("upload-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.getElementById("upload-status");
    const form = event.currentTarget;
    const fileInput = document.getElementById("pdf-file");
    if (!fileInput.files?.length) {
      status.textContent = "Choose a PDF before uploading.";
      return;
    }

    status.textContent = "Uploading and indexing... the first upload can take longer.";
    const data = new FormData(form);
    try {
      const payload = await api("/api/documents/upload", { method: "POST", body: data });
      status.textContent = `Indexed ${payload.filename} successfully.`;
      form.reset();
      await loadDocuments();
    } catch (error) {
      status.textContent = error.message;
    }
  });

  document.getElementById("chat-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const shell = document.getElementById("result-shell");
    shell.className = "result-shell empty-state";
    shell.textContent = "Running request...";

    try {
      const payload = await api("/api/chat/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(serializeChatPayload()),
      });
      renderResult(payload);
    } catch (error) {
      shell.className = "result-shell empty-state";
      shell.textContent = error.message;
    }
  });

  document.getElementById("prompt-search-form").addEventListener("submit", searchPrompts);

  document.getElementById("prompt-search-results").addEventListener("click", async (event) => {
    const card = event.target.closest("[data-prompt-id]");
    if (!card) return;
    await loadPromptDetail(card.dataset.promptId);
  });

  document.getElementById("prompt-improve-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const shell = document.getElementById("prompt-improve-result");
    shell.className = "prompt-improve-result empty-state";
    shell.textContent = "Improving prompt...";

    try {
      const payload = await api("/api/prompts/improve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: document.getElementById("prompt-improve-input").value.trim(),
          outputType: document.getElementById("prompt-output-type").value,
          outputFormat: document.getElementById("prompt-output-format").value,
        }),
      });
      renderPromptImprovement(payload);
    } catch (error) {
      shell.className = "prompt-improve-result empty-state";
      shell.textContent = error.message;
    }
  });
}

async function boot() {
  bindStaticInteractions();
  await loadHealth();
  await loadDocuments();
  await searchPrompts();
}

boot().catch((error) => {
  setHealth(false, error.message);
});
