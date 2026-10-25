# Auditoria dos templates de motion (2026-10-25)

Os 47 templates foram renderizados um a um com o renderizador do próprio editor, sobre um quadro real (Mentos, 9:16).
A auditoria mediu o tempo por quadro, quanto da tela cada um ocupa e quanto cai na zona do rosto. Também verificou o
determinismo no código. As folhas de contato (4 instantes de cada) foram revisadas a olho.

- Ferramenta: `docs/editor-video/auditoria/auditar_templates.py`
- Evidências: `auditoria/templates/folha_1..6.jpg` e `resultado.json`

## Resultado técnico

- **Render:** 47 de 47 renderizam sem erro.
- **Determinismo:** 47 de 47 passam no lint. Nenhum usa `setTimeout`, `requestAnimationFrame`, animação CSS
  automática nem `Math.random()` sem semente. O mesmo `t` dá o mesmo quadro, e é isso que permite cache e
  render por trechos.
- **Lentos (CPU, sem GPU):**
  - `estudio3d`: 2,8 s/quadro, o mais caro de todos.
  - `objeto3d`: 1,0 s/quadro.
  - `profundidade`: 0,95 s/quadro.
  - `clones`: 0,8 s/quadro.
  - `luz`: 0,74 s/quadro.
  - Os outros ficam entre 0,1 e 0,55 s/quadro.
- **Na zona do rosto com a posição padrão:** `checklist` (65%), `onda_audio` (65%), `player` (79%), `giro` (100%),
  `mapa` (100%), `objeto3d` (53%), `pedacos` (44%), `cronometro`, `tomadas` e `tabela` (35 a 39%).
  - Isso já não chega ao vídeo final: a proteção de rosto (`rosto_guarda.py`) mede quadro a quadro e move ou diminui
    o elemento, e o QA reprova o que sobrar.
  - Ainda assim, essas posições padrão estão erradas para close-up. Vale corrigir os defaults; está na lista abaixo.

## Veredito por template

### Premium: entram na biblioteca curta da direção premium (seletor e composições)

| Template | Por quê |
|---|---|
| `palavra_chave` (novo) | Letra em cascata com mola, degradê da emoção, extrusão, emoji com faíscas e brilho. Lê a 3 m do celular. |
| `profundidade` (novo) | 2.5D de verdade: paralaxe pela profundidade, desfoque de lente e palavra entre o cenário e a pessoa. |
| `produto3d` (novo) | Produto extrudado com chanfro, luz key/rim, verniz e sombra. Voa, gira ou pousa na mão. |
| `moldura`, `camadas`, `quadrinho`, `dividida` | Tela cheia com a pessoa dentro do layout. São os mais "caros" visualmente. |
| `manchete`, `pergunta`, `infografico`, `checklist`, `botao_cta`, `final` | Tipografia limpa, hierarquia boa e legíveis no celular. |

### Bons, mas com cuidado: só por pedido explícito ou gatilho, nunca escolhidos sozinhos pela direção premium

| Template | Cuidado |
|---|---|
| `carimbo`, `proibido`, `icone`, `cronometro`, `tomadas`, `tabela`, `notificacao`, `vendas`, `etiqueta` | Posição padrão em cima da testa ou do rosto em close-up. A proteção corrige, mas a origem certa é a zona livre. |
| `objeto3d` | Texto 3D bom, mas atravessa os olhos na posição padrão. Para produto, prefira `produto3d`. |
| `clones`, `cenario`, `estudio3d`, `carrossel3d`, `documentario`, `visor`, `recorte` | Funcionam e têm impacto. `estudio3d` é lento demais para prévia; `cenario` precisa de imagem de cenário de verdade. |
| `tela_ia`, `editor_ia`, `transcricao`, `onda_audio`, `player`, `hud`, `maos` | Linguagem de bastidor ou tecnologia, de nicho. `hud`, `editor_ia` e `transcricao` têm textos pequenos demais para o celular (< 30 px). |
| `passa_mao` (novo) | Transição divertida: emoji de mão com rastro. É lúdica, não "cinema": use em criativo leve. |

### Problemas encontrados (corrigir antes de ampliar a biblioteca)

1. **`pedacos`:** sem os quadros da pessoa (camada behind sem máscara), aparece como blocos pretos sobre a cabeça.
   Precisa de um fallback quando não há máscara.
2. **`hud`, `editor_ia`, `transcricao`, `tomadas`:** textos auxiliares abaixo do mínimo de leitura (44 px em 1080).
3. **Posições padrão em close-up** (`checklist`, `giro`, `mapa`, `player`, `onda_audio`, `cronometro`): o padrão
   deveria vir da zona livre (acima da cabeça ou no peito), não de um y fixo.
4. **`luz`:** o vazamento laranja tinge o rosto. Merece uma máscara que poupe a pele.

## Decisão

A direção premium usa apenas: `palavra_chave`, `profundidade`, `produto3d`, as transições (`zoom_impacto`,
`whip`, `glitch`, `passa_mao`) e os templates de CTA e pergunta que os gatilhos já colocam. Os outros 40 continuam
disponíveis por pedido explícito, porque nenhum foi removido.

A regra é: **nenhum template novo entra na biblioteca curta sem passar por esta auditoria**:
- render sem erro e lint limpo;
- tempo por quadro medido;
- teste no vídeo real com a proteção de rosto ligada;
- folha de contato revisada.
