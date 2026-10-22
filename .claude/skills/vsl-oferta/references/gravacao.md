# Etapas 7 e 8 — Gravação, envio e edição

## O mínimo que precisa (dá para fazer só com o celular)

| Item | Mínimo | Melhor |
|------|--------|--------|
| Câmera | câmera traseira do celular, 1080p 30fps | 4K 30fps, ou câmera com saída limpa |
| Áudio | microfone de lapela com fio (R$ 30–60) | lapela sem fio (R$ 150–400) |
| Luz | de frente para uma janela, de dia | 1 luz LED com softbox a 45° + janela |
| Apoio | tripé de celular | tripé + teleprompter de vidro |
| Fundo | parede limpa ou estante arrumada, 1,5 m atrás de você | fundo com profundidade e uma luz de fundo |

**Formato:** VSL de página = horizontal 16:9 (assistida no computador e no celular deitado) **ou** vertical 9:16 se o
tráfego for 100% celular (TikTok/Reels). Na dúvida: grave **vertical com espaço** acima e abaixo e decida na edição.

## Enquadramento e postura

- Olhos no terço de cima da imagem; um palmo de espaço acima da cabeça.
- Lente na altura dos olhos. Celular de baixo para cima nunca.
- Olhe para a lente, não para a tela. Com teleprompter no celular, deixe o texto bem perto da câmera.
- Roupa lisa, sem listras finas; cor que contraste com o fundo.

## Gravar por blocos (o método que funciona)

1. Abra o `teleprompter.html` (Claude Code) ou cole o roteiro num app de teleprompter.
2. Grave **um bloco por vez** (`teleprompter.html#bloco=3` começa no bloco 3). Errou? Pare, respire, repita a frase
   inteira — o corte fica na edição.
3. Faça 2 tomadas do gancho e da chamada para ação, com energias diferentes.
4. Entre blocos, beba água e confira o áudio do último take.
5. Grave também **tomadas de apoio** (B-roll): mãos mexendo no produto, tela do curso, bastidores, prints — o editor usa
   para cobrir cortes.
6. Total: um roteiro de 12 min leva ~1h30 de gravação.

Checklist antes de gravar: modo avião ✓ · bateria e espaço ✓ · lente limpa ✓ · teste de 10 s ouvido no fone ✓ ·
ar-condicionado/ventilador desligados ✓ · luz do teto apagada se fizer sombra ✓.

## Enviar o vídeo pelo Google Drive (vídeo grande)

Vídeo de 10–30 minutos tem de 500 MB a 4 GB. Nenhuma conversa de IA nem o WhatsApp recebe isso (limites aproximados:
Claude ~30 MB por anexo; WhatsApp 16 MB de vídeo, 100 MB de documento). O caminho é o Drive:

**No celular (app Google Drive):**
1. Toque em **+** → **Upload** → escolha o vídeo. Espere terminar (no Wi-Fi).
2. Toque nos **três pontinhos** do arquivo → **Compartilhar** → **Acesso geral** → mude "Restrito" para
   **"Qualquer pessoa com o link"**, papel **Leitor**.
3. **Copiar link** e cole aqui (ou mande para o editor).

**No computador (drive.google.com):**
1. **Novo** → **Upload de arquivo**.
2. Botão direito no vídeo → **Compartilhar** → **Acesso geral: Qualquer pessoa com o link** → **Leitor** → **Copiar
   link**.

Erros comuns: link de pasta em vez do arquivo (mande o link do arquivo); upload ainda processando (espere o ícone de
vídeo aparecer); conta do trabalho com compartilhamento externo bloqueado (use uma conta pessoal).

## Edição

Uma VSL editada segura mais gente: cortes nas pausas e erros, legenda, zoom nos momentos fortes, imagens na tela quando
cita prova/números.

- **Fazer você mesmo:** CapCut (grátis) — corte as pausas, gere legenda automática, revise os números.
- **Com IA:** use as ferramentas de `config.json → produtos_cruzados` (ex.: Editor Viral, que recebe o link do Drive,
  corta, legenda e anima sozinho). Apresente uma vez, em uma frase, e siga.
- **Com editor humano:** mande o link do Drive + o `roteiro.md` com as notas `> TELA:`.

Depois de editado: hospede (tabela em `pagina-vendas.md`), copie o código de incorporação para `vsl.embed`, meça o
minuto exato em que começa o bloco da oferta e atualize `vsl.delay_oferta_s`. Gere a página de novo.

## Saída das etapas

Gravação: checklist + plano de blocos com tempo. Edição: vídeo hospedado, embed na ficha, página regenerada. Portão:
*"Assista o vídeo inteiro na página, no celular, com som. Travou em algum ponto?"*
