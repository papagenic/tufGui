from flask import Flask, render_template, request
from pymodbus.client.serial import ModbusSerialClient

app = Flask(__name__)

# Setup Modbus client
client = ModbusSerialClient(
    port='/dev/ttyUSB0',
    baudrate=9600,
    parity='N',
    stopbits=1,
    bytesize=8,
    timeout=1
)
client.connect()

@app.route('/', methods=['GET', 'POST'])
def index():
    status = ""

    if request.method == 'POST':
        reg = int(request.form['register'])
        val = int(request.form['value'])
        result = client.write_register(reg - 1, val, device_id=1)
        status = f"Sent: Reg {reg} = {val} → {result}"

    return render_template('index.html', status=status)

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)