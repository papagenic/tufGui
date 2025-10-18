import dash
import serial
import os
import time
import struct
import threading
from dash import html, dcc, Input, Output, State, ctx
from pymodbus.client.serial import ModbusSerialClient
from modbus_worker import Task,ModbusWorker
from callbacks import register_callback,auto_register_callbacks, CALLBACK_REGISTRY
from layout import build_layout
from flask_socketio import SocketIO
from dash import Dash
import logging,sys
import yaml, argparse


# --- Parse command-line arguments ---
parser = argparse.ArgumentParser(description="TUF2000 Dash GUI")
parser.add_argument(
    "-c", "--config",
    default=None,
    help="Path to configuration file (default: ./config.yaml)"
)
args = parser.parse_args()
# --- Determine config path ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")
CONFIG_PATH = args.config or DEFAULT_CONFIG_PATH
# --- Load configuration ---
try:
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    sys.exit(f"Config file not found: {CONFIG_PATH}")

#parameters
data_path = config["data_path"]

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,  # show everything, including debug()
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout # send to standard output
    #filename=config["log_file"],  # full path to log file
    #filemode="a"  # append mode (use 'w' to overwrite each run)
)

#Create a module-level logger
logger = logging.getLogger(__name__)
logger.info (f"✅ Using config: {CONFIG_PATH}")

# Setup Modbus client
ser = serial.Serial(**config["serial"], exclusive=False) # This is what avoids the locking issue


# Pass that serial object to pymodbus
client = ModbusSerialClient(**config["serial"])
client.socket = ser  # Attach the serial connection manually
client.connect()

# Define keyboard layout
baseKeys = config["base_keys"]

functionKeys= config["function_keys"]

# Composite buttons
composite_keys = config["composite_keys"]

# Composite buttons
action_keys = config["action_keys"]
# Initialize Dash app
app = Dash(__name__, suppress_callback_exceptions=True)
socketio = SocketIO(app.server, cors_allowed_origins="*")

meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1.0"}
    ]
app.title = "Modbus Virtual Keyboard"

# Generate rows
composite_button_rows = []
current_row = []

# --- Tracking threads and states ---
active_tasks = {} # key: index, value: threading.Event

#define worker but do not start items
worker = ModbusWorker(client,state_file=os.path.join(data_path, "TUFState"))

# Custom HTML template to include the Socket.IO client library
app.index_string = """
<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <!-- ✅ Add the Socket.IO client script here -->
    <script src="/assets/socket.io.min.js"></script>
  </head>
  <body>
    {%app_entry%}
    <footer>
      {%config%}
      {%scripts%}
      {%renderer%}
    </footer>
  </body>
</html>
"""

# Build App layout
app.layout = build_layout(baseKeys, functionKeys, composite_keys, action_keys)

#-----------callback callled after modbus write----------------
@register_callback("record_and_log")
def record_and_log(task_id, value, timestamp, **kwargs):
    missing = [k for k in ( "target_id","file") if kwargs.get(k) is None]
    label = kwargs.get("label")
    if missing:
        logger.error(f"[record_and_log] Missing parameters {missing} for task id '{task_id}'")
        return "inactive"
    target_id = kwargs.get("target_id")
    file = kwargs.get("file")
    logger.debug(f"; record_and_log: task_id={task_id},timestamp:{timestamp},target_id= {target_id},value={value},file:{file}")
    
    ## write data to a task specific log file
    try:
        os.makedirs(data_path, exist_ok=True)
        file_path = os.path.join(data_path, f"{file}")

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"{timestamp},{value}\n")

    except Exception as e:
        logger.error(f"Failed to write data for task {task_id}: {e}")

    log_to_browser(task_id, value, timestamp, **kwargs)


@register_callback("log_to_browser")
def log_to_browser(task_id, value, timestamp, **kwargs):
    target_id = kwargs.get("target_id")
    logger.debug(f"; log_to_browser: task_id={task_id},timestamp:{timestamp},target_id= {target_id},value={value}")
    # now send status line to be displayed in the browser
    message = {
        "target_id": target_id,
        "content": f"[task:{task_id}--{timestamp}] Modbus result: {value}"
    }
    # Send this to the client (frontend) through a socket
    socketio.emit("update_element", message)
#--------------record action; create or stop task------------------------
def record_action(index, **params):

    # Validate required params
    required = ("label", "addr", "nbReg", "format", "recurrence")
    missing = [k for k in required if params.get(k) is None]
    if missing:
        logger.error(f"[record_action] Missing parameters {missing} for record button '{index}'")
        return "inactive"
    label = params.get("label", f"button_{index}")
    addr = params.get("addr")
    nbReg = params.get("nbReg")
    format = params.get("format")
    recurrence = params.get("recurrence")
    task_id = f"{label.replace(' ', '_')}"

    #now see if needed to start or stop a task
    if task_id in worker.tasks:
        # Stop existing task
        worker.delete_task(worker.tasks[task_id])
        logger.info(f"[record_action] Stopped recording: {label}")
        return "inactive"

    # Start a new recording task
    # all params except the required ones
    extra_params = {k: v for k, v in params.items() if k not in required}
    task = Task(
        task_id=task_id,
        modbus_param={
            "op": "read",
            "addr": int(addr),
            "nbreg": int(nbReg),
            "format": format
        },
        recurrence=float(recurrence),
        callback=record_and_log,
        parameters={"target_id": f"status_{index}"}|extra_params
    )
    worker.create_task(task)
    logger.debug(f"[record_action] created task: {task_id}; parameters:{task.parameters}")
    logger.info (f"[record_action] Started recording: {label}")
    return "active"
#-----------callback to delete a record file------------------
def deleteFile_action(index, **params):
    # Validate required params
    missing = [k for k in ("label","file") if params.get(k) is None]
    if missing:
        logger.error(f"[record_action] Missing parameters {missing} for button '{label}'")
        return "inactive"
    file= params.get("file")
    label = params.get("label", f"button_{index}")

    if not file:
        logger.error(f"[deleteFile_action] Missing 'file' parameter for button '{label}'")
        return "inactive"
    file_path = os.path.join(data_path, file)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"[deleteFile_action] Deleted file: {file_path}")
        else:
            logger.warning(f"[deleteFile_action] File not found: {file_path}")
    except Exception as e:
        logger.error(f"[deleteFile_action] Error deleting file '{file_path}': {e}")

    return "inactive"
#-----------Callback for base and function button press----------
@app.callback(
    Output("response", "children"),
    Input({'group': dash.ALL, 'index': dash.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def on_base_or_function_key_press(n_clicks):
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
    logger.debug(f"; on_base_or_function_key_press addr= {reg}, value={val}")
    #create a one time task to perform this
    task = Task(
        task_id=f"write_{group}_{index}",
        modbus_param={"op": "write", "addr": reg-1, "value": val},
        callback=log_to_browser,
        parameters={"target_id": "response"},  # element to update
    )
    worker.create_task(task)

#---------call back for composite buttons (key sequence)------------
@app.callback(
    Output("response", "children", allow_duplicate=True),
    Input({'type': 'composite', 'index': dash.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def on_composite_key_pressed(n_clicks):
    triggered = ctx.triggered_id
    index = triggered["index"]
    composite = composite_keys[index]

    output_log = []

    for label in composite["sequence"]:
        key = next((k for k in baseKeys if k["label"].lower() == label.lower()), None)
        if key:
            reg, val = key["reg"], key["val"]
            #create a one time task to perform this
            task = Task(
                task_id=f"write_{index}",
                modbus_param={"op": "write", "addr": reg- 1, "value": val},
                callback=log_to_browser,
                parameters={"target_id": "response"},  # element to update
            )
            worker.create_task(task)

    return "Composite Sent:<br>" + "<br>".join(output_log)

 #--- Callback to update button colors and perform  recording  actions  for register keys ---
@app.callback(
    Output({'type': 'rec-btn', 'index': dash.ALL}, 'style'),
    Input("url", "pathname"),  # Fires on page load
    Input({'type': 'rec-btn', 'index': dash.ALL}, 'n_clicks'),  # Fires on clicks
    prevent_initial_call=False
)
def handle_actions_buttons(pathname, n_clicks_list):
    
    # callback handles both:initializing button colors at page load
    # and toggling a recording task when a button is clicked
    # Base styles (default colors)
    
    styles = [{"backgroundColor": "lightgray"} for _ in action_keys]

    # --- Determine what triggered this callback ---
    trigger = ctx.triggered_id

    # --- Handle button click to manage associated tasks  ---
    if isinstance(trigger, dict) and trigger.get("type") == "rec-btn":
        index = trigger["index"]
        key = action_keys[index]
        label = key.get("label", f"button_{index}")

        action = key.get("action")
        if not action:
            logger.error(f"[handle_rec_buttons] Missing 'action' key for button '{label}'.")
            return styles

        # Build the function name dynamically
        func_name = f"{action}_action"
        action_func = globals().get(func_name)

        if not callable(action_func):
            logger.error(f"[handle_rec_buttons] No handler found for action '{action}' (expected function '{func_name}').")
            return styles

        # Prepare arguments: pass all key fields except 'action'
        params = {k: v for k, v in key.items() if k != "action"}

        try:
            logger.debug(f"[handle_rec_buttons] Executing action '{action}' for '{label}' with params={params}")
            result = action_func(index=index, **params)  # Call dynamically
        except Exception as e:
            logger.error(f"[handle_rec_buttons] Error executing action '{action}' for '{label}': {e}")
            return styles

    #refresh the style of all the buttons
    #this part is executed when the page load of when a button is pressed
    active_ids = worker.get_active_task_ids()
    queue_size = worker.queue_size()
    logger.debug(f"[handle_rec_buttons] active_ids: {active_ids} ; worker queue size:{queue_size}")
    for i, key in enumerate(action_keys):
        task_id = f"{key['label'].replace(' ', '_')}"
        if task_id in active_ids:
            logger.debug(f"[handle_rec_buttons] action key: {task_id} is green ")
            styles[i] = {"backgroundColor": "lightgreen"}
        else:
            styles[i] = {"backgroundColor": "lightgray"}
    return styles


        
        
# 1️⃣ Automatically register all callbacks from your callbacks module
# this create association betwen callbacks names and calback functions
#needed to save and restore worker states
auto_register_callbacks(globals())
print("Registered callbacks at startup:", CALLBACK_REGISTRY.keys())
worker.start()

# Run server
if __name__ == "__main__":
    socketio.run(app.server, host="0.0.0.0", port=8050, debug=True,allow_unsafe_werkzeug=True)
