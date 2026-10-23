#!/usr/bin/env python3
"""Calendário de lançamento da VSL: plano dia a dia em Markdown (com caixinhas) e em .ics para a agenda.

  python3 calendario.py metodo-sono-leve                          começa em lancamento.inicio (ou amanhã)
  python3 calendario.py metodo-sono-leve --inicio 2026-11-03 --sem-fds
  python3 calendario.py metodo-sono-leve --dias 21                 estica a fase de leitura de métricas

O .ics abre no Google Agenda (Configurações > Importar), Apple Calendário e Outlook. Cada dia vira um evento às
09:00 com a duração de lancamento.horas_por_dia e a lista de tarefas na descrição.
Etapas que a ficha já passou (campo "etapa") saem marcadas como feitas.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import uuid

from common import ETAPAS, VslError, carregar, die, log, parcelado

# (dia, etapa, título, tarefas). Edite aqui para mudar o plano padrão. O último bloco (métricas) se repete até --dias.
PLANO: list[tuple[int, str, str, list[str]]] = [
    (1, "oferta", "Oferta fechada", [
        "Responder o diagnóstico (produto, ticket, público, provas)",
        "Validar dores, desejos e objeções do público",
        "Fechar promessa, mecanismo do problema e da solução (com nome)",
        "Fechar stack, bônus, garantia e preço com ancoragem",
    ]),
    (2, "angulos", "Ângulos e começo do roteiro", [
        "Escolher a big idea entre os ângulos propostos",
        "Aprovar 3 opções de gancho para os primeiros 30 segundos",
        "Escrever os blocos de abertura até o mecanismo do problema",
    ]),
    (3, "roteiro", "Roteiro completo", [
        "Escrever os blocos de solução, prova, oferta, garantia e CTA",
        "Ler o roteiro em voz alta e cortar o que travar",
        "Conferir o tempo com o teleprompter (meta da ficha)",
        "Definir o segundo em que a oferta aparece na página",
    ]),
    (4, "pagina", "Página de vendas", [
        "Gerar a página em rascunho e revisar os trechos amarelos",
        "Colocar o link do checkout e testar o botão no celular",
        "Configurar checkout: parcelamento, order bump, página de obrigado",
        "Instalar pixel/eventos de conversão (Meta, TikTok ou Google)",
    ]),
    (5, "gravacao", "Gravação", [
        "Montar luz, câmera na altura dos olhos e microfone de lapela",
        "Gravar bloco a bloco no teleprompter (2 tomadas boas de cada)",
        "Gravar 10 ganchos extras para criativos",
        "Subir os arquivos no Google Drive (link: qualquer pessoa com o link)",
    ]),
    (6, "edicao", "Edição e hospedagem", [
        "Editar a VSL (cortes, legenda, zoom; sem música alta)",
        "Hospedar o vídeo no player (Panda, VTurb, Vimeo ou YouTube não listado)",
        "Colar o código do player na ficha e gerar a página final",
        "Assistir a página inteira no celular, do play ao checkout",
    ]),
    (7, "criativos", "Criativos — lote 1", [
        "Escrever 5 roteiros de criativo (um por ângulo)",
        "Gravar ou montar os 5 criativos em 9:16",
        "Escrever textos e títulos dos anúncios",
    ]),
    (8, "criativos", "Criativos — lote 2", [
        "Mais 5 criativos com ganchos diferentes",
        "Separar 2 trechos fortes da própria VSL como criativo",
        "Revisar política de anúncios (promessas, antes/depois, saúde)",
    ]),
    (9, "lancamento", "Campanhas no ar", [
        "Criar a campanha de conversão com os 10 criativos",
        "Verba de teste por dia conforme a ficha",
        "Conferir se o evento de compra chega no gerenciador",
        "Enviar a página para a lista/WhatsApp (se houver)",
    ]),
    (10, "otimizacao", "Leitura de métricas", [
        "Anotar: CPM, CTR, custo por clique, play rate da VSL",
        "Retenção da VSL: % que chega ao pitch (segundo da oferta)",
        "Conversão da página e do checkout",
        "Desligar criativos com CTR abaixo de 0,8% após 1.000 impressões",
    ]),
]

STATUS_ETAPA = {"roteiro": "roteiro", "gravando": "gravacao", "editando": "edicao", "publicado": "criativos"}


def dias_uteis(inicio: dt.date, n: int, sem_fds: bool) -> list[dt.date]:
    out, d = [], inicio
    while len(out) < n:
        if not (sem_fds and d.weekday() >= 5):
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def montar_plano(dias: int) -> list[tuple[str, str, list[str]]]:
    base = [(e, t, tar) for _, e, t, tar in sorted(PLANO, key=lambda x: x[0])]
    ultimo = base[-1]
    while len(base) < dias:
        n = len(base) + 1
        base.append((ultimo[0], f"Leitura de métricas — dia {n}", [
            "Atualizar a planilha de métricas do dia",
            "Trocar o que está pior: gancho (CTR baixo), VSL (retenção), página ou checkout (conversão)",
            "Subir 2 criativos novos se o melhor estiver cansando (frequência > 2,5)",
        ] + (["Revisão da semana: escalar 20% a verba dos conjuntos com venda abaixo do custo-alvo"]
             if n % 7 == 0 else [])))
    return base[:dias]


def escapar_ics(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def dobrar(linha: str) -> str:
    """Linhas do .ics têm no máximo 75 octetos; o resto continua na linha seguinte começando com espaço."""
    b = linha.encode("utf-8")
    if len(b) <= 75:
        return linha
    partes, atual = [], b""
    for ch in linha:
        c = ch.encode("utf-8")
        if len(atual) + len(c) > (75 if not partes else 74):
            partes.append(atual.decode("utf-8"))
            atual = b""
        atual += c
    partes.append(atual.decode("utf-8"))
    return "\r\n ".join(partes)


def main() -> None:
    ap = argparse.ArgumentParser(description="Calendário de lançamento da VSL (.md + .ics)")
    ap.add_argument("slug")
    ap.add_argument("--dir", help="pasta dos projetos (padrão ./vsl)")
    ap.add_argument("--inicio", help="AAAA-MM-DD (padrão: lancamento.inicio da ficha ou amanhã)")
    ap.add_argument("--dias", type=int, default=14)
    ap.add_argument("--sem-fds", action="store_true", help="pula sábado e domingo")
    a = ap.parse_args()
    try:
        ficha, pasta = carregar(a.slug, a.dir)
        txt = a.inicio or ficha["lancamento"].get("inicio")
        try:
            inicio = dt.date.fromisoformat(txt) if txt else dt.date.today() + dt.timedelta(days=1)
        except ValueError:
            raise VslError(f"Data inválida '{txt}'. Use AAAA-MM-DD, por exemplo 2026-11-03.")
    except VslError as e:
        die(str(e))
    if a.dias < 1:
        die("--dias precisa ser 1 ou mais")

    etapa = ficha.get("etapa") if ficha.get("etapa") in ETAPAS else "diagnostico"
    status = STATUS_ETAPA.get(ficha["vsl"].get("status") or "", "diagnostico")
    feito_ate = max(ETAPAS.index(etapa), ETAPAS.index(status))
    horas = max(0.5, float(ficha["lancamento"].get("horas_por_dia") or 2))
    plano = montar_plano(a.dias)
    datas = dias_uteis(inicio, len(plano), a.sem_fds)
    nome = ficha["produto"].get("nome") or a.slug
    sem = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]

    md = [f"# Calendário de lançamento — {nome}", "",
          f"Início {datas[0].strftime('%d/%m/%Y')} · {len(plano)} dias · ~{horas:g} h por dia · oferta "
          f"{parcelado(ficha['produto'])}", ""]
    ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//vsl-oferta//calendario//PT", "CALSCALE:GREGORIAN",
           "METHOD:PUBLISH", f"X-WR-CALNAME:{escapar_ics('Lançamento ' + nome)}"]
    agora = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for i, ((et, titulo, tarefas), data) in enumerate(zip(plano, datas), 1):
        feito = ETAPAS.index(et) < feito_ate
        md.append(f"## Dia {i} — {sem[data.weekday()]} {data.strftime('%d/%m')} · {titulo}"
                  + (" ✓" if feito else ""))
        md += [f"- [{'x' if feito else ' '}] {t}" for t in tarefas]
        md.append("")
        ini = dt.datetime.combine(data, dt.time(9, 0))
        fim = ini + dt.timedelta(hours=horas)
        desc = "\n".join(f"{'☑' if feito else '☐'} {t}" for t in tarefas)
        ics += ["BEGIN:VEVENT", f"UID:{uuid.uuid5(uuid.NAMESPACE_URL, f'vsl/{a.slug}/{i}')}@vsl-oferta",
                f"DTSTAMP:{agora}", f"DTSTART:{ini.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND:{fim.strftime('%Y%m%dT%H%M%S')}",
                f"SUMMARY:{escapar_ics(f'VSL dia {i}: {titulo}')}", f"DESCRIPTION:{escapar_ics(desc)}",
                "TRANSP:OPAQUE", "END:VEVENT"]
    ics.append("END:VCALENDAR")
    (pasta / "calendario.md").write_text("\n".join(md), encoding="utf-8")
    (pasta / "calendario.ics").write_text("\r\n".join(dobrar(l) for l in ics) + "\r\n", encoding="utf-8")
    log(f"OK: {pasta / 'calendario.md'} e calendario.ics ({len(plano)} dias, "
        f"{datas[0].strftime('%d/%m')} a {datas[-1].strftime('%d/%m')})")


if __name__ == "__main__":
    sys.exit(main())
