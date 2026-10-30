"""Assistente de configuração no console: credenciais AWS, região, nomes e coleta -> arquivo .env.

Uso:
    python configurar.py               configura (ou reconfigura)
    python configurar.py --if-needed   só roda se ainda não existir o .env (usado pelo iniciar.bat/.sh)
"""
import argparse
import configparser
import getpass
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_ENV = BASE_DIR / ".env"
NEW_PROFILE_NAME = "cloudwatch-monitor"
COMMON_REGIONS = [
    ("us-east-1", "EUA — Norte da Virgínia"), ("sa-east-1", "Brasil — São Paulo"),
    ("us-east-2", "EUA — Ohio"), ("us-west-2", "EUA — Oregon"), ("eu-west-1", "Irlanda"),
]
IAM_POLICY = {
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "CloudWatchMonitorReadOnly",
        "Effect": "Allow",
        "Action": ["logs:DescribeLogGroups", "logs:StartQuery", "logs:GetQueryResults", "logs:StopQuery",
                   "logs:GetLogEvents", "cloudwatch:DescribeAlarms", "sts:GetCallerIdentity"],
        "Resource": "*",
    }],
}

# ------------------------------------------------------------------ console
if os.name == "nt":
    os.system("")  # liga cores ANSI no console do Windows
BOLD, DIM, GREEN, YELLOW, RED, CYAN, RESET = "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[36m", "\033[0m"


def title(text):
    print(f"\n{BOLD}{CYAN}━━ {text} {'━' * max(0, 60 - len(text))}{RESET}")


def info(text):
    print(f"  {text}")


def ok(text):
    print(f"  {GREEN}✔ {text}{RESET}")


def warn(text):
    print(f"  {YELLOW}! {text}{RESET}")


def fail(text):
    print(f"  {RED}✘ {text}{RESET}")


def ask(prompt, default=None, secret=False, required=False):
    suffix = f" {DIM}[{default}]{RESET}" if default not in (None, "") else ""
    while True:
        label = f"  {BOLD}?{RESET} {prompt}{suffix}: "
        if secret and sys.stdin.isatty():
            value = getpass.getpass(label)
        else:
            value = input(label)
        value = value.strip()
        if not value and default is not None:
            return str(default)
        if value or not required:
            return value
        warn("Este campo é obrigatório.")


def yes(prompt, default=True):
    hint = "S/n" if default else "s/N"
    value = ask(f"{prompt} ({hint})").lower()
    return default if not value else value.startswith("s") or value.startswith("y")


def choose(prompt, options, default=1):
    for i, label in enumerate(options, 1):
        info(f"{BOLD}{i}{RESET}) {label}")
    while True:
        value = ask(prompt, default)
        if value.isdigit() and 1 <= int(value) <= len(options):
            return int(value) - 1
        warn(f"Digite um número de 1 a {len(options)}.")


def ask_int(prompt, default, lo, hi):
    while True:
        value = ask(prompt, default)
        if value.isdigit() and lo <= int(value) <= hi:
            return int(value)
        warn(f"Digite um número entre {lo} e {hi}.")


# ------------------------------------------------------------------ AWS: arquivos de credenciais
def aws_dir() -> Path:
    return Path(os.environ.get("AWS_CONFIG_FILE", Path.home() / ".aws" / "config")).parent


def write_profile(name, key_id, secret, token, region):
    """Grava o profile em ~/.aws/credentials e ~/.aws/config (o mesmo que o 'aws configure' faz)."""
    cred_path = Path(os.environ.get("AWS_SHARED_CREDENTIALS_FILE", Path.home() / ".aws" / "credentials"))
    conf_path = Path(os.environ.get("AWS_CONFIG_FILE", Path.home() / ".aws" / "config"))
    cred_path.parent.mkdir(parents=True, exist_ok=True)

    creds = configparser.RawConfigParser()
    creds.read(cred_path, encoding="utf-8")
    creds[name] = {"aws_access_key_id": key_id, "aws_secret_access_key": secret}
    if token:
        creds[name]["aws_session_token"] = token
    with open(cred_path, "w", encoding="utf-8") as f:
        creds.write(f)

    conf = configparser.RawConfigParser()
    conf.read(conf_path, encoding="utf-8")
    section = name if name == "default" else f"profile {name}"
    if not conf.has_section(section):
        conf.add_section(section)
    conf[section]["region"] = region
    conf[section]["output"] = "json"
    with open(conf_path, "w", encoding="utf-8") as f:
        conf.write(f)
    if os.name != "nt":
        os.chmod(cred_path, 0o600)
    ok(f"Profile '{name}' salvo em {cred_path.parent}")


def find_aws_cli() -> str | None:
    found = shutil.which("aws")
    if found:
        return found
    for candidate in (Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Amazon" / "AWSCLIV2" / "aws.exe",
                      Path("/usr/local/bin/aws"), Path("/opt/homebrew/bin/aws")):
        if candidate.is_file():
            return str(candidate)
    return None


def ensure_aws_cli() -> str | None:
    cli = find_aws_cli()
    if cli:
        return cli
    warn("O login SSO precisa do AWS CLI, que não está instalado.")
    if os.name == "nt" and shutil.which("winget"):
        if yes("Instalar o AWS CLI agora pelo winget?"):
            subprocess.call(["winget", "install", "-e", "--id", "Amazon.AWSCLI",
                             "--accept-package-agreements", "--accept-source-agreements"])
            cli = find_aws_cli()
            if cli:
                ok("AWS CLI instalado.")
                return cli
            fail("Não encontrei o AWS CLI depois da instalação. Feche e abra o iniciar.bat de novo.")
            return None
    elif sys.platform == "darwin":
        info("Instale com:  brew install awscli")
    else:
        info("Instale seguindo: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html")
    return None


def save_iam_policy() -> Path:
    path = BASE_DIR / "iam-policy.json"
    path.write_text(json.dumps(IAM_POLICY, indent=2), encoding="utf-8")
    return path


def explain_access_key():
    title("Como conseguir uma chave de acesso (Access Key)")
    info("Quem administra a AWS da empresa faz isto (ou você, se tiver acesso de administrador):")
    info("  1. Console da AWS → serviço IAM → Usuários → Criar usuário (ex.: cloudwatch-monitor).")
    info("     Não precisa de acesso ao console para esse usuário.")
    info("  2. Permissões → Anexar políticas diretamente → 'CloudWatchReadOnlyAccess'")
    info(f"     (ou a política mínima que salvei em: {save_iam_policy()})")
    info("  3. Abra o usuário → aba 'Credenciais de segurança' → 'Criar chave de acesso'")
    info("     → caso de uso 'Aplicação executada fora da AWS' → copie o Access Key ID e o Secret.")
    info(f"  {DIM}O Secret só aparece uma vez. O monitor só LÊ logs e alarmes; não altera nada na AWS.{RESET}")


# ------------------------------------------------------------------ AWS: teste e SSL
def data_dir() -> Path:
    import config  # noqa: importa só para reaproveitar a pasta de dados
    return config.DB_PATH.parent


def build_windows_ca_bundle() -> Path:
    """Junta as CAs públicas com as do repositório do Windows (inclui a de antivírus/proxy corporativo)."""
    import ssl
    parts = []
    try:
        import botocore
        bundled = Path(botocore.__file__).parent / "cacert.pem"
        if bundled.is_file():
            parts.append(bundled.read_text(encoding="utf-8"))
    except ImportError:
        pass
    try:
        import certifi
        parts.append(Path(certifi.where()).read_text(encoding="utf-8"))
    except ImportError:
        pass
    seen = set()
    for store in ("ROOT", "CA"):
        for cert, encoding, _trust in ssl.enum_certificates(store):
            if encoding == "x509_asn" and cert not in seen:
                seen.add(cert)
                parts.append(ssl.DER_cert_to_PEM_cert(cert))
    dest = data_dir() / "ca-bundle.pem"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(parts), encoding="ascii", errors="ignore")
    return dest


def test_aws(profile: str | None, region: str) -> tuple[str, dict]:
    """Retorna (status, detalhes). status: ok | ssl | no_creds | no_profile | sso | denied | expired | error"""
    import boto3
    from botocore.exceptions import (ClientError, NoCredentialsError, ProfileNotFound, SSLError,
                                     TokenRetrievalError, UnauthorizedSSOTokenError)
    try:
        session = boto3.Session(profile_name=profile or None, region_name=region)
        ident = session.client("sts").get_caller_identity()
        logs = session.client("logs")
        groups = []
        for page in logs.get_paginator("describe_log_groups").paginate():
            groups += [g["logGroupName"] for g in page["logGroups"]]
        return "ok", {"account": ident["Account"], "arn": ident["Arn"], "groups": groups}
    except ProfileNotFound:
        return "no_profile", {}
    except NoCredentialsError:
        return "no_creds", {}
    except (TokenRetrievalError, UnauthorizedSSOTokenError):
        return "sso", {}
    except SSLError as exc:
        return "ssl", {"error": str(exc)}
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("AccessDenied", "AccessDeniedException", "UnauthorizedOperation"):
            return "denied", {"error": str(exc)}
        if code in ("ExpiredToken", "ExpiredTokenException", "InvalidClientTokenId", "SignatureDoesNotMatch",
                    "UnrecognizedClientException"):
            return "expired", {"error": code}
        return "error", {"error": f"{code}: {exc}"}
    except Exception as exc:
        text = str(exc)
        if "CERTIFICATE_VERIFY_FAILED" in text or "SSL" in text:
            return "ssl", {"error": text}
        return "error", {"error": f"{type(exc).__name__}: {text}"}


def summarize_groups(groups: list[str]) -> str:
    kinds = {"Lambda": 0, "ECS": 0, "API Gateway": 0, "RDS": 0, "outros": 0}
    for g in groups:
        if g.startswith("/aws/lambda/"):
            kinds["Lambda"] += 1
        elif g.startswith("/ecs/"):
            kinds["ECS"] += 1
        elif g.startswith("API-Gateway"):
            kinds["API Gateway"] += 1
        elif g.startswith("/aws/rds/"):
            kinds["RDS"] += 1
        else:
            kinds["outros"] += 1
    return ", ".join(f"{n} {k}" for k, n in kinds.items() if n)


# ------------------------------------------------------------------ passos
def step_credentials(env: dict) -> tuple[str | None, str | None]:
    """Escolhe/cria as credenciais. Retorna (profile, região sugerida)."""
    import boto3
    title("1. Acesso à AWS")
    info("O monitor só LÊ logs e alarmes do CloudWatch. Nada é alterado na sua conta AWS.")
    while True:
        session = boto3.Session()
        profiles = sorted(session.available_profiles)
        env_creds = bool(os.environ.get("AWS_ACCESS_KEY_ID"))
        options, actions = [], []
        for p in profiles:
            region = boto3.Session(profile_name=p).region_name or "sem região"
            options.append(f"Usar o profile {BOLD}{p}{RESET} {DIM}({region}){RESET}")
            actions.append(("profile", p))
        options.append("Cadastrar uma chave de acesso (Access Key ID + Secret) — não precisa do AWS CLI")
        actions.append(("keys", None))
        options.append("Entrar com SSO / IAM Identity Center (login pelo navegador)")
        actions.append(("sso", None))
        if env_creds:
            options.append("Usar as credenciais das variáveis de ambiente (AWS_ACCESS_KEY_ID)")
            actions.append(("env", None))
        options.append("Não tenho chave — como consigo uma?")
        actions.append(("help", None))
        if profiles:
            info(f"Encontrei {len(profiles)} profile(s) do AWS CLI nesta máquina:")
        else:
            warn("Nenhum profile do AWS CLI nesta máquina. Sem problema: dá para cadastrar a chave aqui.")
        default = 1 if profiles else len(profiles) + 1
        kind, value = actions[choose("Escolha uma opção", options, default)]

        if kind == "profile":
            return value, boto3.Session(profile_name=value).region_name
        if kind == "env":
            return None, os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        if kind == "help":
            explain_access_key()
            input(f"\n  {DIM}Pressione Enter para voltar ao menu…{RESET}")
            continue
        if kind == "keys":
            info("Cole os dados da chave de acesso (o Secret não aparece enquanto digita).")
            key_id = ask("Access Key ID (começa com AKIA ou ASIA)", required=True)
            secret = ask("Secret Access Key", secret=True, required=True)
            token = ""
            if key_id.startswith("ASIA"):
                token = ask("Session Token (chave temporária ASIA… exige)", required=True)
            region = pick_region(None)
            name = ask("Nome para este profile", NEW_PROFILE_NAME)
            if name in profiles and not yes(f"O profile '{name}' já existe. Substituir?", False):
                continue
            write_profile(name, key_id, secret, token, region)
            return name, region
        if kind == "sso":
            cli = ensure_aws_cli()
            if not cli:
                continue
            name = ask("Nome para este profile", NEW_PROFILE_NAME + "-sso")
            info("Vou abrir o assistente do AWS CLI. Ele pede a URL de início do SSO (ex.: https://minhaempresa.awsapps.com/start),")
            info("a região do SSO, e abre o navegador para você entrar. Depois escolha a conta e a role.")
            subprocess.call([cli, "configure", "sso", "--profile", name])
            if name in boto3.Session().available_profiles:
                return name, boto3.Session(profile_name=name).region_name
            fail("O profile SSO não foi criado. Vamos tentar de novo.")


def pick_region(suggested: str | None) -> str:
    default = suggested or "us-east-1"
    info("Região onde ficam os logs (no console da AWS, aparece no canto superior direito):")
    for code, name in COMMON_REGIONS:
        info(f"   {code:<12} {DIM}{name}{RESET}")
    while True:
        region = ask("Região", default).lower()
        if len(region.split("-")) >= 3:
            return region
        warn("Formato esperado: xx-xxxx-N (ex.: us-east-1, sa-east-1).")


def step_test(profile: str | None, region: str, env: dict) -> tuple[bool, dict]:
    title("2. Testando o acesso")
    while True:
        info(f"Conectando com {'o profile ' + profile if profile else 'as credenciais padrão'} em {region}…")
        status, d = test_aws(profile, region)
        if status == "ok":
            ok(f"Conectado na conta {d['account']} ({d['arn'].split(':')[-1]})")
            ok(f"{len(d['groups'])} log groups encontrados: {summarize_groups(d['groups']) or 'nenhum'}")
            if not d["groups"]:
                warn("Nenhum log group nesta região. Confira se é a região certa.")
                if yes("Escolher outra região?"):
                    region = pick_region(region)
                    env["MONITOR_AWS_REGION"] = region
                    continue
            return True, d
        if status == "ssl":
            fail("Erro de certificado SSL: um antivírus (ex.: Norton, Kaspersky) ou proxy da empresa")
            info("está inspecionando o HTTPS e o Python não reconhece o certificado dele.")
            if os.name == "nt" and yes("Corrigir automaticamente usando os certificados do Windows?"):
                bundle = build_windows_ca_bundle()
                os.environ["AWS_CA_BUNDLE"] = str(bundle)
                env["MONITOR_CA_BUNDLE"] = str(bundle)
                ok(f"Certificados salvos em {bundle}")
                continue
            path = ask("Caminho de um arquivo .pem com a CA do antivírus/proxy (vazio para pular)")
            if path and Path(path).is_file():
                os.environ["AWS_CA_BUNDLE"] = path
                env["MONITOR_CA_BUNDLE"] = path
                continue
        elif status == "sso":
            warn("A sessão SSO expirou ou ainda não foi feito o login.")
            cli = ensure_aws_cli()
            if cli and yes("Fazer o login SSO agora (abre o navegador)?"):
                subprocess.call([cli, "sso", "login", "--profile", profile] if profile else [cli, "sso", "login"])
                continue
        elif status == "denied":
            fail("As credenciais funcionam, mas falta permissão para ler o CloudWatch.")
            info(f"Peça ao administrador para anexar 'CloudWatchReadOnlyAccess' ou a política em: {save_iam_policy()}")
        elif status == "expired":
            fail(f"Chave inválida ou expirada ({d.get('error')}). Confira o Access Key ID e o Secret.")
        elif status in ("no_creds", "no_profile"):
            fail("Credenciais não encontradas para essa escolha.")
        else:
            fail(f"Falhou: {d.get('error')}")
            info("Confira a internet e a região escolhida.")
        choice = choose("O que fazer?", ["Tentar de novo", "Escolher outras credenciais", "Trocar a região",
                                          "Continuar mesmo assim (configuro depois)"], 1)
        if choice == 1:
            return False, {"restart": True}
        if choice == 2:
            region = pick_region(region)
            env["MONITOR_AWS_REGION"] = region
        if choice == 3:
            return False, {}


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def step_preferences(env: dict, groups: list[str]):
    title("3. Preferências")
    env["MONITOR_APP_NAME"] = ask("Nome do painel (aparece no topo e no relatório)", env.get("MONITOR_APP_NAME") or "CloudWatch Monitor")
    env["MONITOR_SYSTEM_NAME"] = ask("Nome da empresa/sistema (vai nos prompts para o Claude; pode deixar vazio)",
                                     env.get("MONITOR_SYSTEM_NAME", ""))
    env["MONITOR_INTERVAL_MIN"] = str(ask_int("Coletar a cada quantos minutos", env.get("MONITOR_INTERVAL_MIN", 5), 1, 240))
    env["MONITOR_FIRST_LOOKBACK_HOURS"] = str(ask_int("Na primeira coleta, buscar quantas horas para trás",
                                                      env.get("MONITOR_FIRST_LOOKBACK_HOURS", 6), 1, 720))
    env["MONITOR_RETENTION_DAYS"] = str(ask_int("Guardar o histórico local por quantos dias",
                                                env.get("MONITOR_RETENTION_DAYS", 30), 1, 365))
    if groups and yes(f"Monitorar todos os {len(groups)} log groups?", True):
        env["MONITOR_GROUP_INCLUDE"] = ""
    elif groups:
        import re
        while True:
            pattern = ask("Monitorar só log groups cujo nome contenha (ex.: prod  ·  ou regex: /aws/lambda/|/ecs/)", required=True)
            try:
                matched = [g for g in groups if re.search(pattern, g)]
            except re.error as exc:
                warn(f"Expressão inválida: {exc}")
                continue
            info(f"{len(matched)} de {len(groups)} log groups: {', '.join(matched[:5])}{' …' if len(matched) > 5 else ''}")
            if matched and yes("Usar este filtro?"):
                env["MONITOR_GROUP_INCLUDE"] = pattern
                break
    port = int(env.get("MONITOR_PORT") or 8765)
    while not port_free(port) and port < 8800:
        port += 1
    env["MONITOR_PORT"] = str(ask_int("Porta do painel no navegador", port, 1024, 65535))


ENV_TEMPLATE = """# Configuração do monitor — gerada por "python configurar.py" (rode de novo para mudar).
# Também dá para editar à mão. Modelo comentado: .env.example

# Acesso à AWS
MONITOR_AWS_PROFILE={MONITOR_AWS_PROFILE}
MONITOR_AWS_REGION={MONITOR_AWS_REGION}
MONITOR_CA_BUNDLE={MONITOR_CA_BUNDLE}

# Nomes
MONITOR_APP_NAME={MONITOR_APP_NAME}
MONITOR_SYSTEM_NAME={MONITOR_SYSTEM_NAME}

# Coleta (valores iniciais; depois ajuste em ⚙ Configurações no painel)
MONITOR_INTERVAL_MIN={MONITOR_INTERVAL_MIN}
MONITOR_FIRST_LOOKBACK_HOURS={MONITOR_FIRST_LOOKBACK_HOURS}
MONITOR_RETENTION_DAYS={MONITOR_RETENTION_DAYS}
MONITOR_GROUP_INCLUDE={MONITOR_GROUP_INCLUDE}

# Painel
MONITOR_PORT={MONITOR_PORT}
"""


def read_env(path: Path) -> dict:
    env = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def main():
    parser = argparse.ArgumentParser(description="Assistente de configuração do monitor")
    parser.add_argument("--if-needed", action="store_true", help="só roda se o .env ainda não existir")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV))
    args = parser.parse_args()
    env_path = Path(args.env_file)

    if args.if_needed and env_path.exists():
        return 0
    if args.if_needed and not sys.stdin.isatty():
        print("Sem console interativo: pulando o assistente (rode 'python configurar.py' para configurar).")
        return 0
    try:
        import boto3  # noqa: F401
    except ImportError:
        fail("Falta a biblioteca boto3. Rode: python -m pip install -r requirements.txt")
        return 1

    env = read_env(env_path)
    print(f"\n{BOLD}Assistente de configuração — CloudWatch Monitor{RESET}")
    info("Responda as perguntas; Enter aceita o valor entre [colchetes]. Ctrl+C cancela.")
    if env_path.exists():
        info(f"{DIM}Já existe uma configuração ({env_path.name}); os valores atuais aparecem como padrão.{RESET}")

    try:
        while True:
            profile, suggested_region = step_credentials(env)
            region = suggested_region or pick_region(env.get("MONITOR_AWS_REGION"))
            env["MONITOR_AWS_PROFILE"] = profile or ""
            env["MONITOR_AWS_REGION"] = region
            if os.environ.get("AWS_CA_BUNDLE") and not env.get("MONITOR_CA_BUNDLE"):
                env["MONITOR_CA_BUNDLE"] = os.environ["AWS_CA_BUNDLE"]
            connected, details = step_test(profile, region, env)
            if details.get("restart"):
                continue
            break
        step_preferences(env, details.get("groups", []))
    except (KeyboardInterrupt, EOFError):
        print()
        warn("Configuração cancelada. Nada foi salvo.")
        return 1

    for key in ("MONITOR_CA_BUNDLE", "MONITOR_GROUP_INCLUDE", "MONITOR_SYSTEM_NAME"):
        env.setdefault(key, "")
    env_path.write_text(ENV_TEMPLATE.format(**env), encoding="utf-8")
    title("Pronto!")
    ok(f"Configuração salva em {env_path}")
    if not connected:
        warn("O acesso à AWS ainda não funcionou. O painel abre, mas a coleta só vai funcionar depois de")
        warn("corrigir as credenciais. Rode 'python configurar.py' de novo quando quiser.")
    info(f"Painel: http://127.0.0.1:{env['MONITOR_PORT']}/   ·   Para reconfigurar: python configurar.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
