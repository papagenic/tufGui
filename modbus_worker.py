# modbus_worker.py
import threading
import json
import os
import time
import struct
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, Callable,Optional
from callbacks import  get_callback_name,CALLBACK_REGISTRY   
import random
import logging

# Create a module-level logger
logger = logging.getLogger(__name__)
logging.getLogger("pymodbus").setLevel(logging.WARNING)
logging.getLogger("pymodbus.logging").setLevel(logging.WARNING)


# ----------------------------------------------------------------------
# task implementation
# ----------------------------------------------------------------------
@dataclass
class Task:
    task_id: str
    modbus_param: Dict[str, Any]
    callback: Optional[Callable[[Any], None]] = None
    callback_name: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    recurrence: float = 0.0
    urgent: bool = False

    def is_periodic(self) -> bool:
        return self.recurrence > 0

    def __repr__(self):
        return f"<Task id={self.task_id}, op={self.modbus_param.get('op')}, rec={self.recurrence}s>"
# ----------------------------------------------------------------------
# Queue implementation
# ----------------------------------------------------------------------

class TaskQueue:
    """Thread-safe deque-based task queue with top/bottom insert."""
    def __init__(self):
        self.q = deque()
        self.lock = threading.Lock()

    def push_bottom(self, item):
        with self.lock:
            self.q.append(item)

    def push_top(self, item):
        with self.lock:
            self.q.appendleft(item)

    def pop_bottom(self):
        with self.lock:
            return self.q.popleft() if self.q else None
    def size(self):
        """Return the number of items currently in the queue."""
        with self.lock:
            return len(self.q)


# ----------------------------------------------------------------------
# Helper to decode Modbus register values
# ----------------------------------------------------------------------

def decode_modbus_registers(registers, fmt="REAL4"):
    """Decode list of 16-bit registers into a Python value (little-endian)."""
    if not registers:
        return None
    raw = b"".join(r.to_bytes(2, "little") for r in registers)

    if fmt == "REAL4":      # 32-bit float
        return round(struct.unpack("<f", raw[:4])[0], 4)
    elif fmt == "LONG":     # 32-bit signed int
        return struct.unpack("<i", raw[:4])[0]
    elif fmt == "INTEGER":  # single 16-bit int
        return registers[0]
    elif fmt == "REAL8":    # 64-bit float
        return struct.unpack("<d", raw[:8])[0]
    else:
        raise ValueError(f"Unknown format: {fmt}")


# ----------------------------------------------------------------------
# Modbus Worker
# ----------------------------------------------------------------------

class ModbusWorker(threading.Thread):
    def __init__(self, client,state_file: str = ""):
        super().__init__(daemon=True)
        self.client = client
        self.queue = TaskQueue()
        self.tasks = {}   # active task definitions
        self.timers = {}  # task_id → threading.Timer
        self.running = True
        self.state_file = state_file

    # ---------------- main worker loop ----------------
    def run(self):
        if self.state_file:
            self.load_state()
        print("[Worker] Started.")
        while self.running:
            task = self.queue.pop_bottom()
            if task:
                try:
                    self.execute_task(task)
                except Exception as e:
                    logger.error(f"Error executing task {getattr(task, 'task_id', '?')}: {e}")            
            else:
                time.sleep(0.05)

    # ---------------- execute modbus operation ----------------
    def execute_task(self, task: Task):
        """Perform the Modbus operation for a given task and invoke callback."""
        mod = task.modbus_param
        op = mod.get("op")
        addr = int(mod.get("addr"))
        nbreg = int(mod.get("nbreg", 1))
        fmt = mod.get("format", "INTEGER")

        value = None

        try:
            if op == "read":
                response = self.client.read_holding_registers(address=addr, count=nbreg, device_id=1)
                value = decode_modbus_registers(response.registers, fmt)
                logger.debug(f"modbus read holding register; addr= {addr}, count={nbreg},value:{value}")
            elif op == "write":
                value= int(mod.get("value"))
                logger.debug(f"modbus write register; addr= {addr}, value={value}")
                self.client.write_register(address=addr, value=value, device_id=1)
            else:
                logger.error(f"[ModbusWorker] Unknown Modbus operation: {op}")
                return
        except Exception as e:
            logger.error(f"[ModbusWorker] Error executing task {task.task_id}: {e}")
            return

        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        if callable(task.callback):
            try:
                logger.debug(f"[ execute_task] calling callback {get_callback_name(task.callback)}, task_id:{task.task_id},timestamp={ts},value:{value},parameters:{task.parameters}")
                task.callback(task_id=task.task_id,value=value, timestamp=ts, **task.parameters)
            except Exception as cb_err:
                logger.error(f"[ModbusWorker] Callback error for {task.task_id}: {cb_err}")
                task_cb=get_callback_name(task.callback)
                logger.error(f"[ModbusWorker] task calback:{task_cb}; parameters for {task.task_id}:{task.parameters}")

    # ---------------- schedule periodic tasks ----------------
    def create_task(self, task: Task,save: bool = True):
        """Register and start a task (one-shot or periodic)."""
        tid = task.task_id
        
        # Infer callback name automatically if missing
        if task.callback and not getattr(task, "callback_name", None):
            task.callback_name = get_callback_name(task.callback)

        # Check for duplicates; 
        # only periodic tasks are inserted in the task list 
        #on time tasks go only to the task queue
        if task.is_periodic() and tid in self.tasks:
            logger.warning(f"[ModbusWorker] Task '{tid}' already exists — ignoring create request.")
            return

        self.tasks[tid] = task

        # Schedule the first execution (immediate)
        def timer_callback():
            if not self.running:
                return
                
            # If task has been deleted, stop
            if tid not in self.tasks:
                logger.debug(f"[ModbusWorker] Timer for deleted task '{tid}' exiting.")
                return
                
            # Push task into queue (urgent vs normal)
            if task.urgent:
                self.queue.push_top(task)
            else:
                self.queue.push_bottom(task)

            # Reschedule if periodic
            if task.is_periodic() and self.running and tid in self.tasks:
                t = threading.Timer(task.recurrence, timer_callback)
                t.daemon = True
                t.start()
                self.timers[tid] = t

        # Start initial call immediately
        timer_callback()
        #save state if not already restoring worker state
        if save:
            logger.info(f"[ModbusWorker] Task '{tid}' created; saving state.")
            self.save_state()

    def delete_task(self, task: Task):
        tid = task.task_id  # ✅ extract ID from Task
        timer = self.timers.pop(tid, None)
        if timer:
            timer.cancel()
        self.tasks.pop(tid, None)
        logger.info(f"[ModbusWorker] Task '{tid}' stopped; savings state")
        self.save_state()

    def stop(self):
        """Stop worker and all timers."""
        self.running = False
        for t in self.timers.values():
            t.cancel()
        self.timers.clear()
        print("[Worker] Stopped.")
        
    def get_active_task_ids(self):
        """Return a list of currently running recurring task IDs."""
        return list(self.tasks.keys())

    #save the state of the worker in a file
    def queue_size(self):
        """Return the number of pending tasks in the queue."""
        return self.queue.size()
    def save_state(self):
        try:
            state = {}
            for task_id, task in self.tasks.items():
                if getattr(task, "recurrence", 0) > 0:
                    state[task_id] = {
                        "task_id": task.task_id,
                        "modbus_param": task.modbus_param,
                        "parameters": task.parameters,
                        "recurrence": task.recurrence,
                        "urgent": task.urgent,
                        "callback_name": task.callback_name,
                    }
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
            logger.info(f"Saved {len(state)} tasks to {self.state_file}")
        except Exception as e:
            logger.error(f"Error saving worker state: {e}")
        
        
    #load the state of the  worker from a file
    def load_state(self):
        if not os.path.exists(self.state_file):
            logger.info(f"No saved state file found at {self.state_file}")
            return

        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
        except Exception as e:
            logger.error(f"Error loading worker state file: {e}")
            return
        
        #recreate the tasks
        logger.info(f"Restoring  state file from  {self.state_file}")
        for task_id, data in state.items():
            try:
                cb_name = data.get("callback_name")
                cb = CALLBACK_REGISTRY.get(cb_name)
                if not cb:
                    logger.warning(f"Unknown callback '{cb_name}' for task {task_id}, skipping.")
                    continue
    
                task = Task(
                    task_id=data["task_id"],
                    modbus_param=data["modbus_param"],
                    parameters=data.get("parameters", {}),
                    recurrence=float(data.get("recurrence", 0)),
                    urgent=bool(data.get("urgent", False)),
                    callback=cb,
                    callback_name=cb_name,
                )
                self.create_task(task,save = False)
                logger.info(f"Restored task: {task_id} (callback={cb_name})")
            except Exception as e:
                logger.error(f"Error restoring task {task_id}: {e}")