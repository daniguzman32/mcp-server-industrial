# fachmann-mcp

Sistema de asistencia comercial B2B para Fachmann, representante en Argentina de **PILZ** (seguridad funcional), **OBO Bettermann** (gestión de cables) y **CABUR** (borneras y conectores).

Compuesto por dos servicios independientes desplegados en Railway:

- **MCP Server** (`web`): servidor HTTP que expone herramientas CRM a clientes MCP (Claude Desktop, agentes, etc.).
- **Telegram Bot** (`worker`): cotizador técnico conversacional que recibe requerimientos en lenguaje natural, consulta el catálogo vía Claude API con function calling, y devuelve una propuesta técnica en PDF con borrador de email.

---

## Architecture

```
                         ┌─────────────────────────────────────────┐
                         │              Railway                      │
                         │                                           │
┌──────────────┐  HTTP   │  ┌──────────────────────────────────────┐│
│ Claude       │◄────────┤  │  web service (MCP HTTP Server)       ││
│ Desktop /    │         │  │  python src/server.py                ││
│ MCP Client   │         │  │  FastMCP + aiosqlite                 ││
└──────────────┘         │  │  Port: $PORT (Railway) / 8000 (local)││
                         │  └──────────────────┬───────────────────┘│
                         │                     │                     │
                         │              SQLite │ data/fachmann.db   │
                         │                     │                     │
                         │  ┌──────────────────┴───────────────────┐│
                         │  │  worker service (Telegram Bot)       ││
                         │  │  python src/bot.py                   ││
                         │  │  python-telegram-bot + cotizador.py  ││
                         │  └──────────────────────────────────────┘│
                         │                     │                     │
                         └─────────────────────┼─────────────────────┘
                                               │ Anthropic API
                                               ▼
                                   ┌───────────────────────┐
                                   │  Claude (claude-       │
                                   │  sonnet-4-6)          │
                                   │  Function calling:     │
                                   │  buscar_catalogo      │
                                   │  consultar_disponib.  │
                                   └───────────────────────┘

Flujo del Telegram Bot:
 Vendedor ──► mensaje de texto ──► bot.py
                                     │
                              cotizador.py (agentic loop)
                                     │
                              Claude API ◄──► SQLite catalog
                                     │
                              propuesta JSON
                                     │
                    ┌────────────────┴────────────────┐
                    │                                  │
              pdf_generator.py                  email_draft
              (Jinja2 + WeasyPrint)             (texto Markdown)
                    │
                PDF bytes ──► Telegram reply_document
```

---

## Features

**MCP Server (CRM tools)**
- Busqueda de texto libre en el catalogo de 15 productos (PILZ, OBO, CABUR) con filtro por marca
- Consulta de precio exacto, stock disponible y tiempo de entrega por SKU
- Recuperacion de perfil completo de clientes/prospectos: datos de contacto, estado del lead, ultimas 5 interacciones y oportunidades de venta activas
- Registro de interacciones (reunion, email, llamada, whatsapp, nota) con timestamp automatico

**Telegram Bot (Cotizador Tecnico)**
- Recibe requerimientos tecnicos en lenguaje natural (sin estructura requerida)
- Extrae nombre del cliente si se menciona en el texto
- Loop agentico: Claude llama a `buscar_catalogo` y `consultar_disponibilidad` iterativamente hasta armar la propuesta optima
- Genera PDF de propuesta comercial numerada (Jinja2 + WeasyPrint) y lo adjunta directamente en el chat
- Incluye borrador de email profesional listo para copiar y enviar al cliente
- Fallback a resumen en texto Markdown si WeasyPrint no esta disponible (ej. Windows local sin GTK3)
- Propuestas numeradas secuencialmente por ano: `2026-001`, `2026-002`, etc.

**Normativa integrada**
- System prompt embebe el conocimiento de ISO 13849-1:2015 (PL a–e, Categorias 1–4)
- Reglas de seleccion de producto PILZ codificadas: parada de emergencia, control dos manos, proteccion de resguardos, sistemas complejos, monitoreo de velocidad
- Justificacion normativa incluida en cada linea de producto de la propuesta

---

## Tech Stack

| Componente            | Tecnologia                                  | Version        |
|-----------------------|---------------------------------------------|----------------|
| MCP Server            | FastMCP (Python)                            | mcp[cli] >=1.0 |
| Async DB driver       | aiosqlite                                   | latest         |
| Base de datos         | SQLite                                      | built-in       |
| Telegram Bot          | python-telegram-bot                         | >=21.0         |
| LLM / Function calling| Anthropic Claude API (claude-sonnet-4-6)    | anthropic SDK  |
| PDF generation        | WeasyPrint + Jinja2                         | latest         |
| Config management     | python-dotenv                               | latest         |
| Deployment            | Railway (Nixpacks builder)                  | —              |
| Runtime               | Python 3.11+                                | —              |

---

## Project Structure

```
fachmann-mcp/
├── Procfile                  # Railway: proceso web y worker
├── requirements.txt          # Dependencias Python
├── .env.example              # Plantilla de variables de entorno
├── data/
│   └── fachmann.db           # SQLite (generado por setup_db.py, no versionar)
├── src/
│   ├── __init__.py
│   ├── server.py             # MCP HTTP server — 4 herramientas CRM
│   ├── setup_db.py           # Inicializa schema y seed data (15 productos, 7 clientes)
│   ├── cotizador.py          # Agentic loop Claude + function calling
│   ├── bot.py                # Telegram bot — handler de requerimientos
│   ├── pdf_generator.py      # Renderiza HTML con Jinja2 y convierte a PDF
│   └── templates/
│       └── propuesta.html    # Plantilla HTML de la propuesta comercial
└── tests/
    ├── __init__.py
    └── test_cotizador.py
```

---

## Setup — Local Development

### Prerequisites

- Python 3.11+
- En Windows: WeasyPrint requiere GTK3 runtime para generar PDFs. Sin GTK3, el bot funciona con fallback a texto.
- En Linux/macOS: `sudo apt install libpango-1.0-0 libpangoft2-1.0-0` (Ubuntu) o equivalente.

### 1. Clonar y crear entorno virtual

```bash
git clone <repo-url>
cd fachmann-mcp

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con los valores reales
```

### 3. Inicializar la base de datos

```bash
python src/setup_db.py
```

Esto crea `data/fachmann.db` con el schema completo y 15 productos de ejemplo (5 por marca) junto con 7 clientes/prospectos, 5 oportunidades de venta y 6 interacciones iniciales.

### 4. Correr los servicios

Correr el MCP server (transporte HTTP por defecto):
```bash
python src/server.py
```

Correr el Telegram bot (en otra terminal):
```bash
python src/bot.py
```

Para usar un transporte distinto en el MCP server (ej. stdio para Claude Desktop):
```bash
MCP_TRANSPORT=stdio python src/server.py
```

### 5. Correr tests

```bash
pytest
```

---

## Setup — Railway Deployment

El proyecto usa dos servicios Railway que comparten la misma imagen pero ejecutan procesos distintos segun el `Procfile`.

### Procfile

```
web:    python src/setup_db.py && python src/server.py
worker: python src/setup_db.py && python src/bot.py
```

Cada servicio corre `setup_db.py` al arranque para garantizar que la base este inicializada (idempotente por uso de `CREATE TABLE IF NOT EXISTS` e `INSERT OR IGNORE`).

### Pasos

1. Crear un proyecto nuevo en [Railway](https://railway.app).
2. Conectar el repositorio GitHub.
3. Railway detecta el `Procfile` automaticamente con Nixpacks.
4. Crear **dos servicios** dentro del mismo proyecto:
   - Servicio `web`: apuntar al proceso `web` del Procfile.
   - Servicio `worker`: apuntar al proceso `worker` del Procfile.
5. Configurar las variables de entorno en cada servicio (ver tabla abajo).
6. Railway asigna `$PORT` automaticamente al servicio web; no es necesario configurarlo manualmente.

> **Nota sobre persistencia:** Para produccion, agregar un volumen Railway con mount path `/app/data` en ambos servicios. Sin volumen, el archivo SQLite se pierde en cada redeploy.

---

## Environment Variables

| Variable            | Requerida | Default              | Descripcion                                                                 |
|---------------------|-----------|----------------------|-----------------------------------------------------------------------------|
| `ANTHROPIC_API_KEY` | Si        | —                    | API key de Anthropic. Usada por `cotizador.py` para llamar a Claude.        |
| `TELEGRAM_TOKEN`    | Si        | —                    | Token del bot de Telegram obtenido via BotFather. Requerido solo en worker. |
| `CLAUDE_MODEL`      | No        | `claude-sonnet-4-6`  | ID del modelo Claude a usar en el cotizador.                                |
| `DB_PATH`           | No        | `data/fachmann.db`   | Ruta al archivo SQLite. Ambos servicios deben apuntar al mismo archivo.     |
| `MCP_PORT`          | No        | `8000`               | Puerto local del MCP server. En Railway se sobreescribe con `$PORT`.        |
| `MCP_HOST`          | No        | `0.0.0.0`            | Host bind del MCP server.                                                   |
| `MCP_TRANSPORT`     | No        | `streamable-http`    | Transporte del MCP server. Opciones: `streamable-http`, `stdio`.            |

`.env.example`:
```env
DB_PATH=data/fachmann.db
TELEGRAM_TOKEN=your_botfather_token_here
ANTHROPIC_API_KEY=your_anthropic_key_here
CLAUDE_MODEL=claude-sonnet-4-6
MCP_PORT=8000
```

---

## Usage

### MCP Tools Reference

El servidor MCP expone cuatro herramientas bajo el namespace `fachmann_mcp`. Cualquier cliente MCP compatible (Claude Desktop, agente Python con SDK MCP, etc.) puede invocarlas.

#### `fachmann_buscar_catalogo`

Busca productos por texto libre en descripcion, SKU, categoria y especificaciones. Filtro opcional por marca.

**Input:**
| Campo  | Tipo            | Requerido | Descripcion                                              |
|--------|-----------------|-----------|----------------------------------------------------------|
| query  | string (2–200)  | Si        | Texto a buscar (ej. `"rele seguridad"`, `"bandeja"`)     |
| marca  | string (enum)   | No        | `"PILZ"`, `"OBO"` o `"CABUR"`. Omitir para todas.       |

**Output:** JSON `{ "total": int, "productos": [...] }` con sku, marca, categoria, descripcion, precio_usd, stock, tiempo_entrega_dias.

---

#### `fachmann_consultar_disponibilidad`

Devuelve la ficha completa de un producto por SKU exacto: precio, stock, tiempo de entrega, especificaciones tecnicas y flag `disponible_inmediato`.

**Input:**
| Campo | Tipo           | Requerido | Descripcion                              |
|-------|----------------|-----------|------------------------------------------|
| sku   | string (2–100) | Si        | SKU exacto (ej. `"PNOZ-S6-24VDC-2NO"`)  |

**Output:** JSON con todos los campos del producto + `disponible_inmediato: bool`.

---

#### `fachmann_buscar_contexto_cliente`

Recupera el perfil de uno o mas clientes/prospectos por nombre (busqueda parcial). Incluye las ultimas 5 interacciones y todas las oportunidades de venta activas (no cerradas).

**Input:**
| Campo   | Tipo           | Requerido | Descripcion                                        |
|---------|----------------|-----------|----------------------------------------------------|
| empresa | string (2–200) | Si        | Nombre o fragmento (ej. `"Arcor"`, `"Valentina"`)  |

**Output:** JSON `{ "total": int, "clientes": [...] }` con datos de contacto, industria, estado_lead, interacciones_recientes y oportunidades_activas.

---

#### `fachmann_registrar_interaccion`

Registra una nueva interaccion en el historial del cliente. El `cliente_id` se obtiene previamente con `fachmann_buscar_contexto_cliente`.

**Input:**
| Campo      | Tipo    | Requerido | Descripcion                                                              |
|------------|---------|-----------|--------------------------------------------------------------------------|
| cliente_id | int     | Si        | ID numerico del cliente (>= 1)                                           |
| notas      | string  | Si        | Resumen de la interaccion, acuerdos y proximos pasos (5–2000 caracteres) |
| tipo       | string  | No        | `"reunion"`, `"email"`, `"llamada"`, `"whatsapp"` o `"nota"` (default)  |

**Output:** JSON de confirmacion con `interaccion_id`, nombre del cliente, tipo y fecha.

---

### Telegram Bot Usage

El bot funciona exclusivamente con mensajes de texto libre. No requiere comandos ni estructura especifica.

**Comandos disponibles:**
- `/start` — Muestra el mensaje de bienvenida y descripcion
- `/ayuda` — Ejemplos de requerimientos que puede procesar

**Flujo de uso:**

1. El vendedor escribe el requerimiento en lenguaje natural:
   ```
   Prensa hidraulica con control dos manos, categoria 4, planta Arcor Cordoba.
   Necesito tambien bandejas portacables para el tablero.
   ```

2. El bot responde: `"Procesando requerimiento... Consultando catalogo y generando propuesta."`

3. Claude ejecuta un loop agentico:
   - Llama a `buscar_catalogo("control dos manos", "PILZ")`
   - Llama a `consultar_disponibilidad("PNOZ-S6-24VDC-2NO")`
   - Llama a `buscar_catalogo("bandeja portacables", "OBO")`
   - Consolida la propuesta en JSON estructurado

4. El bot envia:
   - **PDF adjunto**: `propuesta_Arcor_2026-03-04.pdf` con numero de propuesta, tabla de productos, justificacion normativa y totales
   - **Borrador de email**: texto profesional listo para copiar y enviar al cliente

**Ejemplos de requerimientos validos:**
```
"Modulo seguridad para prensa dos manos categoria 4, cliente Techint"
"Rele para parada de emergencia PL e, planta Arcor Cordoba"
"Bandejas portacables para tablero 2m x 60cm, proyecto Molinos"
"Sistema configurable para 4 funciones de seguridad simultaneas"
"Borneras fusibles 10mm2 para tablero 400A, proyecto farmaceutico"
```

---

## Database Schema

SQLite, archivo unico en `data/fachmann.db`. Inicializado con `python src/setup_db.py`.

### `productos_catalogo`

| Columna              | Tipo    | Descripcion                                          |
|----------------------|---------|------------------------------------------------------|
| id                   | INTEGER | PK autoincrement                                     |
| sku                  | TEXT    | Codigo unico del producto (UNIQUE NOT NULL)          |
| marca                | TEXT    | `PILZ`, `OBO` o `CABUR` (CHECK constraint)           |
| categoria            | TEXT    | Categoria del producto                               |
| descripcion          | TEXT    | Descripcion comercial                                |
| precio_usd           | REAL    | Precio en dolares                                    |
| especificaciones     | TEXT    | Especificaciones tecnicas detalladas                 |
| stock                | INTEGER | Unidades en stock (default: 0)                       |
| tiempo_entrega_dias  | INTEGER | Dias de entrega estimados (default: 30)              |
| activo               | INTEGER | Flag logico (1 = activo, 0 = inactivo)               |
| created_at           | TEXT    | Timestamp de creacion                                |

**Seed data:** 15 productos (5 por marca).

---

### `clientes_prospectos`

| Columna           | Tipo    | Descripcion                                                                      |
|-------------------|---------|----------------------------------------------------------------------------------|
| id                | INTEGER | PK autoincrement                                                                 |
| razon_social      | TEXT    | Nombre de la empresa                                                             |
| contacto_nombre   | TEXT    | Nombre del contacto principal                                                    |
| contacto_email    | TEXT    | Email del contacto                                                               |
| contacto_telefono | TEXT    | Telefono del contacto                                                            |
| industria         | TEXT    | Sector industrial                                                                |
| estado_lead       | TEXT    | `prospecto`, `contactado`, `en_negociacion`, `cliente_activo` o `perdido`        |
| linkedin_url      | TEXT    | URL de LinkedIn del contacto (nullable)                                          |
| notas             | TEXT    | Notas internas sobre el cliente                                                  |
| created_at        | TEXT    | Timestamp de alta                                                                |
| updated_at        | TEXT    | Timestamp de ultima modificacion                                                 |

**Seed data:** 7 clientes/prospectos (Arcor, Techint, Grupo Fate, Metalurgica Santa Rosa, Sistemi Integrazione, Molinos Rio de la Plata, Laboratorio Roemmers).

---

### `oportunidades_ventas`

| Columna                | Tipo    | Descripcion                                                                              |
|------------------------|---------|------------------------------------------------------------------------------------------|
| id                     | INTEGER | PK autoincrement                                                                         |
| cliente_id             | INTEGER | FK a `clientes_prospectos.id`                                                            |
| descripcion            | TEXT    | Descripcion de la oportunidad                                                            |
| monto_usd              | REAL    | Valor estimado en dolares                                                                |
| probabilidad_cierre    | INTEGER | Porcentaje de probabilidad (0–100)                                                       |
| etapa                  | TEXT    | `prospecting`, `qualification`, `proposal`, `negotiation`, `closed_won`, `closed_lost`   |
| notas_tecnicas         | TEXT    | Notas tecnicas y de competencia                                                          |
| fecha_creacion         | TEXT    | Timestamp de creacion                                                                    |
| fecha_cierre_estimada  | TEXT    | Fecha estimada de cierre                                                                 |
| updated_at             | TEXT    | Timestamp de ultima modificacion                                                         |

---

### `interacciones`

| Columna    | Tipo    | Descripcion                                                            |
|------------|---------|------------------------------------------------------------------------|
| id         | INTEGER | PK autoincrement                                                       |
| cliente_id | INTEGER | FK a `clientes_prospectos.id`                                          |
| tipo       | TEXT    | `reunion`, `email`, `llamada`, `whatsapp` o `nota`                     |
| notas      | TEXT    | Descripcion de la interaccion (NOT NULL)                               |
| fecha      | TEXT    | Timestamp de la interaccion                                            |

**Indices:** `idx_productos_marca`, `idx_productos_categoria`, `idx_clientes_nombre`, `idx_interacciones_cli`, `idx_oportunidades_cli`.

---

## ISO 13849-1:2015 — Normative Context

El cotizador embebe conocimiento normativo de **ISO 13849-1:2015** (Safety of machinery — Safety-related parts of control systems) directamente en el system prompt de Claude.

### Performance Levels (PL) y Categorias

| PL    | Categoria | Descripcion de arquitectura                                      | Producto PILZ tipico  |
|-------|-----------|------------------------------------------------------------------|-----------------------|
| PL a  | —         | Sin requisitos de arquitectura especifica                        | —                     |
| PL b  | Cat 1     | Componente unico probado (bien dimensionado)                     | —                     |
| PL c  | Cat 2     | Con funcion de test periodico                                    | —                     |
| PL d  | Cat 3     | Arquitectura redundante de dos canales                           | PNOZ XV2              |
| PL e  | Cat 4     | Redundante + deteccion de fallas de causa comun                  | PNOZ s6, PNOZmulti 2  |

### Reglas de seleccion PILZ (codificadas en el system prompt)

| Aplicacion                          | Producto recomendado            |
|-------------------------------------|---------------------------------|
| Parada de emergencia, Cat 4 / PL e  | PNOZ s6 o PNOZ XV2              |
| Control dos manos, Cat 4            | PNOZ s6 o PNOZ XV2              |
| Proteccion de resguardos, Cat 3–4   | PNOZ XV2                        |
| Multiples funciones de seguridad    | PNOZmulti 2 (PNOZ-M-B0)         |
| Monitoreo de velocidad segura       | PMCprotego DS (SIL 2)           |
| Automatizacion segura a escala      | PSS 4000 CPU                    |

Cada propuesta generada por el cotizador incluye el campo `norma_aplicable` con el PL y categoria requeridos, y una `justificacion` por producto que explica la seleccion en terminos normativos.

---

## Roadmap

- [ ] Persistencia en PostgreSQL (Railway plugin o Supabase) para eliminar limitacion de SQLite efimero
- [ ] Herramienta MCP `fachmann_crear_oportunidad` para registrar oportunidades desde el agente
- [ ] Herramienta MCP `fachmann_actualizar_etapa` para mover oportunidades en el pipeline
- [ ] Autenticacion del bot por `chat_id` para restringir acceso al equipo de ventas
- [ ] Soporte multi-usuario: numeracion de propuestas por usuario
- [ ] Template HTML con logo y estilos corporativos Fachmann
- [ ] Integracion con calendario: sugerir fecha de seguimiento al registrar interaccion
- [ ] Exportacion de pipeline a CSV desde el MCP server

---

## License

Propietario — uso interno Fachmann. No redistribuir.
