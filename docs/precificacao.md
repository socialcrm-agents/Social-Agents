# Precificação: custos reais e escada de produtos

Valores de 22/10/2026. Os preços em dólar viraram reais a **R$ 5,50 por US$ 1** (ajuste pelo câmbio do dia).
Itens marcados com *estimativa* ainda precisam ser medidos em produção. O servidor do WhatsApp grava os tokens
de cada vídeo no banco para isso.

## 1. O produto é um só; o que muda é o pacote

O código continua inteiro neste repositório (perfil "completo"). O empacotador só escolhe o que entra em
cada zip:

| Comando | Zip | Para quem |
|---|---|---|
| `python3 tools/empacotar.py editor-video --perfil corte-viral` | **Corte Viral** (front): 38 arquivos, 0,7 MB, sem Node/Chromium | todo comprador |
| `python3 tools/empacotar.py editor-video --perfil motion` | **Pacote Motion 3D**: só o que falta ao front. O cliente descompacta por cima e vira "completo". | upsell |
| `python3 tools/empacotar.py editor-video` | completo | você, parceiros, licença de agência |
| `python3 tools/empacotar.py anuncio-produto` | anúncio de produto | outro funil |

Testado do zero numa pasta limpa:
- **Só o front instalado:** editou um vídeo de 48 s sem Node nem Chromium e pulou as 4 animações que o plano
  sugeriu. Quando foram pedidas, avisou que elas fazem parte do Pacote Motion.
- **Motion por cima:** o `setup.py` passou a mostrar "pacote completo" e as animações voltaram a ser renderizadas.

## 2. Quanto custa cada vídeo para você

### Skill (front e Motion): custo marginal zero
O comprador roda no computador dele, com o plano Claude dele (o Claude Code exige plano pago). Seu custo
é só a IA tira-dúvidas:

| Atendente | Custo por pergunta | 1.000 perguntas/mês |
|---|---|---|
| Claude Opus 5.5 (padrão, effort low, base em cache) | ~US$ 0,01-0,015 (~R$ 0,07) | ~R$ 70 |
| Claude Haiku 5.5 | ~US$ 0,0005 (~R$ 0,003) | ~R$ 3 |

A base de conhecimento tem ~4 mil tokens e fica em cache. Preços por milhão de tokens:
- **Opus 5.5:** US$ 4 de entrada, US$ 20 de saída e US$ 0,20 de leitura de cache.
- **Haiku 5.5:** US$ 0,10 de entrada e US$ 0,50 de saída.

### SaaS "Editor no WhatsApp": custo variável por vídeo de 30-60 s

| Item | Base do cálculo | Custo/vídeo |
|---|---|---|
| **Cérebro** (Claude decide cortes, gancho, CTA e animações) | Opus 5.5: ~6 mil tokens de regras em cache + ~2 mil de transcrição + ~4 mil de saída, mais 2 correções (*estimativa*) | ~US$ 0,15 = **R$ 0,85** |
| **CPU de render** | Medido: ~85 s (primeiro render) + ~30 s por correção, em 4 núcleos. Servidor Hetzner CCX23 ≈ €86/mês ≈ US$ 0,13/h | ~US$ 0,005 = **R$ 0,03** |
| **WhatsApp** | O cliente inicia a conversa. As primeiras 1.000 mensagens de atendimento por mês são grátis; depois, ~US$ 0,007 cada (fontes divergem). ~4 mensagens por vídeo. | até **R$ 0,15** |
| **Armazenamento** | Vídeos apagados após 7 dias | ~R$ 0 |
| **Total variável** | | **~R$ 1,00 por vídeo** (~R$ 0,60 com Sonnet 5.5 no cérebro) |

**Custo fixo:**
- 1 servidor de 4 núcleos (~R$ 520/mês) processa cerca de 25-30 vídeos por hora, no máximo ~18 mil por mês;
  na prática, contando picos, 6 a 9 mil;
- número de WhatsApp Business;
- domínio;
- você ou alguém para o atendimento humano.

Taxa do meio de pagamento: ~4-6% (varia por plataforma).

## 3. Escada sugerida

| Degrau | Produto | Preço sugerido | Seu custo | Margem bruta |
|---|---|---|---|---|
| Front | **Corte Viral** (skill) + IA tira-dúvidas + 30 ganchos + vídeo de instalação | **R$ 97** (lançamento R$ 67) | ~R$ 1 de atendimento por cliente | ~93% (descontada a taxa) |
| Order bump | **Kit de Marca + 50 ganchos por nicho** | R$ 27 | 0 | ~95% |
| Upsell 1 | **Pacote Motion 3D** (23 animações, gatilhos, versões 15/30 s, 16:9) | **R$ 197** | 0 | ~95% |
| Upsell 2 (recorrente) | **Editor no WhatsApp: Start**, 10 vídeos/mês até 60 s, 3 correções cada | **R$ 97/mês** | ~R$ 10-15 | ~85% |
| | **Pro**: 30 vídeos/mês, Motion 3D, kit de marca, versões 15/30 s | **R$ 197/mês** | ~R$ 45-60 (versões renderizam mais) | ~70-75% |
| | **Agência**: 100 vídeos/mês, 5 marcas, sem marca d'água, prioridade na fila | **R$ 597/mês** | ~R$ 150-200 | ~65-75% |
| Avulso | Vídeo extra no WhatsApp | R$ 7/vídeo | ~R$ 1 | ~85% |
| Topo | **Licença de agência** (pacote completo instalado + kits de marca ilimitados + onboarding) | R$ 1.997 ou mais/ano | horas suas | alta |

- **Ponto de equilíbrio do servidor:** 6 assinantes Start (6 × R$ 97 ≈ R$ 580) pagam a máquina do mês.
- **Ganho de escala:** 10 assinantes Pro (R$ 1.970) pagam o servidor e o custo variável e deixam ~R$ 950 de margem bruta.

## 4. Por que esses preços (e como validar)

- **Preço por valor, não por custo.** O vídeo custa ~R$ 1 para você. O preço vem do que o cliente economiza:
  horas de edição ou um editor contratado.
- **O front não pode depender de você.** A skill roda no computador do cliente, então vender 1.000 cópias não
  aumenta seu custo. O risco está no suporte de instalação, e é isso que a IA tira-dúvidas absorve.
- **O SaaS é o motor de receita recorrente.** Comece só com o plano Pro (um plano só simplifica o lançamento),
  meça o uso real (tokens e minutos de CPU por vídeo ficam gravados) e então abra Start e Agência.
- **Limites protegem a margem.** Vídeos de até 60 s no Start, 3 correções por vídeo e versões extras contando
  como vídeo. Vídeo longo (aula, podcast) só no Agência ou como crédito extra.
- **Plano anual com 2 meses grátis** melhora o caixa e reduz cancelamento.

## 5. O que ainda precisa ser medido antes de cravar o preço

1. Tokens reais do cérebro por vídeo: o worker grava o uso de cada chamada.
2. Tamanho médio dos vídeos que os clientes mandam (duração, qualidade) e o tempo real de render.
3. Taxa de correções por vídeo.
4. Tarifa oficial do WhatsApp no seu número (veja a página de preços da Meta). As fontes de terceiros divergem.
5. Quantas perguntas chegam ao suporte por comprador do front.

Fontes de preços de terceiros:
- WhatsApp Business no Brasil: [Message Central](https://www.messagecentral.com/blog/whatsapp-business-api-pricing-in-brazil),
  [Blueticks](https://blueticks.co/blog/whatsapp-business-api-pricing-2026),
  [WABA Index](https://wabaindex.com/learn/whatsapp-api-pricing-brazil)
- Limite de vídeo enviado (16 MB): [documentação da Meta](https://developers.facebook.com/documentation/business-messaging/whatsapp/business-phone-numbers/media)
- Servidores Hetzner após o reajuste de 2026: [Northflank](https://northflank.com/blog/hetzner-cloud-server-price-increases)

Preços da Claude API: tabela oficial da Anthropic (Opus 5.5, Sonnet 5.5, Haiku 5.5).
