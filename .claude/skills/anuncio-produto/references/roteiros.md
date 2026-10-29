# Roteiros de anúncio por duração

O Claude escreve o `roteiro.json` olhando as fotos do produto e os dados do cliente. Cada **fala** é uma frase
curta (5 a 10 palavras) e abre uma **cena**. Ritmo: uma cena nova a cada 2 a 4 s.

## Quantas palavras cabem

Voz pronta: cerca de 2,3 palavras por segundo. O script mede a voz de verdade e acelera até 1,22x se precisar.
`anuncio.py checar` avisa quando passa ou falta.

| Duração | Palavras | Cenas | Estrutura |
|---|---|---|---|
| 10 s | 18-20 | 3-4 | gancho → produto/benefício → oferta ou CTA |
| 15 s | 28-30 | 4-5 | gancho → produto → 1 benefício forte → oferta → CTA |
| 20 s | 38-42 | 5-6 | gancho → produto → benefícios → detalhe/prova → oferta → CTA |
| 30 s | 58-64 | 7-8 | gancho → problema → produto → benefícios → comparação/detalhe → prova → oferta → CTA |
| 45 s | 90-98 | 9-11 | 30 s + demonstração (vídeo/galeria) + objeção respondida + segunda chamada |
| 60 s | 120-130 | 12-14 | história curta (antes/depois do cliente) + tudo do 45 s |

A duração é o **teto**: um roteiro mais curto gera um vídeo mais curto, o que é melhor do que encher linguiça.

## Fórmulas de gancho (2 primeiros segundos)

Use o que o produto realmente faz. Nunca invente número, prova ou resultado.
- **Pergunta da dor**: "Sua pele tá sem brilho?" / "Cansou de fone que acaba a bateria?"
- **Interrupção**: "Para tudo!" / "Ninguém te conta isso sobre..."
- **Oferta direta** (estilo oferta): "Queima de estoque do X!" / "Esse X tá pela metade do preço."
- **Demonstração**: "Olha o que esse X faz em 3 segundos." (só se houver vídeo mostrando)
- **Comparação**: "Para de gastar com X comum."

## Regras de texto

1. Texto de tela curto: título com até 4 palavras; benefício com até 26 letras.
2. Preços e números exatamente como o cliente passou. A voz lê "R$ 129,90" por extenso sozinha.
3. CTA conforme a plataforma: TikTok Shop "Toca no carrinho", Reels "Comenta EU QUERO" ou "Link na bio",
   Shorts "Link na descrição".
4. Sem alegação absoluta ou de saúde ("cura", "garantido", "emagrece", "100%"): TikTok Shop e Meta reprovam.
   Diga o benefício percebido ("deixa a pele com aspecto iluminado").
5. Prova social só com dado real fornecido (nota, número de vendas, depoimento com autorização).
6. Mesma fala, mesma cena: se uma frase continua o assunto da anterior, use `"cena": "continua"`.

## Formato

```json
{
  "duracao": 20,
  "voz": "dora",                         // ou {"arquivo": "minha_voz.m4a"} para a voz do cliente
  "velocidade": 1.08,                    // opcional (voz pronta)
  "estilo": "tiktok_shop",               // tiktok_shop | premium | oferta
  "musica": "batida",                    // batida | suave | nenhuma | "trilha.mp3" (licença do cliente)
  "falas": [
    {"texto": "Sua pele tá sem brilho?", "cena": {"tipo": "gancho", "titulo": "Pele sem brilho?"}},
    {"texto": "Conheça o sérum LUMA.", "cena": {"tipo": "heroi", "titulo": "LUMA Vitamina C"}},
    {"texto": "Ilumina e uniformiza o tom.", "cena": {"tipo": "beneficios", "itens": [
      {"texto": "Ilumina a pele", "icone": "sparkles", "em": "Ilumina"},
      {"texto": "Uniformiza o tom", "icone": "sun", "em": "uniformiza"}]}},
    {"texto": "De R$ 199,90 por R$ 129,90.", "cena": {"tipo": "oferta"}},
    {"texto": "Toca no carrinho e garante o seu!", "cena": {"tipo": "cta"}}
  ]
}
```

Várias durações do mesmo produto: um arquivo por versão (`roteiro_15s.json`, `roteiro_30s.json`) e
`anuncio.py versoes <projeto> --roteiros roteiro_15s.json roteiro_30s.json`.

## Voz do cliente

O cliente grava pelo celular lendo o roteiro (pode improvisar um pouco). Coloque o arquivo na pasta do
projeto e use `"voz": {"arquivo": "minha_voz.m4a"}`. O script:
- limpa o ruído e encurta pausas maiores que 0,35 s;
- transcreve e alinha com o roteiro. A legenda usa a grafia do roteiro, então nomes e preços saem certos.

Se o alinhamento ficar abaixo de 60%, leia `work/<roteiro>/transcricao.txt` e reescreva as falas com o que ele
disse. Áudio gerado no ElevenLabs ou em outro serviço entra do mesmo jeito.
