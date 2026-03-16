# Guía de Selección CABUR — Criterios para el cotizador

CABUR tiene tres catálogos: **Conectividad Industrial** (borneras — familia principal), **Automatización** (fuentes, relés, convertidores) y **Marcaciones**. Para cotización técnica se usan las dos primeras.

---

## Borneras — Catálogo Conectividad Industrial

### CBC — Familia principal (Spring Clamp)
**Cuándo:** conexión estándar en tableros industriales. CBC es la línea principal de CABUR — siempre ofrecer CBC salvo que el cliente pida screw clamp explícitamente.
**Parámetro clave:** sección del cable (mm²).
- CBC.2: hasta 4 mm² — señal y control (la más frecuente)
- CBC con variantes de 2 niveles (EFD): ahorro de espacio en riel DIN
**Combinaciones:** agregar borneras de tierra y finales de riel en toda propuesta de borneras.

### HMM — Screw Clamp (alternativa)
**Cuándo:** el cliente especifica tornillo, o aplicaciones con vibración severa donde spring clamp no es recomendada.
- HMM.1: paso a paso estándar, ≤ 4 mm²
- HMM.4: versión compacta

### Borneras de alta corriente (GPA / GPM / ACB)
**Cuándo:** cables de potencia > 4 mm².
- GPA.70: 4–70 mm² (tornillo, conexión frontal)
- GPM.95 / GPM.150 / GPM.240: 35–240 mm² (alta sección, tableros de potencia)
- ACB.70: alternativa con apriete por hexagonal

### Borneras fusibles (FVS / SFR / FPC)
**Cuándo:** protección de circuitos de señal o actuadores sin disyuntor separado.
**Parámetro clave:** corriente del fusible (0.5 A → 10 A) y tipo de fusible (5×20 mm / 5×25 mm).
- FVS.4 / SFR.4: las más usadas, fusible cilíndrico 5×20 mm

### Borneras de desconexión (DBC / TE.x/D)
**Cuándo:** circuitos con mantenimiento frecuente que requieren seccionamiento rápido (sensores, lazos 4-20 mA).
- DBC.2: palanca de desconexión, ≤ 4 mm², serie spring clamp

### Borneras de tierra (HTE / HCD)
**Cuándo:** siempre — incluir en toda propuesta de tablero. Tierra de señal y tierra de protección son distintas.

---

## Fuentes de alimentación — Catálogo Automatización

### CSE — Serie nueva principal (24 VDC DIN rail)
**Cuándo:** alimentación estándar de PLC, relés, sensores en tablero industrial. Es la serie de referencia actual.
**Parámetro clave:** corriente de salida. Regla: calcular carga total × 1.25 ≥ corriente nominal.
- Modelos disponibles: 5 A / 10 A / 20 A / 40 A (24 VDC)
**Combinaciones:** para redundancia, conectar dos fuentes en paralelo con diodo ORing (elegir modelos con diodo integrado). Ajustar tensión de ambas antes de conectar.

### CSF — Serie con contacto de alarma
**Cuándo:** aplicaciones donde el PLC debe conocer el estado de la fuente (fault monitoring).
- Incluye contacto de señalización Power Signal OK (1A/30Vdc)

### CSW / CSL3 — Entrada trifásica
**Cuándo:** tableros con alimentación trifásica disponible; reducen corriente de entrada y mejoran eficiencia.

### UPS — Alimentación ininterrumpida en riel DIN
**Cuándo:** PLC, HMI o drives donde el corte de tensión puede causar pérdida de posición, datos o proceso.
**Parámetro clave:** tiempo de autonomía requerido y corriente de carga. La UPS se conecta en cascada a la fuente CABUR.

---

## Relés de interfaz

### Relés electromecánicos (Serie CM / RE)
**Cuándo:** interfaz entre PLC (salida 24 VDC) y actuadores de 110/230 VAC, o cuando se necesita aislamiento galvánico entre circuitos.
**Parámetro clave:** tipo de contacto (SPDT / DPDT) y corriente del actuador.
- CM1C024: 24 VDC, SPDT, 12 A — el más frecuente, enchufable en base
- RE1824D / RE1024D: 24 VDC, SPDT, 16 A — para cargas mayores
- CM2C024: 24 VDC, DPDT, 8 A — cuando se necesitan 2 circuitos conmutados
**Combinaciones:** siempre cotizar base de riel DIN + LED indicador de estado.

### Relés de estado sólido SSR (Serie CM1S / CM1T / O3)
**Cuándo:** alta frecuencia de conmutación, sin desgaste mecánico, o cuando los relés electromecánicos generan interferencia.
- CM1S024 / CM1S024E: salida transistor DC (PNP), 2-5 A
- CM1T024 / CM1T024E: salida triac AC, zero crossing, 3 A
- O332060 (3 A DC) / O332240 (4 A AC): versión no enchufable, compacta

---

## Convertidores y aisladores galvánicos (Serie CON-AA / CAPIPO / LCON_TA)
**Cuándo:** convertir o aislar señales analógicas entre sensores y PLC. Problema típico: lazo de corriente 4-20 mA compartido entre equipos de distintos fabricantes genera tierra común y ruido. La solución es un aislador galvánico de 3 vías (entrada / salida / alimentación independientes).
**Parámetro clave:** tipo de señal de entrada y salida.
- 4-20 mA → 4-20 mA: CON-AA-516P (con DIP switch, el más versátil)
- 0-10 V → 4-20 mA o viceversa: CON-AA-516P / CON-AA-539P
- Termopar → 4-20 mA / 0-10 V: LCON_TA_DFDT (programable por software)
- PT100 → 4-20 mA / 0-10 V: CON-TA-809P

---

## Switches de alimentación (CSBD)
**Cuándo:** distribuir y proteger ramas independientes desde una fuente central 24 VDC, con seccionamiento por canal.
**Parámetro clave:** número de canales y corriente por rama (máx. 15 A por salida).

---

## Lógica de selección rápida

```
¿Qué necesita?
├── Borneras → CBC (spring, principal) / HMM (screw si lo pide)
│   ├── > 4 mm² → GPA / GPM según sección
│   ├── Con fusible → FVS / SFR según corriente
│   └── Con desconexión → DBC.2
├── Fuente 24 VDC → CSE (nueva principal), calcular carga × 1.25
│   ├── Con alarma de falla → CSF
│   ├── Entrada trifásica → CSW / CSL3
│   └── Backup ante corte → UPS en cascada
├── Interfaz PLC → actuador
│   ├── AC o alta corriente → CM1C024 (electromecánico)
│   └── Alta frecuencia / sin ruido → CM1S / CM1T (SSR)
└── Señal analógica con ruido / tierra común → CON-AA / LCON_TA (aislador 3 vías)
```
