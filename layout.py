from dash import dcc, html

def build_layout(baseKeys, functionKeys, composite_keys, register_keys):
    """Builds and returns the full Dash layout."""

    # ── Generate composite button rows ──────────────────────────────
    composite_button_rows = []
    current_row = []

    for i, k in enumerate(composite_keys):
        btn = html.Button(k["label"], id={'type': 'composite', 'index': i}, n_clicks=0)

        if k.get("newline") and current_row:
            composite_button_rows.append(
                html.Div(
                    current_row,
                    style={"display": "flex", "gap": "10px", "marginBottom": "10px"}
                )
            )
            current_row = []

        current_row.append(btn)

    # Add any remaining row
    if current_row:
        composite_button_rows.append(
            html.Div(
                current_row,
                style={"display": "flex", "gap": "10px", "marginBottom": "10px"}
            )
        )

    # ── Return the full layout ─────────────────────────────────────
    return html.Div([
    # This invisible component triggers callbacks on page load/reload
    dcc.Location(id="url", refresh=False),

    html.H2("Modbus Virtual Keyboard"),

    # Base buttons
    html.Div([
        html.Button(k["label"], id={'group': 'base', 'index': i}, n_clicks=0)
        for i, k in enumerate(baseKeys)
    ], style={
        'display': 'grid',
        'gridTemplateColumns': 'repeat(auto-fit, minmax(100px, 1fr))',
        'gap': '10px'
    }),

    html.Hr(),
    html.H3("read actions"),

    # Function keys
    html.Div([
        html.Button(k["label"], id={'group': 'function', 'index': i}, n_clicks=0)
        for i, k in enumerate(functionKeys)
    ], style={
        'display': 'grid',
        'gridTemplateColumns': 'repeat(auto-fit, minmax(100px, 1fr))',
        'gap': '10px'
    }),

    html.Hr(),

    # Composite buttons
    html.Div([
        html.H3("Composite Actions"),
        *composite_button_rows,
        html.Hr(),
        html.Div(id="response", style={"marginTop": "10px", "color": "blue"}),
    ]),

    html.Hr(),
    html.H3("record actions"),
    html.Div([
        html.Div([
            # The button itself
            html.Button(
                k["label"],
                id={'type': 'rec-btn', 'index': i},
                n_clicks=0,
                style={
                    "backgroundColor": "lightgray",
                    "width": "100%",              # full width for mobile
                    "height": "50px",             # comfortable tap area
                    "borderRadius": "10px",
                    "border": "1px solid #aaa",
                    "fontSize": "1.1em",
                    "fontWeight": "bold",
                    "marginBottom": "6px",        # spacing above status
                }
            ),
            # Status line under the button
            html.Div(
                id=f"status_{i}",
                style={
                    "color": "blue",
                    "fontSize": "0.9em",
                    "minHeight": "24px",
                    "textAlign": "center",
                    "marginBottom": "15px",       # spacing before next button
                    "wordWrap": "break-word",
                }
            )
        ],
        style={
            "width": "100%",
            "maxWidth": "400px",                 # keeps readable width on desktop
            "margin": "0 auto",                  # centers on wide screens
            "padding": "5px",
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "stretch",
        })
        for i, k in enumerate(register_keys)
    ],
    style={
        "display": "flex",
        "flexDirection": "column",               # vertical stacking
        "alignItems": "center",                  # center on desktop
        "padding": "0 10px",
    }),
],style={'padding': '20px'})