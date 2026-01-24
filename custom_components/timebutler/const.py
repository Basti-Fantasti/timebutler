"""Constants for the Timebutler integration."""

DOMAIN = "timebutler"

# Configuration
CONF_API_TOKEN = "api_token"
CONF_SCAN_INTERVAL = "scan_interval"

# Defaults
DEFAULT_SCAN_INTERVAL = 300  # 5 minutes
MIN_SCAN_INTERVAL = 60  # 1 minute
MAX_SCAN_INTERVAL = 3600  # 60 minutes

# API
API_BASE_URL = "https://app.timebutler.com/api/v1"
API_TIMEOUT = 30

# Timeclock states
TIMECLOCK_IDLE = "IDLE"
TIMECLOCK_RUNNING = "RUNNING"
TIMECLOCK_PAUSED = "PAUSED"

# User status (derived)
STATUS_WORKING = "working"
STATUS_PAUSED = "paused"
STATUS_OFF = "off"

# Absence states
ABSENCE_STATE_APPROVED = "Approved"
ABSENCE_STATE_DONE = "Done"
