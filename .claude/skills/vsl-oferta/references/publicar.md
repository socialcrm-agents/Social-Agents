# Colocar no ar — guia passo a passo (Netlify, domínio, links, pixel)

Use este guia na etapa 6 (página pronta) e na 8 (vídeo hospedado). Mande **um bloco por vez** e espere a pessoa
dizer "feito" (ou mandar um print) antes do próximo. Ela não precisa saber programação.

## Bloco 1 — Juntar os links (antes de publicar)

A página precisa de 3 links. Peça um por um e grave na ficha:

1. **Link do checkout** (`produto.checkout_url`), onde a pessoa paga:
   - **Hotmart:** Produtos → seu produto → Ferramentas → Links de divulgação/checkout → copiar.
   - **Kiwify:** Produtos → seu produto → Links → copiar o link de checkout.
   - **Eduzz / Hubla:** na página do produto, procure "link de checkout" ou "link de venda".
2. **Vídeo** (`vsl.embed`):
   - **YouTube:** suba como "Não listado" → Compartilhar → Incorporar → copiar o código, ou só o link.
   - **Panda Video / VTurb:** abra o vídeo → "Incorporar" / "Embed" → copiar o código.
3. **WhatsApp de suporte** (opcional, para o rodapé): `https://wa.me/55DDDNUMERO`, por exemplo
   `https://wa.me/5511999998888`.

Também crie as páginas de **Termos de uso** e **Política de privacidade**, que a Meta e o Google exigem. A IA
escreve as duas com os dados da pessoa (nome ou empresa, CNPJ ou CPF, e-mail); salve como `termos.html` e
`privacidade.html` na mesma pasta da página e coloque os links no rodapé.

No Claude Code: `projeto.py set <slug> produto.checkout_url=... vsl.embed='...'` e depois `pagina.py <slug>`.

## Bloco 2 — Preparar a pasta

1. Crie no computador uma pasta com o nome do produto (ex.: `metodo-x-site`).
2. Coloque dentro dela a página com o nome **`index.html`**. O nome tem que ser exatamente esse, porque é o que
   abre primeiro.
3. Coloque também `termos.html`, `privacidade.html` e as imagens que a página usa (foto do autor, depoimentos),
   com os mesmos nomes citados na página.
4. Teste: dê dois cliques no `index.html`. Tem que abrir no navegador e funcionar.

## Bloco 3 — Criar a conta no Netlify (grátis)

1. Entre em **netlify.com** → **Sign up**.
2. Escolha **Continuar com Google**, que é o mais fácil, ou e-mail e senha.
3. Se perguntar o que você vai fazer, escolha a opção pessoal/grátis e pule as perguntas sobre GitHub: não precisa.

## Bloco 4 — Publicar (arrastar e soltar)

1. Abra **app.netlify.com/drop**, logado na conta.
2. **Arraste a pasta inteira** (não só o arquivo) para o quadrado da página.
3. Em segundos aparece um endereço tipo `https://nome-aleatorio-123.netlify.app`. A página está no ar.
4. Trocar o nome feio: **Site configuration** (ou "Site settings") → **Change site name** → ex.: `metodo-x`.
   O endereço vira `https://metodo-x.netlify.app`.
5. Abra o endereço **no celular** e assista uns segundos. Para ver a oferta sem esperar o vídeo, ponha `?ver=1`
   no fim do endereço.

**Atualizar depois** (mudou texto, preço, vídeo): gere a página de novo, troque o `index.html` na pasta e, no
Netlify, abra o site → **Deploys** → arraste a pasta de novo. O endereço continua o mesmo.

## Bloco 5 — Domínio próprio (opcional, recomendado para anúncio)

1. Compre o domínio: **Registro.br** para `.com.br` (cerca de R$ 40 por ano) ou Hostinger/GoDaddy para `.com`.
2. No Netlify: abra o site → **Domain management** → **Add a domain** → digite o domínio (ex.:
   `metodox.com.br`) → **Verify** → **Add domain**.
3. O Netlify mostra o que configurar. O caminho mais simples é usar o **DNS do Netlify**: ele mostra 4 endereços
   (nameservers, tipo `dns1.p01.nsone.net`).
   - **Registro.br:** entre no domínio → **DNS** → **Alterar servidores DNS** → cole os 4 → Salvar.
   - **Hostinger/GoDaddy:** procure "Nameservers" / "Servidores DNS" → personalizado → cole os 4.
4. Espere de 1 a 24 horas. O cadeado (HTTPS) o Netlify coloca sozinho e de graça. Se depois de 24 h não abrir,
   mande um print da tela "Domain management".

## Bloco 6 — Pixel e eventos (para anúncio)

1. **Meta:** Gerenciador de Eventos → **Conectar fontes de dados** → Web → crie o pixel → **Instalar código
   manualmente** → copie o código.
2. Cole o código para a IA. Ela coloca dentro do `<head>` da página; depois atualize no Netlify (Bloco 4).
3. **Compra (Purchase):** configure na plataforma de checkout. Hotmart, Kiwify e as outras têm o campo "Pixel do
   Facebook/Meta": cole o **ID do pixel** (só o número).
4. **TikTok / Google:** mesmo caminho (código base na página, ID na plataforma de checkout).
5. Teste: abra a página e veja no Gerenciador de Eventos se o PageView aparece (até uns 20 minutos).

## Bloco 7 — Teste final antes de ligar o anúncio

- [ ] Página abre no celular (4G) em até 3 s.
- [ ] Vídeo toca no iPhone e no Android, com som.
- [ ] A oferta aparece no minuto certo; com `?ver=1` aparece na hora.
- [ ] Todos os botões levam ao checkout certo.
- [ ] Compra de teste feita (cupom 100% ou valor mínimo) e o acesso chegou.
- [ ] Rodapé com termos, privacidade e contato.
- [ ] Pixel registrando PageView.

## Problemas comuns

| Sintoma | Causa | Solução |
|---|---|---|
| "Page not found" no Netlify | arquivo não se chama `index.html` ou arrastou só o arquivo | renomeie e arraste a pasta inteira |
| Imagens quebradas | imagem fora da pasta ou nome diferente | coloque na mesma pasta, com o nome igual ao da página |
| Vídeo não aparece | link de pasta/privado, ou Drive | use YouTube não listado, Panda ou VTurb |
| Domínio não abre | DNS ainda propagando | espere até 24 h; confira os 4 nameservers |
| Botão abre o lugar errado | link do checkout antigo | atualize na ficha, gere a página e publique de novo |
