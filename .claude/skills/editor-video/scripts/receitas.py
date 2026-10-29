"""Receitas: um jeito de editar salvo com nome, aplicado igual em todo vídeo.

Uma receita é a lista de opções do edit.py que deram certo num vídeo aprovado. "premium" é a do teste aprovado pelo
usuário (2026-10-25): revelação 2.5D no gancho, impacto na frase forte, direção premium, trilha sem direitos,
correção de imagem, estabilização, voz limpa de estúdio (2026-10-26) e legenda 84 px.

O padrão do usuário fica FORA da pasta da skill (~/.editor-viral/padrao.json): reinstalar não apaga.
  python run.py padrao premium     todo projeto novo já nasce com a receita premium
  python run.py padrao aprendida   todo projeto novo usa o que o editor aprendeu com as suas vendas (aprender.py)
  python run.py padrao off         volta ao normal
  python run.py padrao             mostra o padrão atual
  python edit.py <proj> --receita premium [--no-render]   aplica uma receita num projeto que já existe
"""

from __future__ import annotations

import json
import os
from pathlib import Path

RECEITAS: dict[str, list[str]] = {
    "premium": ["--direcao", "premium", "--music", "auto:energia", "--correcao", "auto", "--estabilizar", "auto",
                "--voz", "estudio",
                "--caption-size", "84", "--composicao", "revelacao@auto", "--composicao", "impacto@auto"],
    # sem trilha nem correção: para quem já tratou cor/áudio fora e só quer os efeitos
    "efeitos": ["--direcao", "premium", "--caption-size", "84", "--composicao", "revelacao@auto",
                "--composicao", "impacto@auto"],
}
PASTA = Path(os.environ.get("EDITOR_VIRAL_DIR") or Path.home() / ".editor-viral")   # testes usam outra pasta
ARQUIVO = PASTA / "padrao.json"
APRENDIDA = PASTA / "aprendizado.json"   # gravada por aprender.py analisar --aplicar
# opções que aparecem uma vez só (a última vence); --composicao/--motion/--fx podem repetir
REPETEM = {"--composicao", "--motion", "--fx", "--patch", "--cut", "--emph"}


def _receitas() -> dict[str, list[str]]:
    todas = dict(RECEITAS)
    try:
        ap = json.loads(APRENDIDA.read_text(encoding="utf-8"))
        if ap.get("receita"):
            todas["aprendida"] = list(ap["receita"])
    except (OSError, ValueError):
        pass
    return todas


def sobrepor(base: list[str], extra: list[str]) -> list[str]:
    """base com as opções de `extra` por cima: a mesma opção (não repetível) é trocada, não duplicada."""
    pares, i = [], 0
    while i < len(base):
        tem_valor = i + 1 < len(base) and not base[i + 1].startswith("--")
        pares.append(base[i:i + 2] if tem_valor else base[i:i + 1])
        i += 2 if tem_valor else 1
    i = 0
    while i < len(extra):
        tem_valor = i + 1 < len(extra) and not extra[i + 1].startswith("--")
        par = extra[i:i + 2] if tem_valor else extra[i:i + 1]
        if par[0] not in REPETEM:
            pares = [p for p in pares if p[0] != par[0]]
        pares.append(par)
        i += 2 if tem_valor else 1
    return [x for p in pares for x in p]


def padrao() -> str | None:
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8")).get("receita")
    except (OSError, ValueError):
        return None


def definir_padrao(nome: str | None) -> None:
    if nome and nome not in _receitas():
        raise ValueError(f"receita '{nome}' não existe ({', '.join(_receitas())})")
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps({"receita": nome}, ensure_ascii=False), encoding="utf-8")


def expandir(argv: list[str]) -> list[str]:
    """Troca '--receita NOME' pelas opções da receita (as opções escritas depois continuam valendo por cima)."""
    out, i = [], 0
    todas = _receitas()
    while i < len(argv):
        if argv[i] == "--receita" and i + 1 < len(argv):
            nome = argv[i + 1]
            if nome not in todas:
                raise ValueError(f"receita '{nome}' não existe ({', '.join(todas)})")
            out += todas[nome]
            i += 2
            continue
        out.append(argv[i])
        i += 1
    return out
