"use strict";
// Relatório PNG: KPIs + gráficos (como estão na tela, com filtros) + alarmes + issues com a mensagem de erro.
// Usa os helpers globais de app.js (state, charts, api, qs, css, fmtFull, nf, toast, CATEGORY_LABELS).

const REPORT = {
  width: 1600, pad: 40, gap: 18, scale: 2, maxIssueLines: 16,
  font: 'system-ui, -apple-system, "Segoe UI", sans-serif',
  mono: 'Consolas, "Cascadia Code", ui-monospace, monospace',
};
const PERIOD_LABELS = { "1h": "Última hora", "6h": "Últimas 6 horas", "24h": "Últimas 24 horas", "7d": "Últimos 7 dias", "30d": "Últimos 30 dias" };
const PERIOD_MS = { "1h": 3.6e6, "6h": 2.16e7, "24h": 8.64e7, "7d": 6.048e8, "30d": 2.592e9 };
const STATUS_TAB_LABELS = { open: "abertas", resolved: "resolvidas", ignored: "ignoradas", all: "todas" };

function issueStatusLabel(it) {
  if (it.status === "resolved") return ["Resolvida", "--good"];
  if (it.status === "ignored") return ["Ignorada", "--muted"];
  if (it.regressed_at) return ["Regressão", "--critical"];
  return ["Aberta", "--serious"];
}

// Quebra texto em linhas que cabem em maxW (quebra palavras longas também).
function wrapText(ctx, text, maxW) {
  const out = [];
  for (const para of String(text).split("\n")) {
    let line = "";
    for (const word of para.replace(/\t/g, "  ").split(/(\s+)/)) {
      if (ctx.measureText(line + word).width <= maxW) { line += word; continue; }
      if (line.trim()) out.push(line.trimEnd());
      line = word.trimStart();
      while (ctx.measureText(line).width > maxW) {   // palavra maior que a linha
        let cut = line.length;
        while (cut > 1 && ctx.measureText(line.slice(0, cut)).width > maxW) cut = Math.floor(cut * 0.9);
        out.push(line.slice(0, cut));
        line = line.slice(cut);
      }
    }
    out.push(line.trimEnd());
  }
  return out;
}

function buildReport(ctx, draw, d) {
  const { width: W, pad: P, gap: G, font: F, mono: M } = REPORT;
  const c = (name) => css(name);
  const inner = W - 2 * P;
  let y = P;

  const text = (str, x, yy, size, opts = {}) => {
    ctx.font = `${opts.weight || 400} ${size}px ${opts.mono ? M : F}`;
    if (draw) {
      ctx.fillStyle = opts.color || c("--ink");
      ctx.textAlign = opts.align || "left";
      ctx.textBaseline = "alphabetic";
      ctx.fillText(str, x, yy);
    }
    return ctx.measureText(str).width;
  };
  const box = (x, yy, w, h, fill, stroke, r = 12) => {
    if (!draw) return;
    ctx.beginPath();
    ctx.roundRect(x, yy, w, h, r);
    ctx.fillStyle = fill;
    ctx.fill();
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 1; ctx.stroke(); }
  };
  const pill = (label, x, yy, colorVar) => {
    ctx.font = `600 12px ${F}`;
    const w = ctx.measureText(label).width + 24;
    if (draw) {
      box(x, yy - 14, w, 20, c("--surface-2"), c("--grid"), 10);
      ctx.beginPath(); ctx.arc(x + 9, yy - 4, 4, 0, Math.PI * 2); ctx.fillStyle = c(colorVar); ctx.fill();
      text(label, x + 17, yy + 1, 12, { weight: 600, color: c("--ink") });
    }
    return w;
  };
  const chartImage = (key) => {
    const ch = charts[key];
    if (!ch || ch.canvas.closest(".hidden") || !ch.canvas.width) return null;
    return ch.canvas;
  };
  const card = (x, yy, w, title, subtitle, bodyH, drawBody) => {
    const h = 48 + bodyH + 16;
    box(x, yy, w, h, c("--surface"), c("--grid"));
    text(title, x + 18, yy + 30, 17, { weight: 600 });
    if (subtitle) text(subtitle, x + 18 + text(title, 0, -999, 17, { weight: 600 }) + 10, yy + 30, 12, { color: c("--muted") });
    if (draw) drawBody(x + 16, yy + 48, w - 32);
    return h;
  };
  const imgHeight = (img, w) => (img ? Math.round((img.height / img.width) * w) : 60);
  const drawImg = (img, x, yy, w, emptyMsg) => {
    if (img) ctx.drawImage(img, x, yy, w, imgHeight(img, w));
    else text(emptyMsg, x + w / 2, yy + 36, 14, { color: c("--muted"), align: "center" });
  };

  // ---- fundo
  if (draw) { ctx.fillStyle = c("--page"); ctx.fillRect(0, 0, W, d.height); }

  // ---- cabeçalho
  if (draw) { box(P, y, 34, 34, c("--critical"), null, 8); text("⚠", P + 17, y + 25, 18, { color: "#fff", align: "center", weight: 700 }); }
  text(`Relatório de erros — ${appName()}`, P + 48, y + 26, 26, { weight: 700 });
  y += 58;
  const now = d.report.generated_at;
  text(`${PERIOD_LABELS[state.range]}: ${fmtFull(now - PERIOD_MS[state.range])} → ${fmtFull(now)}`, P, y, 15, { color: c("--ink-2"), weight: 600 });
  y += 24;
  const filters = [];
  if (state.service) filters.push(`Serviço: ${state.service}`);
  if (state.category) filters.push(`Categoria: ${CATEGORY_LABELS[state.category] || state.category}`);
  if (state.q) filters.push(`Busca: "${state.q}"`);
  text(`Filtros: ${filters.length ? filters.join("  ·  ") : "nenhum (todos os serviços e categorias)"}`, P, y, 14, { color: c("--ink-2") });
  y += 22;
  text(`Conta AWS ${d.report.account || "?"} · ${d.report.region} · gerado em ${fmtFull(now)}`, P, y, 13, { color: c("--muted") });
  y += 26;

  // ---- KPIs
  const s = d.summary;
  const diff = s.total - s.previous;
  const delta = s.previous ? `${diff > 0 ? "▲" : diff < 0 ? "▼" : "="} ${Math.abs(Math.round((diff / s.previous) * 100))}% vs anterior (${nf.format(s.previous)})`
    : (s.total ? "▲ novo vs período anterior (0)" : "igual ao período anterior");
  const kpis = [
    ["Erros no período", nf.format(s.total), delta],
    ["Issues abertas", nf.format(s.open_issues), s.regressions ? `${s.regressions} regressão(ões)` : ""],
    ["Issues novas no período", nf.format(s.new_issues), ""],
    ["Serviços com erro", nf.format(s.services), ""],
    ["Alarmes disparados", nf.format(s.alarms_in_alarm), `de ${d.report.total_alarms} alarmes`],
  ];
  const kw = (inner - 4 * G) / 5;
  kpis.forEach(([label, value, sub], i) => {
    const x = P + i * (kw + G);
    const alert = i === 4 && s.alarms_in_alarm > 0;
    box(x, y, kw, 96, c("--surface"), alert ? c("--critical") : c("--grid"));
    text(label, x + 16, y + 26, 13, { color: c("--ink-2") });
    text(value, x + 16, y + 64, 32, { weight: 700 });
    if (sub) text(sub, x + 16, y + 86, 12, { color: diff > 0 && i === 0 ? c("--critical-text") : c("--ink-2") });
  });
  y += 96 + G;

  // ---- gráfico de tempo
  const tl = chartImage("timeline");
  y += card(P, y, inner, "Erros ao longo do tempo", "por serviço · top 5 + outros", imgHeight(tl, inner - 32),
    (x, yy, w) => drawImg(tl, x, yy, w, "Nenhum erro no período")) + G;

  // ---- serviços e categorias lado a lado
  const half = (inner - G) / 2;
  const sv = chartImage("services"), ct = chartImage("categories");
  const bodyH = Math.max(imgHeight(sv, half - 32), imgHeight(ct, half - 32));
  card(P, y, half, "Serviços com mais erros", state.service ? "(selecionado em destaque)" : "", bodyH,
    (x, yy, w) => drawImg(sv, x, yy, w, "Sem dados"));
  y += card(P + half + G, y, half, "Por categoria", state.category ? "(selecionada em destaque)" : "", bodyH,
    (x, yy, w) => drawImg(ct, x, yy, w, "Sem dados")) + G;

  // ---- alarmes
  const alarms = d.report.alarms;
  const alarmH = alarms.length ? alarms.length * 44 : 28;
  y += card(P, y, inner, "Alarmes CloudWatch", `${alarms.length} fora do normal · ${d.report.total_alarms} monitorados`, alarmH, (x, yy, w) => {
    if (!alarms.length) { text("✓ Nenhum alarme disparado.", x, yy + 18, 14, { color: c("--good-text"), weight: 600 }); return; }
    alarms.forEach((a, i) => {
      const ay = yy + i * 44 + 16;
      const pw = pill(a.state === "ALARM" ? "ALARME" : "Sem dados", x, ay, a.state === "ALARM" ? "--critical" : "--warning");
      text(a.name, x + pw + 10, ay + 1, 14, { weight: 600 });
      text(`${a.namespace} · ${a.metric} · desde ${fmtFull(a.state_updated_at)}`, x + pw + 10, ay + 20, 12, { color: c("--muted") });
    });
  }) + G;

  // ---- issues
  const issues = d.report.issues;
  text(`Issues ${STATUS_TAB_LABELS[state.status]} — ${issues.length ? `top ${issues.length} por ocorrências no período` : "nenhuma no período"}`, P, y + 22, 19, { weight: 700 });
  y += 40;
  const msgW = inner - 32 - 24;
  for (const it of issues) {
    ctx.font = `700 14px ${M}`;
    const titleLines = wrapText(ctx, it.title, inner - 32).slice(0, 3);
    ctx.font = `400 12px ${M}`;
    let msgLines = wrapText(ctx, it.message || "(sem mensagem armazenada)", msgW);
    const hidden = Math.max(0, msgLines.length - REPORT.maxIssueLines);
    msgLines = msgLines.slice(0, REPORT.maxIssueLines);
    if (hidden) msgLines.push(`… (+${hidden} linhas — veja o log completo no painel)`);
    const msgH = msgLines.length * 17 + 20;
    const h = 34 + titleLines.length * 20 + 26 + msgH + 16;

    box(P, y, inner, h, c("--surface"), c("--grid"));
    let x = P + 16;
    const [stLabel, stColor] = issueStatusLabel(it);
    x += pill(stLabel, x, y + 26, stColor) + 8;
    x += pill(it.category_label, x, y + 26, "--s1") + 10;
    text(it.service, x, y + 27, 13, { weight: 600, color: c("--ink-2") });
    text(`${nf.format(it.range_count)} no período · ${nf.format(it.count)} no total`, P + inner - 16, y + 27, 13,
      { weight: 700, align: "right" });
    let iy = y + 34;
    titleLines.forEach((ln) => { iy += 20; text(ln, P + 16, iy, 14, { weight: 700, mono: true }); });
    iy += 22;
    text(`Primeira vez: ${fmtFull(it.first_seen)}  ·  Última vez: ${fmtFull(it.last_seen)}  ·  ${it.log_group}`, P + 16, iy, 12, { color: c("--muted") });
    iy += 12;
    box(P + 16, iy, inner - 32, msgH, c("--surface-2"), c("--grid"), 8);
    msgLines.forEach((ln, i) => text(ln, P + 28, iy + 22 + i * 17, 12, { mono: true, color: c("--ink") }));
    y += h + 12;
  }

  // ---- rodapé
  y += 8;
  text(`Dados sensíveis (tokens, senhas, e-mails, CPF/CNPJ, strings de conexão) foram mascarados. Gerado pelo ${appName()}.`,
    P, y + 14, 12, { color: c("--muted") });
  return y + 14 + P;
}

async function generateReport() {
  const btn = $("btnReport");
  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Gerando…";
  try {
    const [summary, report] = await Promise.all([
      api(`/api/summary?${qs()}`),
      api(`/api/report?${qs({ status: state.status, q: state.q })}`),
    ]);
    const data = { summary, report };
    // 1ª passada mede a altura; 2ª desenha
    const measure = document.createElement("canvas").getContext("2d");
    data.height = Math.ceil(buildReport(measure, false, data));
    let scale = REPORT.scale;
    if (data.height * scale > 30000) scale = Math.max(1, Math.floor(30000 / data.height));  // limite de canvas do navegador
    const canvas = document.createElement("canvas");
    canvas.width = REPORT.width * scale;
    canvas.height = data.height * scale;
    const ctx = canvas.getContext("2d");
    ctx.scale(scale, scale);
    buildReport(ctx, true, data);

    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
    const d = new Date(report.generated_at);
    const stamp = `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}`;
    const slug = appName().toLowerCase().normalize("NFD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    const name = `${slug}-relatorio-${state.range}-${stamp}.png`;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    toast(`Relatório salvo: <strong>${esc(name)}</strong> (pasta de Downloads)`, "good");
  } catch (e) {
    toast(`Não consegui gerar o relatório: ${esc(e.message)}`, "critical");
  } finally {
    btn.disabled = false;
    btn.textContent = label;
  }
}

$("btnReport").addEventListener("click", generateReport);
