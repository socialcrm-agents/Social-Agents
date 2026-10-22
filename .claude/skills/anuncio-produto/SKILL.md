---
name: anuncio-produto
description: "Transforma fotos (ou vídeo) de um produto num anúncio de venda em vídeo 9:16 pronto para TikTok Shop, Reels e Shorts, de 10 a 60 segundos: recorta o produto, escreve o roteiro de venda, narra com voz pronta em português (feminina ou masculina, offline) ou com a voz gravada do cliente, monta cenas animadas (gancho, produto girando, benefícios com ícones, zoom em detalhe, comparação, galeria, preço de/por com selo de desconto, CTA do carrinho), legenda palavra por palavra, trilha e efeitos sonoros sem direitos autorais, e exporta MP4. Use com /anuncio-produto ou pedidos como 'meu produto vira vídeo', 'faz um anúncio desse produto', 'vídeo de venda pro TikTok Shop', 'anúncio de 15/30 segundos com essa foto', 'usa a minha voz no anúncio'."
---

# /anuncio-produto

Foto do produto entra, anúncio de venda sai. O cliente manda fotos (de preferência 2 a 5: frente, ângulo, detalhe,
em uso) e, se tiver, um vídeo curto do produto. Diz o nome, o preço e para onde é o anúncio. Você escreve o
roteiro, escolhe as cenas e entrega o MP4.

`SK` = pasta desta skill. `PY` = `python3` (Windows: `python`). Scripts em `SK/scripts/`.

## 0. Pré-requisitos (uma vez por máquina)

```bash
PY -m pip install -r SK/requirements.txt
PY SK/scripts/setup.py --models          # vozes + recorte (~450 MB); --voz-propria para usar a voz do cliente
npm install -g playwright && npx playwright install chromium
PY SK/scripts/setup.py                   # tem que terminar em READY
```

## 1. Intake (pergunte só o que faltar, numa mensagem só)

- **Fotos/vídeos** do produto (obrigatório). Quanto melhor a foto, melhor o recorte: fundo liso e produto inteiro.
- **Nome**, **preço** (e preço antigo/desconto/parcelas se houver promoção). Sem preço, não use a cena `oferta`.
- **Plataforma**: TikTok Shop (padrão), Reels ou Shorts.
- **Duração**: 10, 15, 20, 30, 45 ou 60 s (padrão 20). Pode pedir várias.
- **Voz**: pronta (`dora` feminina, `alex`/`santa`/`faber`/`cadu`/`jeff` masculinas; `anuncio.py vozes`) ou a
  gravação dele lendo o roteiro (você manda o roteiro, ele grava no celular).
- **Estilo**: `tiktok_shop` (padrão), `premium` (beleza, casa, ticket alto) ou `oferta` (promoção).
- **Diferenciais reais**: o que o produto faz, para quem é e prova que exista (nota, vendidos). Não invente nada.

```bash
PY SK/scripts/anuncio.py novo <projeto> --fotos f1.jpg f2.jpg [--videos v.mp4] --nome "Nome" \
   [--preco "R$ 129,90" --preco-antigo "R$ 199,90" --desconto 35% --parcelas "ou 3x de R$ 43,30"] \
   [--estilo tiktok_shop] [--plataforma tiktok_shop|reels|shorts]
PY SK/scripts/anuncio.py recorte <projeto>      # recorta o produto, diz qual foto serve de "herói"
```

## 2. Olhe as fotos e escreva o roteiro (este é o seu trabalho)

1. Abra cada foto (Read) e o resultado do recorte (`work/recortes.json`, `work/recortes/*.png`): veja o que é o
   produto, textura, detalhes, embalagem, texto do rótulo, e qual foto tem o melhor recorte. Sem recorte bom
   (produto na mão), ponha `"foco_principal": [x, y]` no `produto.json` (ver `cenas.md`). Benefícios só do
   que se vê ou do que o cliente disse: material, cor e formato, sim; "proteção UV" ou "polarizado", só com a
   informação dele.
2. Leia `SK/references/roteiros.md`, que traz palavras por duração, fórmulas de gancho e regras. Depois leia
   `SK/references/cenas.md`, com os tipos de cena e seus params.
3. Escreva `<projeto>/roteiro.json`; para outras durações, `roteiro_15s.json`, `roteiro_30s.json`...
   - 1ª cena `gancho`, última `cta`. Uma cena a cada 2 a 4 s.
   - `detalhe` com `foco` no ponto que importa, olhando a foto: textura, botão, tampa, costura.
   - Benefícios com `"em"` na palavra falada.
   - Só dados reais. Preço "de/por" só se o cliente informou.
4. `PY SK/scripts/anuncio.py checar <projeto> [--roteiro roteiro_15s.json]` e corrija o que ele apontar.

Mostre o roteiro ao cliente numa tabela curta (fala → cena) **só se ele pediu para aprovar antes**. Caso
contrário, gere direto.

## 3. Gere

```bash
PY SK/scripts/anuncio.py tudo <projeto> [--roteiro roteiro_15s.json]          # recorte + checar + voz + render
PY SK/scripts/anuncio.py versoes <projeto> --roteiros roteiro_15s.json roteiro_30s.json   # várias durações
```
Rode em segundo plano. Tempo de referência (4 núcleos, sem GPU): cerca de 50 s para um anúncio de 20 s; a voz
só é regerada quando o texto muda e as cenas só quando a imagem muda. `--rascunho` faz uma prévia a 15 fps.
Saída: `renders/<roteiro>_vN.mp4` e `qa/<roteiro>_vN_cenas.jpg`.

## 4. Confira antes de entregar (obrigatório)

Abra `qa/..._cenas.jpg`, que mostra um quadro por cena. Confira:
- texto cortado ou sobreposto;
- produto encostando no título;
- preço certo;
- legenda legível;
- CTA apontando para o carrinho (TikTok Shop).

Extraia o 1º quadro (`ffmpeg -i x.mp4 -frames:v 1 capa.jpg`): ele é a capa e precisa mostrar título e produto.
Se achou problema, corrija o roteiro ou os params e gere de novo. Só entregue o que você viu.

## 5. Correções por texto

O cliente pede em linguagem natural; você edita o `roteiro.json` e roda `tudo` de novo (o cache refaz só o
necessário):
- "troca a voz por masculina": `"voz": "alex"`;
- "mais rápido": `"velocidade": 1.15`;
- "sem música": `"musica": "nenhuma"`;
- "mais premium": `"estilo": "premium"`;
- "tira a cena do detalhe": remova a cena (ou `"cena": "continua"`);
- "muda o título do começo": edite `titulo` no gancho;
- "cor azul": `"cor": "#2B6BFF"` no `produto.json`;
- "põe frete grátis": `"extra": "FRETE GRÁTIS"` na cena `oferta`.

## 6. Entrega

Envie o MP4 (e as outras durações). Diga em poucas linhas: duração, voz, estilo e cenas usadas. Lembre:
- se a voz é sintética, ele deve ativar o rótulo de conteúdo de IA ao publicar (`references/politicas.md`);
- o preço "de" precisa ter sido praticado de verdade.

## Regras fixas

1. Nada de inventar benefício, número, nota, depoimento ou preço. Só o que o cliente informou ou o que se vê na foto.
2. Sem alegação absoluta ou de saúde (o `checar` barra as mais comuns).
3. Nada importante abaixo de y=1480 nem à direita de x=930 (interface do TikTok/Reels).
4. Fotos, vídeos e músicas só do cliente ou licenciados. Nunca use foto de concorrente ou logo de terceiros.
5. Voz de pessoa real só com a gravação ou a autorização dela.
