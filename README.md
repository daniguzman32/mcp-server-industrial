# fachmann-mcp

Sistema de asistencia comercial B2B para Fachmann, representante en Argentina de **PILZ** (seguridad funcional), **OBO Bettermann** (gestión de cables), **CABUR** (borneras y conectores) e **IDEM Safety** (dispositivos de seguridad perimetral).

Compuesto por dos servicios independientes desplegados en Railway:

- **MCP Server** (`web`): servidor HTTP que expone herramientas CRM a clientes MCP (Claude Desktop, agentes, etc.).
- **Telegram Bot** (`worker`): cotizador técnico conversacional que recibe requerimientos en lenguaje natural, guía al vendedor con preguntas técnicas mediante botones inline, y devuelve una propuesta técnica en PDF con borrador de email.

---

## Architecture

```
                         ┌─────────────────────────────────────────┐
                         │              Railway                      │
                         │                                           │
┌──────────────┐  HTTP   │  ┌──────────────────────────────────────┐│
│ Claude       │◄────────┤  │  web service (MCP HTTP Server)       ││
│ Desktop /    │         │  │  python src/server.py                ││
│ MCP Client   │         │  │  FastMCP + asyncpg                   ││
└──────────────┘         │  │  Port: $PORT (Railway) / 8000 (local)││
                         │  └──────────────────┬───────────────────┘│
                         │                     │                     │
                         │           PostgreSQL │ (Railway plugin)   │
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
                                   │  Claude Haiku 4.5     │
                                   │  Function calling:    │
                                   │  buscar_catalogo      │
                                   │  consultar_disponib.  │
                                   │  listar_tarifas       │
                                   └───────────────────────┘

Flujo del Telegram Bot:
 Vendedor ──► mensaje de texto ──► bot.py
                                     │
                              cotizador.py (agentic loop)
                                     │
                         ┌───────────┴───────────┐
                         │                       │
                   Claude API ◄──► PostgreSQL catalog
                         │
                   resultado JSON (tipo)
                         │
          ┌──────────────┼──────────────┐
          │              │              │
       propuesta       preguntas    sin_resultado
          │           (wizard)
          │         botones inline
    ┌─────┴──────┐   por pregunta
    │            │
pdf_generator  email_draft
(ReportLab)   (Markdown)
    │
PDF bytes ──► Telegram reply_document
```

---

## Features

**MCP Server (CRM tools)**
- Búsqueda de texto libre en el catálogo de 27.626 productos (PILZ, OBO, CABUR, IDEM Safety) con filtro por marca
- Consulta de precio exacto, stock disponible, tiempo de entrega y precio neto con descuento por tarifa
- Recuperación de perfil completo de clientes/prospectos: datos de contacto, estado del lead, últimas interacciones y oportunidades activas
- Registro de interacciones (reunión, email, llamada, whatsapp, nota) con timestamp automático
- Gestión de oportunidades de venta: creación y actualización de etapa en el pipeline

**Telegram Bot (Cotizador Técnico)**
- Requerimientos en lenguaje natural sin estructura requerida
- **Wizard de preguntas técnicas con botones inline**: cuando falta información, el bot presenta preguntas con opciones en teclado Telegram (no text input). Cada pregunta incluye contexto técnico, referencia normativa y opción "No sé" con asunción segura
- **Descuentos por tarifa en cascada**: `/tarifa` activa una tarifa de descuento para la sesión; el cotizador calcula `precio = lista × (1-d1) × (1-d2) × (1-d3)` automáticamente
- **TTL de sesión**: estado del wizard auto-expira a los 30 minutos con notificación al usuario
- Prioridad de marcas: PILZ para seguridad funcional, IDEM Safety como complemento, OBO y CABUR para infraestructura
- Genera PDF de propuesta comercial numerada y lo adjunta directamente en el chat
- Borrador de email profesional listo para copiar
- Fallback a resumen en texto Markdown si el generador de PDF no está disponible
- `/cliente <nombre>` — perfil completo + historial de interacciones + oportunidades activas
- `/nueva` — cancela el wizard activo y limpia el estado de la sesión

**Normativa integrada**
- System prompt embebe ISO 13849-1:2015 (PL a–e, Categorías 1–4)
- Guías técnicas de selección por marca en `src/guides/` (pilz.md, idem_safety.md, obo.md, cabur.md)
- Cada pregunta del wizard incluye `nivel_criticidad` (alta/media/baja) y `referencia_normativa`
- Justificación normativa incluida en cada línea de producto de la propuesta

---

## Tech Stack

| Componente            | Tecnología                                          | Versión        |
|-----------------------|-----------------------------------------------------|----------------|
| MCP Server            | FastMCP (Python)                                    | mcp[cli] >=1.0 |
| Async DB driver       | asyncpg                                             | latest         |
| Base de datos         | PostgreSQL (Railway plugin)                         | 15+            |
| Telegram Bot          | python-telegram-bot                                 | >=21.0         |
| LLM / Function calling| Anthropic Claude API (claude-haiku-4-5-20251001)    | anthropic SDK  |
| PDF generation        | ReportLab                                           | latest         |
| Config management     | python-dotenv                                       | latest         |
| Deployment            | Railway (Nixpacks builder)                          | —              |
| Runtime               | Python 3.11+                                        | —              |

---

## Project Structure

```
fachmann-mcp/
├── Procfile                  # Railway: proceso web y worker
├── nixpacks.toml             # Build config Railway (system deps)
├── requirements.txt          # Dependencias Python
├── .env.example              # Plantilla de variables de entorno
├── src/
│   ├── __init__.py
│   ├── server.py             # MCP HTTP server — herramientas CRM
│   ├── setup_db.py           # Inicializa schema PostgreSQL (idempotente)
│   ├── migrar_db.py          # Migración: IDEM Safety + reglas_descuento
│   ├── cotizador.py          # Agentic loop Claude + function calling
│   ├── bot.py                # Telegram bot — wizard inline keyboards
│   ├── pdf_generator.py      # Genera PDF con ReportLab
│   └── guides/               # Guías técnicas de selección por marca
│       ├── pilz.md
│       ├── idem_safety.md
│       ├── obo.md
│       └── cabur.md
└── tests/
    ├── __init__.py
    └── test_cotizador.py
```

> `importar_catalogo.py` y archivos `*.xlsx` son privados y están en `.gitignore`.

---

## Setup — Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL accesible (local o Railway public URL)

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

Crea el schema completo (5 tablas) en PostgreSQL. Es idempotente: se puede correr múltiples veces sin problemas.

### 4. Correr los servicios

```bash
# MCP server (transporte HTTP por defecto)
python src/server.py

# Telegram bot (en otra terminal)
python src/bot.py
```

Para usar stdio (Claude Desktop):
```bash
MCP_TRANSPORT=stdio python src/server.py
```

### 5. Correr tests

```bash
pytest
```

---

## Setup — Railway Deployment

### Procfile

```
web:    python src/setup_db.py && python src/server.py
worker: python src/setup_db.py && python src/bot.py
```

### Pasos

1. Crear proyecto en [Railway](https://railway.app) y conectar el repositorio GitHub.
2. Agregar el **PostgreSQL plugin** al proyecto. Railway inyecta `DATABASE_URL` automáticamente.
3. Crear **dos servicios** dentro del mismo proyecto:
   - Servicio `web`: proceso `web` del Procfile.
   - Servicio `worker`: proceso `worker` del Procfile.
4. Configurar las variables de entorno en cada servicio (ver tabla abajo).
5. Railway asigna `$PORT` automáticamente al servicio web.

> **Importante:** usar siempre `DATABASE_URL` (URL interna del plugin) desde los contenedores Railway. `DATABASE_PUBLIC_URL` es solo para acceso externo desde scripts locales de administración.

---

## Environment Variables

| Variable            | Requerida | Default                       | Descripción                                                                 |
|---------------------|-----------|-------------------------------|-----------------------------------------------------------------------------|
| `DATABASE_URL`      | Sí        | —                             | URL interna de PostgreSQL (inyectada por Railway plugin).                   |
| `ANTHROPIC_API_KEY` | Sí        | —                             | API key de Anthropic. Usada por `cotizador.py`.                             |
| `TELEGRAM_TOKEN`    | Sí (worker)| —                            | Token del bot de Telegram obtenido via BotFather.                           |
| `CLAUDE_MODEL`      | No        | `claude-haiku-4-5-20251001`   | ID del modelo Claude. Usar `claude-sonnet-4-6` para mayor calidad.          |
| `MCP_PORT`          | No        | `8000`                        | Puerto local del MCP server. En Railway se sobreescribe con `$PORT`.        |
| `MCP_HOST`          | No        | `0.0.0.0`                     | Host bind del MCP server.                                                   |
| `MCP_TRANSPORT`     | No        | `streamable-http`             | Transporte del MCP server. Opciones: `streamable-http`, `stdio`.            |

`.env.example`:
```env
DATABASE_URL=postgresql://user:password@host:5432/dbname?sslmode=require
TELEGRAM_TOKEN=your_botfather_token_here
ANTHROPIC_API_KEY=your_anthropic_key_here
CLAUDE_MODEL=claude-haiku-4-5-20251001
MCP_PORT=8000
```

---

## Usage

### MCP Tools Reference

El servidor MCP expone herramientas bajo el namespace `fachmann`. Cualquier cliente MCP compatible puede invocarlas.

#### `fachmann_buscar_catalogo`

Busca productos por texto libre en descripción, SKU, categoría y especificaciones.

**Input:**
| Campo | Tipo           | Requerido | Descripción                                          |
|-------|----------------|-----------|------------------------------------------------------|
| query | string         | Sí        | Texto a buscar (ej. `"relé seguridad"`, `"bandeja"`) |
| marca | string (enum)  | No        | `"PILZ"`, `"OBO"`, `"CABUR"` o `"IDEM SAFETY"`      |

**Output:** `{ "total_mostrados": int, "productos": [...] }` — hasta 20 resultados con sku, marca, categoría, descripción, precio_lista_usd, stock, tiempo_entrega_dias.

---

#### `fachmann_consultar_disponibilidad`

Ficha completa de un producto por SKU: precio de lista, precio neto con descuento de tarifa, análisis de stock vs cantidad solicitada.

**Input:**
| Campo    | Tipo    | Requerido | Descripción                                    |
|----------|---------|-----------|------------------------------------------------|
| sku      | string  | Sí        | SKU exacto (ej. `"PNOZ-S6-24VDC-2NO"`)        |
| cantidad | integer | No        | Cantidad requerida para análisis de stock (default: 1) |

**Output:** Ficha del producto + `estado_stock` (`disponible` / `sin_stock` / `parcial`) + `precio_neto_usd` (con descuento si hay tarifa activa) + `tiempo_entrega_estimado_dias`.

---

#### `fachmann_buscar_contexto_cliente`

Perfil de clientes/prospectos por nombre (búsqueda parcial). Incluye últimas interacciones y oportunidades activas.

**Input:**
| Campo   | Tipo   | Requerido | Descripción                               |
|---------|--------|-----------|-------------------------------------------|
| empresa | string | Sí        | Nombre o fragmento (ej. `"Arcor"`)        |

**Output:** Datos de contacto, industria, estado_lead, interacciones_recientes, oportunidades_activas.

---

#### `fachmann_registrar_interaccion`

Registra una interacción en el historial del cliente.

**Input:**
| Campo      | Tipo    | Requerido | Descripción                                                        |
|------------|---------|-----------|--------------------------------------------------------------------|
| cliente_id | int     | Sí        | ID del cliente (obtenido con `buscar_contexto_cliente`)            |
| notas      | string  | Sí        | Resumen de la interacción y próximos pasos                         |
| tipo       | string  | No        | `"reunion"`, `"email"`, `"llamada"`, `"whatsapp"` o `"nota"`      |

---

#### `fachmann_gestionar_oportunidad`

Crea o actualiza una oportunidad de venta en el pipeline.

---

### Telegram Bot — Comandos

| Comando              | Descripción                                                         |
|----------------------|---------------------------------------------------------------------|
| `/start`             | Mensaje de bienvenida                                               |
| `/ayuda`             | Ejemplos de requerimientos                                          |
| `/tarifa`            | Ver tarifa activa                                                   |
| `/tarifa lista`      | Ver todas las tarifas disponibles                                   |
| `/tarifa <nombre>`   | Activar tarifa de descuento para la sesión                          |
| `/cliente <nombre>`  | Perfil completo + historial + oportunidades activas                 |
| `/nueva`             | Cancelar wizard en curso y empezar de cero                          |

### Telegram Bot — Flujo de uso

1. El vendedor escribe el requerimiento en lenguaje natural:
   ```
   Barrera de luz IDEM de 1500mm para zona de acceso, cliente Techint
   ```

2. Si falta información técnica, el bot presenta un **wizard de preguntas con botones inline**:
   ```
   Pregunta 1/3 (seguridad crítica — ISO 13849-1)

   ¿Qué parte del cuerpo se necesita proteger?

   [Dedos (14mm)]  [Mano (25mm)]
   [Cuerpo (90mm)] [No sé / No tengo el dato]
   ```

3. El usuario elige con un click. El bot avanza a la siguiente pregunta automáticamente.

4. Con toda la información, Claude ejecuta el agentic loop:
   - `buscar_catalogo("cortina luz IDEM", "IDEM SAFETY")`
   - `consultar_disponibilidad("IDEM-SF4B-H1080-14", cantidad=1)`
   - Consolida propuesta JSON

5. El bot envía:
   - **PDF adjunto**: propuesta numerada con tabla de productos y justificación normativa
   - **Borrador de email**: texto profesional listo para enviar

### Tarifas de descuento

Los descuentos se aplican en cascada: `precio_final = lista × (1-d1) × (1-d2) × (1-d3)`

```
/tarifa Dist. Principal - Pilz 25% - Resto 30+10
/tarifa Pilz System Partner - 30+10
/tarifa 30% OBO - Cabur - Pilz 0%
/tarifa End User (5%)
```

---

## Database Schema

PostgreSQL en Railway plugin. Inicializado con `python src/setup_db.py`.

### `productos_catalogo`

| Columna             | Tipo    | Descripción                                      |
|---------------------|---------|--------------------------------------------------|
| id                  | SERIAL  | PK                                               |
| sku                 | TEXT    | Código único del producto (UNIQUE NOT NULL)      |
| marca               | TEXT    | `PILZ`, `OBO`, `CABUR` o `IDEM SAFETY`           |
| categoria           | TEXT    | Categoría del producto                           |
| descripcion         | TEXT    | Descripción comercial                            |
| precio_usd          | NUMERIC | Precio de lista en dólares                       |
| especificaciones    | TEXT    | Especificaciones técnicas                        |
| stock               | INTEGER | Unidades en stock                                |
| tiempo_entrega_dias | INTEGER | Días de entrega estimados                        |
| activo              | INTEGER | Flag lógico (1 = activo)                         |

**Datos reales:** 27.626 productos (PILZ, OBO, CABUR, IDEM Safety).

---

### `clientes_prospectos`

| Columna           | Tipo   | Descripción                                                                    |
|-------------------|--------|--------------------------------------------------------------------------------|
| id                | SERIAL | PK                                                                             |
| razon_social      | TEXT   | Nombre de la empresa                                                           |
| contacto_nombre   | TEXT   | Nombre del contacto principal                                                  |
| contacto_email    | TEXT   | Email del contacto                                                             |
| contacto_telefono | TEXT   | Teléfono del contacto                                                          |
| contacto_cargo    | TEXT   | Cargo del contacto                                                             |
| industria         | TEXT   | Sector industrial                                                              |
| estado_lead       | TEXT   | `nuevo_cliente`, `calificado`, `oferta`, `ganado`, `perdido`, `cancelado`      |
| notas             | TEXT   | Notas internas sobre el cliente                                                |
| updated_at        | TEXT   | Timestamp de última modificación                                               |

---

### `oportunidades_ventas`

| Columna               | Tipo    | Descripción                                                                             |
|-----------------------|---------|-----------------------------------------------------------------------------------------|
| id                    | SERIAL  | PK                                                                                      |
| cliente_id            | INTEGER | FK a `clientes_prospectos.id`                                                           |
| descripcion           | TEXT    | Descripción de la oportunidad                                                           |
| monto_usd             | NUMERIC | Valor estimado en dólares                                                               |
| probabilidad_cierre   | INTEGER | Porcentaje (0–100)                                                                      |
| etapa                 | TEXT    | `prospecting`, `qualification`, `proposal`, `negotiation`, `closed_won`, `closed_lost`  |
| fecha_cierre_estimada | TEXT    | Fecha estimada de cierre                                                                |

---

### `interacciones`

| Columna    | Tipo    | Descripción                                            |
|------------|---------|--------------------------------------------------------|
| id         | SERIAL  | PK                                                     |
| cliente_id | INTEGER | FK a `clientes_prospectos.id`                          |
| tipo       | TEXT    | `reunion`, `email`, `llamada`, `whatsapp` o `nota`     |
| notas      | TEXT    | Descripción de la interacción (NOT NULL)               |
| fecha      | TEXT    | Timestamp de la interacción                            |

---

### `reglas_descuento`

Define los porcentajes de descuento en cascada por tarifa y marca.

| Columna       | Tipo    | Descripción                                 |
|---------------|---------|---------------------------------------------|
| id            | SERIAL  | PK                                          |
| tarifa_nombre | TEXT    | Nombre de la tarifa (ej. "End User (5%)")   |
| marca         | TEXT    | `PILZ`, `OBO`, `CABUR` o `IDEM SAFETY`      |
| desc_1        | NUMERIC | Primer descuento (%)                        |
| desc_2        | NUMERIC | Segundo descuento (%)                       |
| desc_3        | NUMERIC | Tercer descuento (%)                        |

Cálculo: `precio_final = precio_lista × (1 - desc_1/100) × (1 - desc_2/100) × (1 - desc_3/100)`

---

## ISO 13849-1:2015 — Contexto normativo

El cotizador embebe conocimiento normativo de **ISO 13849-1:2015** directamente en el system prompt de Claude, complementado con guías técnicas de selección por marca en `src/guides/`.

### Performance Levels (PL) y Categorías

| PL    | Categoría | Arquitectura                                           | Producto PILZ típico  |
|-------|-----------|--------------------------------------------------------|-----------------------|
| PL a  | —         | Sin requisitos de arquitectura específica              | —                     |
| PL b  | Cat 1     | Componente único probado                               | —                     |
| PL c  | Cat 2     | Con función de test periódico                          | —                     |
| PL d  | Cat 3     | Arquitectura redundante de dos canales                 | PNOZ XV2              |
| PL e  | Cat 4     | Redundante + detección de fallas de causa común        | PNOZ s6, PNOZmulti 2  |

### Reglas de selección (codificadas en el system prompt)

| Aplicación                          | Producto recomendado            |
|-------------------------------------|---------------------------------|
| Parada de emergencia, Cat 4 / PL e  | PNOZ s6 o PNOZ XV2              |
| Control dos manos, Cat 4            | PNOZ s6 o PNOZ XV2              |
| Protección de resguardos, Cat 3–4   | PNOZ XV2                        |
| Múltiples funciones de seguridad    | PNOZmulti 2 (PNOZ-M-B0)         |
| Monitoreo de velocidad segura       | PMCprotego DS (SIL 2)           |
| Cortinas de luz / barreras          | IDEM Safety (SF4B, SF4C series) |
| Interruptores de puerta / bordes    | IDEM Safety                     |

---

## Roadmap

- [ ] Autenticación del bot por `chat_id` para restringir acceso al equipo de ventas
- [ ] Soporte multi-usuario: numeración de propuestas por usuario
- [ ] Template PDF con logo y estilos corporativos Fachmann
- [ ] Carga de clientes reales en `clientes_prospectos` (actualmente datos demo)
- [ ] Integración con calendario: sugerir fecha de seguimiento al registrar interacción
- [ ] Exportación de pipeline a CSV desde el MCP server
- [ ] Wizard de preguntas multi-step tipo grafo de riesgo (máquina → función → PL → tensión)

---

## License

Propietario — uso interno Fachmann. No redistribuir.
