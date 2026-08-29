"""Sobe o Analisador de Artigos: backend, frontend e navegador.

Feito para ser clicado, nao digitado. Entao ele verifica os pre-requisitos e
explica o que fazer em vez de despejar um traceback numa janela que some.

Fechar esta janela (ou Ctrl+C) derruba os dois servidores.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

# A janela do console do Windows abre em cp1252 e quebra nos acentos.
# `line_buffering` importa quando a saida e redirecionada para arquivo: sem
# ele o Python usa buffer de bloco e o progresso so aparece no fim, dando a
# impressao de que o lancador travou.
for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except (AttributeError, ValueError):
        pass

RAIZ = Path(__file__).resolve().parent.parent
BACKEND = RAIZ / "backend"
FRONTEND = RAIZ / "frontend"
LOGS = RAIZ / "dados" / "logs"

PORTA_BACKEND = 8000
PORTA_FRONTEND = 5173
URL_APP = f"http://localhost:{PORTA_FRONTEND}"
URL_SAUDE = f"http://127.0.0.1:{PORTA_BACKEND}/api/saude"

SEGUNDOS_ESPERA = 90


def cabecalho() -> None:
    print()
    print("=" * 62)
    print("  ANALISADOR DE ARTIGOS")
    print("=" * 62)
    print()


def porta_ocupada(porta: int) -> bool:
    """Tenta IPv4 e IPv6.

    O Vite escuta so em `[::1]` nesta maquina, entao testar apenas
    127.0.0.1 daria "porta livre" com o servidor de pe.
    """
    for familia, tipo, proto, _, endereco in socket.getaddrinfo(
        "localhost", porta, proto=socket.IPPROTO_TCP
    ):
        with socket.socket(familia, tipo, proto) as s:
            s.settimeout(0.4)
            if s.connect_ex(endereco) == 0:
                return True
    return False


def servico_responde(url: str) -> bool:
    """Checagem por HTTP, que e o que o navegador vai fazer de fato."""
    try:
        with urllib.request.urlopen(url, timeout=2):
            return True
    except urllib.error.HTTPError:
        # Respondeu, ainda que com erro - o servidor esta de pe.
        return True
    except (urllib.error.URLError, OSError):
        return False


def backend_responde() -> bool:
    return servico_responde(URL_SAUDE)


def frontend_responde() -> bool:
    return servico_responde(URL_APP)


def erro_fatal(titulo: str, *linhas: str) -> None:
    print(f"  [ERRO] {titulo}\n")
    for linha in linhas:
        print(f"    {linha}")
    print()
    input("  Pressione Enter para fechar...")
    sys.exit(1)


def conferir_prerequisitos() -> None:
    if not (RAIZ / ".env").exists():
        erro_fatal(
            "Falta o arquivo .env",
            "Copie .env.example para .env e preencha a chave do Scopus:",
            "",
            f'  copy "{RAIZ}\\.env.example" "{RAIZ}\\.env"',
        )

    try:
        import fastapi  # noqa: F401
        import sqlalchemy  # noqa: F401
    except ImportError:
        erro_fatal(
            "Faltam dependencias do backend",
            "Rode uma vez:",
            "",
            f'  pip install -r "{BACKEND}\\requirements.txt"',
        )

    if not (FRONTEND / "node_modules").exists():
        print("  Instalando dependencias do frontend (so na primeira vez)...")
        resultado = subprocess.run(
            ["npm", "install"], cwd=FRONTEND, shell=True, check=False
        )
        if resultado.returncode != 0:
            erro_fatal(
                "npm install falhou",
                "Confira se o Node.js esta instalado: node --version",
            )


def _kernel32():
    """kernel32 com as assinaturas declaradas.

    Sem `restype`/`argtypes`, o ctypes assume `int` de 32 bits e TRUNCA os
    handles de 64 bits. Foi assim que `AssignProcessToJobObject` falhava com
    ERROR_INVALID_HANDLE (6) mesmo com o job criado corretamente.
    """
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    k32.SetInformationJobObject.restype = wintypes.BOOL
    k32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.GetCurrentProcess.argtypes = []
    k32.AssignProcessToJobObject.restype = wintypes.BOOL
    k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    return k32


def criar_job_windows():
    """Cria um Job Object que mata os servidores quando esta janela morrer.

    O `finally` do Python nao e garantia suficiente: fechando a janela no X,
    o Windows manda CTRL_CLOSE_EVENT e da poucos segundos antes de encerrar o
    processo - com frequencia o `taskkill` do encerramento nao chega a rodar,
    e o uvicorn e o node ficam segurando 8000 e 5173. Na proxima vez o
    lancador acusaria "porta em uso".

    Com JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, quem garante a limpeza e o
    proprio sistema: some o ultimo handle do job, morre a arvore inteira.
    """
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class LIMITES_BASICOS(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
                ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),  # ULONG_PTR
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class CONTADORES_IO(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class LIMITES_ESTENDIDOS(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", LIMITES_BASICOS),
                ("IoInfo", CONTADORES_IO),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = _kernel32()
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None

        info = LIMITES_ESTENDIDOS()
        info.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        # 9 = JobObjectExtendedLimitInformation
        if not kernel32.SetInformationJobObject(
            job, 9, ctypes.byref(info), ctypes.sizeof(info)
        ):
            return None
        return job
    except Exception:  # noqa: BLE001 - sem job o lancador ainda funciona
        return None


def anexar_este_processo(job) -> bool:
    """Poe o PROPRIO lancador no job, nao os filhos.

    Anexar cada filho depois do Popen e uma corrida perdida: medido aqui, o
    `cmd.exe` do backend ja tinha criado o uvicorn antes da associacao, e o
    uvicorn ficava fora do job segurando a porta 8000. Com o lancador dentro
    do job, todo processo que ele criar ja nasce membro - sem janela de corrida.
    """
    if job is None:
        return False
    try:
        import ctypes

        kernel32 = _kernel32()
        return bool(
            kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess())
        )
    except Exception:  # noqa: BLE001
        return False


def iniciar_servidor(nome: str, comando: list[str], pasta: Path) -> subprocess.Popen:
    LOGS.mkdir(parents=True, exist_ok=True)
    log = open(LOGS / f"{nome}.log", "w", encoding="utf-8", errors="replace")
    print(f"  Iniciando {nome}...")
    return subprocess.Popen(
        comando,
        cwd=pasta,
        stdout=log,
        stderr=subprocess.STDOUT,
        # `shell=True` porque npm e um .cmd no Windows; CREATE_NEW_PROCESS_GROUP
        # deixa o Ctrl+C desta janela nao matar os filhos pela metade.
        shell=True,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )


def encerrar(processos: list[subprocess.Popen]) -> None:
    """Mata a arvore de cada servidor.

    `terminate()` sozinho deixa orfaos: o npm e o uvicorn com reload criam
    processos filhos que sobrevivem ao pai e seguram a porta. `taskkill /T`
    e o que de fato libera 5173 e 8000 para a proxima execucao.
    """
    print("\n  Encerrando os servidores...")
    for processo in processos:
        if processo.poll() is not None:
            continue
        try:
            subprocess.run(
                ["taskkill", "/PID", str(processo.pid), "/T", "/F"],
                capture_output=True,
                check=False,
            )
        except OSError:
            processo.terminate()
    print("  Pronto. Pode fechar esta janela.")


def esperar(rotulo: str, checar, segundos: int) -> bool:
    print(f"  Aguardando {rotulo}", end="", flush=True)
    for _ in range(segundos * 2):
        if checar():
            print("  ok")
            return True
        time.sleep(0.5)
        print(".", end="", flush=True)
    print("  nao respondeu")
    return False


def main() -> int:
    cabecalho()

    if backend_responde() and frontend_responde():
        print("  O sistema ja esta rodando. Abrindo no navegador...")
        webbrowser.open(URL_APP)
        print(f"\n  {URL_APP}\n")
        input("  Pressione Enter para fechar esta janela...")
        return 0

    for porta, quem in ((PORTA_BACKEND, "backend"), (PORTA_FRONTEND, "frontend")):
        if porta_ocupada(porta):
            erro_fatal(
                f"A porta {porta} ja esta em uso",
                f"Algum outro programa ocupa a porta do {quem}.",
                "Feche a janela antiga do Analisador e tente de novo.",
            )

    conferir_prerequisitos()

    # Precisa existir antes dos servidores: e ele que garante a limpeza se
    # esta janela for fechada no X.
    job = criar_job_windows()
    if not anexar_este_processo(job):
        print("  (aviso: sem Job Object; feche pelo Ctrl+C para nao deixar")
        print("   processos presos nas portas 8000/5173)")

    processos = [
        iniciar_servidor(
            "backend",
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(PORTA_BACKEND),
            ],
            BACKEND,
        ),
        iniciar_servidor("frontend", ["npm", "run", "dev"], FRONTEND),
    ]

    try:
        if not esperar("o backend", backend_responde, SEGUNDOS_ESPERA):
            erro_fatal(
                "O backend nao subiu",
                f"Veja o motivo em: {LOGS / 'backend.log'}",
            )
        if not esperar("o frontend", frontend_responde, SEGUNDOS_ESPERA):
            erro_fatal(
                "O frontend nao subiu",
                f"Veja o motivo em: {LOGS / 'frontend.log'}",
            )

        print()
        print("  " + "-" * 58)
        print(f"   Pronto!  {URL_APP}")
        print("  " + "-" * 58)
        print()
        print(f"   Logs em: {LOGS}")
        print("   Feche esta janela (ou Ctrl+C) para desligar tudo.")
        print()
        webbrowser.open(URL_APP)

        while all(p.poll() is None for p in processos):
            time.sleep(1)
        print("\n  Um dos servidores parou sozinho. Confira os logs.")
    except KeyboardInterrupt:
        pass
    finally:
        encerrar(processos)

    return 0


if __name__ == "__main__":
    # Fechar a janela no X nao passa por aqui, mas o taskkill do console leva
    # a arvore junto porque os filhos herdam o Job do console.
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    raise SystemExit(main())
