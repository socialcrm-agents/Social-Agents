#!/usr/bin/env python3
"""Valida um JSON do Creative Studio contra o schema (Windows, Mac e Linux; só biblioteca padrão).

  python creative/validar.py <arquivo.json> <brief|decision-plan|shot-plan|revision-plan|qa-report>
  python creative/validar.py -                   decision-plan     (lê o JSON da entrada padrão)

Usa o pacote `jsonschema` quando estiver instalado; senão, um validador próprio que cobre o que os schemas usam
(type, required, properties, additionalProperties, items, minItems, enum, minimum, minLength).
Saída: "OK" (código 0) ou a lista de erros com o caminho do campo (código 1).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
TIPOS = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None),
         "integer": int, "number": (int, float)}


def _tipo_ok(valor, tipo) -> bool:
    tipos = tipo if isinstance(tipo, list) else [tipo]
    for t in tipos:
        if t in ("integer", "number") and isinstance(valor, bool):
            continue
        if isinstance(valor, TIPOS[t]):
            return True
    return False


def validar_simples(valor, sc: dict, caminho: str = "$") -> list[str]:
    erros: list[str] = []
    if "type" in sc and not _tipo_ok(valor, sc["type"]):
        return [f"{caminho}: esperado {sc['type']}, veio {type(valor).__name__}"]
    if "enum" in sc and valor not in sc["enum"]:
        erros.append(f"{caminho}: '{valor}' não está em {sc['enum']}")
    if isinstance(valor, (int, float)) and not isinstance(valor, bool) and "minimum" in sc and valor < sc["minimum"]:
        erros.append(f"{caminho}: {valor} < mínimo {sc['minimum']}")
    if isinstance(valor, str) and len(valor) < sc.get("minLength", 0):
        erros.append(f"{caminho}: texto vazio")
    if isinstance(valor, dict):
        for r in sc.get("required", []):
            if r not in valor:
                erros.append(f"{caminho}: falta o campo obrigatório '{r}'")
        props = sc.get("properties", {})
        for k, v in valor.items():
            if k in props:
                erros += validar_simples(v, props[k], f"{caminho}.{k}")
            elif sc.get("additionalProperties") is False:
                erros.append(f"{caminho}: campo não previsto '{k}'")
    if isinstance(valor, list):
        if len(valor) < sc.get("minItems", 0):
            erros.append(f"{caminho}: precisa de pelo menos {sc['minItems']} item(ns)")
        if "items" in sc:
            for i, v in enumerate(valor):
                erros += validar_simples(v, sc["items"], f"{caminho}[{i}]")
    return erros


def validar(dado, nome: str) -> list[str]:
    sc = json.loads((AQUI / f"{nome}.schema.json").read_text(encoding="utf-8"))
    try:
        import jsonschema
        v = jsonschema.Draft202012Validator(sc)
        return [f"$.{'.'.join(map(str, e.absolute_path))}: {e.message}" for e in v.iter_errors(dado)]
    except ImportError:
        return validar_simples(dado, sc)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    texto = sys.stdin.read() if sys.argv[1] == "-" else Path(sys.argv[1]).read_text(encoding="utf-8")
    try:
        dado = json.loads(texto)
    except json.JSONDecodeError as exc:
        print(f"JSON inválido: {exc}")
        return 1
    erros = validar(dado, sys.argv[2])
    print("OK" if not erros else "\n".join(erros))
    return 0 if not erros else 1


if __name__ == "__main__":
    sys.exit(main())
