"""Dados do template produto3d: caixa do rosto e faixa da legenda na janela (o produto/ícone 3D se posiciona sem
cobrir nenhum dos dois).

Chamado por motion.render_clip via enriquecer(...). Reaproveita a detecção de rosto do hud (MediaPipe, local, com
cache em work/motion/visao_<hash>.json). Sem MediaPipe/modelo, o template usa a posição padrão.
params["rosto"] = [x0, y0, x1, y1] (0..1 do quadro final): caixa típica do rosto no trecho, ampliada até o topo da
cabeça e as orelhas; params["rostos"] = a mesma caixa quadro a quadro (o objeto desvia quando a pessoa se mexe,
mesmo com x/y pedidos). params["legenda"] = [y0, y1] (0..1): faixa vertical que a legenda ocupa no trecho.
"""

from __future__ import annotations

from common import log


def amplia(c: list) -> list:
    """Caixa do detector (testa ao queixo) -> cabeça inteira: ~30% acima e as orelhas ~8% para os lados."""
    w, h = c[2] - c[0], c[3] - c[1]
    return [round(max(0.0, c[0] - 0.08 * w), 3), round(max(0.0, c[1] - 0.3 * h), 3),
            round(min(1.0, c[2] + 0.08 * w), 3), round(min(1.0, c[3] + 0.06 * h), 3)]


def caixa_rosto(quadros: list) -> list | None:
    """Caixa típica do rosto no trecho (percentis 25/75 de cada borda: o rosto se mexe, mas o envelope de todos os
    quadros ocuparia a tela inteira num close), ampliada para a cabeça inteira."""
    caixas = [q[:4] for q in quadros if q]
    if len(caixas) < 3:
        return None
    def pct(vals, q):
        vals = sorted(vals)
        return vals[min(len(vals) - 1, max(0, round(q * (len(vals) - 1))))]
    x0, y0 = pct([c[0] for c in caixas], 0.25), pct([c[1] for c in caixas], 0.25)
    x1, y1 = pct([c[2] for c in caixas], 0.75), pct([c[3] for c in caixas], 0.75)
    return amplia([x0, y0, x1, y1])


def faixa_legenda(tl: dict, t0: float, t1: float, h: int) -> list | None:
    """Faixa vertical (0..1) ocupada pela legenda entre t0 e t1 (base da legenda + até duas linhas acima)."""
    cfg = (tl.get("captions") or {}).get("cfg")
    if not cfg or not (tl.get("captions") or {}).get("pages"):
        return None
    from assets import caption_y
    bases = [caption_y(tl, t0 + (t1 - t0) * k / 4) for k in range(5)]
    alto = 1.25 * (cfg.get("size", 70) + cfg.get("emph_size", cfg.get("size", 70)))
    return [round(max(0.0, (min(bases) - alto) / h), 3), round(min(1.0, (max(bases) + 16) / h), 3)]


def enriquecer(tpl, params, item, *, work, tl, aroll, mask, t0, t1, w, h, fps, project) -> None:
    if tpl != "produto3d":
        return
    if "legenda" not in params:
        try:
            faixa = faixa_legenda(tl, t0, t1, h)
        except Exception:  # timeline antiga/sem legenda: segue sem a faixa
            faixa = None
        if faixa:
            params["legenda"] = faixa
    if "rosto" in params:
        return
    try:
        import motion_dados_visao as mv
        quadros = mv._cached(work, mv._key(aroll, "rosto", t0, t1, fps), lambda: mv.rosto(aroll, t0, t1, fps, w, h))
    except Exception as exc:  # sem mediapipe/modelo: posição padrão
        log(f"   produto3d: sem detecção de rosto ({exc}); posição padrão")
        return
    caixa = caixa_rosto(quadros)
    if caixa:
        params["rosto"] = caixa
        # e quadro a quadro: o objeto desvia do rosto quando a pessoa se mexe
        params["rostos"] = [amplia(q[:4]) if q else None for q in quadros]
