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

# Home-screen status fragments (read-only, no menu navigation required)
ENDPOINT_ALARM_BANNER = "/ifalarms.html"    # current active-alarm text, e.g. "DirtyFilters"
ENDPOINT_ALARM_ICON = "/if7834.html"        # alarm indicator image (any alarm active)
ENDPOINT_BYPASS = "/if5523.html"            # bypass indicator image (free-cooling damper)
ENDPOINT_TEMP_SETPOINT = "/iftemp_sp.html"  # target temperature for the bypass logic

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

# Home-screen status patterns
REGEX_ALARM_BANNER = r"<h2[^>]*>([^<]*)</h2>"        # captures the alarm text (may be empty)
REGEX_ALARM_ICON = r"img7834_alarms_(on|off)"        # "on" => an alarm is active
REGEX_BYPASS = r"img5523_bypass_(on|off)"            # "on" => bypass (free-cooling) open
REGEX_TEMP_SETPOINT = r"<h2[^>]*>\s*(\d+\.\d+)\s*</h2>"

# Substring (case-insensitive) that marks the dirty-filter warning in the alarm banner
ALARM_FILTER_MARKER = "dirtyfilter"

# Temperature sensor identifiers
TEMP_EXTERNAL = "temp_external"
TEMP_RETURN = "temp_return"
TEMP_EXHAUST = "temp_exhaust"
TEMP_INLET = "temp_inlet"