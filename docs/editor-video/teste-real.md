# Teste real (21/10/2026)

## Material

| | Arquivo (Google Drive do usuário) | Papel no teste |
|---|---|---|
| Bruto | `depoimento sistema.mp4`: 50,5 s, 384x848, 60 fps, narração do usuário mostrando o app "Produto em 24h" filmado na tela do notebook | A-roll (voz + imagem) |
| B-roll | `record sistema ultimo.mp4`: 50,5 s, 576x1248, gravação de tela do celular, sem áudio | B-roll |

Por que esses dois: o conector do Drive nesta sessão só entrega arquivos de até ~6 MB, e os clipes de câmera
(talking head) têm de 7,7 MB a 3 GB. Esses foram os únicos vídeos do usuário que chegaram até o ambiente.

## Resultado por estilo

| | Reels Viral (v4) | Editorial Premium (v3) | Anúncio de Alta Conversão (v2) |
|---|---|---|---|
| Duração bruto -> final | 50,5 s -> 48,2 s | 50,5 s -> 49,8 s | 50,5 s -> 48,7 s |
| Planos (cortes + troca de zoom) | 20 | 10 | 16 |
| Páginas de legenda | 68 | 40 | 50 |
| B-roll inserido | 4 (tela cheia) | 3 (cartão) | 3 (tela dividida) |
| Palavras-chave grandes | 7 (na frente: não há rosto) | 1 | 3 |
| Loudness final | -13,5 LUFS | -15,5 LUFS | -13,5 LUFS |
| Tempo de render | 113 s | 151 s | 113 s |

Transcrição: 158 palavras em ~8 s (Parakeet, CPU). Na leitura, sem erros evidentes no texto (um "processas"
que deveria ser "processa"). A narração é contínua, quase sem pausa, então o ganho de tempo é pequeno (~2 s).
Num talking head com pausas e regravações, o corte é bem maior.

O que a edição automática + revisão do Claude tirou:
- "É isso." do começo (abertura fraca; decisão do editor, via `--cut`)
- 12 respiros longos medidos no áudio (estilo Viral)
- a frase final que a gravação corta no meio ("...faça uma oferta irresistível" foi mantida, completa)

## Loop de correção por texto (demonstração)

O pedido abaixo foi **escrito por nós como exemplo** de correção do usuário, não veio do usuário:

> "Tira o 'É isso' do começo, troca o gancho para 'NÃO É TEORIA. É O SISTEMA FUNCIONANDO' e põe 'SISTEMA'
> grande quando eu falo 'mecanismo'"

Tradução feita pelo Claude e versão gerada (v2, 108 s de render):
```
edit.py proj --cut "É isso." --hook "NÃO É TEORIA. É O SISTEMA FUNCIONANDO" \
             --behind-add "SISTEMA@mecanismo" --behind-remove "MECANISMO"
```
v3 e v4 são ajustes de qualidade do próprio editor (gancho sem sobreposição, quebra de linha equilibrada).

## Palavra atrás da pessoa

O vídeo do usuário não tem rosto (só tela e mão), então a regra mandou as palavras para a FRENTE, como esperado.
Para validar o recorte, rodamos um teste técnico de 11 s com a imagem de retrato `business-person.png` do
repositório público de testes do MediaPipe (Apache-2.0), animada em 9:16 com a mesma narração.
Resultado: 2 de 2 palavras atrás da cabeça, legíveis, cor trocada automaticamente para preto (fundo branco).

Bugs que esse teste encontrou e que foram corrigidos antes da entrega:
1. Palavra branca sobre fundo branco (invisível) -> cor escolhida pelo contraste com o fundo real.
2. CTA em cima do rosto -> CTA vai para a faixa livre (embaixo ou no topo).
3. Punch-in centrado no rosto empurrava a cabeça para o topo, sem espaço para a palavra -> nos planos com palavra
   atrás, o rosto fica mais baixo no quadro; palavra que não cabe legível vai para a frente.
4. Legenda cobrindo a boca quando o rosto desce -> legenda sempre abaixo do queixo do plano atual.
5. Palavra atravessando troca de plano -> termina no corte.

## Próximo teste recomendado

Um talking head real de 30-90 s com 2-3 regravações de alguma frase. Envie direto na sessão (anexo) ou rode a
skill no Claude Code local, apontando para a pasta do Drive sincronizada. Isso exercita o que este material não
cobriu: escolha entre tomadas repetidas, corte de pausas longas e palavras atrás da cabeça com movimento real.
