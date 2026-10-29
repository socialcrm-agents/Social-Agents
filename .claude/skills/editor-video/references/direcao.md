# Direção de edição profissional — leia ANTES de planejar qualquer vídeo

O script corta e legenda sozinho. **Quem decide o que aparece na tela é você.** O erro que mais derruba a qualidade é
editar pouco: legenda + zoom e mais nada. Um editor profissional de criativos pensa cada segundo: *o que a pessoa
está dizendo agora, e o que a tela pode mostrar que reforça isso?* Este manual é esse raciocínio, passo a passo.

Regra de ouro: **cada efeito tem um motivo na fala.** Nada entra "porque é bonito"; tudo entra porque ilustra,
prova, organiza ou chama a ação daquilo que está sendo dito naquele instante.

---

## 1. Antes de tudo: o vídeo é bruto ou já editado?

| O usuário disse… | Modo | Como criar o projeto |
|---|---|---|
| nada sobre cortes; vídeo com pausas, erros, várias tomadas | **bruto** | `run.py new ... ` (corta pausas, gaguejos, tomadas repetidas) |
| "já cortei", "já editei no CapCut", "não precisa cortar", "não acelera" | **sem cortes** | `run.py new ... --sem-cortes` (mantém o vídeo inteiro e o ritmo original; só embeleza) |

No modo sem cortes: não use `--cut`, `--velocidade` nem `run.py curta`. Projeto existente: `edit.py --sem-cortes on`.

Pedido de "máxima qualidade": estilo `pro_clean` (anúncio premium) ou `anuncio_conversao` (mais agressivo), render
final sem `--draft`, **densidade alta** (seção 4) e imagem automática (`edit.py --correcao auto --estabilizar auto`,
seção 8c). Pedido de troca de fundo liberada: veja a seção 7.

---

## 2. O método (siga nesta ordem, em toda edição)

1. **Leia `transcript.txt` inteiro** e diga em uma linha qual é o tipo do vídeo (seção 5) e o objetivo (vender,
   seguir, comentar, clicar, assistir a VSL).
2. **Monte o MAPA DE EDIÇÃO**: uma tabela com uma linha por frase (ou a cada 2–4 s):

   | tempo | fala (trecho exato) | função | elemento na tela | camada/zona |
   |---|---|---|---|---|
   | 0,0–2,1 | "Se você tá estudando marketing digital…" | gancho/identificação | `pergunta` digitando | front/topo |
   | 2,1–5,0 | "…você já viu umas 30 aulas" | número | `infografico` 30 contando | front |

   Funções possíveis: gancho, identificação, dor, inimigo/erro, virada, número, lista/passos, comparação/versus,
   pergunta, prova/resultado, bastidor/processo, ferramenta/produto, lugar, citação, objeção, oferta, CTA.
3. **Escolha o elemento de cada linha** pela tabela de gatilhos (seção 3), respeitando densidade (seção 4) e
   cuidados (seção 8). Mostre o mapa ao usuário em formato curto e siga (não espere aprovação, a não ser que ele
   tenha pedido).
4. **Grave tudo num arquivo** `<projeto>/motion.json` (lista de pedidos) e aplique de uma vez:
   `edit.py <projeto> --no-render --motion @<projeto>/motion.json` + gancho/CTA/fx no mesmo comando.
5. **Prévia** `run.py render <projeto> --draft` → QA (seção 9) → corrija → render final sem `--draft`.

---

## 3. Tabela de gatilhos — o que a fala pede, o que a tela mostra

| Quando a pessoa… | Use | Alternativas | Params essenciais / dica |
|---|---|---|---|
| abre com pergunta ("Você sabia…?", "Se você…") | `pergunta` | `manchete` | `text` = a pergunta curta; `ate_at` = última palavra; esconde a legenda sozinho |
| abre com afirmação forte / polêmica | `manchete` | `palavra`, `etiqueta` | 1–3 linhas, ≤ 6 palavras; `destaque` na palavra-chave |
| fala uma palavra de impacto isolada ("SIM.", "NUNCA", "GRÁTIS") | `palavra` | `--fx tremida@palavra` | atrás da cabeça quando há espaço (o editor decide sozinho) |
| diz um número (preço, quantidade, %, tempo, resultado) | `infografico` | `palavra` com o número, `cronometro` (tempo), `etiqueta` | `stats[{value, prefix/suffix, label, at}]` conta até o valor quando dito; **só números ditos** |
| compara A × B, "versus", antes × depois, "X aulas vs 1 método" | `tabela` | `dividida` (`modo:grade`), `giro` (antes→depois), `manchete` com `riscar` | `left/right`, `rows[{l, r, at}]`; o lado "certo" sempre à direita, em destaque |
| descarta algo ("esquece X", "não precisa de Y", "pare de…") | `proibido` | `manchete` com `riscar`, `carimbo` | ícones genéricos (nunca logo de marca), `x_at` na palavra |
| enumera ("primeiro… segundo…", "3 coisas") | `checklist` | `empilha`, `moldura` (com itens), `dividida` `grade` | um item por `at`, texto ≤ 4 palavras |
| explica um processo / passo a passo longo | `moldura` | `dividida`, `camadas` | pessoa vai para a moldura e os passos surgem do outro lado |
| mostra bastidor, "como é feito", "por trás" | `camadas` | `recorte`, `pontos`, `transcricao`, `editor_ia` | 3–5 s; tela cheia |
| fala de IA, tecnologia, "a máquina faz" | `hud`, `pontos`, `recorte` | `editor_ia`, `tela_ia`, `maos` | `hud` segue o rosto; `maos` só se a mão aparece |
| fala de edição, vídeo, "corta", "legenda" | `editor_ia`, `transcricao`, `tomadas` | `onda_audio`, `player` | dados reais do próprio vídeo |
| mostra produto na mão | `objeto3d` (`follow:"hand"`), `card_fogo` | `maos`, `etiqueta` | nunca cobrir o produto; texto ao lado |
| cita uma tela, curso, aula, vídeo | `player` | `carrossel3d`, `giro` | `titulo`, `selo`, `total` ("3:01") |
| cita resultado de cliente / prova social | `vendas` (notificações), `notificacao` | `documentario` (print), `infografico` | só dados reais fornecidos pelo usuário |
| cita print/foto/documento | `documentario` | `giro`, `dividida` (`imagem`) | `marks` (círculo/seta) no tempo da fala |
| fala de lugar / distância | `mapa` | `etiqueta` | `place`, `time_label` |
| conta uma história / exemplo ilustrável (casa, dente, comida…) | `quadrinho` | `cenario`, `dividida` (`imagem`) | `paineis[{ilustracao | imagem, rotulo, at}]` |
| diz uma lista de pendências / dores do dia a dia | `dividida` `modo:pendencias` | `checklist`, `empilha` | post-its que aparecem no tempo da fala |
| muda de assunto / nova seção | `etiqueta` | `luz`, `--fx whip` | rótulo curto ("PASSO 2", "O ERRO") |
| começa a "versão crua" vs "editada" | `visor` (`pb:true`) | `clones` | P&B → cor na palavra da virada |
| faz conta de tempo/prazo ("em 7 dias", "em 30 segundos") | `cronometro` | `infografico` | `seconds`, `label` |
| pede comentário ("comenta EU QUERO") | `comentario` | `final` (com `palavra`) | `chamada` = a palavra exata |
| pede clique / link / carrinho / "saiba mais" | `botao_cta` | `final`, CTA do estilo | `click_at` na palavra "clica" |
| encerra / chamada final | `final` | `botao_cta`, `comentario` | `rotulo`, `palavra`, `nome`, `foto` |
| momento emocional / virada | `luz`, `--fx clarao` | `palavra`, zoom forte (`--zoom forte`) | 0,3–0,6 s, nunca sobre texto importante |
| algo dá errado / "deu ruim" | `--fx glitch` | `carimbo` ("ERRO") | curto |
| pessoa aparece em mais de uma versão / conversa consigo | `clones` | `dividida` | `copies[{label, look, delay}]` |

Palavras-chave soltas (dinheiro, tempo, celular, ideia…) recebem `icone` automático no Viral/Anúncio — não
duplique com outro bloco no mesmo instante. O **mapa de gatilhos** da marca (`triggers.json`) já coloca alguns
sozinhos; confira em `timeline.json` (`motion[].trigger`) antes de pedir outro igual.

---

## 4. Densidade e ritmo (o que separa amador de profissional)

| Tipo | Algo muda na tela a cada | Blocos de motion por 30 s | Tela cheia (máx.) | Respiro (só rosto + legenda) |
|---|---|---|---|---|
| Criativo de tráfego / anúncio (15–60 s) | **2–3 s** | 6–10 | 1 a cada 6–8 s | ≤ 2 s seguidos |
| Reels/TikTok orgânico | 3–4 s | 5–8 | 1 a cada 8 s | ≤ 3 s |
| VSL (3–30 min) | 5–8 s nos blocos de prova/oferta; 10–15 s no resto | 3–5 por minuto | nos pontos-chave (mecanismo, prova, oferta) | trechos de história podem respirar 15–20 s |
| Aula / tutorial 16:9 | 8–15 s | 2–3 por minuto | só para diagramas | sim |
| Depoimento | 6–10 s | 2–4 | nenhuma ou 1 | sim — a emoção é a prova |

"Algo muda" vale: bloco de motion, zoom/corte de plano, palavra atrás, ícone, efeito, B-roll, troca de fundo.

Ritmo:
- **0–1,5 s**: um elemento de gancho SEMPRE (`pergunta`, `manchete`, `palavra`, `etiqueta` ou fx). O primeiro
  quadro já tem texto na tela: use `"at": 0` (número) no gancho — vídeo sem cortes costuma ter silêncio antes da
  primeira palavra.
- **Meio**: alterne famílias — texto → dado → tela cheia → texto. Nunca dois blocos de tela cheia colados, nunca
  dois blocos iguais seguidos.
- **Últimos 3–5 s**: CTA visual (`final`, `botao_cta` ou `comentario`) + o CTA do estilo.
- **Duração mínima** de um elemento: 1,2 s (texto curto) a 2,5 s (card com frase). Leitura ≈ 3 palavras/s.
- **Uma informação por vez**: no máximo 1 bloco de texto grande + legenda ao mesmo tempo.

---

## 4b. Linguagem de editor profissional (o que faz parecer caro)

1. **Um herói por momento.** Em cada frase só UM elemento manda na tela; o resto (legenda, ícone) é coadjuvante.
   Dois elementos fortes ao mesmo tempo = amador.
2. **O elemento conversa com a pessoa.** Prefira o que interage com ela: atrás da cabeça (`palavra`), preso à mão
   (`objeto3d`/`card_fogo` com `follow`), seguindo o rosto (`hud`), a pessoa indo para dentro do layout
   (`moldura`, `dividida`, `quadrinho`). Card solto no meio da tela é o último recurso.
3. **Uma linguagem visual por vídeo.** Mesmas cores (as do estilo/marca), mesmos cantos e sombras, mesma família
   de entrada. Não misture mais de 2 cores de destaque. Varie os blocos, não o estilo.
4. **Hierarquia de texto.** Na tela: palavra-chave grande + no máximo 4 palavras de apoio. Frase inteira só na
   legenda. Números sempre grandes e com unidade (R$, %, dias).
5. **Ritmo de entrada e saída.** Entra no instante exato da palavra (âncora `at` na palavra, não na frase), sai
   antes da próxima ideia. Nada fica na tela "esquecido" depois que a fala mudou de assunto.
6. **Câmera viva.** Todo bloco entra com um empurrão de zoom e todo impacto tem som + tremida — o editor faz isso
   sozinho; não desligue sem motivo.
7. **Escala certa.** Em 9:16 os cards ocupam 70–85% da largura; texto de tela nunca menor que ~44 px; nada
   espremido no canto.
8. **Prova visual > texto.** Se existe print, tela, produto ou resultado real, mostre (`documentario`, `player`,
   `giro`) em vez de escrever sobre ele.
9. **Final forte.** Os últimos 3 s sempre têm o CTA visual mais bonito do vídeo (`final` ou `botao_cta`) e um som
   de fechamento.

## 4c. Direção premium (padrão quando pedirem "máxima qualidade" / "nível concorrente")

Três efeitos extraordinários valem mais que trinta genéricos. Ligue o seletor e use as composições:

```
python scripts/edit.py <proj> --direcao premium [--produto produto.png] \
    --composicao "revelacao@<trecho do gancho>" --composicao "impacto@<número ou palavra forte>" \
    [--composicao "produto_heroi@<quando mostra o produto>"] [--music auto:energia] --no-render
python scripts/run.py previa <proj> --de 0 --ate 5      # prévia rápida só do trecho (não vira versão)
python scripts/seletor.py <proj>                         # o que entrou em cada cena, o que ficou de fora e por quê
```

| Composição | Quando | O que faz |
|---|---|---|
| `revelacao@trecho` | gancho, virada, nome do produto | 2.5D: câmera empurra, fundo em paralaxe pela profundidade, a palavra mais forte do trecho aparece ENTRE o cenário e a pessoa, no lugar livre da parede; riser → hit; chicote de entrada |
| `produto_heroi@trecho` | "olha esse…", "esse produto" (precisa `--produto`, recorte com `scripts/recorte.py`) | produto 3D de verdade (extrudado, luz, sombra) voa e pousa na mão; swoosh + plim + soco de câmera |
| `impacto@trecho` | preço, número, palavra-chave de emoção | soco de câmera + palavra gigante com emoji e cor da emoção + clarão + tremida curta; som da emoção |

O seletor (`--direcao premium`) decide o resto cena a cena: palavra-chave com emoji/cor por emoção (paleta de no
máximo 2 cores), transições no ritmo da fala (zoom de impacto, chicote, glitch, passa a mão) só na troca de frase e
na família da linguagem do estilo, e respeita o orçamento: herói ≥ 2 s, transição ≥ 2,5 s, tela cheia ≤ 1 a cada
8 s, nunca o mesmo efeito em sequência. Pedido seu (motion/composição) sempre vence o automático.

Garantias automáticas no render: **rosto livre** (animações que cobririam olhos/boca descem/sobem/vão para o lado
ou diminuem, desviando também de legenda e gráficos; o QA reprova o que sobrar e avisa quando diminuiu < 70%) e
**QA de densidade/leitura** (`seletor.py <proj>`: buracos > 4,5 s, dois heróis juntos, tela cheia colada, legenda
< 44 px). Antes de entregar, olhe a folha de quadros dos momentos de cada composição.

## 5. Receitas por tipo de vídeo

### Comparação / "VS" (ex.: "30 aulas vs 1 método")
0 s `manchete` ("30 AULAS **vs** 1 MÉTODO") → número dito: `infografico` (30 contando) → o lado ruim: `proibido`
ou `manchete` com `riscar` → explicação do lado bom: `tabela` (2 colunas) ou `dividida` `grade` → prova:
`vendas`/`documentario` → CTA `botao_cta` + `final`.

### Conversa entre dois (duas pessoas, ou a mesma em dois papéis)
Rótulo de quem fala com `etiqueta` na primeira fala de cada um ("ALUNO", "MENTOR") → perguntas do "aluno" em
`pergunta` → respostas com dados em `infografico`/`checklist` → `clones` se for a mesma pessoa nos dois papéis →
punchline com `palavra` + `--fx tremida` → CTA. Mantenha a legenda (diálogo precisa ser lido).

### Pergunta na tela / POV
`pergunta` digitando nos primeiros 2 s (esconde a legenda) → resposta em blocos curtos: `empilha` (itens) ou
`checklist` → número/prova → `comentario` com a palavra-chave → `final`.

### Identificação ("Se você tá estudando X…", "Se você é Y…")
`pergunta` ou `manchete` com o público → dores em `dividida` `pendencias` (post-its) ou `empilha` → virada com
`luz` + `palavra` ("PARA.") → solução em `checklist`/`moldura` → CTA.

### Anúncio de produto (pessoa mostrando)
`etiqueta` com o produto → `objeto3d`/`card_fogo` seguindo a mão → benefícios `checklist` → preço `infografico`
ou `palavra` → `botao_cta` "TOQUE NO CARRINHO".

### VSL longa
Gancho: `manchete` + `palavra`. Mecanismo do problema: `camadas` ou `documentario`. Mecanismo da solução:
`moldura` com os passos. Provas: `vendas`, `documentario`, `infografico`. Oferta: `checklist` do que vem dentro +
`infografico` do preço + `carimbo` "GARANTIA 7 DIAS". CTA: `botao_cta` repetido. Formato 16:9 ou 9:16 conforme o
tráfego; `--draft` na primeira prévia (vídeo longo).

### Aula / tutorial
`etiqueta` a cada seção ("PASSO 1") → `moldura`/`checklist` para listas → `documentario` para telas/prints →
`player` para mostrar vídeo/tela → ritmo calmo (estilo `editorial_premium`).

---

## 6. Capacidade máxima do editor (lembre que tudo isto existe)

- **Texto**: legenda animada (3 estilos + `pro_clean`), palavra gigante atrás da cabeça, `manchete`, `pergunta`,
  `etiqueta`, `empilha`, `carimbo`, `anotacao` (à mão), destaque de palavra na legenda (`--emph`).
- **Dados e listas**: `infografico`, `cronometro`, `tabela`, `checklist`, `vendas`, `notificacao`.
- **3D e tela cheia**: `moldura`, `camadas`, `estudio3d`, `objeto3d` (segue a mão), `carrossel3d`, `clones`,
  `cenario`, `giro`, `quadrinho`, `dividida`, `documentario`, `mapa`, **`profundidade`** (2.5D: a câmera anda, o
  fundo se mexe em paralaxe pela profundidade real e desfoca ao longe; palavra gigante ENTRE o cenário e a pessoa).
- **Produto e ícones 3D de verdade**: `produto3d` — foto do produto sem fundo (`scripts/recorte.py`, local e grátis)
  vira objeto 3D com espessura, luz e sombra que voa, gira, sai da mão (`follow:"hand"`) ou gira atrás da pessoa; emoji/ícone vira 3D igual.
- **Visão computacional (com dados reais do vídeo)**: `hud` (segue o rosto), `pontos` (pessoa em nuvem de
  pontos), `recorte` (pessoa separada do fundo em camadas), `maos` (esqueleto da mão).
- **Edição "ao vivo" (metalinguagem)**: `editor_ia`, `transcricao`, `tomadas`, `onda_audio`, `tela_ia`, `visor`.
- **Interface/CTA**: `player`, `comentario`, `botao_cta`, `final`, `proibido`.
- **Efeitos**: `--fx tremida|clarao|glitch|whip@palavra`, `luz`, zoom (`--zoom suave|forte`), chicote automático
  em tela cheia, sons sintetizados (whoosh, pop, ding, riser) já sincronizados.
- **Composição própria**: qualquer animação nova em HTML/Three.js (contrato em `motion.md`) — use quando a fala
  pede algo que nenhum template mostra (órgão do corpo, gráfico específico, objeto do nicho).
- **Mídia**: B-roll do usuário; **imagens geradas de graça** com `scripts/imagens.py gerar "<prompt>" midia/x.jpg`
  (Gemini/Nano Banana com `GEMINI_API_KEY`, senão Pollinations/Flux sem conta) e `imagens.py atender <proj>`, que
  gera os cenários de `qa/pedidos-de-midia.md` e devolve o `--motion cenario` pronto.

Parâmetros completos de cada bloco: `motion.md`. O que cada um precisa: `hud`/`palavra` atrás → rosto detectado;
`maos`/`objeto3d follow` → mão visível; `pontos`/`recorte`/`estudio3d` → máscara boa (pessoa nítida, fundo
separado); `documentario`/`giro`/`cenario` → imagens.

---

## 7. Fundo: quando trocar

**Sem trocar o fundo, dê profundidade a ele:** `profundidade` (3–6 s) no gancho, numa virada ou com a palavra-chave
(`texto`) entre o cenário e a pessoa — é o efeito "câmera de cinema" dos criativos de tráfego. `movimento: dolly`
(empurra), `orbita` (gira leve) ou `lateral`. Fundo real (padrão) aceita câmera na mão e produto na mão; `fundo:
"limpo"` só com câmera parada. Profundidade de verdade com o Depth Anything (baixado no `setup.py --models`);
sem ele, modo heurístico (pessoa e o que ela segura perto, cenário longe).

Troque (com `estudio3d`, `cenario`, `dividida`, `quadrinho`, `recorte`) quando:
- o fundo original é feio, bagunçado ou não tem nada a ver com o assunto;
- é um anúncio e o usuário liberou ("pode mudar o fundo");
- a fala muda de cenário ("imagina você na praia…") → `cenario` com a imagem.

Não troque quando: o fundo é parte da prova (loja, consultório, bastidor real), a máscara está ruim (cabelo
crespo com fundo da mesma cor, pouca luz — teste 2 s e olhe), ou o vídeo é depoimento. Troca de fundo é trecho
(3–8 s) em criativo; vídeo inteiro só com `estudio3d` e pedido explícito.

---

## 8. Cuidados (bloqueiam a entrega)

1. **Rosto livre**: nenhum texto ou card sobre olhos/boca. Elementos de topo fazem a cena recuar sozinha; confira
   na folha de QA. Cabeça encostando no topo → palavra atrás vira texto na frente (automático).
2. **Zonas seguras 9:16**: nada importante acima de y=220 nem abaixo de y=1470.
3. **Legenda × gráfico**: legenda some em `pergunta`, `final`, `transcricao`; em outros blocos de texto grande,
   confira que não colidem.
4. **Números, nomes, resultados**: só o que foi dito ou fornecido. Nunca invente prova, depoimento ou venda.
5. **Ortografia e acentos** em todo texto de tela; corrija o ASR com `--fix` antes de usar palavras na tela.
6. **Marcas de terceiros**: sem logos (use ícones genéricos), a não ser com arquivo e direito do usuário.
7. **Contraste**: texto claro em fundo claro some — use `bg` escuro ou sombra; teste no quadro.
8. **Produto na mão** nunca coberto.
9. **Excesso**: se dois elementos disputam o mesmo segundo, fique com o que a fala pede; o outro sai.
10. **Vídeo de baixa resolução** (ex.: 360×480): evite zoom forte e tela cheia com a imagem da pessoa ampliada;
    prefira blocos que usam o espaço (topo, dividida).
11. **Políticas de anúncio**: sem antes/depois de corpo, sem promessa de ganho/cura na tela.

---

## 8b. O que o editor já resolve sozinho (não brigue com isso)

- **Som**: toda animação ganha som próprio (whoosh na entrada, clique ao digitar/clicar, ding a cada item
  marcado, boom na palavra gigante e no carimbo, glitch no risco/X, riser antes do botão, ticks na visão
  computacional). Meta: 1 som a cada ~1–2 s num criativo. Mais forte/fraco: `"motion": 1.3` em `sfx` do estilo.

- Elementos do alto (`pergunta`, `manchete`, `etiqueta`, `infografico`, `carimbo`, `checklist`, `player`,
  `proibido`, `tomadas`, `palavra` sem espaço) fazem a pessoa **recuar** (descer e encolher) enquanto estão na tela.
- Dois textos do alto no mesmo instante: o anterior sai quando o próximo entra.
- Palavra automática atrás da pessoa sai se houver qualquer animação no mesmo instante, ou se a cabeça encosta no
  topo (nunca vai para cima do rosto).
- `botao_cta`/`comentario` tiram o CTA do estilo do mesmo instante (nada de CTA duplo); `botao_cta`, `pergunta`,
  `final` e `transcricao` escondem a legenda enquanto estão na tela.
- Fala no fim do vídeo (CTA na última frase): a animação recua para caber, em vez de sumir.
- Gatilho automático não repete um bloco igual ao que você pediu a menos de 6 s.
- `maos`: o render imprime `maos: mão em N/M quadros`; abaixo de metade, troque por outro bloco (fica vazio).

## 8c. Imagem: luz, cor, pele e tremida (vídeo de celular)

Desligado por padrão (projetos antigos renderizam igual). Ligue com
`edit.py <projeto> --correcao auto --estabilizar auto [--pele 0.35]` (fica em `project.json → overrides.imagem`):

- **Quando ligar**: `pro_clean` / "máxima qualidade" (sempre `auto`); vídeo de celular escuro, granulado ou com cor
  puxada (lâmpada amarela); câmera na mão ou selfie tremida; rosto fugindo do centro; pedido de "pele bonita".
  Vídeo de estúdio bem iluminado e no tripé: o `auto` decide sozinho que não precisa (não mexe).
- **O que faz** (100% local, uma análise por clipe em `work/imagem_<clipe>.json`): curva de luz (preto, branco e
  gamma; clareia o rosto até perto do ideal, nunca estoura), balanço de branco (cinza-mundo parcial nos tons
  neutros), denoise proporcional ao ruído e ao quanto a sombra clareou, nitidez só quando falta, pele suavizada só
  nos tons de pele (máx. ~55%: sem plástico) e recorte dinâmico por quadro que compensa o tremor e segue o rosto
  devagar (zoom mínimo 1,06, até 1,10 se tremer muito). O grade do estilo continua por cima, na composição.
- **Limites**: balanço/whip-pan intencional não é "tirado" (só suavizado dentro da margem do zoom); rotação da câmera
  não é compensada; bruto muito pequeno (360p) continua macio (a nitidez só ajuda um pouco).
- **Custo** (medido em 4 núcleos, tudo ligado): planos +0,9 a +2,2 s de CPU por segundo de vídeo (bruto 360p a
  1440p; ~0,25–0,6 s de relógio, os planos rodam em paralelo) + análise 0,3–2,3 s de CPU por segundo, uma vez por
  clipe (quase tudo é decodificar o bruto). Mudar a opção refaz só os planos (e o que depende deles).

## 9. QA antes de entregar

1. Folha `qa/vN_*_cortes.jpg` + 1 quadro no meio de cada bloco de motion (`ffmpeg -ss T ...`).
2. Reprova se: rosto coberto; texto cortado na borda; dois textos grandes ao mesmo tempo; número errado; bloco
   vazio (sem mão/rosto quando precisava); legenda sobre card; CTA ausente no fim.
3. Duração confere com o modo (sem cortes = igual ao original).
4. Áudio: loudness alvo (−14 LUFS anúncio/viral), efeitos sem cobrir a voz.
5. Na entrega, mostre o MAPA DE EDIÇÃO final (o que entrou em cada momento) — o usuário aprende e pede ajustes
   com precisão.

---

## 10. Exemplo completo (criativo de 30 s, vídeo já cortado no CapCut)

```bash
PY SK/scripts/run.py new ~/video-edits/estudando-mkt --clips "se voce ta estudando mkt digital.mp4" \
   --style pro_clean --sem-cortes --cta "COMENTA EU QUERO"
PY SK/scripts/transcribe.py ~/video-edits/estudando-mkt
```
`~/video-edits/estudando-mkt/motion.json` (trechos copiados do transcript):
```json
[
 {"template": "pergunta", "at": "Se você tá estudando", "until": "marketing digital", "params": {"text": "Você tá estudando marketing digital?", "label": "PERGUNTA"}},
 {"template": "infografico", "at": "30 aulas", "dur": 2.6, "params": {"stats": [{"value": 30, "suffix": " aulas", "label": "e nada mudou", "at": "30"}]}},
 {"template": "proibido", "at": "não precisa", "dur": 2.4, "params": {"icones": ["book-open", "video", "file-text"], "rotulo": "MAIS CONTEÚDO", "x_at": "não"}},
 {"template": "dividida", "at": "o que funciona", "dur": 5, "params": {"modo": "grade", "titulo": "O que **funciona**", "itens": [{"texto": "Oferta", "icone": "target", "at": "oferta"}, {"texto": "Criativo", "icone": "clapperboard", "at": "criativo"}, {"texto": "Página", "icone": "layout", "at": "página"}]}},
 {"template": "palavra", "at": "simples", "dur": 1.8, "params": {"text": "SIMPLES."}},
 {"template": "comentario", "at": "comenta", "dur": 3, "params": {"chamada": "EU QUERO"}},
 {"template": "final", "dur": 3, "at": "EU QUERO", "params": {"rotulo": "COMENTA", "palavra": "EU QUERO"}}
]
```
```bash
PY SK/scripts/edit.py ~/video-edits/estudando-mkt --no-render --motion @"$HOME/video-edits/estudando-mkt/motion.json" \
   --fx tremida@simples --emph "funciona"
PY SK/scripts/run.py render ~/video-edits/estudando-mkt --draft     # olhar, ajustar
PY SK/scripts/run.py render ~/video-edits/estudando-mkt             # final
```
(Os trechos `at` precisam existir na fala; copie do `transcript.txt` do vídeo real.)
