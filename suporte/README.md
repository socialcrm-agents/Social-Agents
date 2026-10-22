# IA tira-dúvidas do Editor Viral

| Arquivo | Conteúdo |
|---|---|
| `base-conhecimento.md` | O que o atendente sabe: produtos, instalação (Mac/Windows/Linux), leitura do `setup.py`, erros comuns, como pedir edições, tempos, limites |
| `prompt-sistema.md` | Tom e regras (responde só pela base, não promete resultado, pede o sistema e um print do erro, encaminha com `[ENCAMINHAR_HUMANO]`) |
| `bot.py` | Atendente pela Claude API: modo terminal e a função `responder(historico, pergunta)` para o servidor do WhatsApp |

## Rodar

```bash
pip install anthropic
export ANTHROPIC_API_KEY=...          # ou: ant auth login
python3 suporte/bot.py                # conversa no terminal
```

Variáveis:
- `ATENDENTE_MODELO`: padrão `claude-opus-5-5`; `claude-haiku-5-5` é cerca de 40x mais barato.
- `ANTHROPIC_BASE_URL`: opcional, para proxy.

No servidor do WhatsApp:

```python
from bot import responder
historico = []                         # um por cliente (guarde por número de telefone)
texto = responder(historico, mensagem)
if "[ENCAMINHAR_HUMANO]" in texto:     # avise a equipe e tire a marca antes de enviar
    texto = texto.replace("[ENCAMINHAR_HUMANO]", "").strip()
```

## Custo aproximado por pergunta

O system (prompt + base) tem cerca de 4 mil tokens e vai em cache. A conta abaixo assume histórico curto e uma
resposta de cerca de 300 tokens (mais o raciocínio em effort "low").

| Modelo | 1ª pergunta (grava o cache) | Perguntas seguintes (cache lido) |
|---|---|---|
| Opus 5.5 ($4 entrada / $20 saída / $0,20 cache lido, por milhão) | ~US$ 0,03 | ~US$ 0,01-0,015 |
| Haiku 5.5 ($0,10 / $0,50, por milhão) | ~US$ 0,001 | ~US$ 0,0005 |

- Uma conversa típica de suporte (5-8 perguntas) sai por cerca de **US$ 0,10 no Opus** e menos de **US$ 0,01 no
  Haiku**.
- O `bot.py` imprime em cada resposta os tokens reais (entrada, cache e saída), para conferir o custo de verdade.

## Atualizar

Edite `base-conhecimento.md` quando mudar instalação, preço ou recurso. O bot lê o arquivo a cada pergunta. A
primeira pergunta depois de uma edição grava o cache de novo.

## Ainda não testado

Não foi testado contra a API real. O teste usou um servidor falso local: confirmou a montagem da requisição
(modelo, effort, cache) e a leitura da resposta. A qualidade das respostas precisa ser avaliada com perguntas
reais de clientes.
