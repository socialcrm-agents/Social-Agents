# Editor Viral en Claude — guía paso a paso

Necesitas una cuenta **Claude Pro** (o superior). Hay dos formas de usarlo:

| | **A. En la computadora (recomendada)** | **B. En la app / web de Claude** |
|---|---|---|
| Archivo | `Edicion-de-Videos-ES.zip` | `editor-viral-claude-es.zip` |
| Videos | sin límite de duración, en una carpeta | hasta ~1 minuto, adjuntando en el chat |
| Tu estilo | Claude lo guarda en la carpeta y lo recuerda | adjuntas tu guía de estilo en cada chat |
| Ideal para | editar seguido y con calidad | editar rápido desde el celular |

## A. En la computadora (10 minutos, 1 vez)

1. Descarga la app de Claude en **claude.ai/download** (Windows o Mac) y entra con tu cuenta Pro.
   **No sirve el navegador: tiene que ser la app.**
2. Descomprime `Edicion-de-Videos-ES.zip` (Windows: clic derecho → **Extraer todo**) y mueve la carpeta
   **Edicion-de-Videos** a **Documentos**. Adentro hay 3 carpetas:
    - **1-GRABACIONES**: tus videos sin editar.
    - **2-REFERENCIAS**: videos (o enlaces en `enlaces.txt`) de creadores cuyo estilo te gusta.
    - **3-LISTOS**: aquí aparecen tus videos editados.
3. En la app de Claude, haz clic en **Code** (ícono `</>`, arriba a la izquierda), elige la carpeta
   **Documentos → Edicion-de-Videos**. Cuando Claude pida permiso para ejecutar algo, haz clic en **Permitir**.
4. Escribe los 3 pedidos (están también en `PROMPTS.txt`):

**1 — Solo la primera vez (10 a 20 min):**
> prepara todo

**2 — Tu estilo (1 vez):** pon videos de referencia en **2-REFERENCIAS** (o pega los enlaces) y escribe:
> aprende el estilo de estos videos y crea mi guía de estilo, a mi manera, sin copiar

¿Editas de forma simple? Escribe: **"mi estilo es simple: solo cortes y subtítulo limpio"**.

**3 — Editar:** graba como siempre, pon el video en **1-GRABACIONES** y escribe:
> edita mi video nuevo para Reels, siguiendo mi guía de estilo. Muéstrame el storyboard antes.

Claude te muestra qué va a hacer, tú apruebas (o pides cambios) y el video aparece en **3-LISTOS**.

## B. En la app o la web de Claude (5 minutos, 1 vez)

1. En **claude.ai** (computadora o navegador del celular): tu nombre → **Configuración** → **Capacidades**
   (Capabilities) → activa **Ejecución de código y creación de archivos** (Code execution and file creation).
2. En **Skills**, toca **Subir skill** (Upload skill) y elige `editor-viral-claude-es.zip` (sin descomprimir).
   Listo: funciona en la computadora y en la app del celular.
3. En un chat nuevo: toca **+**, adjunta el video (hasta ~1 minuto, en 1080p) y escribe **edita este video**.
4. Primera vez: escribe **"aprende mi estilo"** y adjunta 1 a 3 videos que te gustan. Claude te entrega un
   archivo **GUIA-DE-ESTILO.txt**: guárdalo y adjúntalo junto con el video en los próximos chats.
5. Si Claude dice que falta el "modelo de voz", adjunta `modelo-voz-editor-viral.zip` y pide "configura el editor".

## Frases mágicas (A y B)

| Tú escribes | Lo que pasa |
|---|---|
| subtítulos más grandes / más chicos | cambia el tamaño |
| quita el inicio / quita la parte donde digo X | corta |
| sin música / música más baja | ajusta la música |
| más simple / menos efectos | limpia la edición |
| nunca pongas emoji | lo recuerda (va a tu guía) |
| haz 3 versiones de gancho | 3 aperturas para probar en el anuncio |
| edita todos los videos de la carpeta | uno por uno (solo en A) |

## Si algo sale mal

- **Windows pide permiso o Mac pide contraseña:** es la instalación de los programas; acepta.
- **Se trabó:** escribe **"sigue desde donde te quedaste"**.
- **Dio error:** escribe **"dio error, resuélvelo"**. Si sigue, manda una captura al soporte.
- **Video muy grande en la opción B:** grábalo en 1080p (no 4K) o mándalo en partes de hasta 60 s.
- **¿Quieres efectos 3D, producto volando o cambio de fondo?** Eso es el **Editor Viral PRO**.
