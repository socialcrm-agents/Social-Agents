# Editor no WhatsApp (MVP)

A pessoa manda um vídeo no WhatsApp e, em cerca de 2 minutos, recebe o vídeo editado de volta. Depois pode
pedir correções em texto ("legenda maior", "tira o começo", "estilo premium"). O motor é a skill
`.claude/skills/editor-video`; este serviço não copia o código dela, só a chama. O cliente nunca vê o código.

```
WhatsApp ─► Meta (Cloud API) ─► POST /webhook (app.py) ─► fila SQLite (fila.py)
                                                              │
                     worker.py ◄──────────────────────────────┘
                     run.py new → transcribe → analyze → cérebro (Claude API) → edit.py → render
                     → comprime < 15 MB (H.264 Main, sem B-frames, AAC, faststart) → envia vídeo + resumo
```

| Arquivo | Papel |
|---|---|
| `app.py` | Webhook: verificação da Meta, assinatura, vídeo → job, texto → comando ou correção, link de download |
| `fila.py` | SQLite: jobs, créditos por telefone, tokens e custo de IA por job |
| `worker.py` | Roda o editor de verdade, um job por vez; 1 nova tentativa; devolve o crédito se falhar; apaga arquivos antigos |
| `cerebro.py` | Claude API com saída estruturada: decide cortes, gancho, CTA, animações e efeitos; entende correções. Sem chave, usa as regras da skill e um mapa de pedidos comuns |
| `whatsapp_api.py` | Graph API: baixar mídia, subir mídia, enviar texto e vídeo (só biblioteca padrão) |
| `teste_local.py` | Teste ponta a ponta com uma Graph API falsa, sem nenhuma credencial |

## O que criar na Meta
1. Conta no **Meta Business** e um app do tipo **Business** em developers.facebook.com, com o produto **WhatsApp**.
2. Um **número de telefone** dedicado (não pode estar em uso no WhatsApp comum) e o nome de exibição aprovado.
3. Um **System User** com a permissão `whatsapp_business_messaging`, que gera o **token permanente** (`WA_TOKEN`).
4. O **Phone Number ID** (`WA_PHONE_NUMBER_ID`) e o **App Secret** (`WA_APP_SECRET`).
5. Webhook: URL `https://seu-dominio/webhook`, verify token igual a `WA_VERIFY_TOKEN` e assinatura do campo
   `messages`.
6. Forma de pagamento na conta do WhatsApp Business, para mensagens fora da janela de 24 h.

## Rodar local
```bash
pip install -r requirements.txt -r ../../.claude/skills/editor-video/requirements.txt
cp config.example.env .env && set -a && . ./.env && set +a
uvicorn app:app --port 8000            # webhook
python3 worker.py                      # outro terminal
# a Meta precisa de HTTPS público: use um túnel (cloudflared tunnel --url http://localhost:8000)
python3 teste_local.py video.mp4       # teste sem credenciais (Graph API falsa)
```

## Deploy sugerido
- 1 servidor com **4 vCPU / 16 GB** roda o webhook e o worker.
  - Um vídeo de 30 a 50 s leva ~1,5 min de CPU, então cabem cerca de **30 a 40 vídeos por hora** por servidor.
  - Para crescer, rode mais workers em outras máquinas apontando para a mesma fila.
  - Nesse ponto troque o SQLite por Postgres e a pasta local por armazenamento de objetos (S3/R2).
- Modelos da skill: `setup.py --models` uma vez no servidor.
- Para o motion 3D funcionar, o servidor precisa de Node + Playwright + Chromium.

## Custo por vídeo (estimativa; confira os preços oficiais)
| Item | Custo |
|---|---|
| Claude API (cérebro), Opus 5.5 a US$ 4 / 20 por milhão de tokens; ~6-12 mil tokens de entrada e ~3-6 mil de saída (inclui raciocínio) | **~US$ 0,05-0,17** por vídeo; correção ~US$ 0,03-0,10. O custo real de cada job fica na tabela `uso` (`GET /saude`) |
| CPU (~1,5 min de um servidor de 4 vCPU) | ~US$ 0,003-0,02, conforme o provedor |
| WhatsApp | Mensagens de resposta dentro da janela de 24 h aberta pelo cliente: a Meta cobra por mensagem e as regras mudam; confira a página oficial de preços da Meta. Mensagens de template (marketing ou cobrança) fora da janela são pagas (~US$ 0,06-0,07 marketing, ~US$ 0,007 utilidade no Brasil, segundo tabelas de terceiros de out/2026) |

## Privacidade
- Vídeos e projetos são apagados após `APAGAR_APOS_DIAS` (padrão 7).
- O link de download (vídeo > 15 MB) usa o nome aleatório da pasta do projeto (não expõe o telefone). Em
  produção, acrescente validade curta ao link.
- Não use os vídeos dos clientes para nada além da edição. Isso vai nos termos de uso.

## O que falta para produção
- **Pagamento**: planos e créditos via checkout (Hubla, Stripe, Mercado Pago) com webhook que chama
  `fila.add_creditos`. Hoje o texto "<link do checkout>" é um marcador.
- **Painel** do cliente e do admin: histórico, créditos, custo por vídeo, reprocessar.
- **Escala**: Postgres, armazenamento de objetos, vários workers, limite de duração e de tamanho por plano, fila
  com prioridade para planos pagos.
- **Termos de uso e LGPD**: consentimento, retenção, pedido de exclusão, DPA com a Meta e a Anthropic.
- **Monitoramento**: alerta de fila parada, de falha de envio e de custo por dia.

## Testado aqui (22/10/2026, 4 vCPU, sem GPU, sem credenciais)
Webhook simulado com um vídeo real de 51 s, pipeline real do editor, sem o cérebro (sem chave de API):
| Etapa | Tempo | Resultado |
|---|---|---|
| Vídeo novo | 89 s (1º, com modelos frios: 120 s) | 48,8 s editado, enviado com **14,5 MB** (H.264 Main, sem B-frames) |
| Correção "deixa a legenda maior" | 58 s | nova versão com legenda 135 px, enviada |
| Comandos | — | "saldo" respondeu; pedido sem sentido ("faz chover confete roxo") recebeu a mensagem de ajuda |

Não testado:
- a chamada real da Claude API (falta chave);
- a Meta real (faltam app, número e token);
- o envio por link de vídeos com mais de 15 MB.
