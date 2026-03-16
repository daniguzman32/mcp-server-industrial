# Guía de Selección PILZ — Criterios para el cotizador

## PNOZ s — Relés de función fija
**Cuándo:** una sola función de seguridad, presupuesto ajustado, no se requiere comunicación con PLC.
**Parámetro clave:** número de circuitos de habilitación requeridos y si necesita temporización de rearme.
- 1–2 circuitos, sin temporización → PNOZ s4 o s5
- 1–2 circuitos + temporización de arranque → PNOZ s6
- Control de dos manos (tipo IIIC) → PNOZ s9
- Puerta con bloqueo de seguridad → PNOZ s10
Todos alcanzan PL e / Cat 4. Tensiones: 24 VDC (más común), 110 VAC, 230 VAC.
**Combinaciones:** recibe directamente contactos de E-stop, final de carrera, o señales OSSD de cortinas de luz IDEM.

## PNOZ XV — Relés universales
**Cuándo:** misma función que PNOZ s pero cuando el cliente ya tiene XV instalados, o cuando se necesita seleccionar modo por DIP switch en campo.
**Parámetro clave:** categoría de seguridad requerida.
- PL c / Cat 2 → PNOZ XV1 (1 canal)
- PL e / Cat 4 → PNOZ XV2 (2 canales, la opción estándar más versátil)
- Control de dos manos → PNOZ XV3
- Tapetes de seguridad / bordes sensibles → PNOZ XV4 (único PILZ para esas entradas)
**Combinaciones:** PNOZ XV4 es el relé obligatorio para tapetes y bordes IDEM Safety.

## PNOZmulti 2 — Controlador configurable
**Cuándo:** 3 o más funciones de seguridad simultáneas, o cuando se requiere diagnóstico por canal en HMI/SCADA, o integración con bus de campo (Profibus, Profinet, EtherNet/IP).
**Parámetro clave:** número de funciones de seguridad + necesidad de comunicación industrial.
- Módulo base PNOZ-M-B0: 4 entradas de seguridad, 2 salidas OSSD
- Expansiones disponibles para I/O adicionales y comunicación
PL e / Cat 4. Se programa con PNOZmulti Configurator (software gratuito de PILZ).
**Combinaciones:** obligatorio cuando se usa muting (paso de producto en cortinas de luz), o cuando se combinan en una misma celda: E-stop + cortinas + puerta con bloqueo + rearme desde múltiples puntos.

## PMCprotego — Monitor de velocidad y posición seguro
**Cuándo:** la velocidad, posición o dirección del eje son parámetros de seguridad (modo ajuste, acceso con movimiento reducido).
**Parámetro clave:** tipo de encoder (SinCos / HTL / TTL) y funciones requeridas.
- SLS (límite de velocidad segura), SMS, SDI, SOS, SLP disponibles
- SIL 2 / PL d–e
**Combinaciones:** siempre se usa junto con un PNOZ s o PNOZmulti 2 que gestiona las salidas de habilitación. PMCprotego solo monitorea; el corte de potencia lo hace el relé aguas arriba.

## PSS 4000 — PLC de seguridad
**Cuándo:** automatización segura a escala de línea o planta, cuando seguridad y control estándar deben integrarse en un único sistema con red SafetyNET p.
**Parámetro clave:** complejidad del sistema (> 10 funciones de seguridad, I/O distribuidos, múltiples CPUs).
No cotizar para aplicaciones de máquina individual — en ese caso PNOZmulti 2 es suficiente y más económico.

---

## Árbol de selección rápida

```
¿Cuántas funciones de seguridad?
├── 1–2 funciones
│   ├── ¿Necesita comunicación industrial? → No → PNOZ s (más económico)
│   └── ¿Prefiere universal/configurable?  → Sí → PNOZ XV2
├── 3+ funciones o muting o bus de campo → PNOZmulti 2
├── Monitoreo de velocidad de eje → PMCprotego (+ PNOZ s o PNOZmulti)
└── Línea completa / planta → PSS 4000

¿Tipo de entrada del sensor?
├── E-stop (contacto NC) → cualquier PNOZ s/XV
├── Puerta (2 contactos NC) → PNOZ s5, s6, XV2
├── Control dos manos → PNOZ s9, XV3
├── Cortina de luz OSSD → PNOZ XV2 o PNOZmulti 2
├── Tapete / borde sensible → PNOZ XV4 (obligatorio)
└── Encoder de velocidad → PMCprotego
```

---

## Qué no cubre PILZ (usar IDEM Safety en estos casos)
- Interruptores de puerta / compuertas (enclavamientos mecánicos y sin contacto)
- Cortinas de luz / barreras ópticas (ESPE)
- Bordes sensibles y tapetes de seguridad ← el relé sigue siendo PILZ XV4
- Tiradores de cable (pull-cord) para transportadores
- Dispositivos para zonas ATEX
