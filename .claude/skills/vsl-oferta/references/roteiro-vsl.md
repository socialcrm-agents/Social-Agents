# Etapa 5 — Roteiro da VSL

## Tamanho

Fala natural em português: **130 a 150 palavras por minuto**. Calcule o total pela duração escolhida no diagnóstico
(12 min ≈ 1.700 palavras). Mais curto que o necessário não sobra espaço para prova; mais longo do que o ticket pede
cansa. Na dúvida, mais curto.

## Os blocos e quanto tempo cada um ocupa

Percentuais de uma VSL de 10–15 min. Ajuste proporcionalmente.

| # | Bloco | % | O que precisa acontecer |
|---|-------|---|-------------------------|
| 1 | **Gancho** | 3–5% | Prender nos primeiros 15–30 s com o ângulo escolhido. Prometer o que ela vai descobrir. |
| 2 | **Promessa + quem sou** | 4–6% | Uma frase de promessa e uma credencial curta. A história completa vem depois. |
| 3 | **Identificação** | 8–10% | Descrever a vida dela com as cenas e palavras da etapa 2. Ela tem que pensar "sou eu". |
| 4 | **Por que nada funcionou** | 8–10% | Mecanismo do problema com nome. Tira a culpa dela. Desmonta as saídas comuns. |
| 5 | **A descoberta** | 10–12% | Sua história de virada e o mecanismo da solução com nome. Lógica simples e visual. |
| 6 | **Prova** | 10–12% | Casos com nome, número e prazo. Antes → o que fez → depois. Pelo menos 3. |
| 7 | **Como funciona** | 8–10% | O método em 3–5 passos. Dá vontade sem entregar tudo. |
| 8 | **Para quem é / não é** | 3–4% | Qualifica. Aumenta a confiança. |
| 9 | **Oferta (stack)** | 8–10% | Cada item com o resultado que entrega e o valor. ← **a oferta aparece na página aqui** |
| 10 | **Bônus** | 4–6% | Cada bônus resolve uma objeção. |
| 11 | **Preço com ancoragem** | 4–5% | Custo do problema → valor total → preço em parcela → à vista. |
| 12 | **Garantia** | 3–4% | Com nome, prazo e a frase "o risco é todo meu". |
| 13 | **Urgência** | 2–3% | Só se real. Senão, custo de esperar. |
| 14 | **Chamada para ação** | 3–4% | O que fazer agora, literalmente: "toque no botão abaixo do vídeo". |
| 15 | **FAQ falado** | 5–7% | As 3–5 objeções restantes respondidas em uma frase cada. |
| 16 | **Chamada final** | 2–3% | Duas vidas: continuar igual ou começar hoje. Botão. |

**Atraso da oferta** (`vsl.delay_oferta_s`): o tempo, em segundos, em que começa o bloco 9. O botão e o preço na página
só aparecem a partir daí — antes disso a pessoa ainda não está pronta. O `teleprompter.py` calcula esse tempo pelo
número de palavras; ajuste depois de gravar com o tempo real do vídeo.

## Regras de escrita falada

- Uma ideia por frase, uma frase por linha. Frases de 6 a 15 palavras.
- Escreva como fala: "você", "a gente", "tá" quando combinar com o autor. Leia em voz alta — se tropeçar, reescreva.
- A cada 60–90 s, um gancho de retenção: "e o terceiro passo é o que ninguém faz…", "daqui a pouco eu te mostro…".
- Números falados por extenso quando forem ditos ("doze vezes de vinte reais e trinta e sete centavos") só na versão
  teleprompter se o autor costuma errar números; na página, sempre em algarismos.
- Nada de "clique no botão" antes do bloco 9.
- Corte adjetivo vazio (incrível, revolucionário, único). Mostre com fato.

## Formato do arquivo (roteiro.md — o teleprompter lê assim)

```
## Gancho
> olhar direto na câmera, sem sorrir ainda
Às 3h17 da manhã, chorando no corredor com meu filho no colo,
eu descobri o erro que nenhum pediatra tinha me contado.
[PAUSA]
Nos próximos minutos eu vou te mostrar qual é.

## Promessa e quem sou
...
```
- `## Nome` abre um bloco (use os nomes da tabela).
- Linhas começando com `>` são instruções para quem grava (não são lidas, não contam no tempo).
- `[PAUSA]` marca uma respiração longa / corte.
- Indicação de imagem para o editor: `> TELA: print do depoimento da Júlia`.

## Revisão antes de entregar (faça você mesmo)

1. O gancho prende sem apresentação?
2. Os dois mecanismos aparecem com nome?
3. Há pelo menos 3 provas concretas (ou `[HIPÓTESE]` pedindo à pessoa)?
4. Cada objeção da etapa 2 foi respondida em algum bloco?
5. O preço aparece só depois do valor?
6. A chamada para ação diz exatamente onde tocar?
7. Nada fere `politicas.md`?
8. Tempo total e o minuto da oferta batem com o plano?

## Saída da etapa

O roteiro completo + tabela com bloco, palavras e tempo estimado + minuto da oferta. No Claude Code: grave
`vsl/<slug>/roteiro.md`, rode `scripts/teleprompter.py <slug>` e grave `vsl.delay_oferta_s`. Portão: *"Leia em voz
alta o gancho e a oferta. Soou como você? O que quer mudar?"*
