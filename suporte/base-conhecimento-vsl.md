# Base de conhecimento — VSL & Oferta (atendimento ao cliente)

Use só o que está aqui. Se a resposta não estiver nesta base, encaminhe para o suporte humano.

---

## 1. O que é o produto

Um pacote (arquivo .zip) que transforma o Claude ou o ChatGPT num estrategista de vendas. A IA entrevista o
cliente e monta, etapa por etapa:

1. **Diagnóstico**: produto, preço (ticket), entrega, provas, canal de venda. Recomenda o formato e a duração da VSL
   pelo preço.
2. **Público**: dores, desejos, objeções, medos e as palavras que o público usa.
3. **Oferta**: promessa, nome do problema e da solução (mecanismo), o que vem incluso com valores, bônus, garantia,
   preço com ancoragem e urgência (só se for real).
4. **Ângulos**: 4 ideias de gancho para a VSL; o cliente escolhe uma.
5. **Roteiro da VSL**: em blocos, com o tempo de cada bloco e o minuto em que a oferta aparece.
6. **Página de vendas**: textos e um arquivo HTML pronto, com o vídeo e a oferta aparecendo no minuto certo, e as
   copies de apoio (e-mails, mensagens de WhatsApp, textos do checkout).
7. **Gravação**: checklist (dá para gravar só com o celular), gravação por blocos e teleprompter.
8. **Edição e hospedagem**: como editar e onde colocar o vídeo.
9. **Criativos**: 10 roteiros de anúncio tirados da VSL, com textos.
10. **Lançamento**: calendário de 14 dias com datas e checklist técnico.
11. **Otimização**: o cliente cola os números (cliques, retenção, vendas) e a IA diz o que mexer primeiro.

O cliente pode pular direto para uma etapa ("só quero a página"). A IA faz as perguntas mínimas e marca o que ela
supôs com **[HIPÓTESE]**, para o cliente confirmar depois.

Também entram no pacote, conforme a oferta comprada: esta IA de dúvidas e os bônus listados na área de membros.

---

## 2. Como instalar (3 jeitos; escolha um)

Dentro do zip:
- **COLAR-NO-CLAUDE-OU-CHATGPT/**: `INSTRUCOES.md` mais 12 arquivos numerados (01-ficha.md … 12-politicas.md).
- **vsl-oferta/**: a versão para o Claude Code.
- **LEIA-ME.txt**: o passo a passo.

**A) Claude.ai, em Projetos (o mais fácil, não instala nada)**
1. Entre em claude.ai → **Projetos** → **Criar projeto** (ex.: "Minha VSL").
2. Em **Instruções do projeto**, cole todo o texto do arquivo `INSTRUCOES.md`.
3. Em **Conhecimento do projeto**, envie os 12 arquivos numerados.
4. Abra uma conversa nova dentro do projeto e escreva: "quero montar minha VSL".

**B) ChatGPT**
- **GPT personalizado:** chatgpt.com → **Explorar GPTs** → **Criar** → aba **Configurar**.
  1. Em **Instruções**, cole o `INSTRUCOES.md`.
  2. Em **Conhecimento**, envie os 12 arquivos.
  3. Deixe ligado o **Interpretador de código**, para ele gerar a página em arquivo.
  4. Clique em **Criar** (pode deixar "Só eu").
- **Projeto do ChatGPT:** Projetos → Novo projeto → **Instruções** (cole o `INSTRUCOES.md`) → **Adicionar
  arquivos** (os 12).
- Depois escreva "quero montar minha VSL".

**C) Claude Code (para quem já usa)**
1. Descompacte a pasta `vsl-oferta` em `~/.claude/skills/vsl-oferta`. No Windows:
   `%USERPROFILE%\.claude\skills\vsl-oferta`.
2. Abra o Claude Code numa pasta de trabalho e digite `/vsl-oferta`.

Nessa versão a IA salva tudo numa pasta (`vsl/<nome-do-projeto>/`) e gera os arquivos sozinha: página,
teleprompter e calendário (também em .ics, para Google Agenda e iPhone). Precisa de Python 3.10 ou mais novo.

Plano: funciona com a conta do próprio cliente no Claude ou no ChatGPT. Projetos e GPTs personalizados exigem plano
pago nessas plataformas. Conversas muito longas no plano grátis param no limite de uso.

---

## 3. Continuar outro dia / conversa ficou longa

- No fim de cada etapa a IA mostra um bloco **FICHA DA OFERTA**. O cliente copia e guarda (bloco de notas,
  WhatsApp para si mesmo).
- Para continuar, abre uma **conversa nova no mesmo Projeto ou GPT** e cola a ficha. A IA retoma da etapa marcada,
  sem refazer nada.
- Se a resposta ficar lenta, repetitiva ou "esquecida", é porque a conversa ficou longa demais. A solução é a mesma:
  conversa nova e colar a ficha.
- No Claude Code a ficha fica salva sozinha em `vsl/<projeto>/ficha.json`.

---

## 4. Explicar o produto gravando (em vez de digitar)

- **Áudio curto:** use o microfone do teclado do celular (ditado) direto na caixa de mensagem. Os apps do ChatGPT e
  do Claude também transcrevem a fala.
- **Vídeo ou áudio longo (até 30 min):** a conversa não recebe arquivo grande. Os caminhos são:
  1. Subir no **YouTube como "Não listado"**.
  2. Esperar uns minutos e, no computador, clicar em "…" abaixo do vídeo → **Mostrar transcrição**.
  3. Copiar o texto e colar na conversa. É grátis e funciona em português.

---

## 5. Mandar o vídeo da VSL (10 a 30 minutos)

**Por que não dá para mandar direto:** uma VSL de 10 a 30 min tem de 500 MB a 4 GB. Os limites aproximados são:
- conversa do Claude: cerca de 30 MB por anexo;
- WhatsApp: 16 MB para vídeo e 100 MB para documento.

O caminho é o **Google Drive**.

**No celular (app Google Drive):**
1. Toque em **+** → **Upload** → escolha o vídeo. Use Wi-Fi e espere terminar.
2. Nos **três pontinhos** do arquivo → **Compartilhar** → **Acesso geral**: troque "Restrito" por **"Qualquer pessoa
   com o link"**, papel **Leitor**.
3. **Copiar link** e mandar (para o editor ou para quem vai editar).

**No computador (drive.google.com):**
1. **Novo** → **Upload de arquivo**.
2. Botão direito no vídeo → **Compartilhar** → **Acesso geral: Qualquer pessoa com o link** → **Leitor** →
   **Copiar link**.

**Erros comuns:**
- **"Link privado" / "pediu login":** falta o passo do "Qualquer pessoa com o link".
- **Mandou o link da pasta:** tem que ser o link do arquivo do vídeo.
- **Upload ainda processando:** espere aparecer o ícone de vídeo no arquivo.
- **Conta do trabalho ou escola que bloqueia compartilhamento externo:** use uma conta pessoal do Google.

---

## 6. Editar a VSL

- **Sozinho:** CapCut (grátis). Corte pausas e erros, gere legenda automática e revise os números.
- **Com IA, sem instalar nada:** o **Editor no WhatsApp**. Manda o link do Drive no WhatsApp do editor e recebe o
  vídeo editado: cortes, legenda, zoom e efeitos. Vídeo longo volta por link de download ou como documento.
- **Com IA, no computador:** o **Editor Viral** (Claude Code) também aceita o link do Drive direto.
- **Com editor humano:** mande o link do Drive e o roteiro com as notas de tela.

Preço e contratação do Editor Viral ou do Editor no WhatsApp: encaminhe para o suporte humano.

---

## 7. Onde hospedar o vídeo (o player da página)

| Onde | Custo | Observação |
|---|---|---|
| **YouTube (não listado)** | grátis | Bom para começar. A página esconde a oferta até o minuto certo; mostra a logo do YouTube e sugestões no fim. |
| **Vimeo** | pago | Player limpo. |
| **Panda Video** | pago | Muito usado para VSL no Brasil: retenção por segundo, botão no player, atraso da oferta. |
| **VTurb** | pago | Feito para VSL: barra de progresso "inteligente", atraso da oferta, teste A/B. |
| **Google Drive** | grátis | Só para revisar. **Não use para vender**: é lento e tem limite de acessos. |

Depois de hospedar:
1. Copie o código de incorporação (embed) ou o link e entregue para a IA.
2. Diga o minuto exato em que começa a oferta no vídeo editado.
3. A IA gera a página de novo, com esse tempo.

---

## 8. Publicar a página de vendas

A página é **um arquivo HTML só**: abre com dois cliques e funciona sem servidor especial.
- **Netlify (grátis), passo a passo:**
  1. Renomeie a página para `index.html` e coloque numa pasta (com `termos.html`, `privacidade.html` e as imagens).
  2. Crie a conta em netlify.com → Sign up → "Continuar com Google".
  3. Abra app.netlify.com/drop e arraste a **pasta inteira**. Sai um link na hora (`...netlify.app`).
  4. Trocar o nome: Site configuration → Change site name.
  5. Atualizar: abra o site → Deploys → arraste a pasta de novo (o link continua o mesmo).
  6. Domínio próprio: Domain management → Add a domain → use os 4 nameservers que o Netlify mostrar no
     Registro.br (DNS → Alterar servidores DNS). Leva de 1 a 24 h; o cadeado HTTPS é automático.
  - "Page not found": o arquivo não se chama `index.html` ou foi arrastado só o arquivo, sem a pasta.
  - Imagem quebrada: a imagem não está na mesma pasta ou o nome é diferente.
- **Hospedagem própria** (Hostinger, Locaweb e outras): suba como `index.html` na pasta do domínio.
- **WordPress / Elementor:** bloco **"HTML personalizado"** e cole o conteúdo do arquivo.
- **Lovable:** peça para criar a página a partir do arquivo HTML ou dos textos.
- **Hotmart, Kiwify, Eduzz, Hubla:** têm página de vendas própria. Use os textos (copy), não o HTML.
- Domínio próprio passa mais confiança que endereço grátis.
- Para ver a página inteira sem esperar o vídeo (revisar), abra com `?ver=1` no fim do endereço.

---

## 9. Checkout (onde a pessoa paga)

- Hotmart, Kiwify, Eduzz e Hubla funcionam: crie o produto lá, copie o **link do checkout** e entregue para a IA.
  Todos os botões da página vão para ele.
- Antes de ligar anúncio, faça uma **compra de teste** (cupom de 100% ou valor mínimo) e confira se chega o acesso.
- Pixel e eventos (Meta, TikTok, Google): configure na plataforma de checkout e na página. Dúvidas de configuração
  de uma plataforma específica: oriente a ajuda oficial dela.

---

## 10. Dúvidas comuns

- **"A IA inventou um depoimento / um número."** Ela não pode. Peça para trocar por **[a preencher: depoimento
  real]**. Depoimento inventado dá processo e bloqueio de conta de anúncio.
- **"Ela não quer escrever 'garantido' / 'cura' / 'ganhe R$ X por dia'."** É de propósito. Essas promessas derrubam
  anúncio e geram reclamação. Ela entrega uma versão forte e permitida.
- **"Quero só a página" / "só o roteiro".** Pode. Peça direto. Ela pergunta o mínimo e marca as hipóteses.
- **"Quanto tempo leva tudo?"** A entrevista e a oferta levam de 30 a 60 min. Roteiro e página, mais 1 a 2 h de
  revisão. A gravação depende do cliente. O calendário de lançamento é de 14 dias, com cerca de 2 h por dia.
- **"Dá para vender produto físico?"** Dá. A IA recomenda uma VSL curta de demonstração e oferta de kits.
- **"Ticket alto (acima de R$ 3.000)?"** A VSL leva para uma aplicação e uma ligação, não direto para o checkout.
- **"A VSL não está vendendo."** Leve os números para a etapa de otimização: cliques no anúncio, quantos dão play,
  até onde assistem, quantos chegam na oferta, cliques no botão e vendas. Ela diz o primeiro gargalo e entrega o
  ajuste escrito.
- **"Funciona no Gemini / outra IA?"** O pacote foi feito e testado para Claude e ChatGPT. Em outras pode funcionar
  colando as instruções, mas sem garantia.

---

## 11. Limites honestos (não prometa além disto)

- A IA escreve e organiza. **Não garante vendas** nem resultado de anúncio.
- Ela não publica a página, não cria o checkout, não sobe anúncios e não acessa as contas do cliente. Ela entrega
  os arquivos e o passo a passo.
- Ela não assiste vídeo longo direto na conversa. O texto chega pela transcrição (seção 4).
- A qualidade depende das respostas: quanto mais concreto o cliente for (números, histórias reais, provas), melhor.

---

## 12. Quando encaminhar para o suporte humano

- Pagamento, reembolso, acesso à área de membros, bônus que não chegou, nota fiscal, licença ou reclamação.
- Preço e contratação de outros produtos (Editor Viral, Editor no WhatsApp, Anúncio de Produto).
- Dúvida jurídica sobre a oferta: promessa, garantia, contrato, saúde ou investimento.
- Qualquer pergunta que não esteja nesta base.
