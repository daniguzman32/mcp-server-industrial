#!/usr/bin/env python3
"""
Migración de base de datos Fachmann.

Cambios que aplica:
  1. Agrega 'IDEM SAFETY' al CHECK constraint de marca en productos_catalogo
  2. Crea tabla reglas_descuento con constraint actualizado
  3. Inserta reglas de descuento iniciales (idempotente)

Correr dentro de Railway (usa DATABASE_URL interna):
  python src/migrar_db.py
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)

MIGRATIONS = [
    # 1. Actualizar CHECK de marca en productos_catalogo para incluir IDEM SAFETY
    "ALTER TABLE productos_catalogo DROP CONSTRAINT IF EXISTS productos_catalogo_marca_check",
    """ALTER TABLE productos_catalogo ADD CONSTRAINT productos_catalogo_marca_check
       CHECK(marca IN ('PILZ', 'OBO', 'CABUR', 'IDEM SAFETY'))""",

    # 2. Crear tabla reglas_descuento con CHECK actualizado
    """CREATE TABLE IF NOT EXISTS reglas_descuento (
        id              SERIAL PRIMARY KEY,
        tarifa_nombre   TEXT    NOT NULL,
        marca           TEXT    NOT NULL CHECK(marca IN ('PILZ', 'OBO', 'CABUR', 'IDEM SAFETY')),
        desc_1          REAL    NOT NULL DEFAULT 0.0,
        desc_2          REAL    NOT NULL DEFAULT 0.0,
        desc_3          REAL    NOT NULL DEFAULT 0.0,
        UNIQUE(tarifa_nombre, marca)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_reglas_tarifa ON reglas_descuento(tarifa_nombre)",
]

REGLAS = [
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


if __name__ == "__main__":
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL no configurada.")
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            print("Aplicando migraciones de schema...")
            for stmt in MIGRATIONS:
                label = stmt.strip().splitlines()[0][:70]
                print(f"  {label}")
                cur.execute(stmt)

            print("Insertando reglas de descuento...")
            cur.executemany(
                """INSERT INTO reglas_descuento (tarifa_nombre, marca, desc_1, desc_2, desc_3)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (tarifa_nombre, marca) DO NOTHING""",
                REGLAS,
            )

        conn.commit()
        print(f"Migracion completada: schema actualizado + {len(REGLAS)} reglas de descuento.")
    except Exception as e:
        conn.rollback()
        print(f"ERROR — rollback aplicado: {e}")
        sys.exit(1)
    finally:
        conn.close()

    sys.exit(0)
