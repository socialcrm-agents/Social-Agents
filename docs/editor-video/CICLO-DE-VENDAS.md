# Editor Viral IA™: o ciclo de vendas (2026-10-26)

Cinco novidades que fazem o editor aprender com as suas vendas, testar mais e soar profissional. Para usar, basta
conversar com o Claude (no Claude Code, com o editor instalado). As frases abaixo são exemplos.

## 1. O editor aprende com as suas vendas

**O que faz:** todo vídeo que o editor entrega agora tem um **código** no nome do arquivo
(ex.: `v3_reels_viral_EV-7F3A2C.mp4`). O editor anota o que tem em cada vídeo: o tipo de gancho, os efeitos, a
trilha, a voz, o tamanho da legenda, o ritmo e a duração. Depois o Claude puxa os números reais do **Meta Ads** e
do **Vturb**, que já estão conectados, e cruza as duas coisas.

**Como usar:**
1. Suba o vídeo no Meta e/ou no Vturb **com o nome do arquivo** (ou ponha o código EV-... no nome do anúncio).
2. Depois de alguns dias rodando, peça: *"aprende com os meus anúncios"* ou *"o que está funcionando nos meus
   vídeos?"*.
3. O Claude mostra:
   - o ranking dos seus vídeos;
   - o que os vencedores têm em comum, com o grau de certeza (alta, média ou baixa);
   - **em que segundo as pessoas saem do vídeo acima do normal e o que estava na tela nessa hora** (pela curva de
     retenção do Vturb).
4. Se você disser "pode aplicar", ele grava a receita **aprendida**. A partir daí, todo vídeo novo já sai do jeito
   que vende mais para você: *"usa a receita aprendida como padrão"*.

**Importante:**
- Precisa de pelo menos 4 vídeos com resultado (cerca de R$ 30 de gasto ou 100 plays cada).
- Com pouco dado, ele avisa e sugere o que testar, em vez de inventar uma regra.

## 2. Fábrica de variações (1 vídeo vira 10)

**O que faz:** do mesmo vídeo saem até 10 versões. Cada uma muda três coisas:

- **a abertura**: pergunta na tela, manchete com zoom, 2.5D ou palavra gigante;
- **a trilha**: energia, inspirador ou sem;
- **a chamada final**: pílula ou botão animado clicando.

As combinações são equilibradas, para dar para saber depois qual dessas coisas fez a diferença. A V01 é sempre o
vídeo original (o "controle").

**Como usar:** *"faz 10 versões desse vídeo pra eu testar"*. O Claude mostra antes o que cada versão muda e depois
renderiza. Só os pedaços que mudam são refeitos: trocar a trilha refaz só o áudio, e trocar a abertura refaz só os
primeiros segundos.

**Teste A/B:**
- **No Vturb:** o Claude sobe as versões e monta o teste A/B. Ele **só liga o teste quando você disser sim**,
  porque um teste ligado não pode ser desfeito.
- **No Meta:** suba todas no mesmo conjunto de anúncios, com o nome do arquivo.

Depois, o item 1 mostra qual versão venceu e por quê.

## 3. Voz limpa de estúdio

**O que faz:** tira o ruído do ambiente (ventilador, rua, eco leve), o "embolado" de microfone de celular e o chiado
do S. O editor sabe onde você fala, então aprende o ruído nas suas pausas e o remove sem robotizar a voz.

**Como usar:** já vem ligado na receita **premium**. Em outro projeto: *"deixa a voz com som de estúdio"*. Para
desligar: *"volta a voz ao normal"*.

**Medido no seu vídeo do Mentos (vídeo final, mesma edição):**

| | voz padrão | voz de estúdio |
|---|---|---|
| ruído nas pausas | −28 dB | −43 dB (15 dB mais silencioso) |
| voz | −14,5 dB | −13,9 dB (mesmo volume) |
| distância voz ↔ ruído | 13,5 dB | 29,2 dB |

Só o áudio é refeito: o vídeo vem inteiro do cache.

**Opcional, ainda melhor:** a voz por IA (Resemble Enhance, grátis) também tira reverberação de sala. Instale com
`python setup.py --voz-ia` (cerca de 1 GB). Com placa de vídeo NVIDIA fica rápida; sem placa funciona, mas
devagar.

## 4. Trilha de verdade com IA (ACE-Step)

**O que faz:** em vez da trilha sintetizada (simples), cria uma música de verdade no clima, na velocidade e na
duração exata do vídeo. A música abaixa sozinha quando você fala. É grátis, roda no seu computador, e a licença
(MIT) permite uso comercial.

**Instalar (uma vez):**
- **Windows:** baixe https://files.acemusic.ai/acemusic/win/ACE-Step-1.5.7z, extraia e dê dois cliques em
  `start_api_server.bat`. Deixe essa janela aberta enquanto edita.
- **Mac:** `git clone https://github.com/ace-step/ACE-Step-1.5`, depois `./start_api_server_macos.sh`.
- Confira com `python musica_ia.py status`: deve aparecer "NO AR".

**Como usar:** com o ACE-Step aberto, toda trilha automática já sai por IA. Fechado, o editor usa a trilha
sintetizada, então nada quebra. Para forçar: *"usa a trilha sintetizada"* ou *"usa a música por IA"*.

**Velocidade:**
- com placa de vídeo NVIDIA (4 GB ou mais): segundos;
- sem placa de vídeo: alguns minutos por música.

Cada música fica guardada, então ela só é gerada uma vez por vídeo.

## 5. Espionar os anúncios vencedores do seu nicho

**O que faz:** busca na Biblioteca de Anúncios os vídeos do seu nicho que estão **há mais tempo no ar**. Quem
paga anúncio por meses é porque está lucrando. Depois:

- dá uma nota a cada um (dias no ar, quantas versões têm e se continua ativo);
- baixa os melhores;
- mede cortes por minuto, texto na tela, legenda, zoom e efeitos;
- lê o gancho de cada um e diz o formato (pergunta, número, dor, promessa...).

**Como usar:** *"espiona os anúncios que mais vendem no nicho de renda extra"*. Você recebe o padrão dos
vencedores (ritmo, duração, tipos de gancho, chamadas) e a tabela com os links. Depois: *"aplica esse ritmo no meu
vídeo"*. O editor copia o ritmo e o estilo, **nunca o conteúdo**: os ganchos deles são inspiração de formato e o
seu vídeo continua com as suas palavras.

## Limites honestos

- **ACE-Step e voz por IA:** não puderam ser baixados no ambiente de testes (rede bloqueada). Foram testados com um
  servidor de mentira que segue o mesmo protocolo do real. O primeiro uso de verdade é no seu computador.
- **Vídeos dos concorrentes:** o servidor de vídeos do Facebook é bloqueado no ambiente de testes. A análise foi
  testada com vídeos locais e baixa normalmente no seu computador.
- **Aprendizado:** a certeza depende de volume. Com poucos vídeos e pouco gasto, as diferenças podem ser sorte, e o
  relatório avisa isso.
- **Suas contas hoje:**
  - nos últimos 90 dias, a conta "MP Conta de Anuncios" não teve gasto;
  - os vídeos do Vturb ainda não têm código EV-...

  O aprendizado começa a valer quando os próximos vídeos editados forem ao ar com o código.
