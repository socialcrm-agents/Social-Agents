# Correções por texto -> operações do edit.py

O Claude traduz o pedido do usuário e chama `edit.py <projeto> ... --note "pedido original"`.
Várias operações podem ir no mesmo comando (uma versão nova por rodada).

| O usuário diz | Operação |
|---|---|
| "tira o 'é isso' do começo", "corta a parte que eu falo X" | `--cut "É isso."` / `--cut "trecho exato"` (copie do transcript.txt) |
| "volta a frase X que você cortou" | `--restore "frase X"` |
| "a legenda escreveu cloud, é Claude" | `--fix "cloud=Claude"` |
| "muda pro estilo anúncio / editorial / viral" | `--style anuncio_conversao` / `editorial_premium` / `reels_viral` |
| "troca o gancho / a faixa do começo para ..." | `--hook "..."` |
| "o CTA tem que ser 'Comenta EU QUERO'" | `--cta "COMENTA EU QUERO"` |
| "põe o título 'X' no começo" (Editorial) | `--title "X"` |
| "destaca a palavra dinheiro" | `--emph "dinheiro"` |
| "coloca LUCRO grande atrás de mim quando eu falo faturamento" | `--behind-add "LUCRO@faturamento"` |
| "tira a palavra X de trás" | `--behind-remove "X"` |
| "não quero palavra atrás de mim" | `--behind off` |
| "põe a gravação de tela quando eu falo 'sistema', 3 segundos, em tela cheia" | `--broll-at "sistema:3:full:b1"` (modos: full, card, split) |
| "tira o segundo B-roll" | `--broll-remove 2` (numeração na ordem de entrada, ver timeline.json) |
| "usa também esse print / vídeo" | `--add-broll caminho/arquivo` (+ `--broll-at` para posicionar) |
| "legenda maior / menor" | `--caption-size +15%` / `--caption-size -10%` |
| "sobe a legenda" | `--caption-y 1100` (base da legenda em px; máx 1470) |
| "menos zoom", "sem zoom", "zoom mais agressivo" | `--zoom suave` / `--zoom off` / `--zoom forte` |
| "coloca essa música baixinha" | `--music trilha.mp3:0.10` (ducking automático sob a voz) |
| "me coloca numa moldura e explica X do lado" | `--motion '{"template":"moldura","at":"trecho","until":"trecho","params":{"title":"...","items":[...]}}'` |
| "separa em camadas de vidro" | `--motion '{"template":"camadas","at":"trecho","dur":4,"params":{"graphic":"..."}}'` |
| "troca meu fundo por um estúdio 3D" | `--motion '{"template":"estudio3d","at":"trecho","dur":5,"params":{"wall_text":"..."}}'` |
| "coloca minha logo em 3D na minha mão" / "joga pra trás de mim" | `--motion '{"template":"objeto3d","at":"trecho","dur":3,"params":{"image":"logo.png","follow":"hand"}}'` / `"layer":"behind"` |
| "anima os números", "mostra no mapa" | templates `infografico` / `mapa` (ver `motion.md`) |
| "anima X" (qualquer coisa sem template) | composição própria em `work/motion/custom/*.html` + `--motion '{"page":"/work/motion/custom/x.html",...}'` |
| "tira a segunda animação" | `--motion-remove 2` |
| "sem ícones" | `--icons off` |
| "faz a versão horizontal pro YouTube" | `--format 16:9` (ou crie outro projeto com `--format 16:9`) |
| "só ajusta, não renderiza ainda" | `--no-render` |
| "quero ver rápido" | `--draft` (render mais rápido, qualidade menor) |

Pedidos sem operação direta (ex.: "o zoom do plano 7 está no lugar errado", "B-roll começa meio segundo
antes"): edite `timeline.json` (campos `shots[n].cx/cy/zoom0/zoom1`, `broll[n].t0/t1`, `graphics[n]`)
e rode `render.py <projeto>`. Atenção: `plan.py` reescreve a timeline; edição manual vale só até o próximo
`edit.py`/`run.py render`. Se o pedido for recorrente, registre como operação nova em `edit.py`.

Histórico: `versions/changelog.md` (pedido + operações por versão) e `versions/vN/` (timeline, projeto, QA).
Voltar para uma versão anterior: copie `versions/vN/project.json` para `project.json` e rode `run.py render`.
