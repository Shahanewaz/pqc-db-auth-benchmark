
import time
import csv
import statistics
from importlib import import_module

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization

# ====================================
# CONFIGURATION
# ====================================

ALGORITHMS = [
    "ECDSA-P256",
    "ml_dsa_44",
    "ml_dsa_65",
    "ml_dsa_87",
    "slh_dsa_sha2_128s"
]

ITERATIONS = 1000
MESSAGE = b"Database authentication challenge"

results = []

# ====================================
# BENCHMARK
# ====================================

for algorithm in ALGORITHMS:

    print("Testing:", algorithm)

    keygen_times = []
    sign_times = []
    verify_times = []
    signature_sizes = []

    if algorithm == "ECDSA-P256":

        for i in range(ITERATIONS):

            start = time.perf_counter_ns()
            sk = ec.generate_private_key(ec.SECP256R1())
            pk = sk.public_key()
            keygen_times.append(
                (time.perf_counter_ns() - start) / 1000
            )

            start = time.perf_counter_ns()
            sig = sk.sign(
                MESSAGE, ec.ECDSA(hashes.SHA256())
            )
            sign_times.append(
                (time.perf_counter_ns() - start) / 1000
            )

            start = time.perf_counter_ns()
            pk.verify(
                sig, MESSAGE, ec.ECDSA(hashes.SHA256())
            )
            verify_times.append(
                (time.perf_counter_ns() - start) / 1000
            )

            signature_sizes.append(len(sig))

        pk_bytes = pk.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint
        )

    else:

        # Load PQC algorithm dynamically
        pqc = import_module("pqcrypto.sign." + algorithm)

        for i in range(ITERATIONS):

            start = time.perf_counter_ns()
            pk, sk = pqc.keygen()
            keygen_times.append(
                (time.perf_counter_ns() - start) / 1000
            )

            start = time.perf_counter_ns()
            sig = pqc.sign(sk, MESSAGE)
            sign_times.append(
                (time.perf_counter_ns() - start) / 1000
            )

            start = time.perf_counter_ns()
            pqc.verify(pk, MESSAGE, sig)
            verify_times.append(
                (time.perf_counter_ns() - start) / 1000
            )

            signature_sizes.append(len(sig))

        pk_bytes = bytes(pk)

    results.append({
        "algorithm": algorithm,
        "keygen_us": round(statistics.median(keygen_times), 3),
        "sign_us": round(statistics.median(sign_times), 3),
        "verify_us": round(statistics.median(verify_times), 3),
        "public_key_bytes": len(pk_bytes),
        "signature_bytes": statistics.median(signature_sizes)
    })

# ====================================
# EXPORT CSV
# ====================================

with open("rq1_results.csv", "w", newline="") as f:

    writer = csv.DictWriter(f, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

print("\nBenchmark completed!")
print("Results saved to rq1_results.csv")