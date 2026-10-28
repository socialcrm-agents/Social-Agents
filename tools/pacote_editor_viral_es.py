"""Textos da versão em espanhol do pacote do Editor Viral (usados por pacote_editor_viral.py --idioma es)."""

COMO_CLAUDE = """EDITOR VIRAL EN CLAUDE - cómo instalarlo (1 vez) y usarlo

NECESITAS: cuenta de Claude con plan pago (Pro o superior). La instalación se hace 1 vez y funciona en la
computadora y en el celular (es la misma cuenta).

INSTALAR (5 minutos - desde la computadora o el navegador del celular en claude.ai):
1. Descarga el archivo editor-viral-claude-es.zip (NO lo descomprimas).
2. Entra a claude.ai > haz clic en tu nombre > Configuración > Capacidades (Capabilities).
3. Activa "Ejecución de código y creación de archivos" (Code execution and file creation).
4. En "Skills", haz clic en "Subir skill" (Upload skill) y elige editor-viral-claude-es.zip.
5. Listo. Verifica que "editor-viral" aparezca activado en la lista.

USAR (computadora o app del celular):
1. Abre una conversación nueva.
2. Toca el + (adjuntar) y elige el video de la galería (hasta ~1 minuto, grabado en 1080p).
3. Escribe: "edita este video".
4. En 2-4 minutos Claude te devuelve el video listo para descargar (+ subtítulo .srt).
5. Pide ajustes a tu manera: "subtítulos más grandes", "quita el inicio", "sin música", "haz 3 versiones de gancho".

OTROS PEDIDOS: "hazme un guion de 30 segundos para [tu nicho]", "dame 10 ganchos", "cómo grabar con el celular".

SI CLAUDE DICE QUE FALTA EL MODELO DE VOZ: adjunta el archivo modelo-voz-editor-viral.zip en la conversación
(desde la computadora; es grande) y pide "configura el editor".
"""

COMO_GPT = """EDITOR VIRAL EN CHATGPT - cómo usarlo

NECESITAS: cuenta de ChatGPT (el plan pago da más videos por día; en el gratuito el límite de uso es menor).

USAR (computadora o app del celular):
1. Abre el enlace del Editor Viral que llegó con tu acceso: {link_gpt}
2. Toca el + (adjuntar) y elige el video de la galería (hasta ~1 minuto, grabado en 1080p).
3. Escribe: "edita este video".
4. En 2-4 minutos te devuelve el enlace para descargar el video listo (+ subtítulo .srt).
5. Pide ajustes a tu manera: "subtítulos más grandes", "quita el inicio", "sin música", "haz 3 versiones de gancho".

CONSEJO: fija el Editor Viral en la barra lateral de ChatGPT para encontrarlo rápido.
"""

COMO_CRIAR_GPT = """CREAR EL GPT "EDITOR VIRAL" EN ESPAÑOL (lo haces 1 vez; los clientes solo usan el enlace)

Es un GPT DISTINTO del de portugués (otro enlace), porque responde en español y transcribe en español.

1. En ChatGPT (computadora): Explorar GPTs > Crear > pestaña "Configurar".
2. Nombre: Editor Viral. Descripción: "Edita tus videos con subtítulos animados, cortes, zoom, voz limpia y música.
   Manda el video y escribe: edita este video."
3. Instrucciones: pega TODO el contenido de instrucciones-del-gpt.txt.
4. Iniciadores de conversación (conversation starters):
   - Edita este video (adjunta el video)
   - Hazme un guion de 30 segundos para mi nicho
   - Dame 10 ganchos para mi producto
   - ¿Cómo grabo un buen video con el celular?
5. Conocimiento: sube TODOS los archivos de la carpeta ARCHIVOS-PARA-SUBIR (son {n} archivos).
   El idioma.txt es el que hace que el editor trabaje en español: no lo olvides.
   Si algún .zip es rechazado, sube los archivos de adentro (carpeta SI-EL-ZIP-ES-RECHAZADO).
6. Capacidades: marca "Intérprete de código y análisis de datos" (Code Interpreter). Puedes desmarcar
   Navegación y Generación de imágenes.
7. Foto: el logo del Editor Viral.
8. Guardar > "Cualquier persona con el enlace" (no "Público en la tienda", para que no lo use quien no compró).
9. Copia el enlace y ponlo en el área de miembros y en COMO-USAR-EN-CHATGPT.txt.

PRUEBA ANTES DE VENDER (5 minutos): abre el GPT desde el celular, adjunta un video tuyo de 30 s EN ESPAÑOL y
escribe "edita este video". Tiene que volver el video con subtítulos en español, corte y zoom.
"""

LEIA_ME = """EDITOR VIRAL - VERSIÓN EN ESPAÑOL - MATERIAL DE LANZAMIENTO ({data})
(Este LÉAME está en portugués para ti; todo lo que ve el cliente está en español.)

O QUE É: a mesma versão leve do Editor Viral, agora em ESPANHOL: o Claude/ChatGPT conversa em espanhol,
transcreve a fala em espanhol, escolhe emojis por palavras em espanhol, e o método (roteiro, 30 ganchos,
gravação, checklist) e os guias estão em espanhol. Custo por vídeo para você: zero.

PASTAS
1-PARA-EL-CLIENTE       vai na página de download (zip do Claude em espanhol + guias)
2-TU-CREAS-EL-GPT       você cria um GPT em espanhol 1 vez (é OUTRO link, separado do GPT em português)
3-PAGINA-DE-DESCARGA    briefing da página + zip com os arquivos da página, tudo em espanhol

TESTE OBRIGATÓRIO ANTES DE VENDER (15 minutos), com um vídeo seu falando ESPANHOL (ou de alguém):
[ ] Claude: instale o editor-viral-claude-es.zip (se já tem o de português instalado na sua conta, desative-o
    antes: os dois têm o mesmo nome). Pelo app do celular, anexe o vídeo e escreva "edita este video".
[ ] ChatGPT: crie o GPT em espanhol (2-TU-CREAS-EL-GPT/COMO-CREAR-EL-GPT.txt) e faça o mesmo teste.
[ ] Confira: a legenda saiu em espanhol, com acentos (á, ñ, ¿, ¡) certos?
Me mande o resultado (print) e eu ajusto o que precisar.
"""

PAGINA = """# Página de descarga — Editor Viral (español)

## Título
**Tu acceso al Editor Viral llegó.** Elige dónde quieres editar:

## Bloque 1 — Claude (recomendado: mejor calidad)
- Botón: **Descargar el Editor Viral para Claude** → `editor-viral-claude-es.zip`
- Botón secundario: **Cómo instalarlo (5 min)** → `COMO-USAR-EN-CLAUDE.txt` (o el video de instalación)
- Nota: necesitas una cuenta Claude Pro. Se instala 1 vez y funciona en la computadora y en el celular.

## Bloque 2 — ChatGPT
- Botón: **Abrir el Editor Viral en ChatGPT** → [enlace del GPT en español]
- Nota: solo abre el enlace, adjunta el video y escribe "edita este video". Fíjalo en la barra lateral.

## Bloque 3 — Cómo usarlo (3 pasos)
1. Graba tu video con el celular (vertical, 1080p, de 20 a 60 segundos).
2. Adjúntalo en la conversación y escribe **"edita este video"**.
3. Descarga el video listo. ¿Quieres cambiar algo? Pídelo a tu manera: "subtítulos más grandes", "quita el inicio",
   "haz 3 versiones".

## Bloque 4 — Qué hace el Editor Viral
- Corta pausas, tartamudeos y frases repetidas
- Subtítulos animados palabra por palabra, con la palabra fuerte gigante y emoji
- Zoom en el momento justo
- Voz limpia de estudio (quita el ruido del ambiente)
- Música sin derechos de autor que baja cuando hablas
- Gancho fuerte en los 3 primeros segundos + 3 versiones para probar en el anuncio
- Formatos 9:16, 4:5 y 1:1 y subtítulo .srt
- Método: guion de 30 s, 30 ganchos listos, guía de grabación con el celular y checklist del anuncio que vende

## Bloque 5 — Preguntas frecuentes
- **¿Funciona en el celular?** Sí, en la app de Claude y de ChatGPT. La instalación en Claude se hace 1 vez
  (desde la computadora o el navegador) y después funciona en la app.
- **¿Cuál es el tamaño máximo del video?** Hasta ~1 minuto por vez (video largo: mándalo en partes).
- **¿Tengo que pagar por video?** No. Funciona en tu cuenta de Claude o de ChatGPT.
- **¿Hay que instalar algún programa?** No. Todo funciona dentro de Claude/ChatGPT.
- **¿Y efectos 3D, producto volando, cambio de fondo?** Son parte del **Editor Viral PRO**. [botón del upsell]
- **¿Dio error?** Abre una conversación nueva y mándalo otra vez. Si sigue: [soporte].

## Bloque 6 — Upsell
**Editor Viral PRO**: efectos 3D, producto volando en tu mano, palabra detrás de ti, cambio de fondo, 2.5D y
motion de nivel agencia. [botón]
"""
