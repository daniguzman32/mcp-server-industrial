# Guía de Selección IDEM Safety — Criterios para el cotizador

> **Regla comercial:** IDEM complementa a PILZ. Siempre verificar si PILZ tiene el equivalente (PSENmag, PSENcode, PSENmech) antes de cotizar IDEM. Usar IDEM solo cuando PILZ no cubre la función.

---

## Switches sin contacto (Non-Contact Safety Switches)
**Cuándo:** detección de posición de resguardo móvil sin contacto físico. Alternativa a PSEN de PILZ cuando el cliente pide IDEM específicamente o PILZ no tiene el formato requerido.
**Parámetro clave:** nivel de anti-manipulación requerido.
- Estándar (magnético Reed, serie R): bajo riesgo de manipulación intencional
- Medio (magnético codificado, serie C): cuando hay riesgo de bypass con imán simple
- Alto (RFID codificado, serie F): máxima seguridad anti-tamper, entornos con alta intención de evasión
**Combinaciones:** conectar los contactos NC directamente al relé PILZ (PNOZ s5, PNOZ XV2). Si se usan en serie, verificar que el relé soporte conexión en cascada.

## Enclavamientos con bloqueo por solenoide (Solenoid Interlocks — Serie KL)
**Cuándo:** la máquina tiene tiempo de paro largo (inercia rotativa, enfriamiento) y el operador no puede acceder hasta que sea seguro. PILZ no tiene equivalente directo en esta categoría.
**Parámetro clave:** fuerza de retención requerida.
- 1400 N → KLP / KL1-P (plástico, IP67)
- 2000 N → KLM / KLTM (fundición, IP67/IP69K)
- 3000 N → KL3-SS / KLT-SS (acero inoxidable, IP69K — alimentaria)
**Combinaciones obligatorias:** requieren relé de seguridad PILZ con función de monitoreo de bloqueo. PNOZmulti 2 cuando se necesita diagnóstico del estado del cerrojo (señal de lock status separada). PNOZ s10 para casos simples.
**Nota:** elegir power-to-release (energizar para desbloquear) como estándar — el resguardo queda bloqueado sin tensión, lo que es fail-safe.

## Switches de bisagra (Hinge Safety Switches — Serie HingeCam / HSM)
**Cuándo:** puertas batientes donde el interruptor debe integrarse en el eje de la bisagra. PILZ no tiene este formato.
**Parámetro clave:** ángulo de activación y si el switch reemplaza la bisagra física.
- HingeCam: solo detección, montado externo a la bisagra
- HSM / HS-SS: reemplaza la bisagra, 800 N de fuerza axial, activa a 10° de apertura
**Combinaciones:** contactos NC al PNOZ s5 o PNOZ XV2.

## Interruptores de lengüeta (Safety Tongue Interlocks — Serie KP / KM)
**Cuándo:** resguardo corredizo o basculante que necesita enclavamiento mecánico sin bloqueo (el operador puede abrir libremente). PILZ tiene PSENmech como alternativa directa — verificar primero.
**Parámetro clave:** tamaño de carcasa (miniatura, estándar, kobra) y material (plástico / metal / inoxidable).
**Combinaciones:** NC al PNOZ s5 o PNOZ XV2.

## Interruptores de cuerda (Rope Pull / Pull-Cord — GuardianLine)
**Cuándo:** parada de emergencia a lo largo de transportadores o líneas largas donde no se pueden instalar resguardos. PILZ no tiene este producto.
**Parámetro clave:** longitud de cuerda a cubrir.
- Hasta 60 m: GLM (plástico IP67) / GLM-SS (inoxidable IP69K)
- Hasta 80 m: GLS / GLS-SS
- Hasta 250 m (doble cabezal): GLHD / GLHD-SS
**Combinaciones:** contactos NC al PNOZ s o cualquier relé de seguridad con entrada E-stop de 2 canales. Un interruptor GLHD puede cubrir hasta 125 m de cada lado.

## Interruptores de desvío de banda (Belt Alignment Switches)
**Cuándo:** protección de transportadores de cinta contra desalineación. PILZ no tiene este producto.
**Parámetro clave:** carga de la cinta (rodillo liviano / mediano / pesado) y material (pintado IP67 / inoxidable IP69K).
**Combinaciones:** 2 contactos independientes: uno para alarma (advertencia), otro para parada. Conectar el de parada al sistema de control o relé de seguridad.

---

## Qué NO cubrir con IDEM (PILZ tiene el equivalente)
- Switches magnéticos de puerta estándar → usar PILZ PSENmag
- Switches codificados de puerta → usar PILZ PSENcode
- Switches mecánicos de puerta → usar PILZ PSENmech
- Control de dos manos → usar PILZ PNOZ s9 / XV3
