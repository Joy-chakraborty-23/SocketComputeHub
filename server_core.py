# server_core.py
import socket
import threading
import subprocess
import os
import json
import time
from uuid import uuid4
import shutil
import sys

class ServerCore:
    def __init__(self, role='master'):
        self.role = role
        self.running = True

        # Directories
        self.upload_dir = "uploads"
        os.makedirs(self.upload_dir, exist_ok=True)

        # Master-specific data
        self.cluster_socket = None         # listening socket for workers
        self.workers = []                  # list of worker info dicts
        self.jobs = {}                     # job_id -> job_info
        self.pending_jobs = []             # queue of pending job_ids

        # Worker-specific data
        self.master_socket = None          # socket to master
        self.free_gpu_indices = []
        self.lock = threading.Lock()

    def shutdown(self):
        """Gracefully stop all loops and close sockets."""
        print("ServerCore: shutting down...")
        self.running = False
        try:
            if self.cluster_socket:
                self.cluster_socket.close()
        except:
            pass
        try:
            if self.master_socket:
                self.master_socket.close()
        except:
            pass

    # ---------------- Master Methods ----------------

    def handle_worker_registration(self, cluster_port):
        """Master: accept worker connections and spawn handler threads."""
        self.cluster_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.cluster_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.cluster_socket.bind(('0.0.0.0', cluster_port))
        self.cluster_socket.listen(10)
        print(f"Master: listening for workers on port {cluster_port}")

        while self.running:
            try:
                worker_sock, worker_addr = self.cluster_socket.accept()
            except OSError:
                break  # socket closed
            print(f"Master: worker connected from {worker_addr}")
            t = threading.Thread(
                target=self._master_handle_worker,
                args=(worker_sock, worker_addr)
            )
            t.start()

    def _master_handle_worker(self, worker_sock, worker_addr):
        """Master: per-worker communication."""
        worker_id = None
        info = {}
        try:
            data = worker_sock.recv(4096).decode()
            reg = json.loads(data)
            worker_id = reg.get("id", str(uuid4()))
            resources = reg.get("resources", {})
            info = {
                "id": worker_id,
                "socket": worker_sock,
                "address": worker_addr,
                "resources": resources,
                "free_gpu_indices": list(range(len(resources.get("gpus", [])))),
                "last_seen": time.time()
            }
            with self.lock:
                self.workers.append(info)
            # ack
            ack = {"type": "register_ack", "worker_id": worker_id}
            worker_sock.send(json.dumps(ack).encode())
        except Exception as e:
            print(f"Master: registration failed: {e}")
            worker_sock.close()
            return

        # Listen for messages
        while self.running:
            try:
                data = worker_sock.recv(4096).decode()
                if not data:
                    break
                msg = json.loads(data)
                mtype = msg.get("type")
                if mtype == "heartbeat":
                    info["last_seen"] = time.time()
                elif mtype == "result":
                    self._master_handle_result(msg)
                elif mtype == "reject":
                    self._master_handle_reject(msg)
            except (OSError, ConnectionResetError):
                break
            except Exception as e:
                print(f"Master: error in worker {worker_id}: {e}")

        # cleanup on disconnect
        print(f"Master: worker {worker_id} disconnected")
        with self.lock:
            if info in self.workers:
                self.workers.remove(info)
        self._master_requeue_jobs_from(worker_id)
        worker_sock.close()

    def _master_handle_result(self, msg):
        job_id = msg["job_id"]
        success = msg["success"]
        output = msg.get("output", "")
        error = msg.get("error", "")
        gpu = msg.get("gpu_index")
        worker_id = msg.get("worker_id")

        # free GPU
        with self.lock:
            for w in self.workers:
                if w["id"] == worker_id:
                    w["free_gpu_indices"].append(gpu)
                    break

        # send to client
        job = self.jobs.pop(job_id, None)
        if job:
            client_sock = job["client_socket"]
            if success:
                resp = {"action": "execution_result", "output": output}
            else:
                resp = {"action": "error", "message": error}
            try:
                client_sock.send(json.dumps(resp).encode())
            except:
                pass

        # schedule next
        self.schedule_pending_jobs()

    def _master_handle_reject(self, msg):
        job_id = msg["job_id"]
        print(f"Master: job {job_id} rejected, requeueing")
        with self.lock:
            job = self.jobs.get(job_id)
            if job:
                job["status"] = "pending"
                self.pending_jobs.append(job_id)
        self.schedule_pending_jobs()

    def _master_requeue_jobs_from(self, worker_id):
        requeue = []
        with self.lock:
            for jid, job in list(self.jobs.items()):
                if job.get("assigned_worker") == worker_id:
                    requeue.append(jid)
                    job["status"] = "pending"
                    job["assigned_worker"] = None
                    self.pending_jobs.append(jid)
        if requeue:
            print(f"Master: requeueing jobs {requeue}")
            self.schedule_pending_jobs()

    def schedule_pending_jobs(self):
        """Assign pending jobs to available workers."""
        with self.lock:
            for job_id in list(self.pending_jobs):
                job = self.jobs.get(job_id)
                if not job:
                    self.pending_jobs.remove(job_id)
                    continue
                # find worker with free GPU
                chosen = None
                for w in self.workers:
                    if w["free_gpu_indices"]:
                        chosen = w
                        break
                if not chosen:
                    return
                gpu = chosen["free_gpu_indices"].pop(0)
                task = {
                    "type": "execute_code",
                    "job_id": job_id,
                    "code": job["code"],
                    "files": job.get("files", []),
                    "worker_id": chosen["id"]
                }
                try:
                    chosen["socket"].send(json.dumps(task).encode())
                    job["status"] = "running"
                    job["assigned_worker"] = chosen["id"]
                    self.pending_jobs.remove(job_id)
                    print(f"Master: dispatched job {job_id} to worker {chosen['id']}")
                except Exception as e:
                    print(f"Master: failed to dispatch job {job_id}: {e}")
                    # rollback
                    chosen["free_gpu_indices"].append(gpu)
                    job["status"] = "pending"

    # ---------------- Worker Methods ----------------

    def connect_to_master(self, master_ip, cluster_port):
        """Worker: connect to master and handle commands."""
        self.master_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.master_socket.connect((master_ip, cluster_port))
        resources = self.get_resource_info()
        reg = {"type": "register", "id": str(uuid4()), "resources": resources}
        self.master_socket.send(json.dumps(reg).encode())
        # ack
        try:
            ack = json.loads(self.master_socket.recv(1024).decode())
            print("Worker: registered, id =", ack.get("worker_id"))
        except:
            pass
        # heartbeat thread
        hb = threading.Thread(target=self.send_heartbeats)
        hb.start()

        # listen for commands
        while self.running:
            try:
                data = self.master_socket.recv(4096).decode()
                if not data:
                    break
                msg = json.loads(data)
                if msg["type"] == "execute_code":
                    gpu = self.free_gpu_indices.pop(0)
                    t = threading.Thread(
                        target=self.execute_job,
                        args=(msg["job_id"], msg["code"], msg.get("files", []), gpu, msg.get("worker_id"))
                    )
                    t.start()
            except (OSError, ConnectionResetError):
                break
            except Exception as e:
                print("Worker error:", e)

        self.master_socket.close()

    def send_heartbeats(self):
        """Worker: send heartbeat periodically."""
        while self.running:
            time.sleep(10)
            try:
                self.master_socket.send(json.dumps({"type": "heartbeat"}).encode())
            except:
                break

    def execute_job(self, job_id, code, files, gpu_index, worker_id):
        """Worker: run code on reserved GPU and return result."""
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = str(gpu_index)
        job_dir = f"job_{job_id}"
        os.makedirs(job_dir, exist_ok=True)
        code_path = os.path.join(job_dir, "job_code.py")
        with open(code_path, "w") as f:
            f.write(code)
        for fobj in files:
            path = os.path.join(job_dir, fobj["filename"])
            with open(path, "w", errors="ignore") as fout:
                fout.write(fobj["content"])
        try:
            res = subprocess.run([sys.executable, code_path],
                                 capture_output=True, text=True,
                                 cwd=job_dir, env=env)
            success = (res.returncode == 0)
            out = res.stdout
            err = res.stderr
        except Exception as e:
            success = False
            out = ""
            err = str(e)
        msg = {
            "type": "result",
            "job_id": job_id,
            "success": success,
            "output": out if success else "",
            "error": err if not success else "",
            "gpu_index": gpu_index,
            "worker_id": worker_id
        }
        try:
            self.master_socket.send(json.dumps(msg).encode())
        except:
            pass
        with self.lock:
            self.free_gpu_indices.append(gpu_index)
        try:
            shutil.rmtree(job_dir)
        except:
            pass

    # ---------------- Shared Methods ----------------

    def get_resource_info(self):
        """Detect GPUs, CPU cores, and RAM."""
        info = {"gpus": [], "cpu_cores": os.cpu_count() or 0, "ram": 0}
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                stderr=subprocess.DEVNULL
            ).decode()
            for idx, line in enumerate(out.strip().splitlines()):
                name, mem = line.split(',', 1)
                mem_mb = int(''.join(filter(str.isdigit, mem)))
                info["gpus"].append({"index": idx, "name": name.strip(), "memory": mem_mb})
        except:
            pass
        try:
            import psutil
            info["ram"] = int(psutil.virtual_memory().total / (1024*1024))
        except:
            pass
        if self.role == 'worker':
            self.free_gpu_indices = [g["index"] for g in info["gpus"]]
        return info

    def save_uploaded_file(self, filename, content):
        """Save an uploaded file into uploads/ directory."""
        try:
            path = os.path.join(self.upload_dir, filename)
            with open(path, "w", encoding="utf-8", errors="ignore") as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Core: failed to save uploaded file {filename}: {e}")
            return False

    def enqueue_job(self, client_socket, code, files):
        """Create a new job, queue it, and attempt scheduling."""
        job_id = str(uuid4())
        with self.lock:
            self.jobs[job_id] = {
                "client_socket": client_socket,
                "code": code,
                "files": files,
                "status": "pending",
                "assigned_worker": None
            }
            self.pending_jobs.append(job_id)
        # try to dispatch immediately
        self.schedule_pending_jobs()
        return job_id

