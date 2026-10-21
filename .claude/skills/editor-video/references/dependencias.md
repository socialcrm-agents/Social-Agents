# Dependências

| Item | Para quê | Instalação | Licença |
|---|---|---|---|
| ffmpeg ≥ 5 com libass | cortes, zoom, cor, legendas ASS, mixagem, export H.264/AAC | Mac `brew install ffmpeg` · Ubuntu `sudo apt install ffmpeg` · Windows `winget install --id Gyan.FFmpeg -e` | LGPL/GPL (usado como programa externo, não embutido) |
| Python ≥ 3.10 | scripts | python.org / brew / apt | PSF |
| numpy, pillow | áudio, gráficos PNG | `pip install -r requirements.txt` | BSD / HPND |
| sherpa-onnx | roda o modelo de transcrição offline | idem | Apache-2.0 |
| mediapipe | rosto + recorte da pessoa | idem (Linux: `sudo apt install libegl1 libgles2 libgl1`) | Apache-2.0 |
| Modelo Parakeet TDT 0.6B v3 int8 (~640 MB) | transcrição pt-BR com tempo por token | `setup.py --models` (GitHub releases do sherpa-onnx) | CC-BY-4.0 (NVIDIA): uso comercial ok com atribuição |
| MediaPipe blaze_face + selfie_segmenter (~0,5 MB) | rosto e máscara | `setup.py --models` | Apache-2.0 |
| Fontes Anton, Poppins, DM Serif Display | legendas e gráficos | já incluídas em `assets/fonts` | SIL OFL 1.1 |
| Node.js ≥ 18 + Playwright + Chromium | motion graphics (HTML/CSS 3D/Three.js -> vídeo) | `npm install -g playwright && npx playwright install chromium` | MIT / Apache-2.0 / BSD |
| three.js 0.180, opentype.js, ícones Lucide | 3D, texto 3D com acento, ~1.900 ícones | já incluídos em `assets/motion/vendor` | MIT / MIT / ISC |
| MediaPipe hand_landmarker (~7 MB) | objeto 3D seguindo a mão | `setup.py --models` | Apache-2.0 |

Opcional: `faster-whisper` (`EDITOR_VIDEO_ASR=whisper`, modelo via `EDITOR_VIDEO_WHISPER`, padrão `small`).
Baixa modelos do HuggingFace; use quando a rede permitir e para comparar precisão.

Variáveis: `EDITOR_VIDEO_MODELS` muda a pasta dos modelos (padrão `~/.cache/editor-video/models`).

Hardware de referência (teste real): 4 vCPU x86, 15 GB RAM, sem GPU.
Transcrição ~0,15x o tempo real; render final ~2,2x o tempo real (48 s de vídeo ≈ 110 s), mais o tempo dos
motion graphics: CSS/SVG 10-25 quadros/s, Three.js 2-7 quadros/s (com cache por clipe).
