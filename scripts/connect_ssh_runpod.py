import os
import stat
import subprocess
import sys
import time

# ==============================
# 📝 DEFINE YOUR IP AND PORT HERE
# ==============================
IP = "89.221.67.137"  # <--- Change this IP
PORT = "22630"  # <--- Change this Port


def run_command(cmd):
    """Runs a shell command silently."""
    subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main(ip, port):
    print(f"🚀 Setting up connection to {ip}:{port}...")

    # 1. Update SSH Config
    ssh_dir = os.path.expanduser("~/.ssh")
    config_path = os.path.join(ssh_dir, "config")
    os.makedirs(ssh_dir, exist_ok=True)

    config_content = f"""Host vast-gpu
    HostName {ip}
    Port {port}
    User root
    StrictHostKeyChecking no
    LocalForward 127.0.0.1:8000 localhost:8000
    LocalForward 127.0.0.1:18888 localhost:8888
"""

    try:
        with open(config_path, "w") as f:
            f.write(config_content)
        os.chmod(config_path, stat.S_IRUSR | stat.S_IWUSR)  # chmod 600
        print("✅ SSH Config updated.")
    except Exception as e:
        print(f"❌ Error writing config: {e}")
        sys.exit(1)

    # 2. Kill old background tunnels to clear the port
    print("🧹 Cleaning up old connections...")
    run_command("pkill -f 'ssh -f -N vast-gpu'")
    time.sleep(1)

    # 3. Start the new tunnel
    print("🔌 Connecting to GPU in background...")
    result = subprocess.run("ssh -f -N vast-gpu", shell=True)

    # 4. Verification
    if result.returncode == 0:
        print("\n✅ SUCCESS! Tunnel is active.")
        print("   FastAPI: curl http://127.0.0.1:8000/health")
        print("   vLLM:    curl http://127.0.0.1:18888/v1/models")
    else:
        print("\n❌ ERROR: Connection failed. Check your IP/Port or keys.")


if __name__ == "__main__":
    if len(sys.argv) == 3:
        IP = sys.argv[1]
        PORT = sys.argv[2]

    main(IP, PORT)
