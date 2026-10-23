# O que os anúncios do ME.IA mostram vs. o que a nossa Skill faz

Fonte: 5 vídeos de anúncio de "Tiago Lemos - I.A." (página edicaomia.com.br) na Biblioteca de Anúncios da Meta,
transcritos em 21/10/2026. Não tivemos acesso ao curso em si nem ao "sistema" que ele instala: a comparação é
com o que ele mostra e diz nos anúncios. Nenhum material dele foi copiado.

| O que o anúncio mostra / promete | Nossa Skill | Como |
|---|---|---|
| "Você grava, pede em português e a IA edita" | ✅ | Claude Code + `/editor-video`; correções por texto viram operações (`edit.py`) |
| Corta pausas e respirações do vídeo inteiro | ✅ | `analyze.py`: pausas medidas no áudio, regravações, gaguejos |
| Legenda no tempo de cada fala | ✅ | Parakeet (pt-BR, tempo por palavra) + legendas animadas libass |
| Imagens e ícones no momento certo | ✅ | Ícones automáticos por palavra-chave (~1.900 Lucide) + B-roll por gatilho + `--broll-at` |
| Texto atrás da pessoa | ✅ | Máscara MediaPipe, palavra atrás da cabeça com regra de legibilidade |
| "Me coloca numa moldura do lado direito, do lado esquerdo explica com motion graphic" | ✅ | template `moldura` (pessoa em moldura 3D + itens no tempo da fala) |
| "Separa tudo em camadas de vidro: fundo, logos e eu" | ✅ | template `camadas` (vídeo real em movimento, rótulos, gira e junta) |
| Logos 3D na mão acompanhando o movimento | ✅* | template `objeto3d` com `follow: "hand"` (MediaPipe Hands). *Detecção validada; rastreio com mão em movimento real ainda não testado |
| "Deixa flutuando e joga para trás de mim" | ✅ | `objeto3d` com `layer: "behind"` |
| Remove o fundo e reconstrói o cenário em 3D, iluminado | ✅ parcial | `estudio3d`: fundo substituído por estúdio 3D (Three.js) com parallax e luz de recorte. Não "reconstrói" o ambiente real em 3D (isso exigiria fotogrametria/IA generativa de cena) |
| Casa 3D / explicação montada enquanto fala | ✅ por composição | Claude escreve uma composição HTML/Three.js própria (contrato em `references/motion.md`); templates `infografico` e `mapa` cobrem o caso do corretor |
| Vídeo virando documentário, câmera entrando na imagem, marcações no mapa | ✅ | template `documentario` (Ken Burns + círculos/setas/rótulos) e `mapa` (ilustrativo) |
| Terra abrindo em 3D, anatomia (médico) | ⚠️ sob medida | Possível com composição Three.js própria; precisa de modelos 3D licenciados para ficar realista |
| Vídeo de 20 minutos, aula, podcast, YouTube | ✅ | `--format 16:9`; o pipeline trabalha em blocos; render ~2-3x a duração em CPU |
| "Estúdio rodando dentro do Claude" | ✅ | Tudo local no Claude Code: ffmpeg + Chromium headless + Three.js, sem programa de edição |
| VSL de 3 minutos 100% por IA | ✅ (pipeline) | Mesmo fluxo; qualidade final depende das decisões do editor (Claude) e da revisão humana |

## Diferenças de abordagem

- Os anúncios sugerem um "sistema" instalado no ChatGPT/Claude. O mais provável é um framework HTML->vídeo
  (como o HyperFrames, da HeyGen) mais instruções. Nós construímos o equivalente com runtime e renderizador
  próprios. Escolhemos não depender do GSAP (licença restritiva da Webflow) nem do Remotion (pago para empresas).
- O ChatGPT (chat) não roda ffmpeg/Chromium localmente. O fluxo real precisa de um agente com terminal, como o
  Claude Code. Nossa Skill é feita para ele.
- Velocidade: aqui (CPU de 4 núcleos, sem GPU), 25 s com 5 animações renderizaram em ~3,5 min. Em Mac com
  Apple Silicon ou PC com GPU, cai bastante.

## Uso de logos de terceiros

O anúncio usa logos do ChatGPT e do Claude em 3D. São marcas registradas. A Skill aceita qualquer logo que você
fornecer (`objeto3d` com `image`), mas a responsabilidade pelo direito de uso é sua. Em anúncio pago, evite logo de
outra empresa sem autorização.
