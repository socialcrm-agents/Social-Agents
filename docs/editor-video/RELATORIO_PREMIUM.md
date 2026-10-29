# Editor Viral IA™: acabamento premium (2026-10-25)

Pedido: acabamento audiovisual premium, uma auditoria dos templates, um seletor de efeitos por intenção, três
composições de referência e os 10 itens da lista. Tudo foi testado no vídeo real (Mentos, celular, close-up, câmera
na mão) e com testes automáticos.

**Testes:** 101 do editor (com render real) e o fluxo do Creative Studio passam.

## Entrega no vídeo real (render final)

| Medida | Resultado |
|---|---|
| Arquivo | 1080×1920, 30 qps, 17,37 s, H.264 + AAC |
| Loudness / pico | −14,4 LUFS / −1,0 dBFS |
| Rosto tampado | 0 quadros. Antes da proteção: 69 (impacto), 37 (OLHADINHA) e 41 (SABORES) |
| Densidade | 2,5 mudanças a cada 3 s, sem buraco > 4,5 s e sem dois heróis juntos |
| QA | sem alertas |

## O que entrou

| # | Item | Como funciona | Prova |
|---|---|---|---|
| — | Auditoria dos templates | 47 de 47 renderizam, lint de determinismo limpo, tempo por quadro medido, folhas revisadas e veredito por template | `AUDITORIA_TEMPLATES.md` |
| — | Seletor por intenção | Divide a fala em batidas e identifica a intenção. Escolhe 1 herói por momento e a transição da família do estilo, com orçamento de densidade, sem repetição, paleta de no máx. 2 cores e relatório cena a cena (`seletor.py`) | `test_seletor.py` |
| — | 3 composições de referência | `revelacao@` (2.5D + palavra entre o cenário e a pessoa, no lugar livre da parede + riser → hit), `produto_heroi@` (produto 3D pousa na mão + plim + soco de câmera), `impacto@` (soco + palavra gigante com emoji + clarão + som da emoção) | render real |
| — | Prévia rápida | `run.py previa --de A --ate B`: só a janela, sem criar versão | `test_previa.py` |
| 1 | Rosto nunca tampado | Medida por quadro com os olhos e a boca reais (pontos do detector), folga para o atraso do detector, conta letra semitransparente. Move ou diminui sem bater em outra animação, na legenda ou nos gráficos. O QA reprova o que sobrar | `test_rosto_guarda.py`; CTA 31→0, impacto 69→0 |
| 2 | Produto recortado | `recorte.py`: rembg → IS-Net → OpenCV (fundo liso); borda com filtro guiado e sem halo | IoU ≈ 0,999 nos sintéticos |
| 3 | 3D de verdade | `produto3d`: contorno → extrusão com chanfro, luz key/rim, verniz e sombra. Voa, gira, pousa na mão ou passa atrás; ícone 3D de emoji ou texto | render real |
| 4 | Legenda dos concorrentes | `palavra_chave`: palavra dita, gigante, cor da emoção (léxico pt-BR) e emoji, na batida certa | render real |
| 5 | Transições | Zoom de impacto, chicote, glitch e passa a mão, só na troca de frase e no ritmo da fala | render real |
| 6 | Sons e trilha | `trilha.py` sintetizada (5 climas, BPM pelo ritmo da fala, sem direitos) e `sfx.py` (hit, swoosh, swipe, cash, plim...); ducking de 8,8 dB sob a voz | `test_trilha.py` |
| 7 | Correção de imagem | Luz (curva nos médios), balanço de branco, ruído, nitidez e pele, tudo local | escuro: luma 0,19→0,46, cor R/B 2,0→1,26 |
| 8 | Estabilizar e reenquadrar | Recorte dinâmico que compensa a tremida e segue o rosto | tremor −65%, rosto −45% |
| 9 | Ganchos testados | `run.py ganchos`: 3 aberturas diferentes; só o trecho 0–4 s é refeito | `test_ganchos.py` |
| 10 | Referência do concorrente | `referencia.py analisar/aplicar`: cortes/min, plano médio, punch-ins, texto na tela, legenda, ritmo, paleta → estilo, zoom, legenda e cores (nunca copia conteúdo) | editado 24,9 cortes/min vs bruto 0–1,2 |

## Defeitos achados nos testes visuais (corrigidos)

- Botão de CTA cobrindo a boca; o detector via 14 quadros, eram 31.
- Elemento empurrado para fora da tela ao liberar o rosto.
- Palavra-chave colada na legenda e embaixo da pílula de CTA.
- Fantasma do produto na placa limpa do 2.5D.
- Mão-emoji borrada pelo chicote.
- Página pesada travando a espera do renderizador.
- Palavra da revelação escondida atrás da cabeça.
- Letra entrando por cima dos olhos (3 quadros).
- `until` parando na 1ª palavra.
- Cache de motion servindo clipe velho quando muda o código que prepara os dados.
- Chicote duplicado.
- Mesma palavra destacada duas vezes seguidas.
- Disco cheio no meio dos testes, que causava `ERR_INSUFFICIENT_RESOURCES`.

## Limites honestos

- **Fonte em 360×480:** o vídeo de teste é de baixa resolução; o produto recortado dele fica mole quando ampliado, e
  a nitidez/pele ajudam pouco. Com foto de produto de estúdio e vídeo 1080p o 3D fica nítido.
- **Revelação 2.5D:** brilha em plano médio (com parede livre). Num close-up de selfie a cabeça ocupa a parede; o
  editor acha o lugar livre, mas a palavra sai menor.
- **Produto herói:** neste vídeo o produto 3D duplica o pote que a pessoa segura. Vale quando ela não está com o
  produto na mão ou com foto de estúdio.
- **Profundidade:** o modelo Depth Anything e a geração de imagem não puderam ser baixados neste ambiente (rede
  bloqueada). Os testes usaram o modo heurístico e respostas simuladas; o instalador baixa o modelo na máquina do
  usuário.
- **Áudio:** trilha e efeitos foram avaliados por medidas (LUFS, pico, espectro), não ouvidos.
- **Mão do "passa a mão":** é emoji (lúdica, não cinema).
- **Velocidade:** 2.5D e 3D custam ~1 s/quadro em CPU. A prévia de trecho e o cache evitam refazer.
