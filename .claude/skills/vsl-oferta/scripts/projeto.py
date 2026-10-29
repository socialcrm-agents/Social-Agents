#!/usr/bin/env python3
"""Projetos de VSL: cria, mostra o andamento e edita a ficha da oferta.

  python3 projeto.py novo "Método Sono Leve"           cria vsl/metodo-sono-leve/ficha.json
  python3 projeto.py listar                            projetos existentes e a etapa de cada um
  python3 projeto.py status metodo-sono-leve           checklist das 11 etapas, campos vazios, hipóteses, próximo passo
  python3 projeto.py etapa metodo-sono-leve roteiro    marca a etapa atual
  python3 projeto.py set metodo-sono-leve produto.preco=197 'publico.dores=["noites sem dormir"]'

Opção em todos: --dir PASTA (padrão ./vsl).
"""

from __future__ import annotations

import argparse
import json
import sys

from common import (ETAPA_NOME, ETAPAS, OBRIGATORIOS, VslError, carregar, definir, die, hipoteses, log, nova, obter,
                    raiz, salvar, vazio)


def cmd_novo(a) -> None:
    f = nova(a.nome)
    p = raiz(a.dir) / f["slug"]
    if (p / "ficha.json").exists():
        die(f"Já existe um projeto '{f['slug']}' em {p}. Use: projeto.py status {f['slug']}")
    salvar(f, p)
    log(f"OK: projeto criado em {p / 'ficha.json'}")
    log(f"Próximo passo: {ETAPA_NOME['diagnostico']}")


def cmd_listar(a) -> None:
    r = raiz(a.dir)
    fichas = sorted(r.glob("*/ficha.json")) if r.exists() else []
    if not fichas:
        log(f"Nenhum projeto em {r}. Crie com: projeto.py novo \"Nome do produto\"")
        return
    for fp in fichas:
        try:
            d = json.loads(fp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log(f"  {fp.parent.name:30} (ficha.json com erro de formato)")
            continue
        log(f"  {fp.parent.name:30} {d.get('produto', {}).get('nome', ''):30} etapa: {d.get('etapa', '?')}")


def pendentes(ficha: dict, etapa: str) -> list[str]:
    return [c for c in OBRIGATORIOS.get(etapa, []) if vazio(obter(ficha, c))]


def cmd_status(a) -> None:
    ficha, p = carregar(a.slug, a.dir)
    atual = ficha.get("etapa") if ficha.get("etapa") in ETAPAS else "diagnostico"
    i_atual = ETAPAS.index(atual)
    log(f"{ficha['produto'].get('nome') or a.slug}  ({p})\n")
    for i, e in enumerate(ETAPAS):
        falta = pendentes(ficha, e)
        marca = "✓" if i < i_atual and not falta else ("→" if i == i_atual else ("!" if i < i_atual else " "))
        extra = f"   falta: {', '.join(falta)}" if falta and i <= i_atual else ""
        log(f"  {marca} {i + 1:2}. {ETAPA_NOME[e]}{extra}")
    arquivos = [n for n in ("roteiro.md", "pagina.html", "teleprompter.html", "calendario.md", "criativos.md",
                            "copies.md") if (p / n).exists()]
    log(f"\nArquivos: {', '.join(arquivos) or 'nenhum ainda'}")
    hip = hipoteses(ficha)
    if hip:
        log(f"\nHipóteses ainda não confirmadas pelo cliente ({len(hip)}):")
        for h in hip:
            log(f"  - {h}")
    falta = pendentes(ficha, atual)
    log(f"\nPróximo passo: {ETAPA_NOME[atual]}"
        + (f" — preencher {', '.join(falta)}" if falta else
           (f" — pronto; avance para '{ETAPAS[i_atual + 1]}'" if i_atual + 1 < len(ETAPAS) else " — ciclo completo")))


def cmd_etapa(a) -> None:
    if a.etapa not in ETAPAS:
        die(f"Etapa '{a.etapa}' não existe. Use uma destas: {', '.join(ETAPAS)}")
    ficha, p = carregar(a.slug, a.dir)
    ficha["etapa"] = a.etapa
    salvar(ficha, p)
    log(f"OK: etapa = {a.etapa} ({ETAPA_NOME[a.etapa]})")


def cmd_set(a) -> None:
    ficha, p = carregar(a.slug, a.dir)
    for par in a.pares:
        if "=" not in par:
            die(f"Use campo=valor (recebi '{par}')")
        campo, valor = par.split("=", 1)
        try:
            valor = json.loads(valor)
        except json.JSONDecodeError:
            pass
        try:
            definir(ficha, campo.strip(), valor)
        except (ValueError, IndexError, TypeError):
            die(f"Não consegui gravar '{campo}' (índice de lista inválido?)")
        log(f"  {campo} = {json.dumps(valor, ensure_ascii=False)[:120]}")
    salvar(ficha, p)
    log("OK: ficha salva")


def main() -> None:
    ap = argparse.ArgumentParser(description="Projetos de VSL (ficha da oferta)")
    ap.add_argument("--dir", help="pasta dos projetos (padrão ./vsl)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("novo"); s.add_argument("nome"); s.set_defaults(fn=cmd_novo)
    s = sub.add_parser("listar"); s.set_defaults(fn=cmd_listar)
    s = sub.add_parser("status"); s.add_argument("slug"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("etapa"); s.add_argument("slug"); s.add_argument("etapa"); s.set_defaults(fn=cmd_etapa)
    s = sub.add_parser("set"); s.add_argument("slug"); s.add_argument("pares", nargs="+"); s.set_defaults(fn=cmd_set)
    a = ap.parse_args()
    try:
        a.fn(a)
    except VslError as e:
        die(str(e))


if __name__ == "__main__":
    main()
