"""Fila de jobs e créditos em SQLite (um arquivo, sem servidor de banco).

jobs: um vídeo novo ou uma correção. clientes: créditos por telefone. uso: tokens da Claude API por job.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS clientes (
  telefone TEXT PRIMARY KEY, creditos INTEGER NOT NULL, estilo TEXT, criado REAL NOT NULL);
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, telefone TEXT NOT NULL, tipo TEXT NOT NULL,      -- novo | correcao
  status TEXT NOT NULL DEFAULT 'fila',                                                -- fila|rodando|ok|erro
  projeto TEXT, entrada TEXT, pedido TEXT, tentativas INTEGER NOT NULL DEFAULT 0, erro TEXT,
  saida TEXT, segundos REAL, criado REAL NOT NULL, atualizado REAL);
CREATE TABLE IF NOT EXISTS uso (
  job INTEGER, modelo TEXT, entrada INTEGER, saida INTEGER, cache_lido INTEGER, cache_criado INTEGER,
  custo_usd REAL, criado REAL);
CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status, id);
"""

# US$ por milhão de tokens (entrada, saída, leitura de cache) — conferir a página de preços da Anthropic
PRECOS = {"claude-opus-5-5": (4.0, 20.0, 0.20), "claude-sonnet-5-5": (2.0, 10.0, 0.20),
          "claude-haiku-5-5": (0.10, 0.50, 0.01)}


@contextmanager
def db():
    config.DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB, timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def cliente(tel: str) -> sqlite3.Row:
    with db() as c:
        row = c.execute("SELECT * FROM clientes WHERE telefone=?", (tel,)).fetchone()
        if not row:
            c.execute("INSERT INTO clientes VALUES (?,?,?,?)", (tel, config.FREE_CREDITS, config.DEFAULT_STYLE, time.time()))
            row = c.execute("SELECT * FROM clientes WHERE telefone=?", (tel,)).fetchone()
        return row


def set_estilo(tel: str, estilo: str) -> None:
    cliente(tel)
    with db() as c:
        c.execute("UPDATE clientes SET estilo=? WHERE telefone=?", (estilo, tel))


def add_creditos(tel: str, n: int) -> None:
    cliente(tel)
    with db() as c:
        c.execute("UPDATE clientes SET creditos=creditos+? WHERE telefone=?", (n, tel))


def novo_job(tel: str, tipo: str, entrada: str | None = None, pedido: str | None = None,
             projeto: str | None = None) -> int | None:
    """Vídeo novo gasta 1 crédito (None = sem crédito). Correção é grátis até FREE_FIXES por vídeo."""
    with db() as c:
        if tipo == "novo":
            cur = c.execute("UPDATE clientes SET creditos=creditos-1 WHERE telefone=? AND creditos>0", (tel,))
            if cur.rowcount == 0:
                return None
        else:
            n = c.execute("SELECT COUNT(*) FROM jobs WHERE projeto=? AND tipo='correcao'", (projeto,)).fetchone()[0]
            if n >= config.FREE_FIXES:
                return None
        cur = c.execute("INSERT INTO jobs (telefone,tipo,entrada,pedido,projeto,criado) VALUES (?,?,?,?,?,?)",
                        (tel, tipo, entrada, pedido, projeto, time.time()))
        return cur.lastrowid


def pegar_proximo() -> sqlite3.Row | None:
    with db() as c:
        row = c.execute("SELECT * FROM jobs WHERE status='fila' ORDER BY id LIMIT 1").fetchone()
        if row:
            c.execute("UPDATE jobs SET status='rodando', tentativas=tentativas+1, atualizado=? WHERE id=?",
                      (time.time(), row["id"]))
        return row


def concluir(job: int, **campos) -> None:
    campos["atualizado"] = time.time()
    keys = ", ".join(f"{k}=?" for k in campos)
    with db() as c:
        c.execute(f"UPDATE jobs SET {keys} WHERE id=?", (*campos.values(), job))


def falhou(job: sqlite3.Row, erro: str) -> bool:
    """Volta para a fila uma vez; na segunda falha devolve o crédito. True = vai tentar de novo."""
    retry = job["tentativas"] < 2
    concluir(job["id"], status="fila" if retry else "erro", erro=erro[-2000:])
    if not retry and job["tipo"] == "novo":
        add_creditos(job["telefone"], 1)
    return retry


def ultimo_projeto(tel: str, horas: float = 48) -> str | None:
    with db() as c:
        row = c.execute("SELECT projeto FROM jobs WHERE telefone=? AND status='ok' AND tipo='novo' AND criado>? "
                        "ORDER BY id DESC LIMIT 1", (tel, time.time() - horas * 3600)).fetchone()
        return row["projeto"] if row else None


def registrar_uso(job: int, modelo: str, usage) -> float:
    pin, pout, pcache = PRECOS.get(modelo, PRECOS["claude-opus-5-5"])
    ent = getattr(usage, "input_tokens", 0) or 0
    sai = getattr(usage, "output_tokens", 0) or 0
    lido = getattr(usage, "cache_read_input_tokens", 0) or 0
    criado = getattr(usage, "cache_creation_input_tokens", 0) or 0
    custo = (ent * pin + sai * pout + lido * pcache + criado * pin * 1.25) / 1e6
    with db() as c:
        c.execute("INSERT INTO uso VALUES (?,?,?,?,?,?,?,?)", (job, modelo, ent, sai, lido, criado, custo, time.time()))
    return custo


def job(job_id: int | None = None) -> sqlite3.Row | None:
    """Um job pelo id (ou o mais recente)."""
    with db() as c:
        if job_id is None:
            return c.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT 1").fetchone()
        return c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()


def relatorio() -> dict:
    with db() as c:
        r = c.execute("SELECT COUNT(DISTINCT job), SUM(custo_usd), SUM(entrada+cache_lido+cache_criado), SUM(saida) "
                      "FROM uso").fetchone()
        t = c.execute("SELECT AVG(segundos), COUNT(*) FROM jobs WHERE status='ok'").fetchone()
    return {"jobs_com_ia": r[0], "custo_ia_usd": round(r[1] or 0, 4), "tokens_entrada": r[2] or 0,
            "tokens_saida": r[3] or 0, "jobs_ok": t[1], "segundos_medios": round(t[0] or 0, 1)}
