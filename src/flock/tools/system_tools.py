from flock.core.logging.trace_and_logged import traced_and_logged


@traced_and_logged
def get_current_time() -> str:
    import datetime

    time = datetime.datetime.now().isoformat()
    return time
