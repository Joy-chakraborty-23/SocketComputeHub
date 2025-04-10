# run_server.py (fixed and recommended)
import argparse
import threading
import signal
import sys
import time
from server_core import ServerCore
from server_ui import ServerUI

def main():
    parser = argparse.ArgumentParser(description="Run ServerGPU as master or worker.")
    parser.add_argument("--role", choices=["master", "worker"], required=True)
    parser.add_argument("--master_ip", help="Master IP (required for worker)")
    parser.add_argument("--port", default=8080, type=int)
    parser.add_argument("--cluster_port", default=5000, type=int)

    args = parser.parse_args()

    core = ServerCore(role=args.role)

    threads = []

    if args.role == "master":
        print("Starting as Master...")
        worker_thread = threading.Thread(target=core.handle_worker_registration, args=(args.cluster_port,))
        worker_thread.start()
        threads.append(worker_thread)

        ui = ServerUI('0.0.0.0', args.port, core)
        ui_thread = threading.Thread(target=ui.start_client_listener)
        ui_thread.start()
        threads.append(ui_thread)

    elif args.role == "worker":
        if not args.master_ip:
            print("Master IP is required for worker.")
            sys.exit(1)
        print("Starting as Worker...")
        worker_conn_thread = threading.Thread(target=core.connect_to_master, args=(args.master_ip, args.cluster_port))
        worker_conn_thread.start()
        threads.append(worker_conn_thread)

    def shutdown(sig, frame):
        print("\nGraceful shutdown initiated...")
        core.shutdown()  # Implement resource clean-up
        for t in threads:
            t.join(timeout=2)
        print("Shutdown complete.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Keep main alive until shutdown
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()

