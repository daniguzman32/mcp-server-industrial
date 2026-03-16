# Guía de Selección PILZ

## Familias de productos y cuándo usar cada una

### PNOZ s (relés de seguridad de función fija)
Relés compactos para una función de seguridad específica. Elección cuando la máquina tiene 1-2 funciones de seguridad y no requiere lógica configurable.

| Modelo | Aplicación principal | PL / Categoría |
|--------|---------------------|----------------|
| PNOZ s4 | Parada de emergencia, 1 circuito de habilitación | PL e / Cat 4 |
| PNOZ s5 | Parada de emergencia + protección de resguardos, 2 circuitos | PL e / Cat 4 |
| PNOZ s6 | E-stop + temporización de arranque, 2 circuitos | PL e / Cat 4 |
| PNOZ s7 | E-stop + 3 circuitos de habilitación | PL e / Cat 4 |
| PNOZ s9 | Control de dos manos (tipo IIIC), 2 circuitos | PL e / Cat 4 |
| PNOZ s10 | Monitoreo de puerta con bloqueo, 2 circuitos | PL e / Cat 4 |

Tensiones disponibles: 24 VDC (más común), 110 VAC, 230 VAC.
Tiempo de respuesta: ≤20 ms (salvo modelos con temporización).

### PNOZ XV (relés universales)
Relés universales que pueden configurarse para múltiples aplicaciones mediante DIP switches o software.

| Modelo | Aplicación | PL / Cat |
|--------|-----------|----------|
| PNOZ XV1 | 1 canal, menor costo, guardas fijas | PL c / Cat 2 |
| PNOZ XV2 | 2 canales, la opción más versátil, E-stop y guardas | PL e / Cat 4 |
| PNOZ XV3 | Control de dos manos tipo IIIC | PL e / Cat 4 |
| PNOZ XV4 | Tapete de seguridad y bordes sensibles | PL e / Cat 4 |

### PNOZmulti 2 (controlador de seguridad configurable)
Para máquinas con 3+ funciones de seguridad simultáneas o cuando se requiere diagnóstico centralizado. Se programa con PNOZmulti Configurator (software gratuito).

- Módulo base: PNOZ-M-B0 (4 entradas de seguridad, 2 salidas OSSD)
- Módulos de expansión: I/O adicionales, comunicación (Profibus, Profinet, EtherNet/IP)
- Aplicaciones: líneas de producción, robots, prensas con múltiples zonas de seguridad
- PL e / Cat 4 con arquitectura dual

Cuándo elegir PNOZmulti sobre PNOZ s:
- Más de 2 funciones de seguridad
- Se requiere comunicación con PLC maestro
- Se necesita diagnóstico de falla por canal

### PMCprotego (monitoreo de velocidad y posición seguro)
Para aplicaciones donde la velocidad, posición o dirección del movimiento son parámetros de seguridad.

- Funciones: SLS (límite de velocidad segura), SMS (máxima velocidad segura), SDI (dirección segura), SOS (parada segura), SLP (posición límite segura)
- Entradas encoder: SinCos, HTL, TTL, resolvers
- SIL 2 / PL d-e
- Aplicaciones: tornos, centros de mecanizado, prensas con modo ajuste

### PSS 4000 (PLC de seguridad)
Para sistemas de automatización segura a escala de planta o líneas completas.
- SafetyNET p para comunicación distribuida
- Cuando se requiere integrar seguridad y automatización estándar en un solo sistema
- PL e / Cat 4

---

## Lógica de selección por aplicación

**Parada de emergencia (E-stop)**
- 1 función, presupuesto ajustado → PNOZ s4 o PNOZ XV2
- Múltiples E-stops en serie → PNOZ s5 o PNOZmulti 2

**Protección de resguardos / puertas**
- Puerta con enclavamiento sin bloqueo → PNOZ XV2
- Puerta con bloqueo (muting) → PNOZ s10 o PNOZmulti 2

**Control de dos manos**
- Función única → PNOZ s9 o PNOZ XV3
- Con otras funciones simultáneas → PNOZmulti 2

**Cortinas de luz / barreras ópticas (ESPE)**
- El relé de seguridad recibe las señales OSSD de la cortina
- Para 1 zona: PNOZ XV2
- Para múltiples zonas con muting: PNOZmulti 2

**Tapetes de seguridad**
- PNOZ XV4 (diseñado específicamente para tapetes y bordes sensibles)

**Monitoreo de velocidad**
- PMCprotego DS (con encoder) o PMCprotego D (sin encoder, por frecuencia)

---

## Reglas de arquitectura ISO 13849-1

| PL requerido | Arquitectura mínima | Relé típico |
|-------------|--------------------|-|
| PL c | Cat 2 (1 canal + test) | PNOZ XV1 |
| PL d | Cat 3 (2 canales, sin detección de falla común) | PNOZ XV2 |
| PL e | Cat 4 (2 canales + diagnóstico de falla) | PNOZ s4/s5/s6, PNOZ XV2, PNOZmulti 2 |

Nota: Cat 4 / PL e requiere siempre dos canales de entrada independientes y monitoreo de fallas de causa común. Todos los PNOZ s y PNOZ XV2 cumplen esto de fábrica.

---

## Términos de búsqueda en el catálogo para PILZ
- Relés de seguridad: "relé seguridad", "PNOZ", "safety relay"
- Control dos manos: "control dos manos", "two hand", "PNOZ s9"
- Parada emergencia: "parada emergencia", "emergency stop", "PNOZ s4", "PNOZ s5"
- Sistemas configurables: "configurable", "PNOZmulti", "PNOZ-M"
- Velocidad: "velocidad", "PMCprotego", "speed monitor"
