
import os
import csv
import time
import secrets
import random
import statistics
from pathlib import Path
from importlib import import_module

import psycopg
import mysql.connector
from pymongo import MongoClient
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes


# ==========================================
# 1. EXPERIMENT CONFIGURATION
# ==========================================

ALGORITHMS = [
    "ECDSA-P256",
    "ml_dsa_44",
    "ml_dsa_65",
    "ml_dsa_87",
    "slh_dsa_sha2_128s"
]

DATABASES = [
    "postgresql",
    "mysql",
    "mongodb"
]

ITERATIONS = 100
WARMUP = 5

DB_CONFIG = {
    "postgresql": {
        "host": "localhost",
        "port": 5432,
        "dbname": "pqcbench",
        "user": "postgres",
        "password": os.getenv("PGPASSWORD", "")
    },
    "mysql": {
        "host": "localhost",
        "port": 3306,
        "database": "pqcbench",
        "user": "root",
        "password": os.getenv("MYSQL_PASSWORD", "")
    },
    "mongodb": {
        "uri": os.getenv(
            "MONGODB_URI",
            "mongodb://localhost:27017/"
        )
    }
}

Path("results").mkdir(exist_ok=True)


def elapsed_ms(start):
    return (time.perf_counter_ns() - start) / 1e6


# ==========================================
# 2. CRYPTOGRAPHIC AUTHENTICATION
# ==========================================

def create_keys(algorithm):

    if algorithm == "ECDSA-P256":
        sk = ec.generate_private_key(ec.SECP256R1())
        return None, sk.public_key(), sk

    pqc = import_module("pqcrypto.sign." + algorithm)
    pk, sk = pqc.keygen()
    return pqc, pk, sk


def authenticate(algorithm, pqc, pk, sk):

    challenge = (
        b"RQ2-DB-AUTH-v1|client-1|"
        + secrets.token_bytes(32)
    )

    start = time.perf_counter_ns()

    if algorithm == "ECDSA-P256":
        signature = sk.sign(
            challenge, ec.ECDSA(hashes.SHA256())
        )
        pk.verify(
            signature,
            challenge,
            ec.ECDSA(hashes.SHA256())
        )
    else:
        signature = pqc.sign(sk, challenge)
        result = pqc.verify(pk, challenge, signature)
        if result is False:
            raise RuntimeError("Signature rejected")

    return elapsed_ms(start)


# ==========================================
# 3. DATABASE CONNECTIONS
# ==========================================

def connect_db(database):

    start = time.perf_counter_ns()

    if database == "postgresql":
        conn = psycopg.connect(
            **DB_CONFIG["postgresql"],
            connect_timeout=5
        )
        conn.autocommit = True

    elif database == "mysql":
        conn = mysql.connector.connect(
            **DB_CONFIG["mysql"],
            connection_timeout=5
        )

    elif database == "mongodb":
        conn = MongoClient(
            DB_CONFIG["mongodb"]["uri"],
            serverSelectionTimeoutMS=5000,
            connect=False
        )
        # MongoClient is lazy; force a real connection.
        try:
            conn.admin.command("ping")
        except Exception:
            conn.close()
            raise

    else:
        raise ValueError(database)

    return conn, elapsed_ms(start)


# ==========================================
# 4. PREPARE IDENTICAL LOGICAL RECORDS
# ==========================================

def prepare_database(database):

    conn, _ = connect_db(database)

    try:
        if database == "postgresql":
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS rq2_items (
                        id INTEGER PRIMARY KEY,
                        value INTEGER NOT NULL
                    )
                """)
                cur.execute("""
                    INSERT INTO rq2_items (id, value)
                    VALUES (1, 100)
                    ON CONFLICT (id)
                    DO UPDATE SET value = EXCLUDED.value
                """)

        elif database == "mysql":
            cur = conn.cursor()
            try:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS rq2_items (
                        id INT PRIMARY KEY,
                        value INT NOT NULL
                    )
                """)
                cur.execute("""
                    INSERT INTO rq2_items (id, value)
                    VALUES (1, 100)
                    ON DUPLICATE KEY UPDATE value = 100
                """)
                conn.commit()
            finally:
                cur.close()

        elif database == "mongodb":
            collection = conn["pqcbench"]["rq2_items"]
            collection.update_one(
                {"_id": 1},
                {"$set": {"value": 100}},
                upsert=True
            )

    finally:
        conn.close()


# ==========================================
# 5. DATABASE READ
# ==========================================

def read_database(database, conn):

    start = time.perf_counter_ns()

    if database == "postgresql":
        with conn.cursor() as cur:
            cur.execute(
                "SELECT value FROM rq2_items WHERE id = 1"
            )
            value = cur.fetchone()[0]

    elif database == "mysql":
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT value FROM rq2_items WHERE id = 1"
            )
            value = cur.fetchone()[0]
        finally:
            cur.close()

    elif database == "mongodb":
        document = conn["pqcbench"]["rq2_items"].find_one(
            {"_id": 1}
        )
        value = document["value"] if document else None

    if value != 100:
        raise RuntimeError("Incorrect database result")

    return elapsed_ms(start)


# ==========================================
# 6. ONE COMPLETE EXPERIMENT
# ==========================================

def run_once(algorithm, database, pqc, pk, sk):

    start = time.perf_counter_ns()

    # Authenticate first
    auth_ms = authenticate(algorithm, pqc, pk, sk)

    # Connect only after successful authentication
    conn, connect_ms = connect_db(database)

    try:
        query_ms = read_database(database, conn)
    finally:
        conn.close()

    total_ms = elapsed_ms(start)

    return {
        "auth_ms": auth_ms,
        "connect_ms": connect_ms,
        "query_ms": query_ms,
        "total_ms": total_ms
    }


# ==========================================
# 7. RUN ALL CONFIGURATIONS
# ==========================================

print("Preparing databases...")

for database in DATABASES:
    prepare_database(database)
    print("Ready:", database)

keys = {
    name: create_keys(name)
    for name in ALGORITHMS
}

combinations = [
    (algorithm, database)
    for algorithm in ALGORITHMS
    for database in DATABASES
]

random.Random(42).shuffle(combinations)

raw_results = []
summary = []

for algorithm, database in combinations:

    print(f"\nTesting {algorithm} on {database}")

    pqc, pk, sk = keys[algorithm]
    samples = []

    # Warm-up is not recorded
    for _ in range(WARMUP):
        run_once(algorithm, database, pqc, pk, sk)

    for iteration in range(1, ITERATIONS + 1):

        measurement = run_once(
            algorithm, database, pqc, pk, sk
        )

        raw_results.append({
            "algorithm": algorithm,
            "database": database,
            "iteration": iteration,
            **measurement
        })

        samples.append(measurement)

    row = {
        "algorithm": algorithm,
        "database": database
    }

    for metric in [
        "auth_ms",
        "connect_ms",
        "query_ms",
        "total_ms"
    ]:
        row[metric] = round(
            statistics.median(
                sample[metric] for sample in samples
            ),
            4
        )

    summary.append(row)
    print("Median total (ms):", row["total_ms"])


# ==========================================
# 8. SAVE RESULTS
# ==========================================

def save_csv(filename, rows):
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=list(rows[0].keys())
        )
        writer.writeheader()
        writer.writerows(rows)


save_csv("results/rq2_raw.csv", raw_results)
save_csv("results/rq2_summary.csv", summary)

print("\nRQ2 completed successfully.")
print("Results saved in results/")