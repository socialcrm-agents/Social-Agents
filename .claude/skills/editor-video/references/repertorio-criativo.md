# Repertório criativo: o que propor sem a pessoa pedir

O editor é o **diretor criativo**. A pessoa não precisa saber pedir "use uma maquete 3D": quando ela fala de
cômodos e metragem, a maquete é proposta. Esta lista é a memória de ideias. Para cada vídeo, cruze **o que é dito**
com a tabela e proponha **3 ideias ousadas** (seção 2 do SKILL.md: "Proposta criativa").

Regra de ouro: **a ideia tem que ilustrar o que está sendo dito, no segundo em que é dito**, e cada 3-4 s algo
muda na tela. Ousadia sem ruído: no máximo 1 efeito "herói" por frase.

## 1. Por assunto falado

| A pessoa fala de… | Ideia ousada (herói) | Como fazemos | Alternativa leve |
|---|---|---|---|
| **imóvel, cômodos, metragem, planta, "3 quartos", "suíte"** | **Maquete 3D que se monta** e passeia cômodo a cômodo com "QUARTO · 12 m²" | `maquete` (comodos com w, d, x, z e `at` na palavra) | `infografico` com os m² |
| **construção, reforma, "do zero", obra** | A casa **subindo em blocos** (monta_ate longo) ou o objeto **se desmontando e remontando** | `maquete` / `cena3d` com `explodir` | `checklist` de etapas |
| **consórcio, carro, carta de crédito, "sua casa própria"** | Objeto 3D (carro, casa) **montando peça por peça** enquanto fala do plano; moedas/números subindo | `cena3d` com modelo .glb + `explodir`; `infografico` | `objeto3d` com o valor |
| **produto físico** (cosmético, comida, acessório) | **Vista explodida** do produto ou produto voando e pousando na mão | `cena3d` (modelo do produto; foto→3D pelo Hugging Face quando liberado) / `produto3d` | `giro` antes/depois |
| **"imagina…", sonho, viagem, lugar** | **Trocar o fundo** pelo lugar descrito, com a câmera andando (2.5D) | `cenario` com imagem do Canva/Hugging Face (`generate-image`, 9:16) + `profundidade` | `documentario` com foto |
| **números, faturamento, "3x mais", porcentagem** | Número **rolando gigante** com cards de vidro / barras subindo | `infografico`, `palavra_chave` com o número | `cinetico` |
| **antes e depois, transformação** | Card **girando** (antes → depois) ou tela dividida | `giro`, `dividida` | `tabela` |
| **lista, passos, "3 erros"** | Palavras **empilhando** no tempo da fala, ou checklist marcando | `empilha`, `checklist` | `manchete` |
| **erro, dor, "pare de…"** | Palavra gigante com **glitch e tremida**; ícones levando um X vermelho | `palavra_chave` + `--fx glitch`, `proibido` | `carimbo` |
| **prova, cliente, print, depoimento** | **Prints voando em 3D** / notificações de venda empilhando | `carrossel3d`, `vendas` (só números reais), `documentario` | `giro` |
| **ferramenta, app, IA, "eu uso o…"** | Tela de app animada; a pessoa **dentro de uma moldura 3D** explicando | `tela_ia`, `editor_ia`, `moldura` | `notificacao` |
| **mapa, bairro, "a 5 min do metrô"** | Mapa ilustrado com a rota sendo desenhada | `mapa` | `infografico` |
| **tempo, prazo, "em 7 dias"** | Cronômetro de vidro contando | `cronometro` | `palavra_chave` |
| **comentar, chamada final** | Caixa de comentário digitando a palavra-chave; tela final | `comentario`, `final`, `botao_cta` | CTA do estilo |
| **gancho (0-3 s)** | Frase do gancho em **tipografia cinética** ou a revelação 2.5D | `cinetico` (estilo `explode`/`sobe`), `revelacao@auto` | `pergunta` |

| **qualquer objeto concreto** (sofá, lápis, chave, troféu, celular, carro, café…) | O **objeto em 3D** entra no segundo da palavra (monta peça por peça, cai, gira) | `objeto_cinema` (biblioteca; se não existir, modele e salve — `references/motion.md`, "Objetos 3D sob demanda") | `produto3d` com `icone` |

## 2. Pedidos que a pessoa faz falando (valem como ordem)

Se na fala ou no pedido aparece:
- "muda o fundo", "coloca na praia", "num escritório": `cenario` com imagem gerada.
- "imagina": `cenario` + `profundidade`.
- "olha isso", "veja": zoom de impacto e foco no que é mostrado.
- "mudança de tela", "agora": `--fx whip` ou `passa_mao` nessa frase.
- "lista", "primeiro… segundo…": `empilha`.
- "coloca um sofá girando", "quero um lápis em 3D", qualquer objeto pedido: `objeto_cinema` (crie na biblioteca se faltar).

Execute esses pedidos e conte no resumo o que foi feito.

## 3. O que ainda não fazemos (não prometa; ofereça a alternativa)

| Não fazemos | Alternativa |
|---|---|
| Trocar a roupa da pessoa no vídeo | Trocar o fundo, ou um card com a roupa nova (imagem gerada) |
| Objetos se desfazendo em partículas | `objeto_cinema` com `explodir` ou o `cerebro` (pontos que se formam) |
| Vídeo gerado por IA do zero | Hugging Face Wan 2.2 (foto → vídeo) quando for liberado |

## 4. Formato da proposta (sempre assim, curta)

```
3 ideias para este vídeo:
1. [00:03] Quando você fala "sala de 20 m²": maquete 3D se montando e mostrando cada cômodo com a metragem. (3D, ~4 min de render)
2. [00:00] Gancho "Quanto custa um apê de 2 quartos?" em tipografia cinética explodindo. (leve)
3. [00:12] "Imagina acordar com essa vista": fundo trocado por uma varanda com vista para o mar, câmera andando. (imagem do Canva)
Faço as 3? (ou diga quais)
```
Se a pessoa disse "faz tudo", "capricha" ou "sem perguntar", execute as 3 e mostre o resultado.
