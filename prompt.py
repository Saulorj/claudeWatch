"""Monta o prompt de diagnóstico de uma issue para colar no Claude."""
import re
from datetime import datetime

import fingerprint as fp
from config import AWS_REGION, SYSTEM_NAME

MAX_MESSAGE_CHARS = 20_000
MAX_CONTEXT_LINES = 120
MAX_LINE_CHARS = 2_000

_MASKS = [
    (re.compile(r"eyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{5,}"), "<JWT>"),
    (re.compile(r"(?i)(bearer\s+)[\w\-.=~+/]+"), r"\1<TOKEN>"),
    (re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"), "<AWS_ACCESS_KEY>"),
    (re.compile(r"(?i)([\"']?(password|passwd|senha|secret|token|api[_-]?key|authorization|access[_-]?key)"
                r"[\"']?\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,}&]+)"), r"\1<OCULTO>"),
    (re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), "<CPF>"),
    (re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"), "<CNPJ>"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<EMAIL>"),
    (re.compile(r"(?i)(mysql|postgres(ql)?|mongodb(\+srv)?|redis)://[^\s\"']+"), r"\1://<OCULTO>"),
]


def _system_line(account_id: str | None) -> str:
    prefix = f"{SYSTEM_NAME} " if SYSTEM_NAME else ""
    return f"- Sistema: {prefix}(AWS, conta {account_id or '?'}, região {AWS_REGION})"


def mask(text: str) -> str:
    for pattern, repl in _MASKS:
        text = pattern.sub(repl, text)
    return text


def fmt_ts(ms: int | None) -> str:
    if not ms:
        return "-"
    return datetime.fromtimestamp(ms / 1000).astimezone().strftime("%d/%m/%Y %H:%M:%S (UTC%z)")


def _cut(text: str, size: int) -> str:
    return text if len(text) <= size else text[:size] + f"\n… [cortado, {len(text) - size} caracteres omitidos]"


def fetch_context(logs_client, group: str, stream: str, ts: int, message: str) -> tuple[str, str]:
    """Busca as linhas ao redor do erro no próprio stream. Em Lambda, recorta a invocação inteira."""
    resp = logs_client.get_log_events(logGroupName=group, logStreamName=stream, startTime=ts - 5 * 60_000,
                                      endTime=ts + 60_000, startFromHead=True, limit=2_000)
    events = resp["events"]
    if not events:
        return "", ""

    req = fp.UUID_RE.search(message)
    if group.startswith("/aws/lambda/") and req:
        rid = req.group(0)
        start_i = next((i for i, e in enumerate(events) if f"START RequestId: {rid}" in e["message"]), None)
        end_i = next((i for i, e in enumerate(events) if f"REPORT RequestId: {rid}" in e["message"]), None)
        if start_i is not None:
            end_i = end_i if end_i is not None else len(events) - 1
            chunk = events[start_i:end_i + 1][-MAX_CONTEXT_LINES:]
            return "\n".join(_cut(e["message"].rstrip(), MAX_LINE_CHARS) for e in chunk), \
                f"invocação completa da Lambda (RequestId {rid})"

    # Sem request id: linhas antes e depois do horário do erro
    pos = next((i for i, e in enumerate(events) if e["timestamp"] >= ts), len(events))
    chunk = events[max(0, pos - 80):pos + 40]
    return "\n".join(_cut(e["message"].rstrip(), MAX_LINE_CHARS) for e in chunk), \
        "linhas do mesmo log stream ao redor do horário do erro"


def build_for_line(logs_client, account_id: str | None, group: str, stream: str, ts: int, message: str,
                   search_text: str = "", do_mask: bool = True) -> str:
    """Prompt para uma linha encontrada na busca livre (não precisa ser uma issue)."""
    try:
        context, context_desc = fetch_context(logs_client, group, stream, ts, message)
    except Exception as exc:
        context, context_desc = "", f"(não foi possível buscar o contexto na AWS: {exc})"
    parts = [
        "Você é um engenheiro sênior de backend/SRE. Encontrei a linha de log abaixo"
        + (f" ao procurar por \"{search_text}\"" if search_text else "")
        + " e preciso entender o que a gerou e se há um problema.",
        "",
        "## Ambiente",
        _system_line(account_id),
        f"- Tipo de recurso: {fp.kind_of(group)}",
        f"- Serviço: {fp.service_of(group)}",
        f"- Log group: {group}",
        f"- Log stream: {stream}",
        f"- Horário: {fmt_ts(ts)}",
        "",
        "## Linha encontrada",
        "```",
        _cut(message, MAX_MESSAGE_CHARS),
        "```",
    ]
    if context:
        parts += ["", f"## Contexto: {context_desc}", "```", context, "```"]
    elif context_desc:
        parts += ["", "## Contexto", context_desc]
    parts += [
        "",
        "## O que preciso de você",
        "1. Qual serviço/fluxo gerou essa linha e o que estava acontecendo (com base no contexto).",
        "2. Se isso indica um erro ou problema — e qual a causa mais provável.",
        "3. Se for um problema: a correção proposta (com código, se aplicável) e como validar.",
        "4. Se faltar informação (código, configuração, payload), diga exatamente o que devo te enviar.",
    ]
    text = "\n".join(parts)
    if do_mask:
        text = mask(text) + "\n\n(Obs.: dados sensíveis como tokens, senhas, e-mails e CPFs foram mascarados.)"
    return text


def build(conn, logs_client, account_id: str | None, fingerprint: str, event_id: int | None,
          do_mask: bool = True) -> str:
    issue = conn.execute("SELECT * FROM issues WHERE fingerprint=?", (fingerprint,)).fetchone()
    if issue is None:
        raise KeyError("issue não encontrada")
    if event_id:
        event = conn.execute("SELECT * FROM events WHERE id=? AND fingerprint=?", (event_id, fingerprint)).fetchone()
    else:
        event = conn.execute("SELECT * FROM events WHERE fingerprint=? ORDER BY ts DESC LIMIT 1",
                             (fingerprint,)).fetchone()
    if event is None:
        raise KeyError("nenhuma ocorrência armazenada para esta issue")

    now = int(datetime.now().timestamp() * 1000)
    c1h, c24h = conn.execute(
        "SELECT SUM(ts >= ?), SUM(ts >= ?) FROM events WHERE fingerprint=?",
        (now - 3_600_000, now - 86_400_000, fingerprint)).fetchone()
    streams = conn.execute("SELECT COUNT(DISTINCT log_stream) FROM events WHERE fingerprint=?",
                           (fingerprint,)).fetchone()[0]
    variants = conn.execute(
        "SELECT message, MAX(ts) AS ts FROM events WHERE fingerprint=? AND id != ? "
        "GROUP BY substr(message, 1, 300) ORDER BY ts DESC LIMIT 3", (fingerprint, event["id"])).fetchall()
    related = conn.execute(
        "SELECT service, title, count, last_seen FROM issues WHERE fingerprint != ? AND status != 'ignored' "
        "AND last_seen BETWEEN ? AND ? ORDER BY count DESC LIMIT 5",
        (fingerprint, event["ts"] - 15 * 60_000, event["ts"] + 15 * 60_000)).fetchall()

    try:
        context, context_desc = fetch_context(logs_client, event["log_group"], event["log_stream"],
                                              event["ts"], event["message"])
    except Exception as exc:
        context, context_desc = "", f"(não foi possível buscar o contexto na AWS: {exc})"

    status = {"open": "aberta", "resolved": "resolvida", "ignored": "ignorada"}[issue["status"]]
    if issue["regressed_at"]:
        status += f" — REGRESSÃO: tinha sido resolvida e voltou em {fmt_ts(issue['regressed_at'])}"

    parts = [
        "Você é um engenheiro sênior de backend/SRE. Preciso diagnosticar e corrigir um erro que está "
        "acontecendo em produção. Analise os logs abaixo com cuidado.",
        "",
        "## Ambiente",
        _system_line(account_id),
        f"- Tipo de recurso: {fp.kind_of(event['log_group'])}",
        f"- Serviço: {issue['service']}",
        f"- Log group: {event['log_group']}",
        f"- Log stream: {event['log_stream']}",
        "",
        "## Resumo do problema",
        f"- Erro: {issue['title']}",
        f"- Categoria: {fp.CATEGORIES.get(issue['category'], issue['category'])}",
        f"- Primeira ocorrência registrada: {fmt_ts(issue['first_seen'])}",
        f"- Última ocorrência: {fmt_ts(issue['last_seen'])}",
        f"- Ocorrências: {issue['count']} no total, {c24h or 0} nas últimas 24h, {c1h or 0} na última hora "
        f"(em {streams} log stream(s) diferente(s))",
        f"- Status: {status}",
        "",
        f"## Log completo do erro (ocorrência de {fmt_ts(event['ts'])})",
        "```",
        _cut(event["message"], MAX_MESSAGE_CHARS),
        "```",
    ]
    if context:
        parts += ["", f"## Contexto: {context_desc}", "```", context, "```"]
    elif context_desc:
        parts += ["", f"## Contexto", context_desc]
    if variants:
        parts += ["", "## Outras variações recentes do mesmo erro"]
        for v in variants:
            parts += [f"- {fmt_ts(v['ts'])}:", "```", _cut(v["message"], 3_000), "```"]
    if related:
        parts += ["", "## Outros erros em serviços próximos no mesmo horário (±15 min) — podem estar relacionados"]
        parts += [f"- [{r['service']}] {r['title']} ({r['count']}x)" for r in related]
    parts += [
        "",
        "## O que preciso de você",
        "1. A causa raiz mais provável, explicada com base nas evidências dos logs (e hipóteses alternativas, "
        "em ordem de probabilidade).",
        "2. Se é um bug de código, de configuração/infra, de dependência externa ou de dados.",
        "3. A correção proposta — com código, se aplicável — e o que fazer de imediato para mitigar.",
        "4. Como validar que a correção funcionou e como evitar que volte (alarme, teste, retry etc.).",
        "5. Se faltar informação (trecho de código, variável de ambiente, payload, configuração), "
        "diga exatamente o que devo te enviar.",
    ]
    text = "\n".join(parts)
    if do_mask:
        text = mask(text) + "\n\n(Obs.: dados sensíveis como tokens, senhas, e-mails e CPFs foram mascarados.)"
    return text
