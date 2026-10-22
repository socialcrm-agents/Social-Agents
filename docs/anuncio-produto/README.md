# Anúncio de produto (Claude Code Skill)

Skill: [`.claude/skills/anuncio-produto`](../../.claude/skills/anuncio-produto/SKILL.md). Produto separado do editor de
vídeo: tem pasta, dependências e pacote de venda próprios (`python3 tools/empacotar.py anuncio-produto`).

```
fotos/vídeo do produto + nome + preço
   ─► recorte   (IS-Net: produto sem fundo + cores dele)               ◄── Claude olha as fotos
   ─► roteiro   (Claude escreve: gancho, benefícios, oferta, CTA) ─► checar (tamanho x duração, promessas)
   ─► voz       (Kokoro/Piper offline, ou gravação do cliente alinhada com Parakeet)
   ─► cenas     (HTML no Chromium: 11 tipos de cena + legenda palavra por palavra)
   ─► mix       (voz -14 LUFS + trilha sintetizada com ducking + efeitos) ─► renders/<roteiro>_vN.mp4
```

## Teste (22/10/2026, CPU de 4 núcleos, sem GPU)

Produto de teste **fictício** ("Sérum LUMA Vitamina C"): os bancos de imagem estão bloqueados nesta nuvem, então
as 3 fotos e o vídeo girando foram renderizados em 3D aqui mesmo. O teste definitivo é com fotos reais do cliente.

| Versão | Voz | Estilo | Cenas | Duração | Tempo total |
|---|---|---|---|---|---|
| 20 s | dora (feminina, Kokoro) | tiktok_shop | gancho, herói, benefícios, detalhe, oferta, CTA | 20,3 s | 48 s (1ª vez: 88 s com recorte e voz) |
| 30 s | alex (masculina, Kokoro) | premium | gancho, vídeo do produto, benefícios, comparação, galeria, oferta, CTA | 26,2 s | 55 s |
| 15 s | faber (masculina, Piper) | oferta | gancho com selo, herói, oferta, CTA | 12,5 s | 30 s |
| 20 s | gravação "do cliente" (simulada com outra voz, com pausas e improviso) | tiktok_shop | 5 cenas | 19,8 s | 45 s |

- **Gravação do cliente**:
  - pausas encurtadas: 21,2 s → 18,4 s de fala;
  - 82% do roteiro alinhado com a fala;
  - o "Gente," improvisado ficou fora da legenda.
  
  A transcrição ouviu o preço errado ("209,90%"), mas a legenda usa a grafia do roteiro e o preço saiu certo.
- **Vozes**: transcrevendo de volta as 6 vozes, o texto saiu idêntico ao roteiro (números e preços por extenso).
- **QA visual**: um quadro por cena e o 1º quadro (capa). Bugs encontrados e corrigidos:
  - título com palavra sozinha na linha;
  - produto encostando no título;
  - legenda sobre o CTA;
  - ícone do carrinho pequeno;
  - selo de desconto girando de cabeça para baixo;
  - legenda em caixa partida palavra por palavra;
  - comparação ilegível em fundo claro;
  - 1º quadro vazio.

## Durações e planos

A skill gera 10, 15, 20, 30, 45 e 60 s. A duração é o teto: o roteiro decide quanto falar.
Planos como "10 e 20 s grátis, 30 s ou mais pago" são regra da camada de venda (site/serviço), não da skill.

## Limitações

- **Recorte**:
  - funciona muito bem com fundo liso;
  - com fundo poluído ou vários objetos encostados, pode levar o objeto vizinho junto (no teste, uma laranja
    encostada no frasco veio junto na foto de ângulo);
  - o script escolhe sozinho a foto com o melhor recorte para as cenas de produto.
- **Vozes prontas**:
  - 1 feminina (Kokoro) e 5 masculinas; o Piper não tem voz feminina pt-BR de qualidade publicada;
  - não testei a naturalidade de ouvido, só a inteligibilidade (transcrição). Ouça as amostras em
    `vozes/amostras/` e escolha;
  - voz premium (ElevenLabs etc.) entra como "gravação": gere o áudio lá e passe o arquivo.
- **Sem vídeo gerado por IA**: as cenas animam as fotos (zoom, 3D, brilho, galeria) e o vídeo do cliente, sem
  gerar filmagem nova. Para cenas geradas (pessoa usando o produto), use Veo, Kling ou Runway e traga o MP4 como
  `video`.
- **Trilha sintetizada**: simples (batida pop em lá menor ou pad suave). É livre de direitos, mas não tem
  produção de estúdio. Música licenciada do cliente entra por arquivo.
- **Rótulo de IA**: com voz sintética, ative o rótulo de conteúdo de IA na plataforma (`references/politicas.md`).
- **Formato**: só 9:16 por enquanto, que é o formato do TikTok Shop, do Reels e do Shorts.

## Licenças

| Item | Licença | Observação |
|---|---|---|
| Kokoro-82M (voz) | Apache-2.0 | uso comercial ok |
| Vozes Piper pt_BR (faber, cadu, jeff) | dataset CC0 (OHF-Voice) | uso comercial ok |
| IS-Net / U2-Net (recorte) | Apache-2.0 | modelos baixados das releases do rembg no GitHub |
| Parakeet TDT v3 (voz do cliente, opcional) | CC-BY-4.0 | citar NVIDIA nos créditos |
| sherpa-onnx, onnxruntime | Apache-2.0 / MIT | |
| Fontes Anton, Poppins, DM Serif Display, Caveat | SIL OFL 1.1 | incluídas |
| Ícones Lucide | ISC | subconjunto de 160 ícones incluído |
| Trilha e efeitos | gerados pelo script | sem terceiros |
| Playwright/Chromium, ffmpeg | Apache-2.0 / LGPL-GPL | instalados à parte, usados como programas externos |
