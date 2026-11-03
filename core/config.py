"""Local configurable thresholds and product defaults."""
from . import database
DEFAULTS={'cpu_attention_percent':85,'memory_attention_percent':90,'storage_low_space_percent':10,'temperature_attention_c':80,'temperature_problem_c':90,'reminder_months':6,'cleanup_min_age_days':7,'command_timeout_seconds':30}

def get_threshold(name):
    default=DEFAULTS[name]
    try:return float(database.get_setting('threshold_'+name,str(default)))
    except (TypeError,ValueError):return float(default)

def set_threshold(name,value):
    if name not in DEFAULTS:raise KeyError(name)
    number=float(value)
    if number<0 or number>10000:raise ValueError('Threshold is outside a safe range')
    database.set_setting('threshold_'+name,str(number))
    return number
