# Ficha da oferta — o arquivo que guarda tudo

Cada projeto mora numa pasta `vsl/<slug>/` (no Claude Code) ou num bloco **FICHA DA OFERTA** que a IA atualiza na
conversa (no Claude.ai / ChatGPT). Tudo que as etapas decidem vai para a ficha; os scripts só leem a ficha.

```
vsl/<slug>/
  ficha.json          dados da oferta (abaixo)
  roteiro.md          roteiro da VSL em blocos  (## Nome do bloco  — uma linha por frase falada)
  pagina.html         página de vendas gerada   (scripts/pagina.py)
  teleprompter.html   roteiro rolando na tela   (scripts/teleprompter.py)
  calendario.md/.ics  plano dia a dia           (scripts/calendario.py)
  criativos.md        roteiros de anúncio
  copies.md           headlines, e-mails, mensagens de WhatsApp, textos do checkout
```

## ficha.json

Campo vazio = ainda não decidido. `[HIPÓTESE]` no começo de um texto = a IA propôs e o cliente ainda não confirmou
(a página mostra esses trechos com fundo amarelo no modo rascunho, para ninguém publicar sem revisar).

```json
{
  "slug": "metodo-x",
  "etapa": "diagnostico",
  "criado_em": "2026-10-22",
  "produto": {
    "nome": "Método X",
    "formato": "curso online | mentoria | e-book | físico | serviço | software | comunidade",
    "entrega": "como e quando o cliente recebe",
    "preco": 297,
    "preco_ancora": 997,
    "parcelas": 12,
    "valor_parcela": 30.72,
    "moeda": "BRL",
    "checkout_url": "https://...",
    "garantia_dias": 7,
    "garantia_texto": "texto da garantia"
  },
  "publico": {
    "quem": "descrição concreta (idade, rotina, contexto)",
    "consciencia": "inconsciente | problema | solução | produto | mais_consciente",
    "dores": ["..."], "desejos": ["..."], "objecoes": ["..."], "medos": ["..."],
    "palavras": ["expressões que o público usa"]
  },
  "oferta": {
    "promessa": "resultado em uma frase",
    "prazo_resultado": "em quanto tempo",
    "big_idea": "a ideia central / ângulo",
    "mecanismo_problema": {"nome": "", "explicacao": ""},
    "mecanismo_solucao": {"nome": "", "explicacao": ""},
    "stack": [{"item": "Módulo 1 — ...", "descricao": "", "valor": 497}],
    "bonus": [{"nome": "", "descricao": "", "valor": 197}],
    "escassez": "motivo REAL de urgência (ou vazio)",
    "order_bump": {"nome": "", "preco": 0},
    "upsell": {"nome": "", "preco": 0}
  },
  "autor": {"nome": "", "credencial": "", "historia": "", "foto": "autor.jpg"},
  "provas": [{"tipo": "depoimento | print | número | caso", "texto": "", "nome": "", "imagem": ""}],
  "faq": [{"p": "", "r": ""}],
  "vsl": {
    "duracao_min": 12,
    "delay_oferta_s": 540,
    "embed": "código <iframe>/<script> do player (YouTube, Vimeo, Panda, VTurb) ou link do Drive",
    "status": "roteiro | gravando | editando | publicado"
  },
  "pagina": {
    "headline": "", "subheadline": "", "aviso_play": "⚠️ Assista até o final — o vídeo sai do ar em breve",
    "chamada_botao": "QUERO COMEÇAR AGORA",
    "bullets": ["o que a pessoa leva"],
    "para_quem": ["é para você se..."], "nao_para_quem": ["não é para você se..."],
    "rodape": "CNPJ / contato / termos"
  },
  "marca": {"cor": "#7C5CFF", "cor2": "#22C55E", "fundo": "#0B0B12", "texto": "#F5F5F7", "fonte": "system"},
  "trafego": {"canal": "Meta | TikTok | Google | orgânico | lista", "verba_dia": 50},
  "lancamento": {"inicio": "2026-11-03", "horas_por_dia": 2}
}
```

Etapas (`etapa`), na ordem: `diagnostico` → `publico` → `oferta` → `angulos` → `roteiro` → `pagina` → `gravacao`
→ `edicao` → `criativos` → `lancamento` → `otimizacao`.
