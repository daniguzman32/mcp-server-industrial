# Guía de Selección PILZ — Criterios para el cotizador

PILZ cubre dos grandes categorías: **lógica de seguridad** (relés y controladores) y **sensórica de seguridad** (PSEN — detectores de posición y presencia). Ambas categorías son propias de PILZ.

---

## Lógica de seguridad — Relés y controladores

### PNOZ s — Relés de función fija
**Cuándo:** una sola función de seguridad, presupuesto ajustado, sin comunicación con PLC.
**Parámetro clave:** número de circuitos de habilitación y si necesita temporización o función especial.
- 1–2 circuitos, sin temporización → PNOZ s4 o s5
- 1–2 circuitos + temporización de arranque → PNOZ s6
- Control de dos manos (tipo IIIC) → PNOZ s9
- Puerta con bloqueo de seguridad → PNOZ s10
- Monitoreo de velocidad / paro / dirección → PNOZ s30 (encoder HTL/TTL, SLS/SOS/SDI, PL d)
- Control y monitoreo de freno → PNOZ s50

Todos PL e / Cat 4 salvo s30 (PL d). Tensiones: 24 VDC (más común), 110 VAC, 230 VAC.
**Combinaciones:** recibe contactos NC de E-stop, puerta, o señales OSSD de cortinas PSENopt.

### PNOZ XV — Relés universales
**Cuándo:** cliente ya tiene XV instalados, o necesita selección de modo por DIP switch en campo.
**Parámetro clave:** categoría de seguridad.
- PL c / Cat 2 → PNOZ XV1 (1 canal)
- PL e / Cat 4 → PNOZ XV2 (2 canales, opción estándar más versátil)
- Control de dos manos → PNOZ XV3
- Tapetes de seguridad / bordes sensibles → PNOZ XV4 (único PILZ para esas entradas)

**Combinaciones:** PNOZ XV4 es el relé obligatorio para tapetes y bordes IDEM Safety.

### PNOZmulti Mini — Controlador compacto configurable
**Cuándo:** 2–4 funciones de seguridad, se necesita lógica configurable pero la aplicación no justifica el PNOZmulti 2 completo. Escalón intermedio entre PNOZ s y PNOZmulti 2.
**Parámetro clave:** número de entradas de seguridad requeridas (4 bases disponibles: B0, B1, B2, B3).
- Sin expansión de I/O ni comunicación de bus de campo — si se necesita eso, usar PNOZmulti 2.
PL e / Cat 4. Programado con PNOZmulti Configurator.

### PNOZmulti 2 — Controlador configurable
**Cuándo:** 3 o más funciones de seguridad, diagnóstico por canal en HMI/SCADA, bus de campo (Profibus, Profinet, EtherNet/IP), o función de muting.
**Parámetro clave:** número de funciones + comunicación industrial.
- Módulo base PNOZ-M-B0: 4 entradas, 2 salidas OSSD
- Expansiones de I/O y comunicación disponibles

PL e / Cat 4. PNOZmulti Configurator (software gratuito).
**Combinaciones:** obligatorio con muting (cortinas de luz con paso de producto), o cuando se combinan E-stop + cortinas + puerta con bloqueo + rearme múltiple.

### PMCprotego — Monitor de velocidad y posición seguro (hardware dedicado)
**Cuándo:** la velocidad / posición / dirección es parámetro de seguridad Y se necesita diagnóstico avanzado o SIL 2 en aplicaciones de servo. Diferencia con PNOZ s30: PMCprotego soporta SinCos encoder y mayor densidad de funciones.
**Parámetro clave:** tipo de encoder (SinCos / HTL / TTL) y funciones (SLS, SMS, SDI, SOS, SLP).
**Combinaciones:** siempre con PNOZ s o PNOZmulti 2 para las salidas de habilitación. PMCprotego solo monitorea.

### PITgatebox — Terminal portátil de operador (enabling device)
**Cuándo:** el operador necesita ingresar a la zona de peligro para ajuste, setup o mantenimiento con movimiento habilitado. PITgatebox es la caja de mano que habilita el movimiento solo mientras el operador la sostiene conscientemente.
**Parámetro clave:** funciones requeridas en la caja y tipo de conexión.
- Incluye interruptor de habilitación de 3 posiciones (enabling switch) — posición intermedia = habilita; soltar o apretar fuerte = para
- Variantes: con E-stop integrado, con selector de modo, con display, inalámbrico
- Conexión: cable (variante estándar) o radio (PITgatebox wireless)
**Combinaciones:** la señal de enabling switch conecta al PNOZ s o PNOZmulti 2. En modo "ajuste" el sistema reduce velocidad (SLS vía PMCprotego o s30) y habilita solo con enabling activo.
> Regla de seguridad: el enabling switch nunca reemplaza al E-stop — siempre incluir ambos en la PITgatebox.

### PSS 4000 — PLC de seguridad
**Cuándo:** automatización segura a escala de línea o planta, seguridad + control estándar integrados, red SafetyNET p, > 10 funciones de seguridad, I/O distribuidos.
No cotizar para máquina individual — PNOZmulti 2 es suficiente y más económico.

---

## Sensórica de seguridad — Familia PSEN

### PSENmag — Switches magnéticos de puerta
**Cuándo:** detección de posición de resguardo móvil, aplicación estándar sin riesgo alto de manipulación.
**Parámetro clave:** nivel de codificación.
- Sin codificación (low coding): bajo riesgo de bypass
- Codificado (high coding): cuando hay riesgo de manipulación con imán externo

PL e / Cat 4 con 2 sensores en serie. Conectar OSSD o contactos NC al PNOZ s5 / XV2.
> Nota comercial: si el cliente pide IDEM para esta función, verificar PSENmag primero — es la oferta principal.

### PSENcode — Switches magnéticos codificados
**Cuándo:** resguardos donde se requiere alta resistencia a manipulación mediante imanes. Alternativa a IDEM serie C cuando se prefiere PILZ completo.
**Parámetro clave:** nivel de codificación (único o múltiple código). Tecnología magnética codificada — no confundir con PSENcode RFID (ver sección siguiente).
PL e / Cat 4.

### PSENcode RFID — Switches codificados por transponder RFID
**Cuándo:** máxima seguridad anti-tamper. El sensor lee un código único grabado en el transponder (tag RFID) — no puede ser bypasseado con imán ni con otro sensor del mismo tipo. Equivalente PILZ a IDEM serie F.
**Parámetro clave:** si el código es estándar (mismo código en todos los actuadores del lote) o único (cada actuador tiene código individual). Para alta seguridad siempre elegir código único.
PL e / Cat 4. Salidas OSSD al PNOZ XV2 o PNOZmulti 2.

### PSENmech — Switches mecánicos de seguridad
**Cuándo:** enclavamiento mecánico de resguardo con llave o lengüeta. Aplicaciones donde el cliente especifica contacto físico.
**Parámetro clave:** tipo de actuador (llave / lengüeta / rodillo) y número de contactos NC.
PL e / Cat 4 con 2 canales.
> Alternativa IDEM: KP / KM si el cliente pide formato específico no disponible en PSENmech.

### PSENbolt — Switch combinado (enclavamiento + cerrojo manual)
**Cuándo:** resguardo que necesita enclavamiento mecánico con manija integrada y bloqueo por cerrojo accionado manualmente. Combina detección + mantenimiento en un solo dispositivo.
PL e / Cat 4.

### PSENsgate — Switch de seguridad con bloqueo por solenoide (interruptor con bloqueo)
**Cuándo:** resguardo que debe permanecer bloqueado hasta que la máquina llegue a estado seguro (inercia rotativa, tiempo de paro definido). PILZ PSENsgate es la alternativa directa a IDEM KL para fuerzas de retención estándar.
**Parámetro clave:** fuerza de retención y tensión de desbloqueado.
- Bloqueo por resorte (fail-safe): resguardo queda bloqueado sin tensión — estándar recomendado
- Bloqueo por energización: resguardo bloqueado solo con tensión aplicada
**Combinaciones:** requiere relé con función de monitoreo de cerrojo. PNOZ s10 para casos simples; PNOZmulti 2 cuando se necesita diagnóstico de estado del cerrojo en HMI.
> Nota: para fuerzas de retención muy altas (> 2000 N, maquinaria pesada) usar IDEM KL serie metal (KLM/KLTM/KL3-SS).

### PSENopt — Cortinas de luz (ESPE)
**Cuándo:** protección de zona de acceso donde no se puede instalar resguardo físico, o donde se requiere acceso frecuente sin abrir puertas.
**Parámetro clave:** resolución (tamaño mínimo de objeto a detectar) → define qué parte del cuerpo se protege.
- 14 mm: protección de dedos (finger protection)
- 20–25 mm: protección de mano
- 30–40 mm: protección de brazo
- ≥ 90 mm: protección de cuerpo / acceso de persona

Salidas OSSD (2 canales). Conectar al PNOZ XV2 o PNOZmulti 2.
**Combinaciones:** si se necesita muting (paso de pallets / productos), obligatorio PNOZmulti 2 (no es posible con PNOZ s o XV).
**Parámetro adicional:** alcance (distancia entre emisor y receptor, típico 0.2–6 m o 0.3–20 m según serie).

### PSENscan — Escáner láser de seguridad
**Cuándo:** monitoreo de área 2D en planta, protección perimetral de celdas robotizadas, AGVs, o zonas donde la cortina no es práctica (ángulo de 270°).
**Parámetro clave:** distancia de detección requerida y número de zonas configurables.
- Zonas de protección y advertencia configurables por software
- PL d / SIL 2

**Combinaciones:** conexión OSSD al PNOZmulti 2 para manejo de múltiples zonas y muting.

### PSENradar — Sensor de radar de seguridad
**Cuándo:** detección de presencia de personas en zonas donde la óptica falla — ambientes con polvo, humo, vapor, niebla, o iluminación variable. Alternativa al PSENscan cuando las condiciones ambientales impiden el uso del láser.
**Parámetro clave:** distancia de detección y ángulo de cobertura.
- No afectado por partículas en el aire ni cambios de luz
- Configurable en zonas de protección y advertencia
- PL d / SIL 2

**Combinaciones:** salidas OSSD al PNOZmulti 2. Para aplicaciones móviles (AGV en ambiente con polvo) es preferible a PSENscan.

### SafetyEYE / PSENvip — Sistema de cámara segura (3D)
**Cuándo:** monitoreo volumétrico 3D, espacios complejos donde escáner 2D no alcanza, zonas de colaboración humano-robot (detección de presencia + velocidad).
**Parámetro clave:** volumen de la zona de protección a cubrir.
PL d / SIL 2. Integra directamente con PNOZmulti 2 o PSS 4000.
No cotizar para aplicaciones simples de puerta — en ese caso PSENmag o PSENopt son más económicos y suficientes.

---

## Árbol de selección rápida

```
¿Qué necesita?
├── Lógica de seguridad (relé / controlador)
│   ├── 1–2 funciones, sin bus de campo
│   │   ├── Velocidad / freno → PNOZ s30 / s50
│   │   └── E-stop / puerta / dos manos → PNOZ s (más económico) o XV2
│   ├── 2–4 funciones, lógica configurable simple → PNOZmulti Mini
│   ├── 3+ funciones o muting o bus de campo → PNOZmulti 2
│   ├── Velocidad avanzada + SIL 2 (SinCos) → PMCprotego
│   └── Línea completa / planta → PSS 4000
│
├── Dispositivo de habilitación portátil (operador en zona peligro) → PITgatebox
│   └── Siempre combinar con PNOZ s o PNOZmulti 2 + PMCprotego/s30 para SLS
│
└── Sensórica de seguridad (detector)
    ├── Detección de puerta / resguardo (sin bloqueo)
    │   ├── Sin contacto, estándar → PSENmag
    │   ├── Sin contacto, anti-tamper (magnético codificado) → PSENcode
    │   ├── Sin contacto, anti-tamper máximo (RFID transponder) → PSENcode RFID
    │   ├── Mecánico (lengüeta / llave) → PSENmech
    │   └── Mecánico + cerrojo manual integrado → PSENbolt
    ├── Detección de puerta / resguardo (con bloqueo por solenoide)
    │   ├── Fuerza estándar (< 2000 N) → PSENsgate + PNOZ s10 o PNOZmulti 2
    │   └── Alta fuerza (≥ 2000 N) / industria alimentaria → IDEM KL serie metal
    ├── Detección de presencia / zona
    │   ├── Acceso puntual (dedos / manos / cuerpo) → PSENopt (cortina)
    │   │   └── Con muting → obligatorio PNOZmulti 2
    │   ├── Área 2D, ambiente limpio → PSENscan (escáner láser)
    │   ├── Área 2D, ambiente con polvo/humo/vapor → PSENradar
    │   └── Volumen 3D (colaboración robot-humano) → SafetyEYE / PSENvip
    ├── Tapete / borde sensible → PNOZ XV4 (relé obligatorio) + sensor IDEM
    └── E-stop → cualquier PNOZ s/XV
```

---

## Qué NO cubre PILZ (usar IDEM Safety en estos casos)
- Bloqueo por solenoide de alta fuerza (≥ 2000 N, maquinaria pesada) → IDEM KLM / KLTM / KL3-SS
- Switches de bisagra integrados en el eje de la puerta → IDEM HingeCam / HSM
- Tiradores de cable (pull-cord) para transportadores → IDEM GuardianLine
- Switches de desvío de banda (belt alignment) → IDEM
- Enclavamientos de lengüeta en formato no disponible en PSENmech → IDEM KP/KM
