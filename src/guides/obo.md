# Guía de Selección OBO Bettermann — Criterios para el cotizador

OBO tiene 5 líneas de catálogo. Para automatización industrial, las relevantes son KTS (bandejas) y TBS (protección contra sobretensiones). VBS cubre cajas de paso.

---

## Bandejas y soportes de cable (Catálogo KTS)

### Bandejas portacables perforadas (Cable Tray)
**Cuándo:** conducción de cables de potencia y control en tableros, celdas y planta.
**Parámetro clave:** ancho requerido (mm) y carga (kg/m).
- Ancho estándar disponible: 60 / 100 / 150 / 200 / 300 / 400 / 500 / 600 mm
- Altura: 35 / 60 / 85 / 110 mm según carga
- Material: acero galvanizado en caliente (estándar industrial) o acero inoxidable (alimentario/exterior)
**Combinaciones obligatorias:** siempre cotizar accesorios: curvas, T, crucetas, reducciones y tapa si el recorrido lo requiere. Un recorrido completo sin accesorios no cierra la oferta.

### Bandejas de malla (Mesh Cable Tray)
**Cuándo:** instalaciones donde se necesita flexibilidad de corte en obra, ventilación máxima o estética (data centers, salas técnicas).
**Parámetro clave:** ancho y material. No tienen tapa (es su característica).

### Escaleras portacables (Cable Ladder)
**Cuándo:** cargas pesadas, cables de gran sección, recorridos largos entre soportes.
**Parámetro clave:** ancho y separación entre peldaños (100 / 150 mm). Permiten mayor separación entre soportes que la bandeja perforada.

### Canaletas (Cable Duct / Trunking)
**Cuándo:** conducción de cables en tableros eléctricos internos y canalizados.
**Parámetro clave:** sección (ancho × alto mm). Con tapa articulada para acceso frecuente.
- Uso típico: dentro del tablero, entre aparatos y borneras.

---

## Protección contra sobretensiones (Catálogo TBS)

### Protectores de sobretensión Tipo 1+2
**Cuándo:** instalación en el punto de entrada de la red (tablero general), cuando hay riesgo de rayo directo. Requerido por norma si el edificio tiene pararrayos.
**Parámetro clave:** corriente de impulso (Iimp) y tensión de protección (Up).

### Protectores Tipo 2
**Cuándo:** tableros de distribución secundarios, protección de equipos sensibles (PLC, drives, HMI). Es la protección más frecuente en proyectos industriales.
**Parámetro clave:** corriente de descarga (In), tensión de protección Up y tensión de operación (230 V AC monofásico / 400 V trifásico / 24 VDC para señales de control).

### Protectores Tipo 3 / señales y datos
**Cuándo:** protección de equipos de instrumentación, señales analógicas, comunicaciones (RS485, Ethernet, PROFIBUS).

---

## Cajas de paso y distribución (Catálogo VBS)

### Cajas de paso IP65 (Junction Boxes)
**Cuándo:** derivaciones y empalmes en campo, exterior o ambientes húmedos.
**Parámetro clave:** dimensiones (mm) y material (poliestireno estándar / poliamida reforzada / inoxidable).
- IP65: estándar para interior con salpicaduras
- IP67: inmersión temporal
- IP69K: lavado a presión (industria alimentaria)
**Combinaciones:** siempre cotizar prensaestopas (cantidad y diámetro de cables) si no están incluidos en el modelo base.

---

## Lógica de selección rápida

```
¿Qué necesita?
├── Conducción de cables en planta/tablero
│   ├── Dentro del tablero → Canaleta
│   ├── En planta, cargas medias → Bandeja perforada KTS
│   └── Cargas pesadas / tramos largos → Escalera portacables
├── Protección contra sobretensiones
│   ├── Entrada principal / riesgo de rayo → Tipo 1+2
│   ├── Tablero secundario / equipos → Tipo 2
│   └── Instrumentación / señales → Tipo 3
└── Derivación en campo → Caja de paso VBS (IP según ambiente)
```
