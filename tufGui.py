import tkinter as tk
from pymodbus.client.serial import ModbusSerialClient
import logging
slave=1

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

# Connect to RS485 Modbus device
client = ModbusSerialClient(
    port='/dev/ttyUSB0',       # Change to your COM port
    baudrate=9600,
    parity='N',
    stopbits=1,
    bytesize=8,
    timeout=2,
    retries=6
)
print(type(client))
client.connect()

# Command handler
def send_modbus_command(register, value):
    #subtract 1 to register as  register start at 0
    result = client.write_register(register-1, value,device_id=1)
    print(f"Sent: Reg {register} = {value} → {result}")

# GUI setup
root = tk.Tk()
root.title("Modbus Virtual Keyboard")

# Define keys and associated modbus actions
keys = [
    {"label": "Menu", "reg": 59, "val": 60},
    {"label": "enter", "reg": 59, "val": 61},
    {"label": "up", "reg": 59, "val": 62},
    {"label": "0", "reg": 59, "val": 48},
    {"label": "1", "reg": 59, "val": 49},
    {"label": "2", "reg": 59, "val": 50},
    {"label": "3", "reg": 59, "val": 51},
    {"label": "4", "reg": 59, "val": 52},
    {"label": "5", "reg": 59, "val": 53},
    {"label": "6", "reg": 59, "val": 54},
    {"label": "7", "reg": 59, "val": 55},
    {"label": "8", "reg": 59, "val": 56},
    {"label": "9", "reg": 59, "val": 57},
    {"label": ".", "reg": 59, "val": 58},
    {"label": "pipe out diam", "reg": 60, "val": 17},
    {"label": "pipe tickness", "reg": 60, "val": 18},
]

# Create buttons
current_row = 0
current_col = 0
columns = 3
for key in keys:
    if key.get("new_row", False):
        current_row += 1
        current_col = 0

    btn = tk.Button(root, text=key["label"], width=12, height=2,
                    command=lambda k=key: send_modbus_command(k["reg"], k["val"]))
    btn.grid(row=current_row, column=current_col, padx=10, pady=10)

    current_col += 1
    if current_col >= columns:
        current_row += 1
        current_col = 0
#

root.mainloop()
client.close()

