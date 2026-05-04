const state = {
  documents: [],
  latestPubmedPayload: null,
  latestPromptEnhanceV2: null,
  promptCategory: "",
  promptSuggestions: [],
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
          <div class="document-card-top">
            <strong>${escapeHtml(doc.filename)}</strong>
            <button class="danger-outline-button" type="button" data-delete-document="${escapeHtml(doc.document_id)}">Remove</button>
          </div>
          <div class="meta-line">
            <span>ID: <span class="mono">${escapeHtml(doc.document_id)}</span></span>
            <span>${doc.page_count} pages</span>
            <span>${doc.chunk_count} chunks</span>
            <span>${escapeHtml(formatIndexingStatus(doc.indexing_status))}</span>
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

function formatIndexingStatus(status) {
  const labels = {
    indexed: "Vector indexed",
    indexed_text_only: "Text fallback",
  };
  return labels[status] || "Vector indexed";
}

function cleanOpenLiteratureQuery(payload) {
  const source = payload.open_literature_query || payload.original_input || "";
  let query = source
    .replace(/^[\s\-:•]+/, "")
    .replace(/\b(find|search|show|explain|compare|summarize)\b/gi, " ")
    .replace(/\b(real|usable)\b/gi, " ")
    .replace(/\b(not just abstracts?|abstracts?)\b/gi, " ")
    .replace(/\b(articles?|papers?|studies|literature)\b/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!query) query = payload.original_input || "";
  if (/diabetes/i.test(query) && !/mellitus/i.test(query)) {
    query = query.replace(/\bdiabetes\b/i, "diabetes mellitus");
  }
  if (!/\bfull[- ]?text\b/i.test(query)) query = `${query} full text`;
  if (!/\breview\b/i.test(query)) query = `${query} review`;
  if (!/\bopen access\b/i.test(query)) query = `${query} open access`;
  return query.replace(/\s+/g, " ").trim();
}

function inferFullTextRequired(payload) {
  return Boolean(
    payload.full_text_required ||
      /full[- ]?text|not just abstracts?|real articles|open access/i.test(
        `${payload.original_input || ""} ${payload.optimized_prompt || ""} ${payload.open_literature_query || ""}`,
      ),
  );
}

function outputFormatToOpenLiteratureMode(outputFormat) {
  const map = {
    evidence_table: "evidence_table",
    article_digest: "article_digest",
    study_notes: "study_notes",
    quiz_json: "quiz",
    deep_review: "deep_review",
  };
  return map[outputFormat] || "quick_answer";
}

async function deleteDocument(documentId) {
  const status = document.getElementById("upload-status");
  const confirmed = window.confirm(
    "Delete this document from MARA? This removes it from retrieval and study workflows.",
  );
  if (!confirmed) return;
  try {
    const payload = await api(`/api/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" });
    status.textContent = payload.warnings?.length
      ? `Deleted document with warnings: ${payload.warnings.join(" ")}`
      : "Deleted document from MARA.";
    await loadDocuments();
  } catch (error) {
    status.textContent = error.message;
  }
}

function renderDocumentSources(sources) {
  return (sources || [])
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
}

function renderSelectedPubmedSources(sources) {
  return (sources || [])
    .map(
      (source) => `
        <article class="source-card">
          <strong>${escapeHtml(source.title)}</strong>
          <div class="meta-line">
            <span>${escapeHtml(source.source_type)}</span>
            ${source.pmid ? `<span>PMID ${escapeHtml(source.pmid)}</span>` : ""}
            ${source.pmcid ? `<span>${escapeHtml(source.pmcid)}</span>` : ""}
          </div>
          <p>${escapeHtml(source.excerpt)}</p>
          <a class="ghost-link" href="${escapeHtml(source.source_url)}" target="_blank" rel="noreferrer">Open source</a>
        </article>
      `,
    )
    .join("");
}

function renderQuizItems(items) {
  return (items || [])
    .map(
      (item) => `
        <article class="quiz-card">
          <strong>${escapeHtml(item.question)}</strong>
          <ul>
            ${(item.options || []).map((option) => `<li>${escapeHtml(option)}</li>`).join("")}
          </ul>
          <p><strong>Correct:</strong> ${escapeHtml(item.correct_answer)}</p>
          <p>${escapeHtml(item.explanation)}</p>
          ${
            (item.source_pages || []).length
              ? `<p class="microcopy">Source pages: ${(item.source_pages || []).join(", ")}</p>`
              : ""
          }
          ${
            (item.source_titles || []).length
              ? `<p class="microcopy">Source titles: ${(item.source_titles || []).map(escapeHtml).join("; ")}</p>`
              : ""
          }
        </article>
      `,
    )
    .join("");
}

function renderPubmedResults(results) {
  return (results || [])
    .map(
      (item) => `
        <article class="pubmed-card">
          <label class="pubmed-select-card">
            <input type="checkbox" name="selected_pubmed_pmids" value="${escapeHtml(item.pmid)}" />
            <span>
              <strong>${escapeHtml(item.title)}</strong>
              <div class="meta-line">
                <span>${escapeHtml(item.journal)} &middot; ${escapeHtml(item.publication_date)}</span>
              </div>
              <p>${escapeHtml((item.authors || []).join(", "))}</p>
              <div class="result-topline">
                <span class="mode-badge">${escapeHtml(item.content_availability || "metadata_only")}</span>
                ${item.pmcid ? `<span class="mode-badge">${escapeHtml(item.pmcid)}</span>` : ""}
              </div>
              <div class="inline-actions">
                <a class="ghost-link" href="${escapeHtml(item.pubmed_url)}" target="_blank" rel="noreferrer">
                  View PMID ${escapeHtml(item.pmid)}
                </a>
                ${
                  item.full_text_url
                    ? `<a class="ghost-link" href="${escapeHtml(item.full_text_url)}" target="_blank" rel="noreferrer">Open PMC full text</a>`
                    : ""
                }
              </div>
            </span>
          </label>
        </article>
      `,
    )
    .join("");
}

function renderPubmedActionPanel() {
  if (!state.latestPubmedPayload?.pubmed_results?.length) {
    return "";
  }
  return `
    <article class="result-card">
      <div class="section-headline">
        <h3>Turn selected studies into study material</h3>
        <span class="microcopy" id="pubmed-selection-count">0 selected</span>
      </div>
      <p class="microcopy">
        Choose 3 to 5 results for merged synthesis. MARA will try PMC full text first when available, then fall back to
        PubMed abstracts.
      </p>
      <label class="field">
        <span>Optional follow-up instruction</span>
        <textarea
          id="pubmed-followup-question"
          rows="3"
          placeholder="Optional: focus the synthesis, comparison, simplification, or quiz on a specific angle."
        ></textarea>
      </label>
      <div class="toggle-row">
        <label class="switch">
          <input id="pubmed-prefer-fulltext-toggle" type="checkbox" checked />
          <span>Prefer PMC full text when available</span>
        </label>
        <label class="switch">
          <input id="pubmed-enhance-toggle" type="checkbox" />
          <span>Enhance follow-up prompt</span>
        </label>
      </div>
      <div class="inline-actions">
        <button class="secondary-button" type="button" data-pubmed-action="summarize">Summarize selected</button>
        <button class="secondary-button" type="button" data-pubmed-action="compare">Compare 3-5 studies</button>
        <button class="secondary-button" type="button" data-pubmed-action="simplify">Simplify selected</button>
        <button class="secondary-button" type="button" data-pubmed-action="quiz">Quiz selected</button>
      </div>
      <p class="microcopy" id="pubmed-action-status">Selections stay local to this page until you run an action.</p>
    </article>

    <article class="result-card">
      <h3>Experimental open-access URL import</h3>
      <p class="microcopy">
        Paste a public article URL to try summarization, simplification, or quiz generation from
        the visible article text. This is experimental and may fail on some sites.
      </p>
      <label class="field">
        <span>Open-access article URL</span>
        <input
          id="open-access-url"
          type="url"
          placeholder="https://..."
        />
      </label>
      <label class="field">
        <span>Optional instruction for imported article</span>
        <textarea
          id="open-access-question"
          rows="3"
          placeholder="Optional: e.g. Summarize this article for first-year medical students."
        ></textarea>
      </label>
      <div class="toggle-row">
        <label class="switch">
          <input id="open-access-enhance-toggle" type="checkbox" />
          <span>Enhance imported-article prompt</span>
        </label>
      </div>
      <div class="inline-actions">
        <button class="secondary-button" type="button" data-open-access-action="summarize">Summarize URL</button>
        <button class="secondary-button" type="button" data-open-access-action="simplify">Simplify URL</button>
        <button class="secondary-button" type="button" data-open-access-action="quiz">Quiz URL</button>
      </div>
      <p class="microcopy" id="open-access-status">Only public open-access article pages are allowed.</p>
    </article>
  `;
}

function renderResult(payload) {
  const shell = document.getElementById("result-shell");
  const statusLabel = payload.mode_used || payload.action || "result";
  const warnings = (payload.warnings || [])
    .map((warning) => `<span class="warning-chip">${escapeHtml(warning)}</span>`)
    .join("");
  const sources = renderDocumentSources(payload.sources || []);
  const selectedSources = renderSelectedPubmedSources(payload.selected_sources || []);
  const quizItems = renderQuizItems(payload.quiz_items || []);
  const pubmedResults = renderPubmedResults(payload.pubmed_results || []);

  if (payload.pubmed_results?.length) {
    state.latestPubmedPayload = payload;
  }

  shell.className = "result-shell";
  shell.innerHTML = `
    <article class="result-card">
      <div class="result-topline">
        <span class="status-badge ${escapeHtml(payload.status)}">${escapeHtml(payload.status)}</span>
        <span class="mode-badge">${escapeHtml(statusLabel)}</span>
        <span class="mode-badge">Safety: ${escapeHtml(payload.safety.category)}</span>
      </div>
      <div class="answer-body">${escapeHtml(payload.answer || "")}</div>
      ${warnings ? `<div class="result-topline">${warnings}</div>` : ""}
      ${
        payload.action && state.latestPubmedPayload?.pubmed_results?.length
          ? `<div class="inline-actions"><button class="secondary-button" type="button" data-restore-pubmed="true">Back to latest PubMed search</button></div>`
          : ""
      }
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
      selectedSources
        ? `<article class="result-card">
            <h3>Selected PubMed sources</h3>
            <div class="document-list">${selectedSources}</div>
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
          </article>
          ${renderPubmedActionPanel()}`
        : ""
    }
  `;

  if (payload.pubmed_results?.length) {
    updatePubmedSelectionStatus();
  }
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
    enhance_prompt: false,
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
          <div class="result-topline">
            <span class="mode-badge">${escapeHtml(item.category)}</span>
            <span class="mode-badge">${escapeHtml(item.prompt_type)}</span>
            ${item.has_variables ? `<span class="mode-badge">fill-in ready</span>` : ""}
          </div>
          <strong>${escapeHtml(item.title)}</strong>
          <p>${escapeHtml(item.description)}</p>
          <div class="meta-line">
            <span>${escapeHtml(item.author_name)}</span>
          </div>
          <div class="tag-row">
            ${(item.tags || []).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}
          </div>
        </article>
      `,
    )
    .join("");
}

function renderPromptSuggestions(payload) {
  const shell = document.getElementById("prompt-suggest-results");
  state.promptSuggestions = payload.suggestions || [];
  if (!state.promptSuggestions.length) {
    shell.className = "prompt-results empty-state";
    shell.textContent = "No prompt suggestions were generated.";
    return;
  }

  shell.className = "prompt-results suggestion-results";
  shell.innerHTML = `
    <article class="result-card suggestion-summary-card">
      <div class="result-topline">
        <span class="mode-badge">${escapeHtml(payload.inferred_category)}</span>
        <span class="mode-badge">mode hint: ${escapeHtml(payload.mode_hint_used)}</span>
      </div>
      <p class="microcopy">
        MARA suggested ${state.promptSuggestions.length} prompt variant(s). Pick one, then send it to the improver or straight into Assistant Lab.
      </p>
    </article>
    ${state.promptSuggestions
      .map(
        (item) => `
          <article class="prompt-card suggestion-card">
            <div class="result-topline">
              <span class="mode-badge">${escapeHtml(item.category)}</span>
              ${(item.tags || []).map((tag) => `<span class="mode-badge">${escapeHtml(tag)}</span>`).join("")}
            </div>
            <strong>${escapeHtml(item.title)}</strong>
            <p>${escapeHtml(item.rationale)}</p>
            <div class="prompt-template mono">${escapeHtml(item.prompt)}</div>
            <div class="inline-actions">
              <button class="secondary-button" type="button" data-suggestion-to-improver="${escapeHtml(item.id)}">Send to improver</button>
              <button class="secondary-button" type="button" data-suggestion-to-chat="${escapeHtml(item.id)}">Use in Assistant Lab</button>
            </div>
          </article>
        `,
      )
      .join("")}
  `;

  if (payload.recommended_recipe_id) {
    loadPromptDetail(payload.recommended_recipe_id).catch(() => {});
  }
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
    : `<p class="microcopy">This recipe has no fill-in variables.</p>`;

  const starter = buildPromptStarter(prompt);

  shell.className = "prompt-detail";
  shell.innerHTML = `
    <article class="result-card prompt-recipe-card">
      <div class="result-topline">
        <span class="mode-badge">${escapeHtml(prompt.category)}</span>
        <span class="mode-badge">${escapeHtml(prompt.prompt_type)}</span>
        <span class="mode-badge">Recipe by ${escapeHtml(prompt.author_name)}</span>
      </div>
      <h3>${escapeHtml(prompt.title)}</h3>
      <p>${escapeHtml(prompt.description)}</p>
      <p class="microcopy">Best for: ${(prompt.tags || []).map(escapeHtml).join(" | ")}</p>
      ${variables}
      <div class="inline-actions">
        <button class="secondary-button" type="button" id="load-prompt-into-improver">Load recipe into improver</button>
        <button class="secondary-button" type="button" id="load-prompt-into-chat">Use recipe hint in Assistant Lab</button>
      </div>
      <details class="template-disclosure">
        <summary>View full recipe template</summary>
        <div class="prompt-template mono">${escapeHtml(prompt.template)}</div>
      </details>
    </article>
  `;

  document.getElementById("load-prompt-into-improver").addEventListener("click", () => {
    document.getElementById("prompt-improve-input").value = prompt.template;
    document.getElementById("prompt-improve-input").focus();
  });
  document.getElementById("load-prompt-into-chat").addEventListener("click", () => {
    document.getElementById("chat-question").value = starter;
    document.getElementById("chat-question").focus();
  });
}

function renderPromptImprovement(payload) {
  const shell = document.getElementById("prompt-improve-result");
  shell.className = "prompt-improve-result";
  shell.innerHTML = `
    <article class="result-card">
      <h3>Improved prompt</h3>
      <div class="prompt-improved-body mono">${escapeHtml(payload.improved_prompt)}</div>
      <div class="tag-row prompt-change-row">
        ${(payload.changes || []).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
      </div>
    </article>
  `;
}

function renderKeyValueList(items) {
  return (items || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function renderPromptEnhanceV2(payload) {
  const shell = document.getElementById("prompt-enhance-v2-result");
  shell.className = "result-shell";
  state.latestPromptEnhanceV2 = payload;
  const optimizedTask = cleanOptimizedTask(payload);
  const mostlyUnchanged =
    normalizeComparableText(optimizedTask) &&
    normalizeComparableText(optimizedTask) === normalizeComparableText(payload.original_input || "");
  const routeButtons = `
    ${
      payload.inferred_mode === "open_literature"
        ? `<button class="secondary-button" type="button" data-enhanced-to-open-literature="true">Send to Open Literature</button>`
        : ""
    }
    ${
      payload.inferred_mode === "open_article"
        ? `<button class="secondary-button" type="button" data-enhanced-to-open-article="true">Send to Open Article</button>`
        : ""
    }
  `;
  shell.innerHTML = `
    <article class="result-card">
      <div class="result-topline">
        <span class="mode-badge">${escapeHtml(payload.inferred_mode)}</span>
        <span class="mode-badge">${payload.can_send_to_assistant ? "sendable" : "blocked"}</span>
      </div>
      <h3>Improved Prompt</h3>
      ${
        mostlyUnchanged
          ? `<p class="microcopy">This request was already clear; MARA kept the task mostly unchanged and added routing, source, and safety planning.</p>`
          : ""
      }
      <div class="prompt-template mono">${escapeHtml(payload.optimized_prompt)}</div>
      <div class="inline-actions">
        <button class="secondary-button" type="button" data-copy-text="${escapeHtml(payload.optimized_prompt)}">Copy prompt</button>
        <button class="secondary-button" type="button" data-enhanced-to-chat="true">Send to Assistant Lab</button>
        ${routeButtons}
      </div>
    </article>
    <article class="result-card">
      <h3>Route & Source Plan</h3>
      <ul>
        <li>Route: ${escapeHtml(payload.inferred_mode)}</li>
        <li>RAG query: ${escapeHtml(payload.rag_query || "not required")}</li>
        <li>PubMed query: ${escapeHtml(payload.pubmed_query || "not required")}</li>
        <li>Open Literature query: ${escapeHtml(payload.open_literature_query || "not required")}</li>
        <li>Open Article: ${escapeHtml(payload.open_article_instruction || "not required")}</li>
      </ul>
    </article>
    <article class="result-card">
      <h3>Retrieval Plan</h3>
      <ul>${renderKeyValueList(payload.retrieval_plan)}</ul>
    </article>
    <article class="result-card">
      <h3>Context Plan</h3>
      <ul>${renderKeyValueList(payload.context_plan)}</ul>
    </article>
    <article class="result-card">
      <h3>Safety & Harness Checks</h3>
      <ul>${renderKeyValueList([...(payload.safety_plan || []), ...(payload.quality_checks || [])])}</ul>
      ${(payload.warnings || []).map((warning) => `<span class="warning-chip">${escapeHtml(warning)}</span>`).join("")}
    </article>
    <details class="result-card">
      <summary>Raw JSON</summary>
      <div class="prompt-template mono">${escapeHtml(JSON.stringify(payload, null, 2))}</div>
      <div class="inline-actions">
        <button class="secondary-button" type="button" data-copy-text="${escapeHtml(JSON.stringify(payload, null, 2))}">Copy JSON</button>
      </div>
    </details>
  `;
  shell.dataset.optimizedTask = optimizedTask;
  shell.dataset.optimizedPrompt = payload.optimized_prompt || "";
  shell.dataset.originalInput = payload.original_input || "";
  shell.dataset.inferredMode = payload.inferred_mode || "auto";
  shell.dataset.openLiteratureQuery = cleanOpenLiteratureQuery(payload);
  shell.dataset.fullTextRequired = String(inferFullTextRequired(payload));
  shell.dataset.outputFormat = payload.output_format || "markdown";
}

function normalizeComparableText(value) {
  return String(value || "")
    .trim()
    .replace(/\s+/g, " ")
    .replace(/[.?!]+$/g, "")
    .toLowerCase();
}

function cleanOptimizedTask(payload) {
  const direct = cleanTaskText(payload.optimized_task || "");
  if (direct) return direct;
  const optimizedPrompt = String(payload.optimized_prompt || "").trim();
  const taskMatch = optimizedPrompt.match(/^Task:\s*(.+)$/im);
  if (taskMatch?.[1]) return cleanTaskText(taskMatch[1]);
  return cleanTaskText(optimizedPrompt) || String(payload.original_input || "").trim();
}

function cleanTaskText(value) {
  return String(value || "")
    .trim()
    .replace(/\s+/g, " ")
    .split(/\s+(?:Audience|Route|Source scope|Output format|Instructions|Use only|Cite each|Do not|If evidence)\s*:/i)[0]
    .split(/\s+(?:Use only retrieved|Use retrieved|Cite each source|Do not diagnose|If evidence is lacking)\b/i)[0]
    .trim();
}

function promptEnhancementHandoffTask(payload, resultShell) {
  const fromPayload = cleanOptimizedTask(payload || {});
  if (fromPayload) return fromPayload;
  const fromDataset = String(resultShell?.dataset?.optimizedTask || "").trim();
  if (fromDataset) return fromDataset;
  const optimizedPrompt = String(resultShell?.dataset?.optimizedPrompt || "").trim();
  const taskMatch = optimizedPrompt.match(/^Task:\s*(.+)$/im);
  if (taskMatch?.[1]) return cleanTaskText(taskMatch[1]);
  const originalInput = String(resultShell?.dataset?.originalInput || "").trim();
  if (originalInput) return originalInput;
  return document.getElementById("prompt-enhance-v2-input").value.trim();
}

function setAssistantModeFromEnhancement(inferredMode) {
  const modeSelect = document.getElementById("chat-mode");
  const modeMap = {
    document_rag: "document_rag",
    rag: "rag",
    open_literature: "open_literature",
    pubmed_metadata: "pubmed",
    pubmed: "pubmed",
    general_education: "general_education",
    open_article: "auto",
  };
  const nextMode = modeMap[inferredMode] || "auto";
  if (Array.from(modeSelect.options).some((option) => option.value === nextMode)) {
    modeSelect.value = nextMode;
  }
}

function renderOpenLiterature(payload) {
  const shell = document.getElementById("open-literature-result");
  const warnings = (payload.warnings || []).map((warning) => `<span class="warning-chip">${escapeHtml(warning)}</span>`).join("");
  const evidence = (payload.evidence_table || [])
    .map(
      (row) => `
        <article class="source-card">
          <strong>${escapeHtml(row.article)}</strong>
          <p>${escapeHtml(row.main_finding)}</p>
          <div class="meta-line">
            <span>${escapeHtml(row.source_status)}</span>
            <span>${escapeHtml(row.citation)}</span>
          </div>
        </article>
      `,
    )
    .join("");
  shell.className = "result-shell";
  shell.innerHTML = `
    <article class="result-card">
      <div class="result-topline">
        <span class="status-badge ${escapeHtml(payload.status)}">${escapeHtml(payload.status)}</span>
        <span class="mode-badge">Candidates ${payload.candidate_count || 0}</span>
        <span class="mode-badge">Full text ${payload.full_text_count || 0}</span>
        <span class="mode-badge">Abstract ${payload.abstract_only_count || 0}</span>
        <span class="mode-badge">Restricted ${payload.restricted_count || 0}</span>
      </div>
      <div class="answer-body">${escapeHtml(payload.answer || "")}</div>
      ${warnings ? `<div class="result-topline">${warnings}</div>` : ""}
    </article>
    <article class="result-card">
      <h3>Search Details</h3>
      <p class="microcopy">Sources: ${(payload.sources_searched || []).map(escapeHtml).join(", ")}</p>
      <p class="microcopy">Variants: ${(payload.query_variants || []).map(escapeHtml).join(" | ")}</p>
    </article>
    ${evidence ? `<article class="result-card"><h3>Evidence Table</h3><div class="document-list">${evidence}</div></article>` : ""}
  `;
}

function renderOpenArticle(payload) {
  const shell = document.getElementById("open-article-result");
  const article = payload.article || {};
  const warnings = (payload.warnings || []).map((warning) => `<span class="warning-chip">${escapeHtml(warning)}</span>`).join("");
  const quizItems = renderQuizItems(payload.quiz_items || []);
  shell.className = "result-shell";
  shell.innerHTML = `
    <article class="result-card">
      <div class="result-topline">
        <span class="status-badge ${escapeHtml(payload.status)}">${escapeHtml(payload.status)}</span>
        <span class="mode-badge">${escapeHtml(payload.action || "import")}</span>
        <span class="mode-badge">${escapeHtml(article.full_text_status || "unknown")}</span>
        <span class="mode-badge">Quality ${escapeHtml(article.extraction_quality_score ?? "n/a")}</span>
      </div>
      <strong>${escapeHtml(article.title || "Open article")}</strong>
      <div class="answer-body">${escapeHtml(payload.answer || "")}</div>
      ${warnings ? `<div class="result-topline">${warnings}</div>` : ""}
    </article>
    ${quizItems ? `<article class="result-card"><h3>Quiz items</h3><div class="document-list">${quizItems}</div></article>` : ""}
  `;
}

function getPromptSuggestionById(suggestionId) {
  return (state.promptSuggestions || []).find((item) => item.id === suggestionId) || null;
}

function buildPromptStarter(prompt) {
  const loweredCategory = String(prompt.category || "").toLowerCase();
  if (loweredCategory.includes("literature")) {
    return `Use a focused PubMed search approach for this topic: ${prompt.title}.`;
  }
  if (loweredCategory.includes("assessment")) {
    return `Create quiz questions from the uploaded source using the style of "${prompt.title}".`;
  }
  if (loweredCategory.includes("simplification")) {
    return `Explain the uploaded content in simpler terms using the style of "${prompt.title}".`;
  }
  return `Use the style of "${prompt.title}" for this medical learning task.`;
}

function updatePubmedSelectionStatus() {
  const count = getSelectedPubmedPmids().length;
  const countLabel = document.getElementById("pubmed-selection-count");
  const statusLabel = document.getElementById("pubmed-action-status");
  if (countLabel) {
    countLabel.textContent = `${count} selected`;
  }
  if (statusLabel) {
    statusLabel.textContent =
      count >= 1
        ? "Ready for a selected-study action. Compare works best with 3 to 5 studies."
        : "Select 3 to 5 studies for the strongest merged synthesis.";
  }
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

async function suggestPrompts(event) {
  if (event) {
    event.preventDefault();
  }
  const shell = document.getElementById("prompt-suggest-results");
  shell.className = "prompt-results empty-state";
  shell.textContent = "Generating prompt suggestions...";

  try {
    const payload = await api("/api/prompts/suggest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task: document.getElementById("prompt-suggest-task").value.trim(),
        audience: document.getElementById("prompt-suggest-audience").value.trim() || null,
        modeHint: document.getElementById("prompt-suggest-mode").value,
        outputType: document.getElementById("prompt-output-type")?.value || "text",
        outputFormat: document.getElementById("prompt-output-format")?.value || "text",
      }),
    });
    renderPromptSuggestions(payload);
  } catch (error) {
    shell.className = "prompt-results empty-state";
    shell.textContent = error.message;
  }
}

function getSelectedPubmedPmids() {
  return Array.from(document.querySelectorAll('input[name="selected_pubmed_pmids"]:checked')).map(
    (input) => input.value,
  );
}

async function runSelectedPubmedAction(action) {
  const shell = document.getElementById("result-shell");
  const status = document.getElementById("pubmed-action-status");
  const pmids = getSelectedPubmedPmids();
  if (!pmids.length) {
    if (status) status.textContent = "Select at least one PubMed result first.";
    return;
  }

  const payload = {
    pmids,
    action,
    question: document.getElementById("pubmed-followup-question")?.value.trim() || null,
    enhance_prompt: document.getElementById("pubmed-enhance-toggle")?.checked || false,
    prefer_full_text: document.getElementById("pubmed-prefer-fulltext-toggle")?.checked ?? true,
  };

  if (action === "compare" && (pmids.length < 3 || pmids.length > 5)) {
    if (status) status.textContent = "Compare works with 3 to 5 selected PubMed studies.";
    return;
  }

  shell.className = "result-shell empty-state";
  shell.textContent = "Building PubMed article context...";
  try {
    const result = await api("/api/pubmed/transform", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderResult(result);
  } catch (error) {
    shell.className = "result-shell empty-state";
    shell.textContent = error.message;
  }
}

async function runOpenAccessAction(action) {
  const shell = document.getElementById("result-shell");
  const status = document.getElementById("open-access-status");
  const url = document.getElementById("open-access-url")?.value.trim() || "";
  if (!url) {
    if (status) status.textContent = "Paste an open-access article URL first.";
    return;
  }
  const payload = {
    url,
    action,
    question: document.getElementById("open-access-question")?.value.trim() || null,
    enhance_prompt: document.getElementById("open-access-enhance-toggle")?.checked || false,
  };

  shell.className = "result-shell empty-state";
  shell.textContent = "Importing open-access article...";
  try {
    const result = await api("/api/pubmed/import-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderResult(result);
  } catch (error) {
    shell.className = "result-shell empty-state";
    shell.textContent = error.message;
  }
}

function bindStaticInteractions() {
  document.getElementById("refresh-docs").addEventListener("click", async () => {
    await loadDocuments();
  });

  document.getElementById("documents-list").addEventListener("click", async (event) => {
    const deleteButton = event.target.closest("[data-delete-document]");
    if (deleteButton) {
      await deleteDocument(deleteButton.dataset.deleteDocument);
    }
  });

  document.getElementById("all-docs-toggle").addEventListener("change", (event) => {
    document.getElementById("doc-picker-wrap").classList.toggle("hidden", event.target.checked);
  });

  document.querySelectorAll(".quick-queries .chip-button").forEach((button) => {
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
      status.textContent =
        payload.status === "indexed_text_only"
          ? `Saved ${payload.filename} for direct PDF workflows. Vector indexing is unavailable, so retrieval will use PDF text fallback.`
          : `Indexed ${payload.filename} successfully.`;
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

  document.getElementById("result-shell").addEventListener("click", async (event) => {
    const pubmedActionButton = event.target.closest("[data-pubmed-action]");
    if (pubmedActionButton) {
      await runSelectedPubmedAction(pubmedActionButton.dataset.pubmedAction);
      return;
    }

    const openAccessButton = event.target.closest("[data-open-access-action]");
    if (openAccessButton) {
      await runOpenAccessAction(openAccessButton.dataset.openAccessAction);
      return;
    }

    const restoreButton = event.target.closest("[data-restore-pubmed]");
    if (restoreButton && state.latestPubmedPayload) {
      renderResult(state.latestPubmedPayload);
    }
  });

  document.getElementById("result-shell").addEventListener("change", (event) => {
    if (event.target.matches('input[name="selected_pubmed_pmids"]')) {
      updatePubmedSelectionStatus();
    }
  });

  document.getElementById("prompt-suggest-form")?.addEventListener("submit", suggestPrompts);
  document.getElementById("prompt-search-form")?.addEventListener("submit", searchPrompts);

  document.querySelectorAll(".prompt-filter-button").forEach((button) => {
    button.addEventListener("click", async () => {
      document.querySelectorAll(".prompt-filter-button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.promptCategory = button.dataset.category || "";
      const categoryInput = document.getElementById("prompt-search-category");
      if (categoryInput) categoryInput.value = state.promptCategory;
      await searchPrompts();
    });
  });

  document.querySelectorAll(".prompt-insert-button").forEach((button) => {
    button.addEventListener("click", () => {
      document.getElementById("prompt-improve-input").value = button.dataset.promptText || "";
      document.getElementById("prompt-improve-input").focus();
    });
  });

  document.getElementById("prompt-search-results")?.addEventListener("click", async (event) => {
    const card = event.target.closest("[data-prompt-id]");
    if (!card) return;
    await loadPromptDetail(card.dataset.promptId);
  });

  document.getElementById("prompt-suggest-results")?.addEventListener("click", (event) => {
    const improveButton = event.target.closest("[data-suggestion-to-improver]");
    if (improveButton) {
      const suggestion = getPromptSuggestionById(improveButton.dataset.suggestionToImprover);
      if (suggestion) {
        document.getElementById("prompt-improve-input").value = suggestion.prompt;
        document.getElementById("prompt-improve-input").focus();
      }
      return;
    }

    const chatButton = event.target.closest("[data-suggestion-to-chat]");
    if (chatButton) {
      const suggestion = getPromptSuggestionById(chatButton.dataset.suggestionToChat);
      if (suggestion) {
        document.getElementById("chat-question").value = suggestion.prompt;
        document.getElementById("chat-question").focus();
      }
    }
  });

  document.getElementById("prompt-improve-form")?.addEventListener("submit", async (event) => {
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

  document.getElementById("prompt-enhance-v2-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const shell = document.getElementById("prompt-enhance-v2-result");
    shell.className = "result-shell empty-state";
    shell.textContent = "Building prompt package...";
    try {
      const payload = await api("/api/prompts/enhance-v2", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          raw_input: document.getElementById("prompt-enhance-v2-input").value.trim(),
          target_mode: document.getElementById("prompt-enhance-v2-mode").value,
          audience: document.getElementById("prompt-enhance-v2-audience").value.trim() || null,
          source_scope: document.getElementById("prompt-enhance-v2-scope").value,
          output_format: document.getElementById("prompt-enhance-v2-output").value,
          strict_grounding: document.getElementById("prompt-enhance-v2-grounding").checked,
          include_retrieval_plan: true,
          include_safety_checks: true,
          full_text_required: document.getElementById("prompt-enhance-v2-fulltext").checked,
        }),
      });
      renderPromptEnhanceV2(payload);
    } catch (error) {
      shell.className = "result-shell empty-state";
      shell.textContent = error.message;
    }
  });

  document.getElementById("prompt-enhance-v2-result").addEventListener("click", async (event) => {
    const copyButton = event.target.closest("[data-copy-text]");
    if (copyButton) {
      await navigator.clipboard?.writeText(copyButton.dataset.copyText || "");
      return;
    }
    const sendButton = event.target.closest("[data-enhanced-to-chat]");
    if (sendButton) {
      const resultShell = document.getElementById("prompt-enhance-v2-result");
      document.getElementById("chat-question").value =
        promptEnhancementHandoffTask(state.latestPromptEnhanceV2, resultShell);
      setAssistantModeFromEnhancement(resultShell.dataset.inferredMode || "auto");
      document.getElementById("chat-question").focus();
    }
    const openLiteratureButton = event.target.closest("[data-enhanced-to-open-literature]");
    if (openLiteratureButton) {
      const resultShell = document.getElementById("prompt-enhance-v2-result");
      const queryInput = document.getElementById("open-literature-query");
      const fullTextInput = document.getElementById("open-literature-fulltext");
      const modeSelect = document.getElementById("open-literature-mode");
      queryInput.value = resultShell.dataset.openLiteratureQuery || resultShell.dataset.originalInput || "";
      fullTextInput.checked = resultShell.dataset.fullTextRequired === "true";
      const targetMode = outputFormatToOpenLiteratureMode(resultShell.dataset.outputFormat || "markdown");
      if (Array.from(modeSelect.options).some((option) => option.value === targetMode)) {
        modeSelect.value = targetMode;
      }
      queryInput.focus();
    }
    const openArticleButton = event.target.closest("[data-enhanced-to-open-article]");
    if (openArticleButton) {
      const resultShell = document.getElementById("prompt-enhance-v2-result");
      const match = (resultShell.dataset.originalInput || "").match(/https?:\/\/\S+/i);
      document.getElementById("open-article-url").value = match ? match[0] : "";
      document.getElementById("open-article-url").focus();
    }
  });

  document.getElementById("open-literature-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const shell = document.getElementById("open-literature-result");
    shell.className = "result-shell empty-state";
    shell.textContent = "Searching open literature...";
    try {
      const payload = await api("/api/open-literature/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: document.getElementById("open-literature-query").value.trim(),
          output_mode: document.getElementById("open-literature-mode").value,
          filters: {
            max_results: Number(document.getElementById("open-literature-max-results").value),
            full_text_required: document.getElementById("open-literature-fulltext").checked,
            open_access_only: true,
          },
        }),
      });
      renderOpenLiterature(payload);
    } catch (error) {
      shell.className = "result-shell empty-state";
      shell.textContent = error.message;
    }
  });

  document.getElementById("open-article-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const shell = document.getElementById("open-article-result");
    shell.className = "result-shell empty-state";
    shell.textContent = "Importing article and running action...";
    try {
      const payload = await api("/api/open-article/transform", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: document.getElementById("open-article-url").value.trim(),
          action: document.getElementById("open-article-action").value,
          question: document.getElementById("open-article-question").value.trim() || null,
        }),
      });
      renderOpenArticle(payload);
    } catch (error) {
      shell.className = "result-shell empty-state";
      shell.textContent = error.message;
    }
  });
}

async function boot() {
  bindStaticInteractions();
  await loadHealth();
  await loadDocuments();
}

boot().catch((error) => {
  setHealth(false, error.message);
});

