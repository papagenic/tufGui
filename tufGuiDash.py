import dash
import serial
import time
from dash import html, dcc, Input, Output, State, ctx
from pymodbus.client.serial import ModbusSerialClient

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

# Define keyboard layout
baseKeys = [
    {"label": "Menu", "reg": 59, "val": 60},
    {"label": "Enter", "reg": 59, "val": 61},
    {"label": "Up", "reg": 59, "val": 62},
    {"label": "down", "reg": 59, "val": 63},
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
]

functionKeys= [
    {"label": "Pipe ext Diam", "reg": 60, "val": 17},
    {"label": "Pipe Thickness", "reg": 60, "val": 18},
    {"label": "Pipe material", "reg": 60, "val": 20},
]

# Composite buttons
composite_keys = [
    {
        "label": "set pipe ext diameter",
        "sequence": ["Menu", "1", "1", "Enter"]
    },
    {
        "label": "set pipe thickness",
        "sequence": ["Menu", "1", "2", "Enter"]
    },
{
        "label": "set pipe material",
        "sequence": ["Menu", "1", "4", "Enter"]
    },
    {
        "label": "show spacing",
        "sequence": ["Menu", "2", "5"],
        "newline" : True,
    },
    {
        "label": "show error code",
        "sequence": ["Menu", "0", "8"],
    },
]

# Initialize Dash app
app = dash.Dash(__name__)
meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1.0"}
    ]
app.title = "Modbus Virtual Keyboard"

# Generate rows
composite_button_rows = []
current_row = []

for i, k in enumerate(composite_keys):
    btn = html.Button(k["label"], id={'type': 'composite', 'index': i}, n_clicks=0)

    # If this button should start on a new line
    if k.get("newline") and current_row:
        composite_button_rows.append(
            html.Div(current_row, style={"display": "flex", "gap": "10px", "marginBottom": "10px"})
        )
        current_row = []

    current_row.append(btn)

# Add any remaining buttons
if current_row:
    composite_button_rows.append(
        html.Div(current_row, style={"display": "flex", "gap": "10px", "marginBottom": "10px"})
    )

# App layout
app.layout = html.Div([
    html.H2("Modbus Virtual Keyboard"),

    html.Div([
        html.Button(k["label"], id={'group': 'base', 'index': i}, n_clicks=0)
        for i, k in enumerate(baseKeys)
    ], style={'display': 'grid', 'gridTemplateColumns': 'repeat(auto-fit, minmax(100px, 1fr))', 'gap': '10px'}),

    html.Hr(),
    html.H3("read actions"),

    html.Div([
        *[
            html.Button(k["label"], id={'group': 'function', 'index': i}, n_clicks=0)
            for i, k in enumerate(functionKeys)
        ]
    ], style={'display': 'grid', 'gridTemplateColumns': 'repeat(auto-fit, minmax(100px, 1fr))', 'gap': '10px'}),

    html.Hr(),

    html.Div([
        html.H3("Composite Actions"),
        *composite_button_rows,  # Unpack all rows
        html.Hr(),
        html.Div(id="response", style={"marginTop": "10px", "color": "blue"}),
    ]),

], style={'padding': '20px'})

# Callback for button presses
@app.callback(
    Output("response", "children"),
    Input({'group': dash.ALL, 'index': dash.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def on_key_press(n_clicks):
    triggered = dash.callback_context.triggered_id
    if not triggered:
        return ""
    group = triggered["group"]
    index = triggered["index"]
    if group == 'base':
        key = baseKeys[index]
    else:
        key = functionKeys[index]
    reg, val = key["reg"], key["val"]

    result = client.write_register(reg - 1, val, device_id=1)
    return f"Sent: Reg {reg} = {val} → {result}"

@app.callback(
    Output("response", "children", allow_duplicate=True),
    Input({'type': 'composite', 'index': dash.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def on_composite_pressed(n_clicks):
    triggered = ctx.triggered_id
    index = triggered["index"]
    composite = composite_keys[index]

    output_log = []

    for label in composite["sequence"]:
        key = next((k for k in baseKeys if k["label"].lower() == label.lower()), None)
        if key:
            result = client.write_register(key["reg"] - 1, key["val"], device_id=1)
            output_log.append(f"{key['label']} → Reg {key['reg']} = {key['val']}")
            time.sleep(0.3)  # small delay between commands
        else:
            output_log.append(f"[Error: '{label}' not found in base Keys]")

    return "Composite Sent:<br>" + "<br>".join(output_log)

# Run server
if __name__ == "__main__":
    app.run(
      host="0.0.0.0",
      port=8050,
      debug=True)