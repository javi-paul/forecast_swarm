from flask import Flask
import concurrent.futures
import time
import random
import logging
import numpy as np

# --- Config ---
MAX_WORKERS = 50
CPU_DURATION_RANGE = (1, 10)
RAM_DURATION_RANGE = (10, 15)
RAM_SIZE_RANGE_MB = (200, 250)

# --- Setup ---
app = Flask(__name__)
executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# --- Job Functions ---
def cpu_job(duration):
    logging.info(f"CPU job started for {duration}s")
    end_time = time.time() + duration
    size = 100  # matrix size — increase for more load
    while time.time() < end_time:
        a = np.random.rand(size, size)
        b = np.random.rand(size, size)
        np.dot(a, b)
        time.sleep(1)
    logging.info("CPU job finished")

def ram_job(duration, size_mb):
    logging.info(f"RAM job started: {size_mb}MB for {duration}s")
    data = bytearray(size_mb * 1024 * 1024)
    for i in range(0, len(data), 4096):
        data[i] = 1
    try:
        time.sleep(duration)
    finally:
        del data
    logging.info("RAM job finished")

# --- Endpoints ---
@app.route("/cpu-job")
def cpu_endpoint():
    duration = random.randint(*CPU_DURATION_RANGE)
    executor.submit(cpu_job, duration)
    return f"CPU job queued for {duration} seconds\n", 200

@app.route("/ram-job")
def ram_endpoint():
    duration = random.randint(*RAM_DURATION_RANGE)
    size_mb = random.randint(*RAM_SIZE_RANGE_MB)
    executor.submit(ram_job, duration, size_mb)
    return f"RAM job queued: {size_mb} MB for {duration} seconds\n", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True)
