# Cenas do anúncio

Todas as cenas ocupam o quadro inteiro (1080x1920), desenhadas em `assets/web/anuncio.html`.
- Fotos são citadas pelo nome do arquivo sem extensão (`"foto": "frente"`).
- `"em": "palavra"` faz o item entrar no instante em que a palavra é dita.
- A legenda fica sempre por cima, em y=1330. A cena pode mudá-la com `legenda_y` ou desligá-la com `"legenda": false`.

| Tipo | Quando usar | Params |
|---|---|---|
| `gancho` | 1ª cena, sempre. Produto cai com impacto e o título entra palavra a palavra. O 1º quadro já mostra título e produto (vira a capa). | `titulo`, `selo` ("SÓ HOJE"), `foto` (usa a foto inteira em vez do recorte), `fundo` |
| `heroi` | Apresentar o produto: flutua, balança em 3D e um brilho passa por ele | `titulo`, `subtitulo`, `altura` |
| `beneficios` | 2 a 4 benefícios com ícone, entrando na palavra falada; produto ao lado | `titulo`, `itens[{texto, icone, em}]` |
| `detalhe` | Zoom num ponto da foto + círculo e seta desenhados + texto à mão | `foto`, `foco: [x, y]` (0..1 na foto), `zoom` (0.6-1.6), `rotulo` |
| `foto` | Foto inteira com movimento lento (lifestyle, uso real) | `foto`, `foco`, `zoom`, `titulo`, `rotulo` |
| `video` | Vídeo do produto (gravado pelo cliente) em tela cheia | `video` (padrão: 1º vídeo do projeto), `inicio` (s), `titulo`, `rotulo` |
| `galeria` | Várias fotos girando em 3D, uma depois da outra | `fotos: [..]`, `cada` (s), `titulo` |
| `comparacao` | "Comum x este" em duas colunas | `esquerda`, `direita`, `linhas[{l, r, em}]` |
| `prova` | Nota com estrelas + número de vendas ou depoimento. **Só com dado real.** | `nota` ("4,9"), `texto` ("+2.000 vendidos") |
| `oferta` | Preço antigo riscado, preço novo batendo na fala, selo de desconto, parcelas | `chamada` ("por apenas"), `extra` ("FRETE GRÁTIS"), `preco_at` (s, automático) |
| `cta` | Última cena. No TikTok Shop o carrinho pulsa e uma seta aponta para o produto fixado; nas outras plataformas, botão com toque | `texto` ("TOQUE NO CARRINHO"), `botao` |
| `continua` | A fala continua a cena anterior | — |

Preço, preço antigo, desconto e parcelas vêm do `produto.json` (`anuncio.py novo --preco ...`).
O roteiro pode sobrescrever com `"produto": {"preco": "..."}`.

## Foto sem recorte bom (produto na mão, foto de ambiente)

O caso mais comum é a foto de celular com o produto na mão. Quando `recorte` diz "foto inteira", as cenas de
produto (`heroi`, `oferta`, `cta`, `prova`) mostram a foto num **cartão** enquadrado no produto.
- Diga onde o produto está na foto principal: `"foco_principal": [x, y]` no `produto.json` (0..1).
- `"zoom_cartao": 1.5` (padrão) aproxima o cartão.
- `gancho`, `foto` e `detalhe` usam a foto inteira.
- Nunca "conserte" o produto: se a mão cobre uma parte, essa parte não aparece. Não se desenha o que não está
  na foto.

## Ícones

Nomes do Lucide (em inglês), lista em `assets/web/icons/`. Exemplos por categoria:
- beleza: sparkles, droplet, sun, flower, leaf, feather, gem;
- eletrônicos: battery-full, bluetooth, headphones, volume-2, zap, wifi, smartphone;
- casa e cozinha: home, chef-hat, cooking-pot, utensils, sofa, lamp, washing-machine;
- moda: shirt, footprints, ruler, gem, crown;
- saúde e fitness: dumbbell, activity, heart-pulse, apple, pill (sem alegação médica);
- entrega e compra: truck, package-check, shield-check, badge-percent, credit-card, gift, clock.

## Cores

Saem sozinhas do recorte do produto: a cor mais viva vira o destaque e o fundo é derivado dela.
- Para forçar a cor: `anuncio.py novo ... --cor "#E8892B"`.
- Para trocar uma cor específica, use `"cores": {"preco": "#00E07A"}` no `produto.json`.

## Estilos

| Estilo | Para | Visual | Som |
|---|---|---|---|
| `tiktok_shop` | Maioria dos produtos, público jovem | Fundo na cor do produto com raios girando, chicote, título Anton, legenda gigante amarela | Batida + whoosh, boom, pop, "plim" de venda |
| `premium` | Beleza, casa, presentes, ticket alto | Fundo claro, serifa, zoom suave, legenda em caixa | Trilha suave, efeitos leves |
| `oferta` | Promoção, queima, data comemorativa | Fundo escuro, preço gigante, selo girando | Batida forte |

Ajuste fino sem criar estilo novo: `"estilo_ajustes": {"raios": false, "transicao": "zoom"}` no roteiro.
