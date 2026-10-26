"""Receitas: um jeito de editar salvo com nome, aplicado igual em todo vídeo.

Uma receita é a lista de opções do edit.py que deram certo num vídeo aprovado. "premium" é a do teste aprovado pelo
usuário (2026-10-25): revelação 2.5D no gancho, impacto na frase forte, direção premium, trilha sem direitos,
correção de imagem, estabilização e legenda 84 px.

O padrão do usuário fica FORA da pasta da skill (~/.editor-viral/padrao.json): reinstalar não apaga.
  python run.py padrao premium     todo projeto novo já nasce com a receita premium
  python run.py padrao off         volta ao normal
  python run.py padrao             mostra o padrão atual
  python edit.py <proj> --receita premium [--no-render]   aplica uma receita num projeto que já existe
"""

from __future__ import annotations

import json
from pathlib import Path

RECEITAS: dict[str, list[str]] = {
    "premium": ["--direcao", "premium", "--music", "auto:energia", "--correcao", "auto", "--estabilizar", "auto",
                "--caption-size", "84", "--composicao", "revelacao@auto", "--composicao", "impacto@auto"],
    # sem trilha nem correção: para quem já tratou cor/áudio fora e só quer os efeitos
    "efeitos": ["--direcao", "premium", "--caption-size", "84", "--composicao", "revelacao@auto",
                "--composicao", "impacto@auto"],
}
ARQUIVO = Path.home() / ".editor-viral" / "padrao.json"


def padrao() -> str | None:
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8")).get("receita")
    except (OSError, ValueError):
        return None


def definir_padrao(nome: str | None) -> None:
    if nome and nome not in RECEITAS:
        raise ValueError(f"receita '{nome}' não existe ({', '.join(RECEITAS)})")
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps({"receita": nome}, ensure_ascii=False), encoding="utf-8")


def expandir(argv: list[str]) -> list[str]:
    """Troca '--receita NOME' pelas opções da receita (as opções escritas depois continuam valendo por cima)."""
    out, i = [], 0
    while i < len(argv):
        if argv[i] == "--receita" and i + 1 < len(argv):
            nome = argv[i + 1]
            if nome not in RECEITAS:
                raise ValueError(f"receita '{nome}' não existe ({', '.join(RECEITAS)})")
            out += RECEITAS[nome]
            i += 2
            continue
        out.append(argv[i])
        i += 1
    return out
