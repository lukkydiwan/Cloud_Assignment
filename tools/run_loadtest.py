import subprocess
import time
import json
import os

print("=== Starting Locust Load Test (2 minutes) ===")
os.makedirs("results", exist_ok=True)

# Launch locust process in background
locust_cmd = [
    ".venv/bin/locust",
    "-f", "tools/locustfile.py",
    "--headless",
    "--users", "4",
    "--spawn-rate", "4",
    "--run-time", "2m",
    "--host", "http://localhost:8080",
    "--csv", "results/loadtest"
]

proc = subprocess.Popen(locust_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

pod_metrics = []
start_time = time.time()

# Poll kubectl top pods periodically during the 2-minute test
while proc.poll() is None:
    time.sleep(15)
    try:
        top_out = subprocess.check_output(["kubectl", "top", "pods", "-n", "app"], text=True)
        ts = round(time.time() - start_time, 1)
        print(f"[{ts}s] kubectl top pods:\n{top_out.strip()}")
        pod_metrics.append({"timestamp": ts, "metrics": top_out.strip()})
    except Exception as e:
        print(f"Could not poll kubectl top pods: {e}")

stdout, _ = proc.communicate()
print("Locust execution completed!")
print(stdout)

with open("results/pod_load_telemetry.json", "w") as f:
    json.dump(pod_metrics, f, indent=2)

print("Saved telemetry to results/pod_load_telemetry.json")
