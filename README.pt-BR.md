<div align="center">

# 📈 CloudWatch Monitor

**Painel local e leve de erros do AWS CloudWatch — uma alternativa gratuita ao Datadog para acompanhar erros.**

Roda na sua máquina · lê seus logs do CloudWatch a cada poucos minutos · agrupa erros em issues ·
gráficos, alertas, busca em todos os logs, relatório em PNG e um botão **✨ Gerar Prompt** que entrega
o contexto completo do erro para o Claude (ou outra IA) diagnosticar.

[![Licença: MIT](https://img.shields.io/badge/Licen%C3%A7a-MIT-green.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![Plataformas](https://img.shields.io/badge/plataforma-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![AWS somente leitura](https://img.shields.io/badge/AWS-somente%20leitura-orange)
![Sem servidor](https://img.shields.io/badge/servidor-n%C3%A3o%20precisa-brightgreen)

[🇺🇸 English](README.md) · 🇧🇷 Português

<img src="docs/screenshots/dashboard-dark.png" alt="Painel" width="900">

</div>

---

## Por quê

Pagar uma plataforma completa de observabilidade só para *ver os erros* das suas Lambdas e containers
é exagero para muitos times. O CloudWatch já tem os logs — só não deixa fácil acompanhá-los.

O CloudWatch Monitor transforma os logs que você já tem num painel de erros para deixar aberto numa
segunda tela. **Nada é instalado na AWS**, não há servidor para hospedar e só precisa de credenciais
**somente leitura**. Seus dados ficam no seu computador.

## Funcionalidades

| | |
|---|---|
| 🔄 **Coleta automática** | A cada N minutos (1–60, ajustável no painel) via CloudWatch Logs Insights em **todos** os log groups — Lambda, ECS, API Gateway, RDS, Glue… |
| 🧩 **Agrupamento inteligente** | Erros parecidos viram uma **issue** (ids, números e horários são ignorados). Entende tracebacks Python quebrados em várias linhas, logs JSON (pino, structlog…), HTTP 5xx e timeouts |
| 📊 **Gráficos interativos** | Erros no tempo por serviço, serviços com mais erros, categorias. Clique na barra ou na legenda para filtrar; período de 1h a 30 dias |
| 🚨 **Alarmes do CloudWatch** | Mostra o estado (OK / ALARME / sem dados) dos alarmes que já existem na conta |
| ✨ **Gerar Prompt** | Monta um prompt de diagnóstico pronto para colar: erro completo, a **invocação inteira da Lambda** (ou as linhas ao redor no container), estatísticas e erros relacionados. Dados sensíveis mascarados |
| 🔎 **Busca nos logs** | Procure qualquer texto (id de pedido, e-mail, código de erro) em todos os log groups e veja qual serviço o gerou, com contexto |
| 🖼 **Relatório PNG** | Um clique exporta KPIs, gráficos, alarmes e os principais erros com mensagens — ótimo para o chat da equipe ou um ticket |
| 🔔 **Notificações** | Aviso do sistema em issue nova ou regressão |
| ✅ **Fluxo de trabalho** | Resolver (reabre como *Regressão* se voltar) ou Ignorar (ruído conhecido) |
| ⏪ **Recuperação de lacunas** | O painel ficou fechado? Até 24h é recuperado sozinho; períodos maiores perguntam o que buscar — em segundo plano |
| 🧙 **Instalação guiada** | `iniciar.bat` / `iniciar.sh` verificam e instalam Python, dependências e AWS CLI; depois um assistente configura as credenciais (mesmo sem AWS CLI) |
| 🧪 **Modo demonstração** | `python app.py --demo` — experimente tudo com dados fictícios, sem conta AWS |

## Telas

| Detalhe da issue | Gerar Prompt |
|---|---|
| <img src="docs/screenshots/issue-detail.png" alt="Detalhe da issue" width="440"> | <img src="docs/screenshots/prompt.png" alt="Prompt" width="440"> |
| **Busca nos logs** | **Visão filtrada** |
| <img src="docs/screenshots/search.png" alt="Busca nos logs" width="440"> | <img src="docs/screenshots/filtered.png" alt="Filtrado" width="440"> |
| **Tema claro** | **Relatório PNG** |
| <img src="docs/screenshots/dashboard-light.png" alt="Tema claro" width="440"> | <img src="docs/screenshots/report.png" alt="Relatório PNG" width="440"> |

> Todas as telas vêm do **modo demonstração** (uma loja fictícia) — nenhum dado real.

---

## Início rápido

```bash
git clone https://github.com/Saulorj/claudeWatch.git
cd claudeWatch
```

| Sistema | Rode |
|---|---|
| **Windows** | dois cliques em **`iniciar.bat`** |
| **macOS / Linux** | `./iniciar.sh` |

O inicializador faz tudo, explicando cada passo:

1. **Python 3.10+** — confere a versão; instala se faltar (winget / Homebrew / apt, dnf, pacman, zypper).
2. **Dependências** — confere e instala o `requirements.txt` (só o `boto3`).
3. **AWS CLI** — opcional (só para login SSO); oferece instalar.
4. **Assistente de configuração** — só na 1ª vez (veja abaixo).
5. Abre o painel em **http://127.0.0.1:8765/**

### Só quer dar uma olhada?

```bash
python app.py --demo
```

Abre o painel com uma loja fictícia cheia de erros realistas. Não precisa de conta AWS.

---

## O assistente de configuração

Roda sozinho na 1ª vez (ou quando quiser, com `python configurar.py`) e grava as respostas num
arquivo local **`.env`**.

**1. Acesso à AWS** — escolha uma opção:

| Opção | Quando usar |
|---|---|
| Usar um profile existente | lista todos os profiles do AWS CLI encontrados na máquina |
| **Cadastrar uma chave de acesso** | o mais comum. Cole o *Access Key ID* e o *Secret*; o assistente grava o profile em `~/.aws` (igual ao `aws configure`). **Não precisa do AWS CLI** |
| SSO / IAM Identity Center | instala o AWS CLI se faltar e abre o login no navegador |
| Variáveis de ambiente | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` já definidas |
| “Não tenho chave” | passo a passo no console da AWS + salva a política IAM em `iam-policy.json` para o administrador |

**2. Teste de conexão** — conecta na hora e mostra a conta e quantos log groups encontrou. Se algo
falhar, explica o motivo e oferece a correção: erro de SSL causado por antivírus/proxy é
**corrigido sozinho no Windows**; sessão SSO expirada pode logar de novo; falta de permissão é
explicada; chave ou região erradas podem ser trocadas e testadas de novo.

**3. Preferências** — nome do painel, nome da empresa/sistema (vai nos prompts), intervalo de coleta,
quanto buscar na 1ª vez, dias de histórico local, quais log groups monitorar e a porta.

---

## Requisitos

| | |
|---|---|
| Sistema | Windows 10/11, macOS ou Linux, com internet |
| AWS | uma conta com CloudWatch Logs |
| Credenciais | **somente leitura** (chave de acesso, profile existente ou SSO) |
| Python | 3.10+ (o inicializador instala se faltar) |
| AWS CLI | opcional (só SSO) |

Não precisa de servidor de banco, Docker nem Node.js — o SQLite vem com o Python. O painel carrega o
Chart.js de um CDN.

### Permissões IAM

Anexe a política gerenciada da AWS **`CloudWatchReadOnlyAccess`** ou esta política mínima:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudWatchMonitorReadOnly",
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups",
        "logs:StartQuery",
        "logs:GetQueryResults",
        "logs:StopQuery",
        "logs:GetLogEvents",
        "cloudwatch:DescribeAlarms",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

**Criando a chave de acesso (para quem administra a AWS):** IAM → Usuários → *Criar usuário* (sem
acesso ao console) → anexe a política acima → *Credenciais de segurança* → *Criar chave de acesso* →
caso de uso *Aplicação executada fora da AWS* → copie o Access Key ID e o Secret (aparece só uma vez).

### Custo

O CloudWatch Logs Insights cobra **US$ 0,005 por GB varrido**. Em contas com dezenas de MB de log por
dia, coletar a cada 5 minutos custa **centavos por mês**. Uma busca manual de 30 dias numa conta grande
pode custar alguns centavos.

---

## Configuração (`.env`)

Criado pelo assistente; dá para editar à mão (modelo comentado: [`.env.example`](.env.example)).
Variáveis de ambiente do sistema têm prioridade.

| Variável | Padrão | Para quê |
|---|---|---|
| `MONITOR_AWS_PROFILE` | `AWS_PROFILE` ou credenciais padrão | profile do AWS CLI |
| `MONITOR_AWS_REGION` | região do profile, senão `us-east-1` | região dos logs |
| `MONITOR_CA_BUNDLE` | — | `.pem` extra para antivírus/proxy que inspeciona HTTPS |
| `MONITOR_APP_NAME` | `CloudWatch Monitor` | nome no painel e no relatório |
| `MONITOR_SYSTEM_NAME` | — | nome da empresa/sistema citado nos prompts |
| `MONITOR_INTERVAL_MIN` | `5` | intervalo de coleta inicial (min) |
| `MONITOR_FIRST_LOOKBACK_HOURS` | `6` | horas buscadas na 1ª coleta |
| `MONITOR_RETENTION_DAYS` | `30` | dias de histórico local |
| `MONITOR_GROUP_INCLUDE` | — (todos) | regex: monitorar só log groups que casam |
| `MONITOR_GROUP_EXCLUDE` | warmup, containerinsights… | regex: log groups ignorados |
| `MONITOR_PORT` | `8765` | porta do painel |
| `MONITOR_DB` | pasta de dados do usuário | caminho do banco SQLite |

Os valores de coleta são só os **iniciais** — depois, use **⚙ Configurações** no painel.

**Várias contas AWS?** Clone o projeto uma vez por conta, cada um com seu `.env`
(`MONITOR_PORT` e `MONITOR_DB` diferentes).

| Sistema | Local padrão do banco |
|---|---|
| Windows | `%LOCALAPPDATA%\cloudwatch-monitor\monitor.db` |
| macOS | `~/Library/Application Support/cloudwatch-monitor/monitor.db` |
| Linux | `~/.local/share/cloudwatch-monitor/monitor.db` |

Fica fora da pasta do projeto de propósito: OneDrive, Dropbox e iCloud travam ou corrompem arquivos
SQLite em uso.

---

## Usando o painel

- **Topo**: estado da coleta, intervalo, *Coletar agora*, **🔎 Buscar nos logs** (tecla `/`), tema, ⚙.
- **Filtros**: período, serviço e categoria. Clique numa barra ou na legenda para filtrar; clique de
  novo para limpar. O filtro ativo aparece em destaque.
- **Issues**: clique para ver o log completo, as ocorrências e as ações **✨ Gerar Prompt**,
  **Resolver**, **Ignorar** e **AWS Console**.
- **🔎 Busca**: opções de período (15 min a 30 dias), log groups contendo um trecho do nome, palavra
  inteira (`387` não acha `13870`), maiúsculas e regex. Cada resultado tem **Ver contexto**,
  **✨ Gerar Prompt**, AWS Console e copiar.
- **🖼 Gerar relatório**: baixa um PNG com o que está na tela (respeitando os filtros).
- **Alarmes**: os alarmes já existentes na conta (5xx, latência, fila de erro…); o monitor só lê o estado.

### Quando o painel ficou fechado

| Situação | O que acontece |
|---|---|
| 1ª execução | busca as últimas `MONITOR_FIRST_LOOKBACK_HOURS` (padrão 6h) |
| Fechado por até 24h | recupera tudo sozinho |
| Fechado por mais tempo | **pergunta**: tudo desde a última execução, últimas N horas, a partir de uma data, ou nada |
| Falha de rede/AWS | não avança; a próxima coleta tenta a mesma janela de novo |

---

## Segurança e privacidade

- **Somente leitura**: o app nunca grava nada na AWS.
- **Só local**: o painel escuta em `127.0.0.1` — não fica acessível na rede.
- **Credenciais** ficam nos arquivos padrão `~/.aws`; o projeto guarda só o *nome* do profile.
  O `.env` é ignorado pelo git.
- **Nada vai para uma IA automaticamente** — o prompt só sai da sua máquina se você copiar e colar.
  Tokens, senhas, e-mails, CPF/CNPJ e strings de conexão são mascarados por padrão.

## Iniciar junto com o computador (opcional)

Rode o inicializador manualmente uma vez antes, para o assistente criar o `.env`.

**Windows** — `Win + R` → `shell:startup` → crie ali um atalho para o `iniciar.bat`
(em *Propriedades*, *Executar: Minimizada*).

**macOS** — crie `~/Library/LaunchAgents/com.cloudwatch-monitor.plist` (ajuste o caminho):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.cloudwatch-monitor</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/SEU_USUARIO/caminho/claudeWatch/iniciar.sh</string>
    <string>--no-browser</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/cloudwatch-monitor.log</string>
  <key>StandardErrorPath</key><string>/tmp/cloudwatch-monitor.log</string>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.cloudwatch-monitor.plist
```

**Linux (systemd, por usuário)** — crie `~/.config/systemd/user/cloudwatch-monitor.service`:

```ini
[Unit]
Description=CloudWatch Monitor

[Service]
WorkingDirectory=%h/caminho/claudeWatch
ExecStart=%h/caminho/claudeWatch/iniciar.sh --no-browser
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now cloudwatch-monitor
journalctl --user -u cloudwatch-monitor -f     # ver o log
```

## Problemas comuns

| Sintoma | Solução |
|---|---|
| “Não consegui acessar a AWS” ao iniciar | rode `python configurar.py` — ele testa e diz o que corrigir (`python app.py --check` só testa) |
| `SSL: CERTIFICATE_VERIFY_FAILED` | antivírus/proxy inspecionando HTTPS: `python configurar.py` (corrige sozinho no Windows) ou `MONITOR_CA_BUNDLE` |
| `AccessDenied` | faltam permissões — veja *Permissões IAM* |
| Sessão SSO expirada | `aws sso login --profile SEU_PROFILE` |
| Porta ocupada | mude `MONITOR_PORT` no `.env` |
| Painel vazio | aguarde a 1ª coleta (“coleta ok” no topo) ou aumente o período |
| Gráficos não aparecem | o navegador precisa acessar `cdn.jsdelivr.net` |
| Python não encontrado após instalar | feche e abra o terminal e rode o inicializador de novo |
| Linux: `ensurepip is not available` | `sudo apt install python3-venv` (o inicializador oferece) |

## Como funciona

A cada intervalo, o coletor roda consultas do **CloudWatch Logs Insights** em todos os log groups
(50 por consulta), filtrando por uma regex de erro editável. As janelas se sobrepõem 3 minutos para
pegar logs que chegam atrasados; duplicados são descartados. Tracebacks em várias linhas são juntados
e buscados completos no log stream; linhas INFO/DEBUG são ignoradas, exceto quando indicam 5xx ou
timeout. De logs JSON, o tipo e a mensagem do erro viram o título. Erros parecidos viram uma issue
(Timeout / HTTP 5xx / Fatal / Exceção / Erro), guardada em SQLite e servida por um pequeno servidor
HTTP da biblioteca padrão.

```
iniciar.bat / iniciar.sh   inicializadores (requisitos + assistente + painel)
configurar.py              assistente de configuração  →  .env
app.py                     servidor local + API  (--demo, --check, --port, --no-browser)
collector.py               coleta Logs Insights, alarmes, recuperação de lacunas, busca
fingerprint.py             classificação e agrupamento de erros
prompt.py                  gerador de prompts (com mascaramento)
demo.py                    dados fictícios do modo demonstração
db.py · config.py          banco SQLite · configuração
web/                       painel (HTML/CSS/JS puro + Chart.js)
```

## Contribuindo

Issues e pull requests são bem-vindos. O projeto é mantido no esquema “quando der”.

## Licença

[MIT](LICENSE) © Saulo Oliveira

---

<sub>Sem vínculo, endosso ou patrocínio da Amazon Web Services ou da Anthropic. “AWS” e “CloudWatch”
são marcas da Amazon.com, Inc.; “Claude” é marca da Anthropic, PBC — citadas apenas para descrever
compatibilidade.</sub>
