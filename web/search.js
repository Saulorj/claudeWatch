"use strict";
// Busca livre nos logs (Logs Insights em todos os log groups). Usa helpers globais de app.js.

const search = { result: null, groupFilter: "", regex: null, text: "", abort: null, timer: null };

const AWS_BUTTON = ` <button type="button" class="chip" id="searchAwsBtn" title="Pode gerar custos no CloudWatch Logs Insights">🔎 Buscar em todos os logs (AWS)</button>`;

function escapeRegExp(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

function buildHighlighter(text, { regex, word, case: matchCase }) {
  try {
    let src = regex ? text : escapeRegExp(text);
    if (word) src = `\\b(?:${src})\\b`;
    return new RegExp(src, matchCase ? "g" : "gi");
  } catch {
    return null;
  }
}

// Escapa HTML e envolve os trechos encontrados em <mark>
function highlight(str, re) {
  if (!re) return esc(str);
  let out = "", last = 0;
  re.lastIndex = 0;
  for (const m of str.matchAll(re)) {
    if (!m[0]) continue;
    out += esc(str.slice(last, m.index)) + `<mark>${esc(m[0])}</mark>`;
    last = m.index + m[0].length;
  }
  return out + esc(str.slice(last));
}

function openSearch() {
  $("searchModal").classList.add("show");
  setTimeout(() => $("searchText").focus(), 50);
}

async function runSearch(e) {
  e?.preventDefault();
  const f = $("searchForm");
  const body = {
    text: f.elements.text.value.trim(), range: f.elements.range.value, group: f.elements.group.value.trim(),
    word: f.elements.word.checked, case: f.elements.case.checked, regex: f.elements.regex.checked,
    scope: f.elements.aws.checked ? "all" : "errors",   // padrão: só os erros coletados (local, sem custo)
  };
  const status = $("searchStatus");
  if (body.text.length < 2) { status.className = "search-status error"; status.textContent = "Digite pelo menos 2 caracteres."; return; }
  store.set("lastSearch", { text: body.text, range: body.range });

  search.abort?.abort();
  search.abort = new AbortController();
  clearInterval(search.timer);
  const t0 = Date.now();
  const groupsHint = state.status_?.groups_monitored ? `${state.status_.groups_monitored} log groups` : "todos os log groups";
  status.className = "search-status";
  const where = body.scope === "all" ? `em todos os logs da AWS (${groupsHint})` : "nos erros coletados";
  const slow = body.scope === "all" ? " (períodos longos podem levar 1–2 min)" : "";
  const tick = () => { status.innerHTML = `<span class="spin">◌</span>Buscando “${esc(body.text)}” ${where}… ${Math.round((Date.now() - t0) / 1000)}s${slow}`; };
  tick();
  search.timer = setInterval(tick, 1000);
  $("searchGo").disabled = true;
  try {
    const res = await api("/api/search", { method: "POST", body, signal: search.abort.signal });
    search.result = res;
    search.text = body.text;
    search.regex = buildHighlighter(body.text, body);
    search.groupFilter = "";
    renderSearch();
  } catch (err) {
    if (err.name === "AbortError") return;
    status.className = "search-status error";
    status.textContent = `Falha na busca: ${err.message}`;
  } finally {
    clearInterval(search.timer);
    $("searchGo").disabled = false;
  }
}

function renderSearch() {
  const r = search.result;
  const status = $("searchStatus");
  status.className = "search-status";
  const shown = r.items.length;
  const period = `${fmtTime(r.start)} → ${fmtTime(r.end)}`;
  if (!r.total) {
    // Sem resultado: mostra o motivo (falha na AWS) e as opções que podem estar restringindo a busca
    const f = $("searchForm").elements;
    const active = [];
    if (f.group.value.trim()) active.push(`só log groups contendo “${esc(f.group.value.trim())}”`);
    if (f.word.checked) active.push("palavra inteira");
    if (f.case.checked) active.push("diferenciar maiúsculas");
    if (f.regex.checked) active.push("expressão regular");
    if (r.errors.length) {
      status.className = "search-status error";
      status.innerHTML = `A busca falhou em ${r.errors.length} lote(s) de log groups: ${esc(r.errors[0])}`;
    } else {
      const where = r.scope === "all" ? `em todos os logs da AWS (${period}, ${r.groups_searched} log groups, ${r.elapsed_s}s)`
        : `nos erros coletados (${period})`;
      status.innerHTML = `Nada encontrado para “<strong>${esc(search.text)}</strong>” ${where}.` +
        (active.length ? ` Opções ativas: ${active.join(", ")}. <button type="button" class="chip" id="clearSearchOpts">limpar opções e buscar de novo</button>` : "") +
        (r.scope !== "all" ? AWS_BUTTON : active.length ? "" : " Tente um período maior.");
    }
    $("searchResults").classList.add("hidden");
  } else {
    status.innerHTML = r.scope === "all"
      ? `<strong>${nf.format(r.total)}</strong> ocorrência(s) em todos os logs · <strong>${r.groups.length}</strong> log group(s) · ${period} · ${r.elapsed_s}s` +
        (r.total > shown ? ` · mostrando as ${shown} mais recentes` : "") +
        (r.errors.length ? ` · <span class="muted">⚠ parte dos grupos falhou: ${esc(r.errors[0])}</span>` : "")
      : `<strong>${nf.format(r.total)}</strong> erro(s) coletado(s) com “${esc(search.text)}” em <strong>${r.groups.length}</strong> serviço(s) · ${period}` +
        (r.total > shown ? ` · mostrando os ${shown} mais recentes` : "") + AWS_BUTTON.replace("Buscar em", "Buscar também em");
    $("searchResults").classList.remove("hidden");
  }

  const max = Math.max(1, ...r.groups.map((g) => g.n));
  $("searchGroups").innerHTML =
    `<button class="sg-item ${search.groupFilter ? "" : "active"}" data-group=""><div class="sg-top"><span class="sg-name">Todos</span><span class="sg-n">${nf.format(r.total)}</span></div></button>` +
    r.groups.map((g) => `
      <button class="sg-item ${search.groupFilter === g.log_group ? "active" : ""}" data-group="${esc(g.log_group)}" title="${esc(g.log_group)}">
        <div class="sg-top"><span class="sg-name">${esc(g.service)}</span><span class="sg-n">${nf.format(g.n)}</span></div>
        <div class="sg-kind">${esc(g.kind)}</div>
        <div class="sg-bar" style="width:${Math.round((g.n / max) * 100)}%"></div>
      </button>`).join("");

  const items = r.items.filter((it) => !search.groupFilter || it.log_group === search.groupFilter);
  $("searchList").innerHTML = items.map((it) => {
    const idx = r.items.indexOf(it);
    return `<li class="sr-item" data-i="${idx}">
      <div class="sr-head"><span>${fmtFull(it.ts)}</span><span class="sr-svc">${esc(it.service)}</span><span class="sr-stream">${esc(it.log_stream)}</span></div>
      <div class="sr-msg">${highlight(it.message, search.regex)}</div>
      <div class="sr-actions">
        <button class="btn" data-act="context">📜 Ver contexto</button>
        ${it.fingerprint ? `<button class="btn" data-act="issue">🧩 Abrir issue</button>` : ""}
        <button class="btn primary" data-act="prompt">✨ Gerar Prompt</button>
        <a class="btn" target="_blank" rel="noopener" href="${esc(consoleUrl(it.log_group, it.log_stream))}">AWS Console ↗</a>
        <button class="btn" data-act="copy">📋 Copiar linha</button>
      </div>
      <div class="sr-context"></div>
    </li>`;
  }).join("") || `<li class="muted">Nenhuma das ${shown} linhas mais recentes é deste log group — refine a busca com o filtro de log group.</li>`;
}

async function showSearchContext(li, it) {
  const box = li.querySelector(".sr-context");
  if (box.classList.toggle("show") === false) return;
  box.innerHTML = `<span class="muted small">Buscando o contexto no log stream…</span>`;
  try {
    const res = await api("/api/search/context", { method: "POST", body: it });
    const lines = (res.context || "").split("\n");
    box.innerHTML = `<h3>Contexto <span class="muted small">— ${esc(res.description)}</span></h3>
      <pre class="log">${lines.map((ln) => highlight(ln, search.regex)).join("\n") || "(vazio)"}</pre>`;
    const mark = box.querySelector("mark");
    if (mark) mark.scrollIntoView({ block: "center", behavior: "smooth" });
  } catch (err) {
    box.innerHTML = `<span class="muted">Não consegui buscar o contexto: ${esc(err.message)}</span>`;
  }
}

function searchPrompt(it) {
  state.promptSource = { kind: "line", item: { ...it, text: search.text } };
  generatePrompt();
}

function bindSearch() {
  $("openSearch").addEventListener("click", openSearch);
  $("searchForm").addEventListener("submit", runSearch);
  $("searchGroups").addEventListener("click", (e) => {
    const b = e.target.closest("[data-group]");
    if (!b) return;
    search.groupFilter = b.dataset.group;
    renderSearch();
  });
  $("searchList").addEventListener("click", async (e) => {
    const li = e.target.closest(".sr-item");
    if (!li) return;
    const it = search.result.items[Number(li.dataset.i)];
    const act = e.target.closest("[data-act]")?.dataset.act;
    if (act === "context") return showSearchContext(li, it);
    if (act === "issue") {
      $("searchModal").classList.remove("show");
      return loadIssue(it.fingerprint);
    }
    if (act === "prompt") return searchPrompt(it);
    if (act === "copy") {
      try { await navigator.clipboard.writeText(it.message); toast("Linha copiada.", "good"); } catch { toast("Não consegui copiar.", "critical"); }
      return;
    }
    if (e.target.closest("a")) return;
    li.classList.toggle("open");
  });
  // atalho "/" abre a busca (fora de campos de texto)
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "")) {
      e.preventDefault();
      openSearch();
    }
  });
  $("searchAws").addEventListener("change", (e) => $("awsWarning").classList.toggle("hidden", !e.target.checked));
  $("searchStatus").addEventListener("click", (e) => {
    if (e.target.id === "searchAwsBtn") {
      $("searchAws").checked = true;
      $("awsWarning").classList.remove("hidden");
      return runSearch();
    }
    if (e.target.id !== "clearSearchOpts") return;
    const f = $("searchForm").elements;
    f.group.value = "";
    f.word.checked = f.case.checked = f.regex.checked = false;
    runSearch();
  });
  // Lembra só o texto e o período: filtros "esquecidos" de uma busca anterior faziam a próxima não achar nada
  const last = store.get("lastSearch", null);
  if (last) {
    const f = $("searchForm");
    f.elements.text.value = last.text || "";
    f.elements.range.value = last.range || "24h";
  }
}

bindSearch();
