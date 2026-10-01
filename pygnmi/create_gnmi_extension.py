"""This module contains the converter of dict() to Extension() GRPC class
(c)2019-2024, karneliuk.com"""

# Modules
import datetime
from pygnmi.spec.v0100.gnmi_ext_pb2 import Extension


# Statics
COMMIT_ACTIONS = ("commit", "confirm", "cancel", "set_rollback_duration")


# Functions
def get_gnmi_extension(ext: dict = None) -> list:
    """This helper function allows conversion of dictinary to Extension class"""
    result = None

    # Don't build empty extension
    if not ext:
        return result

    else:
        result = Extension()

    # Create history extension
    if "history" in ext:

        if "snapshot_time" in ext["history"] and "range" in ext["history"]:
            raise Exception("Both 'snapshot_time' and 'range' are provided. Choose one")

        # Set snapshot_time key
        if "snapshot_time" in ext["history"]:
            result.history.snapshot_time = _get_time_ns_epoch(ext["history"]["snapshot_time"])

        # Set time range
        if "range" in ext["history"]:
            if not ("start" in ext["history"]["range"] and "end" in ext["history"]["range"]):
                raise Exception("'/extension/history/range' requires both 'start' and 'end'.")

            else:
                result.history.range.start = _get_time_ns_epoch(ext["history"]["range"]["start"])
                result.history.range.end = _get_time_ns_epoch(ext["history"]["range"]["end"])

    if "master_arbitration" in ext:

        result.master_arbitration.election_id.high = ext["master_arbitration"]["election_id"]["high"]
        result.master_arbitration.election_id.low = ext["master_arbitration"]["election_id"]["low"]

        if "role" in ext["master_arbitration"]:
            result.master_arbitration.role.id = ext["master_arbitration"]["role"]["id"]

    # Create commit confirmed extension
    if "commit" in ext:
        if len(ext) > 1:
            raise ValueError("'/extension/commit' cannot be combined with other extensions in one Extension.")

        _set_commit(result, ext["commit"])

    return result


def _set_commit(result, commit: dict) -> None:
    """This helper function sets the commit confirmed extension. The dict mirrors the Commit message:
    an 'id' and exactly one action out of 'commit', 'confirm', 'cancel' and 'set_rollback_duration'."""
    if not commit.get("id"):
        raise ValueError("'/extension/commit' requires a non-empty 'id'.")

    actions = [action for action in COMMIT_ACTIONS if action in commit]
    if len(actions) != 1:
        raise ValueError(f"'/extension/commit' requires exactly one action out of {', '.join(COMMIT_ACTIONS)}.")

    result.commit.id = commit["id"]
    action = actions[0]
    params = {} if commit[action] is None else commit[action]
    if not isinstance(params, dict):
        raise ValueError(f"'/extension/commit/{action}' must be a dict or None.")

    if action in ("commit", "set_rollback_duration"):
        # An action message is set even when empty, as it is what selects the action
        message = getattr(result.commit, action)
        message.SetInParent()

        if "rollback_duration" in params:
            message.rollback_duration.FromTimedelta(_get_timedelta(params["rollback_duration"]))

        elif action == "set_rollback_duration":
            raise ValueError("'/extension/commit/set_rollback_duration' requires 'rollback_duration'.")

    else:
        getattr(result.commit, action).SetInParent()


def _get_timedelta(duration) -> datetime.timedelta:
    """This helper function takes a duration as datetime.timedelta() or seconds as int() or float()."""
    if isinstance(duration, datetime.timedelta):
        return duration

    if isinstance(duration, (int, float)) and not isinstance(duration, bool):
        return datetime.timedelta(seconds=duration)

    raise ValueError(f"Rollback duration {duration} must be seconds as int or float, or a datetime.timedelta.")


def _get_time_ns_epoch(time_in_question) -> int:
    """This helper function takes input as int() or str() and returns int() with time in ns
    since the beginning of the epoch."""
    if isinstance(time_in_question, int):
        result = time_in_question

    else:
        try:
            time_stamp = datetime.datetime.strptime(time_in_question, "%Y-%m-%dT%H:%M:%SZ")
            result = int(time_stamp.timestamp() * pow(10, 9))

        except Exception as err:
            err.args += f"Time conversion error: cannot convert {time_in_question}, use 'yyyy-mm-ddTHH:MM:SSZ' format. Details: {err}"
            raise

    return result
