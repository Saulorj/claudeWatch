# CloudWatch Monitor

Painel **local** de erros do AWS CloudWatch — uma alternativa leve ao Datadog para acompanhar
erros. Roda na sua máquina, coleta os logs de X em X minutos, guarda tudo em SQLite e mostra
gráficos, issues agrupadas, alarmes, busca em todos os logs, relatório em PNG e um botão
**✨ Gerar Prompt** que monta o diagnóstico completo de um erro para colar no Claude.

Nada é instalado na AWS: o monitor só **lê** logs e alarmes com as suas credenciais.

---

## Início rápido

| Sistema | O que fazer |
|---|---|
| **Windows** | dois cliques em **`iniciar.bat`** |
| **Linux / macOS** | no terminal, dentro da pasta: `chmod +x iniciar.sh` (só a 1ª vez) e `./iniciar.sh` |

O inicializador faz tudo, em ordem, e explica cada passo:

1. **Python 3.10+** — verifica a versão; se faltar, instala (winget no Windows, Homebrew no
   macOS, apt/dnf/pacman/zypper no Linux) ou abre a página de download.
2. **Dependências** (`requirements.txt`) — verifica e instala o que faltar (inclusive o `pip`).
3. **AWS CLI** — verifica e mostra a versão. É **opcional** (só é necessário para login SSO);
   se faltar, oferece instalar.
4. **Configuração** — na 1ª execução abre um **assistente no console** (veja abaixo).
5. Abre o painel no navegador: **http://127.0.0.1:8765/**

Nas próximas vezes ele só confere os requisitos (rápido) e abre o painel.

---

## O assistente de configuração

Roda sozinho na 1ª vez (ou a qualquer momento com `python configurar.py`) e grava as respostas
no arquivo **`.env`**, na pasta do projeto.

**1. Acesso à AWS** — escolha uma opção:

| Opção | Quando usar |
|---|---|
| Usar um profile existente | já existe um profile do AWS CLI na máquina; o assistente lista todos |
| **Cadastrar uma chave de acesso** | o caso mais comum. Cole o *Access Key ID* e o *Secret*; o assistente grava o profile em `~/.aws` (igual ao `aws configure`). **Não precisa do AWS CLI** |
| Entrar com SSO | a empresa usa IAM Identity Center; o assistente instala o AWS CLI se faltar e abre o login no navegador |
| Variáveis de ambiente | já existem `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` definidas |
| “Não tenho chave — como consigo uma?” | mostra o passo a passo no console da AWS e salva a política de permissões em `iam-policy.json` para mandar ao administrador |

**2. Teste de conexão** — conecta na hora, mostra a conta e quantos log groups encontrou
(Lambda, ECS, API Gateway…). Se algo falhar, explica o motivo e oferece a correção:

| Problema | O que o assistente faz |
|---|---|
| Erro de certificado SSL (antivírus/proxy inspecionando HTTPS) | no Windows, corrige sozinho montando os certificados a partir do repositório do sistema |
| Sessão SSO expirada | oferece fazer o login de novo |
| Falta permissão | diz o que pedir e salva `iam-policy.json` |
| Chave inválida/expirada, região errada | permite trocar e testar de novo |

**3. Preferências** — nome do painel, nome da empresa/sistema (vai nos prompts para o Claude),
intervalo de coleta, quantas horas buscar na 1ª vez, dias de histórico local, quais log groups
monitorar (todos ou só os que contêm um trecho do nome — mostra quantos casam) e a porta do
painel (sugere uma livre).

---

## O que você precisa ter

| Item | Detalhe |
|---|---|
| Computador | Windows 10/11, macOS ou Linux, com internet |
| Conta AWS | com logs no CloudWatch Logs |
| Credencial AWS **somente leitura** | chave de acesso de um usuário IAM, profile existente ou SSO (veja abaixo) |
| Python 3.10+ | o inicializador instala se faltar |
| AWS CLI | opcional (só para SSO) |

Não precisa de banco de dados, Docker nem Node: o SQLite já vem com o Python. O painel carrega a
biblioteca de gráficos (Chart.js) de um CDN, então o navegador precisa de internet.

### Permissões na AWS (IAM)

A credencial precisa apenas de **leitura**. Use a política gerenciada **`CloudWatchReadOnlyAccess`**
ou esta política mínima (o assistente também a salva em `iam-policy.json`):

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

### Como criar a chave de acesso (para quem administra a AWS)

1. Console da AWS → **IAM** → **Usuários** → **Criar usuário** (ex.: `cloudwatch-monitor`),
   sem acesso ao console.
2. **Permissões** → *Anexar políticas diretamente* → `CloudWatchReadOnlyAccess` (ou a política acima).
3. Abra o usuário → aba **Credenciais de segurança** → **Criar chave de acesso** → caso de uso
   *Aplicação executada fora da AWS* → copie o **Access Key ID** e o **Secret** (o Secret só
   aparece uma vez).

### Custo

O CloudWatch Logs Insights cobra US$ 0,005 por GB varrido. Para contas com dezenas de MB de log
por dia, coletar a cada 5 min custa centavos por mês. Buscas manuais de 30 dias em contas grandes
podem custar alguns centavos cada.

---

## Configuração (`.env`)

O assistente cria o `.env`; dá para editar à mão (modelo comentado em **`.env.example`**).
Variáveis de ambiente do sistema têm prioridade sobre o arquivo.

| Variável | Padrão | Para quê |
|---|---|---|
| `MONITOR_AWS_PROFILE` | `AWS_PROFILE` ou credenciais padrão | profile do AWS CLI |
| `MONITOR_AWS_REGION` | região do profile, senão `us-east-1` | região dos logs |
| `MONITOR_CA_BUNDLE` | — | arquivo `.pem` extra (antivírus/proxy que inspeciona HTTPS) |
| `MONITOR_APP_NAME` | `CloudWatch Monitor` | nome no painel e no relatório |
| `MONITOR_SYSTEM_NAME` | — | nome da empresa/sistema citado nos prompts |
| `MONITOR_INTERVAL_MIN` | `5` | intervalo de coleta inicial (min) |
| `MONITOR_FIRST_LOOKBACK_HOURS` | `6` | horas buscadas na 1ª coleta |
| `MONITOR_RETENTION_DAYS` | `30` | dias de histórico local |
| `MONITOR_GROUP_INCLUDE` | — (todos) | regex: monitorar só log groups que casam |
| `MONITOR_GROUP_EXCLUDE` | warmup, containerinsights… | regex: log groups ignorados |
| `MONITOR_PORT` | `8765` | porta do painel |
| `MONITOR_DB` | pasta de dados do usuário | caminho do banco SQLite |

Os valores de coleta são só os **iniciais**: depois, ajuste em **⚙ Configurações** no painel.

**Várias contas AWS?** Copie a pasta do projeto uma vez por conta (cada uma com seu `.env`,
`MONITOR_PORT` e `MONITOR_DB` diferentes) e rode cada uma.

### Onde ficam os dados

| Sistema | Banco SQLite (padrão) |
|---|---|
| Windows | `%LOCALAPPDATA%\cloudwatch-monitor\monitor.db` |
| macOS | `~/Library/Application Support/cloudwatch-monitor/monitor.db` |
| Linux | `~/.local/share/cloudwatch-monitor/monitor.db` |

Fica fora da pasta do projeto de propósito: OneDrive, Dropbox e iCloud travam ou corrompem
arquivos SQLite em uso. Para recomeçar do zero, feche o monitor e apague essa pasta.

**Privacidade:** tudo fica na sua máquina. O painel só escuta em `127.0.0.1` (não fica acessível
na rede). Nada é enviado ao Claude automaticamente — o prompt só sai se você copiar e colar.

---

## Usando o painel

- **Topo**: estado da coleta, intervalo (1 a 60 min), *Coletar agora*, **🔎 Buscar nos logs**, tema, ⚙.
- **Filtros**: período (1h a 30 dias), serviço e categoria. Clique numa barra ou na legenda dos
  gráficos para filtrar; clique de novo para limpar. O filtro ativo aparece em destaque no topo.
- **Issues**: erros iguais agrupados (ids, números e horários são ignorados no agrupamento).
  Clique para ver o log completo, as ocorrências e as ações:
  - **✨ Gerar Prompt** — erro completo + a invocação inteira da Lambda (ou as linhas ao redor no
    container) + estatísticas + erros relacionados. Tokens, senhas, e-mails e CPF são mascarados.
  - **Resolver** — se o erro voltar, a issue reabre como *Regressão*.
  - **Ignorar** — some dos gráficos (use para ruídos conhecidos).
- **Notificações**: ative em ⚙ para receber aviso do sistema em issue nova ou regressão.

### 🔎 Buscar nos logs

Botão no topo (ou tecla `/`). Procura **qualquer texto** em todos os log groups — não só erros —
para descobrir a origem de um id, pedido, e-mail ou código de erro (ex.: “erro id 387”).

- Opções: período (15 min a 30 dias), só log groups contendo um trecho do nome, palavra inteira
  (`387` não acha `13870`), diferenciar maiúsculas e expressão regular.
- Resultado: ocorrências por serviço (clique para filtrar) e as 300 linhas mais recentes, com o
  texto destacado. Em cada linha: **Ver contexto**, **✨ Gerar Prompt**, AWS Console e copiar.
- Buscas de 24h levam de ~5 a 40 s; 30 dias podem levar 1–2 min.

### 🖼 Gerar relatório

Baixa um **PNG** com o que está na tela — período, filtros, KPIs, os três gráficos, alarmes e as
15 issues com mais ocorrências, cada uma com a última mensagem de erro (dados sensíveis
mascarados). Bom para mandar no chat da equipe ou anexar em um ticket.

### Alarmes CloudWatch

São os alarmes que já existem na conta (criados no console do CloudWatch). Cada um vigia uma
métrica — 5xx no load balancer, latência, hosts sem saúde, mensagens em fila de erro (DLQ) etc. —
e vai para **ALARM** quando passa do limite. O monitor só **lê** o estado (OK, ALARME, Sem dados).

### Quando o monitor ficou fechado

| Situação | O que acontece |
|---|---|
| 1ª execução | busca as últimas `MONITOR_FIRST_LOOKBACK_HOURS` (padrão 6h) |
| Fechado por até 24h | recupera tudo sozinho |
| Fechado por mais tempo | o painel **pergunta**: tudo desde a última execução, últimas N horas, a partir de uma data, ou nada |
| Falha de rede/AWS | não avança; a próxima coleta tenta a mesma janela de novo |

A recuperação roda em segundo plano (barra de progresso no topo) sem parar o monitoramento ao
vivo e continua de onde parou se você fechar no meio. O limite é a retenção dos logs no CloudWatch.

---

## Iniciar junto com o computador (opcional)

**Windows** — `Win + R` → `shell:startup` → crie ali um atalho para o `iniciar.bat`
(em *Propriedades* do atalho, *Executar: Minimizada*).

**macOS** — crie `~/Library/LaunchAgents/com.cloudwatch-monitor.plist` (ajuste o caminho):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.cloudwatch-monitor</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/SEU_USUARIO/caminho/do/projeto/iniciar.sh</string>
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
WorkingDirectory=%h/caminho/do/projeto
ExecStart=%h/caminho/do/projeto/iniciar.sh --no-browser
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now cloudwatch-monitor
journalctl --user -u cloudwatch-monitor -f     # ver o log
```

> Rode o `iniciar` manualmente uma vez antes (para o assistente criar o `.env`): sem console
> interativo, o assistente não aparece.

---

## Problemas comuns

| Sintoma | Solução |
|---|---|
| Python não encontrado mesmo depois de instalar | feche e abra o terminal / rode o `iniciar` de novo; no Windows, reinstale marcando “Add python.exe to PATH” |
| Falha ao instalar o `requirements.txt` | verifique internet/proxy; tente `python -m pip install --user -r requirements.txt` |
| “Não consegui acessar a AWS” ao iniciar | rode `python configurar.py` — ele testa e diz o que corrigir |
| `SSL: CERTIFICATE_VERIFY_FAILED` | antivírus ou proxy inspecionando HTTPS: rode `python configurar.py` (no Windows corrige sozinho) ou defina `MONITOR_CA_BUNDLE` |
| `AccessDenied` | faltam permissões — veja *Permissões na AWS* |
| Sessão SSO expirada | `aws sso login --profile NOME_DO_PROFILE` |
| Porta ocupada | mude `MONITOR_PORT` no `.env` (ou rode `python configurar.py`) |
| Painel vazio | aguarde a 1ª coleta (“coleta ok” no topo) ou aumente o período para 24h/7 dias |
| Gráficos não aparecem | o navegador precisa acessar `cdn.jsdelivr.net` |
| Linux: `ensurepip is not available` | `sudo apt install python3-venv` (o `iniciar.sh` oferece instalar) |
| macOS/Linux: `Permission denied` no `iniciar.sh` | `chmod +x iniciar.sh` |

---

## Arquivos

| Arquivo | Função |
|---|---|
| `iniciar.bat` / `iniciar.sh` | verificam/instalam requisitos, chamam o assistente e abrem o painel |
| `configurar.py` | assistente de configuração (gera o `.env`) |
| `app.py` | servidor local + API (`python app.py --check` só testa o acesso à AWS) |
| `collector.py` | coleta via Logs Insights, alarmes, recuperação de lacunas e busca |
| `fingerprint.py` | classificação e agrupamento de erros |
| `prompt.py` | gerador dos prompts para o Claude |
| `db.py` / `config.py` | banco SQLite e configuração |
| `web/` | painel (HTML, CSS, JS) |
| `.env.example` | modelo de configuração comentado |

## Como funciona (resumo técnico)

A cada intervalo, o coletor roda consultas do **CloudWatch Logs Insights** em todos os log groups
(50 por consulta), filtrando por uma regex de erro (editável em ⚙). Janelas se sobrepõem 3 min
para não perder logs que chegam atrasados; duplicados são descartados. Tracebacks logados linha a
linha são juntados e buscados completos no log stream; linhas INFO/DEBUG são ignoradas, exceto
quando indicam HTTP 5xx ou timeout. Logs em JSON (pino, structlog…) têm o tipo e a mensagem do
erro extraídos para o título. Erros iguais viram uma **issue** (Timeout / HTTP 5xx / Fatal /
Exceção / Erro).
