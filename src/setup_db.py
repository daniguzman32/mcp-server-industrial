#!/usr/bin/env python3
"""
Inicializa la base de datos PostgreSQL de Fachmann con el schema y datos de ejemplo.
Idempotente: CREATE TABLE IF NOT EXISTS + INSERT ON CONFLICT DO NOTHING.
"""

import os
import sys

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

# Railway provee postgres://, psycopg2 requiere postgresql://
DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)

DDL = [
    """CREATE TABLE IF NOT EXISTS productos_catalogo (
        id                   SERIAL PRIMARY KEY,
        sku                  TEXT    UNIQUE NOT NULL,
        marca                TEXT    NOT NULL CHECK(marca IN ('PILZ', 'OBO', 'CABUR', 'IDEM SAFETY')),
        categoria            TEXT    NOT NULL,
        descripcion          TEXT    NOT NULL,
        precio_usd           REAL,
        especificaciones     TEXT,
        stock                INTEGER DEFAULT 0,
        tiempo_entrega_dias  INTEGER DEFAULT 30,
        activo               INTEGER DEFAULT 1,
        created_at           TEXT    DEFAULT NOW()::TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS clientes_prospectos (
        id                SERIAL PRIMARY KEY,
        razon_social      TEXT NOT NULL,
        contacto_nombre   TEXT,
        contacto_cargo    TEXT,
        contacto_email    TEXT,
        contacto_telefono TEXT,
        industria         TEXT,
        estado_lead       TEXT DEFAULT 'nuevo_cliente'
                          CHECK(estado_lead IN ('nuevo_cliente','calificado','oferta','ganado','cancelado','perdido')),
        linkedin_url      TEXT,
        notas             TEXT,
        created_at        TEXT DEFAULT NOW()::TEXT,
        updated_at        TEXT DEFAULT NOW()::TEXT
    )""",
    # Migraciones idempotentes para DBs existentes
    "ALTER TABLE clientes_prospectos ADD COLUMN IF NOT EXISTS contacto_cargo TEXT",
    # Normalizar valores viejos de estado_lead antes de aplicar el nuevo constraint
    "UPDATE clientes_prospectos SET estado_lead = 'ganado'        WHERE estado_lead = 'cliente_activo'",
    "UPDATE clientes_prospectos SET estado_lead = 'oferta'        WHERE estado_lead = 'en_negociacion'",
    "UPDATE clientes_prospectos SET estado_lead = 'calificado'    WHERE estado_lead = 'contactado'",
    "UPDATE clientes_prospectos SET estado_lead = 'nuevo_cliente' WHERE estado_lead = 'prospecto'",
    "UPDATE clientes_prospectos SET estado_lead = 'nuevo_cliente' WHERE estado_lead NOT IN ('nuevo_cliente','calificado','oferta','ganado','cancelado','perdido')",
    # Actualizar constraint de estado_lead con los nuevos valores
    "ALTER TABLE clientes_prospectos DROP CONSTRAINT IF EXISTS clientes_prospectos_estado_lead_check",
    """ALTER TABLE clientes_prospectos ADD CONSTRAINT clientes_prospectos_estado_lead_check
       CHECK(estado_lead IN ('nuevo_cliente','calificado','oferta','ganado','cancelado','perdido'))""",
    """CREATE TABLE IF NOT EXISTS oportunidades_ventas (
        id                    SERIAL PRIMARY KEY,
        cliente_id            INTEGER NOT NULL REFERENCES clientes_prospectos(id),
        descripcion           TEXT    NOT NULL,
        monto_usd             REAL,
        probabilidad_cierre   INTEGER DEFAULT 50,
        etapa                 TEXT    DEFAULT 'prospecting'
                              CHECK(etapa IN ('prospecting','qualification','proposal','negotiation','closed_won','closed_lost')),
        notas_tecnicas        TEXT,
        fecha_creacion        TEXT DEFAULT NOW()::TEXT,
        fecha_cierre_estimada TEXT,
        updated_at            TEXT DEFAULT NOW()::TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS interacciones (
        id         SERIAL PRIMARY KEY,
        cliente_id INTEGER NOT NULL REFERENCES clientes_prospectos(id),
        tipo       TEXT DEFAULT 'nota'
                   CHECK(tipo IN ('reunion','email','llamada','whatsapp','nota')),
        notas      TEXT NOT NULL,
        fecha      TEXT DEFAULT NOW()::TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS reglas_descuento (
        id              SERIAL PRIMARY KEY,
        tarifa_nombre   TEXT    NOT NULL,
        marca           TEXT    NOT NULL CHECK(marca IN ('PILZ', 'OBO', 'CABUR')),
        desc_1          REAL    NOT NULL DEFAULT 0.0,
        desc_2          REAL    NOT NULL DEFAULT 0.0,
        desc_3          REAL    NOT NULL DEFAULT 0.0,
        UNIQUE(tarifa_nombre, marca)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_productos_marca     ON productos_catalogo(marca)",
    "CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos_catalogo(categoria)",
    "CREATE INDEX IF NOT EXISTS idx_clientes_nombre     ON clientes_prospectos(razon_social)",
    "CREATE INDEX IF NOT EXISTS idx_interacciones_cli   ON interacciones(cliente_id)",
    "CREATE INDEX IF NOT EXISTS idx_oportunidades_cli   ON oportunidades_ventas(cliente_id)",
    "CREATE INDEX IF NOT EXISTS idx_reglas_tarifa       ON reglas_descuento(tarifa_nombre)",
]


def create_tables(conn) -> None:
    with conn.cursor() as cur:
        for statement in DDL:
            cur.execute(statement)
    conn.commit()


def insert_seed_data(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM clientes_prospectos")
        if cur.fetchone()[0] > 0:
            print("Seed data ya existe, saltando.")
            return

        productos = [
            # PILZ — Seguridad funcional
            ("PNOZ-S6-24VDC-2NO",  "PILZ", "Rele de Seguridad",    "Relé de seguridad PNOZ s6, 24 VDC, 2 contactos NA, categoría 4 / PL e",                                           485.00,  "Tensión: 24 VDC; Contactos salida: 2 NA; Categoría: 4 / PL e; Tiempo respuesta: ≤20 ms",                5,  21),
            ("PNOZ-XV2-24VDC",     "PILZ", "Rele de Seguridad",    "Relé de seguridad PNOZ XV2, 24 VDC, parada de emergencia y protección de resguardos",                              320.00,  "Tensión: 24 VDC; Entradas: 2 canales; Categoría: 4 / PL e; Arranque manual/automático",                 8,  21),
            ("PNOZ-M-B0",          "PILZ", "Sistema Configurable", "PNOZmulti 2 — base unit, 24 VDC, 4 entradas de seguridad, 2 salidas OSSD",                                        1850.00, "Tensión: 24 VDC; Entradas seg.: 4; Salidas OSSD: 2; Expansión modular; Profibus opcional",              2,  30),
            ("PMCprotego-DS",      "PILZ", "Monitor de Velocidad", "Monitor de velocidad y posición seguro PMCprotego DS, SIL 2",                                                     2400.00, "Entradas encoder: SinCos/HTL/TTL; SIL 2; Categoría 3; Funciones: SMS, SLS, SDI, SOS",                  1,  45),
            ("PSS-4000-CPU",       "PILZ", "PLC de Seguridad",     "Sistema de automatización seguro PSS 4000 — CPU modular, SafetyNET",                                             3200.00, "CPU: 400 MHz; RAM: 64 MB; Red: SafetyNET p; Categoría 4 / PL e; I/O expansible",                        0,  60),
            # OBO Bettermann — Gestión de cables
            ("OBO-TS-60-E-2M",    "OBO",  "Bandeja Portacables",  "Bandeja portacables con protección de bordes TS 60 E, longitud 2 m, acero galvanizado en caliente",                 45.00,  "Ancho: 60 mm; Alto: 35 mm; Material: Acero galvanizado; Longitud: 2 m; Carga: 28 kg/m",               120,  14),
            ("OBO-WLK-25060",     "OBO",  "Canaleta",             "Canaleta de cable WLK 250×60, PVC gris RAL 7030, con tapa",                                                         28.00,  "Ancho: 250 mm; Alto: 60 mm; Material: PVC; Color: Gris RAL 7030; Con tapa",                            80,  14),
            ("OBO-T-60-DEG",      "OBO",  "Accesorio Bandeja",    "Pieza en T para bandeja TS 60, acero galvanizado",                                                                   18.50,  "Tipo: T-junction; Compatible: TS 60; Material: Acero galvanizado en caliente",                         200,  14),
            ("OBO-GEK-0802E-R",   "OBO",  "Caja de Paso",         "Caja de empalme IP 65, 80×75 mm, sin prensaestopas, tapa con bisagra",                                              12.00,  "Protección: IP 65; Dimensiones: 80×75×42 mm; Material: Poliestireno; Color: Gris",                     150,  10),
            ("OBO-V-TBS-1008",    "OBO",  "Bandeja Portacables",  "Bandeja perforada V-TBS 100×80, acero galvanizado, ideal para bandejas horizontales",                               62.00,  "Ancho: 100 mm; Alto: 80 mm; Perforada: Sí; Material: Acero galvanizado; Longitud: 3 m",                 60,  14),
            # CABUR — Conexión y borneras
            ("CAB-XCMF010",       "CABUR","Bornera Fusible",       "Bornera portafusibles XCMF, sección 10 mm², para fusible 5×20 mm",                                                  8.50,  "Sección: 10 mm²; Corriente: 32 A; Tensión: 800 V; Fusible: 5×20 mm; Color: Gris",                     300,  15),
            ("CAB-XCSF010",       "CABUR","Bornera Tornillo",      "Bornera de tornillo XCS, sección 10 mm², azul (neutro)",                                                             3.20,  "Sección: 10 mm²; Corriente: 57 A; Tensión: 800 V; Color: Azul; Paso: 6 mm",                            500,  15),
            ("CAB-XCT010U",       "CABUR","Bornera Universal",     "Bornera universal XCT, sección 10 mm², 2 niveles de conexión",                                                       6.80,  "Sección: 10 mm²; Corriente: 57 A; Tensión: 800 V; Niveles: 2; Paso: 6 mm",                             250,  15),
            ("CAB-XCPE010",       "CABUR","Bornera PE",            "Bornera de tierra/PE XCP, sección 10 mm², amarillo-verde, conexión a masa directa",                                  4.10,  "Sección: 10 mm²; Conexión masa: Directa; Color: Amarillo-Verde; Norma: IEC 60947-7-1",                 400,  15),
            ("CAB-XCF004",        "CABUR","Bornera Fusible",       "Bornera portafusibles XCF, sección 4 mm², para fusible 5×20 mm, LED indicador",                                      7.20,  "Sección: 4 mm²; Corriente: 16 A; Tensión: 800 V; LED: Sí; Fusible: 5×20 mm",                          180,  15),
        ]

        cur.executemany(
            """INSERT INTO productos_catalogo
               (sku, marca, categoria, descripcion, precio_usd, especificaciones, stock, tiempo_entrega_dias)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (sku) DO NOTHING""",
            productos,
        )

        clientes = [
            ("Arcor S.A.I.C.",                  "Ing. Roberto Martínez",  "r.martinez@arcor.com",         "+54 9 351 555-0101", "Alimentos y Bebidas",        "ganado",        "https://linkedin.com/in/roberto-martinez-arcor",    "Principal cliente PILZ. Planta packaging en Córdoba. Compras anuales ~USD 30k."),
            ("Techint Ingeniería y Construcción","Lic. Andrea Soto",       "andrea.soto@techint.com",      "+54 9 11 555-0202",  "Siderurgia / Construcción",  "oferta",        "https://linkedin.com/in/andrea-soto-techint",       "Proyecto tablero distribución planta San Nicolás. Esperan aprobación presupuesto marzo."),
            ("Grupo Fate S.A.",                  "Ing. Carlos Pérez",      "c.perez@fate.com.ar",          "+54 9 11 555-0303",  "Automotriz",                 "calificado",    "https://linkedin.com/in/carlos-perez-fate",         "Interesados en relés de seguridad para prensas. Tienen presupuesto Q2 aprobado."),
            ("Metalúrgica Santa Rosa",           "Sr. Hugo Rodríguez",     "hrodriguez@msrosa.com.ar",     "+54 9 261 555-0404", "Metalurgia",                 "nuevo_cliente", None,                                                "Tablerista mediano, 5 empleados. Actualmente trabajan con Siemens. Visitar en abril."),
            ("Sistemi Integrazione SRL",         "Ing. Valentina Bruni",   "v.bruni@sistemi.com.ar",       "+54 9 11 555-0505",  "Integradores de Sistemas",   "ganado",        "https://linkedin.com/in/valentina-bruni-sistemi",   "Integrador clave. Proyectos en industria farmacéutica. Negociando descuento por volumen."),
            ("Molinos Río de la Plata",          "Ing. Diego Fernández",   "d.fernandez@molinos.com",      "+54 9 11 555-0606",  "Alimentos",                  "oferta",        "https://linkedin.com/in/diego-fernandez-molinos",   "Renovación tableros de distribución. OBO + CABUR. Solicitan ingeniería de tablero."),
            ("Laboratorio Roemmers S.A.",        "Lic. Sofía Castro",      "s.castro@roemmers.com.ar",     "+54 9 11 555-0707",  "Farmacéutica",               "nuevo_cliente", "https://linkedin.com/in/sofia-castro-roemmers",     "Nuevo proyecto GMP Zona Libre. Requieren certificación ATEX. Contactar tras feria ExpoAgro."),
        ]

        cur.executemany(
            """INSERT INTO clientes_prospectos
               (razon_social, contacto_nombre, contacto_email, contacto_telefono,
                industria, estado_lead, linkedin_url, notas)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            clientes,
        )

        oportunidades = [
            (1, "Renovación sistema de seguridad línea packaging",          12500.00, 75, "proposal",      "8× PNOZ s6 + 2× PNOZmulti 2. Ingeniería de puesta en marcha incluida.",            "2026-04-30"),
            (2, "Tablero distribución planta San Nicolás — CABUR",           8200.00, 40, "qualification", "Borneras CABUR para tablero 400 A. Competencia: Phoenix Contact.",                    "2026-06-15"),
            (3, "Relés de seguridad para prensas — 3 unidades",              2100.00, 30, "prospecting",   "3× PNOZ XV2. Piden demostración técnica primero.",                                  "2026-05-01"),
            (5, "Proyecto farma — OBO + CABUR bandejas y borneras",         18000.00, 85, "negotiation",   "50× bandeja OBO TS 60 E + mix borneras CABUR. Pedido grande, negociando 8% dto.",   "2026-03-30"),
            (6, "Modernización tableros distribución — OBO canaletas",       6500.00, 55, "proposal",      "WLK 250×60 (30u) + cajas GEK (20u). Solicitan plano de montaje.",                  "2026-05-15"),
        ]

        cur.executemany(
            """INSERT INTO oportunidades_ventas
               (cliente_id, descripcion, monto_usd, probabilidad_cierre, etapa, notas_tecnicas, fecha_cierre_estimada)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            oportunidades,
        )

        interacciones = [
            (1, "reunion",  "Visita planta Córdoba. Confirman upgrade PNOZ. Próximo paso: enviar cotización esta semana.",            "2026-02-15 10:00:00"),
            (1, "email",    "Enviada cotización formal 8× PNOZ s6 + 2× PNOZmulti 2. Esperando aprobación de compras.",               "2026-02-20 09:30:00"),
            (2, "llamada",  "Seguimiento con Andrea. Confirma interés pero esperan aprobación presupuesto planta en marzo.",           "2026-02-28 15:00:00"),
            (5, "reunion",  "Reunión técnica con Valentina. Proyecto farma muy avanzado. Negociando descuento por volumen.",           "2026-03-01 11:00:00"),
            (3, "email",    "Primer contacto por LinkedIn. Carlos derivó al Ing. de Seguridad. Agendar demo técnica en planta.",       "2026-02-10 08:00:00"),
            (6, "llamada",  "Diego confirma presupuesto aprobado. Quieren plano de tablero incluido. Enviar propuesta esta semana.",   "2026-03-01 14:00:00"),
        ]

        cur.executemany(
            "INSERT INTO interacciones (cliente_id, tipo, notas, fecha) VALUES (%s, %s, %s, %s)",
            interacciones,
        )

    conn.commit()
    print("Seed data insertado: 15 productos, 7 clientes, 5 oportunidades, 6 interacciones.")


def insert_reglas_descuento(conn) -> None:
    """Inserta las reglas de descuento por tarifa y marca. Idempotente."""
    reglas = [
        # (tarifa_nombre, marca, desc_1, desc_2, desc_3)
        ("Dist. Principal - Pilz 25% - Resto 30+10", "PILZ",  25.0,  0.0, 0.0),
        ("Dist. Principal - Pilz 25% - Resto 30+10", "OBO",   30.0, 10.0, 0.0),
        ("Dist. Principal - Pilz 25% - Resto 30+10", "CABUR", 30.0, 10.0, 0.0),
        ("Pilz System Partner - 30+10",               "PILZ",  30.0, 10.0, 0.0),
        ("30% OBO - Cabur - Pilz 0%",                 "OBO",   30.0,  0.0, 0.0),
        ("30% OBO - Cabur - Pilz 0%",                 "CABUR", 30.0,  0.0, 0.0),
        ("30% OBO - Cabur - Pilz 0%",                 "PILZ",   0.0,  0.0, 0.0),
        ("End User (5%)",                              "PILZ",   5.0,  0.0, 0.0),
        ("End User (5%)",                              "OBO",    5.0,  0.0, 0.0),
        ("End User (5%)",                              "CABUR",  5.0,  0.0, 0.0),
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO reglas_descuento (tarifa_nombre, marca, desc_1, desc_2, desc_3)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (tarifa_nombre, marca) DO NOTHING""",
            reglas,
        )
    conn.commit()
    print(f"Reglas de descuento: {len(reglas)} reglas cargadas (ON CONFLICT DO NOTHING).")


if __name__ == "__main__":
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL no configurada.")
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    try:
        create_tables(conn)
        insert_seed_data(conn)
        insert_reglas_descuento(conn)
        print(f"Base de datos lista.")
        print("Tablas: productos_catalogo, clientes_prospectos, oportunidades_ventas, interacciones, reglas_descuento")
    finally:
        conn.close()

    sys.exit(0)
