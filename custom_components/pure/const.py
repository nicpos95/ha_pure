"""Constants for the Pure VMC integration."""

DOMAIN = "pure"
DEFAULT_SCAN_INTERVAL = 30  # seconds

# Config entry keys
CONF_HOST = "host"

# Endpoints
ENDPOINT_SPEED = "/ifspeed_sp.html"
ENDPOINT_TEMP_EXTERNAL = "/iftemp_e.html"
ENDPOINT_TEMP_RETURN = "/iftemp_r.html"
ENDPOINT_TEMP_EXHAUST = "/iftemp_x.html"
ENDPOINT_TEMP_INLET = "/iftemp_i.html"

# POST payloads
PAYLOAD_SPEED_UP_TEN = "iic0001.x=1&iic0001.y=1"
PAYLOAD_SPEED_DOWN_TEN = "ddc0001.x=1&ddc0001.y=1"
PAYLOAD_SPEED_UP_ONE = "inc0001.x=1&inc0001.y=10"
PAYLOAD_SPEED_DOWN_ONE = "dec0001.x=1&dec0001.y=10"
PAYLOAD_ON_OFF = "tgl0001.x=8&tgl0001.y=8"
PAYLOAD_BOOST = "tgl0002.x=8&tgl0002.y=11"
ENDPOINT_BOOST = "/iftimer.html"

# Special speed values
SPEED_OFF = 0
SPEED_TIMER_MODE = 101
SPEED_MIN = 20
SPEED_MAX = 100

# Regex patterns — \s+ handles space or newline between label and value
REGEX_SPEED = r"<h2>(\d{2,3}%|Off|Orologio)\s*</h2>"
REGEX_TEMP_EXTERNAL = r"<h3>Te\s+(\d+\.\d+)\s*</h3>"
REGEX_TEMP_RETURN = r"<h3>Tr\s+(\d+\.\d+)\s*</h3>"
REGEX_TEMP_EXHAUST = r"<h3>Tx\s+(\d+\.\d+)\s*</h3>"
REGEX_TEMP_INLET = r"<h3>Ti\s+(\d+\.\d+)\s*</h3>"

# Temperature sensor identifiers
TEMP_EXTERNAL = "temp_external"
TEMP_RETURN = "temp_return"
TEMP_EXHAUST = "temp_exhaust"
TEMP_INLET = "temp_inlet"