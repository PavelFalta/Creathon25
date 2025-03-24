import datetime


def format_timedelta(td):
    # Calculate the total number of seconds in the timedelta object
    total_seconds = td.total_seconds()

    # Calculate the number of days, hours, minutes, and seconds in the timedelta object
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Format the timedelta object as "DAY:HOUR:MINUTE:SECOND"
    return f"{int(days)}:{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

def ts_to_tick(ts, date=True):
    dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    if date:
        return dt.strftime("%m/%d %H:%M:%S")
    else:
        return dt.strftime("%H:%M:%S")

def ts_to_full_date(ts):
    dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    return dt.strftime("%Y/%m/%d %H:%M:%S")

def str_time_fill_ms(strtime: str):
    splitted = strtime.split(".")
    if len(splitted) == 1:
        strtime = f"{strtime}.000000"
    elif len(splitted) == 2:
        ms = splitted[1]
        strtime = f"{splitted[0]}.{ms:0<6}"
    return strtime
