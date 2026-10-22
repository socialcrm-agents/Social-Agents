"""Configuração do Editor no WhatsApp (variáveis de ambiente; modelo em config.example.env)."""

from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SKILL = Path(os.environ.get("EDITOR_SKILL_DIR", REPO / ".claude" / "skills" / "editor-video"))
SCRIPTS = SKILL / "scripts"

DATA = Path(os.environ.get("EDITOR_DATA_DIR", HERE / "dados"))      # projetos, vídeos, banco
DB = DATA / "fila.sqlite3"

WA_TOKEN = os.environ.get("WA_TOKEN", "")                  # token permanente do app (System User)
WA_PHONE_ID = os.environ.get("WA_PHONE_NUMBER_ID", "")     # id do número que envia
WA_VERIFY = os.environ.get("WA_VERIFY_TOKEN", "")          # texto combinado no cadastro do webhook
WA_API = os.environ.get("WA_API_BASE", "https://graph.facebook.com")
WA_VERSION = os.environ.get("WA_API_VERSION", "v23.0")

PUBLIC_URL = os.environ.get("PUBLIC_URL", "")              # para link quando o vídeo passa de 15 MB
MAX_SEND_MB = 15.0                                         # WhatsApp aceita 16 MB em vídeo enviado
MAX_RECV_MB = 100.0                                        # vídeo recebido do cliente

MODEL = os.environ.get("EDITOR_MODELO", "claude-opus-5-5")
EFFORT = os.environ.get("EDITOR_EFFORT", "medium")
DEFAULT_STYLE = os.environ.get("EDITOR_ESTILO", "reels_viral")
FREE_CREDITS = int(os.environ.get("CREDITOS_GRATIS", "2"))  # vídeos grátis para número novo
FREE_FIXES = int(os.environ.get("CORRECOES_POR_VIDEO", "3"))
KEEP_DAYS = int(os.environ.get("APAGAR_APOS_DIAS", "7"))
