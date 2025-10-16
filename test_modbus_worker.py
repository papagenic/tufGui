# test_modbus_worker.py
import time
from modbus_worker import Task,ModbusWorker
from pymodbus.client.serial import ModbusSerialClient
import serial
import logging,sys

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,  # show everything, including debug()
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout      # send to standard output
)

#Create a module-level logger
logger = logging.getLogger(__name__)

# simple callback function
def print_Modbus_result(value, timestamp, **kwargs):
    print(f"[{timestamp}] {kwargs.get('operation', '')}: {value}")

def on_write_done(value, timestamp, **kwargs):
    print(f"[{timestamp}] Write complete: {value}")

# initialize mock client + worker
# Setup Modbus client
ser = serial.Serial(
    port='/dev/ttyUSB0',
    baudrate=9600,
    bytesize=8,
    parity='N',
    stopbits=1,
    timeout=1,
    exclusive=False  # This is what avoids the locking issue
)

# Pass that serial object to pymodbus
client = ModbusSerialClient(
    port='/dev/ttyUSB0',     # Required even if we override socket
    baudrate=9600,
    bytesize=8,
    parity='N',
    stopbits=1,
    timeout=1
)
client.socket = ser  # Attach the serial connection manually
client.connect()
worker = ModbusWorker(client)
worker.start()

# define a periodic read task to read the flow
read_flow = Task(
    task_id = "flow_read",
    parameters= {"operation": "Flow(l/s)"},
    modbus_param = {"op": "read", "addr": 1, "nbreg": 2, "format": "REAL4"},
    callback = print_Modbus_result,
    recurrence = 2,   # seconds
)
read_velocity = Task(
    task_id = "velocity_read",
    parameters = {"operation": "Velocity(m/s)"},
    modbus_param = {"op": "read", "addr": 5, "nbreg": 2, "format": "REAL4"},
    callback = print_Modbus_result,
    recurrence = 3,   # seconds
)

# define a one-shot write task
get_pipe_diameter = Task(
    task_id = "get Pipe ext Diam",
    parameters = {},
    modbus_param = {"op": "write", "addr": 60+1, "value": 17},
    callback = on_write_done,
)

# register tasks
print("starting recurrent read flow")
worker.create_task(read_flow)
print("getting pipe diameter on tuf2000")
worker.create_task(get_pipe_diameter)

try:
    time.sleep(10)  # run for 10 seconds
    print("starting recurrent read velocity")
    worker.create_task(read_velocity)
    time.sleep(10)  # run for 10 seconds
    print("getting pipe diameter on tuf2000")
    worker.create_task(get_pipe_diameter)
    time.sleep(10)
    print("stopping recurrent read flow")
    worker.stop_task(read_flow)
    worker.stop_task(get_pipe_diameter)
finally:
    worker.stop()