
import os
import csv
import time
import secrets
import statistics
from pathlib import Path
from importlib import import_module
from concurrent.futures import ThreadPoolExecutor

import psycopg
import mysql.connector
from pymongo import MongoClient

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes


# ==========================================
# 1. CONFIGURATION
# ==========================================

ALGORITHMS = [
    "ECDSA-P256",
    "ml_dsa_44",
    "slh_dsa_sha2_128s"
]

DATABASES = [
    "postgresql",
    "mysql",
    "mongodb"
]

CONCURRENCY = [1, 5, 10]
SESSION_MODES = ["fresh", "reuse"]

REQUESTS_PER_CLIENT = 5

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


def authenticate(algorithm, keys):

    pqc, pk, sk = keys

    challenge = (
        b"RQ3-AUTH-v1|" + secrets.token_bytes(32)
    )

    if algorithm == "ECDSA-P256":

        signature = sk.sign(
            challenge,
            ec.ECDSA(hashes.SHA256())
        )

        pk.verify(
            signature,
            challenge,
            ec.ECDSA(hashes.SHA256())
        )

    else:

        signature = pqc.sign(sk, challenge)

        # pqcrypto.verify raises on invalid signatures.
        result = pqc.verify(pk, challenge, signature)

        if result is False:
            raise RuntimeError("Signature verification failed")


# ==========================================
# 3. DATABASE CONNECTION
# ==========================================

def connect_db(database):

    if database == "postgresql":
        conn = psycopg.connect(
            **DB_CONFIG["postgresql"],
            connect_timeout=30
        )
        conn.autocommit = True
        return conn

    if database == "mysql":
        return mysql.connector.connect(
            **DB_CONFIG["mysql"],
            connection_timeout=30
        )

    if database == "mongodb":
        conn = MongoClient(
            DB_CONFIG["mongodb"]["uri"],
            serverSelectionTimeoutMS=5000,
            connect=False
        )
        try:
            conn.admin.command("ping")
        except Exception:
            conn.close()
            raise
        return conn

    raise ValueError(database)


# ==========================================
# 4. DATABASE READ
# ==========================================

def read_db(database, conn):

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

        doc = conn["pqcbench"]["rq2_items"].find_one(
            {"_id": 1}
        )
        value = doc["value"] if doc else None

    if value != 100:
        raise RuntimeError("Database read failed")


# ==========================================
# 5. SIMULATE ONE CLIENT
# ==========================================

def client_workload(
    algorithm, database, mode, keys
):

    latencies = []
    auth_count = 0

    if mode == "fresh":

        # Authenticate and connect for EVERY query
        for _ in range(REQUESTS_PER_CLIENT):

            start = time.perf_counter()

            authenticate(algorithm, keys)
            auth_count += 1

            conn = connect_db(database)

            try:
                read_db(database, conn)
            finally:
                conn.close()

            latencies.append(
                (time.perf_counter() - start) * 1000
            )

    elif mode == "reuse":

        # Authenticate and connect only ONCE
        start = time.perf_counter()

        authenticate(algorithm, keys)
        auth_count += 1

        conn = connect_db(database)

        try:
            for i in range(REQUESTS_PER_CLIENT):

                # First request includes initial authentication
                if i == 0:
                    query_start = start
                else:
                    query_start = time.perf_counter()

                read_db(database, conn)

                latencies.append(
                    (time.perf_counter() - query_start) * 1000
                )

        finally:
            conn.close()

    else:
        raise ValueError(mode)

    return latencies, auth_count


# ==========================================
# 6. BENCHMARK CONCURRENCY
# ==========================================

def benchmark(
    algorithm, database, mode,
    clients, keys
):

    start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=clients) as pool:

        futures = [
            pool.submit(
                client_workload,
                algorithm, database, mode, keys
            )
            for _ in range(clients)
        ]

        all_latencies = []
        auth_count = 0

        for future in futures:
            latencies, count = future.result()
            all_latencies.extend(latencies)
            auth_count += count

    total_time = time.perf_counter() - start

    operations = len(all_latencies)

    ordered = sorted(all_latencies)

    # Nearest-rank 95th percentile
    p95_index = max(
        0, int(__import__("math").ceil(0.95 * operations)) - 1
    )

    return {
        "algorithm": algorithm,
        "database": database,
        "mode": mode,
        "clients": clients,
        "operations": operations,
        "auth_count": auth_count,
        "total_time_s": round(total_time, 4),
        "throughput_ops_s": round(
            operations / total_time, 3
        ),
        "mean_latency_ms": round(
            statistics.mean(all_latencies), 3
        ),
        "p95_latency_ms": round(
            ordered[p95_index], 3
        )
    }


# ==========================================
# 7. RUN EXPERIMENTS
# ==========================================

results = []

for algorithm in ALGORITHMS:

    keys = create_keys(algorithm)

    for database in DATABASES:

        for clients in CONCURRENCY:

            for mode in SESSION_MODES:

                print(
                    f"{algorithm} | {database} | "
                    f"{clients} clients | {mode}",
                    flush=True
                )

                result = benchmark(
                    algorithm, database,
                    mode, clients, keys
                )

                results.append(result)

                print(
                    "  Throughput:",
                    result["throughput_ops_s"],
                    "ops/s"
                )


# ==========================================
# 8. SAVE CSV
# ==========================================

with open(
    "results/rq3_results.csv",
    "w",
    newline=""
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=list(results[0].keys())
    )

    writer.writeheader()
    writer.writerows(results)

print("\nRQ3 completed!")
print("Saved to results/rq3_results.csv")