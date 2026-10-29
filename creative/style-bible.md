# Style Bible — Creative Studio (Editor Viral IA™)

A linguagem visual e sonora que todos os especialistas seguem. Detalhe operacional (gatilhos, densidade, receitas)
está em `.claude/skills/editor-video/references/direcao.md`; parâmetros dos blocos em `references/motion.md`.
Decisões que não se discutem: `creative/approved-decisions.json`.

## 1. Princípios

1. **Um herói por momento.** Cada frase tem UM elemento principal na tela; legenda e ícone são coadjuvantes.
2. **O efeito conversa com a pessoa.** Atrás da cabeça, preso à mão, seguindo o rosto, ou a pessoa entrando no
   layout (moldura, dividida, quadrinho). Card solto no meio da tela é o último recurso.
3. **Motivo na fala.** Nada entra porque é bonito; entra porque ilustra, prova, organiza ou chama a ação do que está
   sendo dito naquele instante.
4. **Rosto sagrado.** Nunca cobrir olhos/boca (D01). Topo ocupado → a cena recua sozinha.
5. **Verdade.** Números, nomes e provas só os ditos/fornecidos (D05).

## 2. Paleta e tipo (padrão `pro_clean`; a marca do cliente substitui)

| Papel | Valor |
|---|---|
| Destaque 1 | `#B794FF` (lilás) |
| Destaque 2 | `#7C5CFF` (roxo) |
| Texto em fundo escuro | `#FFFFFF` com sombra suave |
| Cards claros | `#FFFFFF` / `#F4EFE6`, texto `#1B1233` |
| Positivo / negativo | `#22C55E` / `#F43F5E` |
| Fonte | Poppins (800–900 títulos, 600 apoio); Anton só em letreiro |

No máximo 2 cores de destaque por vídeo. Cards com o mesmo raio, sombra e borda do design system (`lib/base.css`,
classes `ds-*`).

## 3. Hierarquia de texto

- Palavra-chave grande + até 4 palavras de apoio. Frase inteira só na legenda.
- Números grandes e com unidade (R$, %, dias), contando até o valor quando ditos.
- Texto de tela ≥ 44 px; leitura ≈ 3 palavras/s; tempo mínimo 1,2 s.

## 4. Movimento

- Entradas com mola (spring), cascata por palavra/letra e desfoque de movimento; saídas limpas (blur + escala).
- Durante a permanência: micro-movimento (flutuar, brilho passando), nunca parado "morto".
- Câmera viva: empurrão de zoom nas entradas, tremida no impacto (`--fx tremida@palavra`).
- Ritmo (anúncio): algo muda a cada 2–3 s; tela cheia no máx. 1 a cada 6–8 s; nunca dois blocos iguais seguidos.

## 5. Som

- Voz em primeiro plano (−14 LUFS). Cada animação com som próprio (D08): whoosh na entrada, clique ao digitar e
  clicar, ding em item marcado, boom em palavra gigante/carimbo, glitch em risco/X, riser antes do botão.
- Trilha só do usuário ou licenciada, com ducking sob a voz (`--music arquivo:0.12`).

## 6. Estrutura por tipo (resumo)

| Tipo | Abertura (0–1,5 s) | Meio | Fechamento |
|---|---|---|---|
| VS / comparação | `manchete` "A **vs** B" | `infografico` → `proibido` → `tabela`/`dividida` | `botao_cta` + `final` |
| Pergunta na tela | `pergunta` digitando | `empilha`/`checklist` → prova | `comentario` + `final` |
| Identificação | `pergunta`/`manchete` com o público | `dividida pendencias` → `luz` + `palavra` | CTA |
| Conversa entre dois | `etiqueta` de quem fala | `pergunta` → `infografico`/`checklist`; `clones` se a mesma pessoa | `palavra` + CTA |
| Produto | `etiqueta` | `objeto3d`/`card_fogo` na mão → `checklist` → preço | `botao_cta` |
| VSL | `manchete` + `palavra` | `camadas`/`documentario` → `moldura` → provas | oferta + `botao_cta` |

## 7. Não fazer

- Dois textos grandes ao mesmo tempo; CTA duplicado (D07); logos de terceiros (D06).
- Antes/depois de corpo, promessa de ganho/cura na tela.
- Efeito que precisa de mão/rosto onde eles não aparecem (bloco vazio).
- Zoom forte em vídeo de baixa resolução.
