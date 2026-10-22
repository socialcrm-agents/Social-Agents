# Etapa 6 — Página de vendas

## A anatomia de uma página de VSL

**Antes do vídeo (a dobra, o que aparece sem rolar):**
1. Faixa fina no topo — urgência real ou aviso ("Vídeo disponível por tempo limitado" só se for verdade; senão, a
   promessa curta).
2. **Headline** — a promessa ou o gancho do ângulo, até 14 palavras.
3. Subheadline — para quem é + sem o sacrifício temido, uma linha.
4. Aviso de play — "🔊 Ative o som e assista até o final".
5. **Player** — sem nada clicável em volta. Nada de menu, logo com link, redes sociais.

**Depois do minuto da oferta (aparece sozinho):**
6. Botão grande → checkout. Repetido depois de cada bloco.
7. O que você recebe — stack com valores riscados e total.
8. Bônus.
9. Preço com ancoragem (de R$ X por 12x R$ Y ou R$ Z à vista).
10. Selo de garantia com o nome da garantia.
11. Provas — depoimentos com foto/print, nome e cidade (com autorização).
12. Para quem é / não é.
13. Quem é o autor — foto, 3 linhas, credencial.
14. Perguntas frequentes.
15. Chamada final + rodapé (CNPJ ou CPF, contato, termos, política de privacidade — exigido por Meta/Google).

**Regras:** página fechada (todo botão vai para o mesmo checkout); mobile primeiro (90% abre no celular); carregamento
rápido (sem imagem pesada acima do vídeo); texto legível (contraste alto, letra 17px+).

## Copy da página

Escreva os textos de cada seção usando a ficha (headline: 3 opções; o resto: uma versão). No Claude Code, grave em
`pagina.*` da ficha e gere:

```
python3 scripts/pagina.py <slug> --rascunho   # para revisar (trechos [HIPÓTESE] em amarelo)
python3 scripts/pagina.py <slug>              # versão final
```
Para conferir a página com a oferta já aberta, abra `pagina.html?ver=1`.

No Claude.ai/ChatGPT: entregue um único arquivo HTML com CSS e JavaScript dentro do próprio arquivo, o player no lugar
marcado e o bloco da oferta escondido até `delay_oferta_s` (um `setTimeout` que remove a classe `oculto`).

## Vídeo na página (o código do player)

| Onde hospedar | Custo | Atraso de oferta / métricas | Observação |
|---------------|-------|-----------------------------|-----------|
| **YouTube (não listado)** | grátis | atraso pela página (script) / métricas básicas | mostra logo e sugestões no fim; ok para começar |
| **Vimeo** | pago | atraso pela página | player limpo |
| **Panda Video** | pago (BR) | atraso, retenção por segundo, botão no player | muito usado em VSL no Brasil |
| **VTurb** | pago (BR) | feito para VSL: barra de progresso "inteligente", atraso, teste A/B | padrão de mercado de VSL |
| **Google Drive** | grátis | não | só para revisar, **não use para vender** (lento, limite de acessos) |

Cole o código de incorporação (embed) do player em `vsl.embed`. Link do YouTube/Vimeo também serve: o script converte.

## Onde publicar a página

- **Netlify Drop** (grátis): app.netlify.com/drop → arraste a pasta com o `pagina.html` renomeado para `index.html`.
- **Hospedagem própria** (Hostinger, Locaweb…): suba como `index.html` numa pasta/domínio.
- **WordPress / Elementor**: bloco "HTML personalizado", cole o conteúdo.
- **Plataforma de checkout**: Hotmart, Kiwify, Eduzz e Hubla têm página de vendas própria — use a copy, não o HTML.
- Domínio próprio passa mais confiança que subdomínio grátis.

## Copies de apoio (copies.md)

Veja `copies.md`: headlines alternativas, textos do checkout, página de obrigado, e-mails e mensagens de recuperação.

## Saída da etapa

`pagina.html` (ou o HTML no Artifact) + `copies.md` + lista do que falta preencher (checkout, fotos, depoimentos).
Portão: *"Abra no celular. O que te incomodou nos primeiros 5 segundos?"*
