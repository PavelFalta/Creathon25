import datetime
from .helpers import str_time_fill_ms


class Artefact:

    def __init__(self, start_time, end_time,
                 modified_time=None, modified_by="Administrator"):
        self.start_time = start_time
        self.end_time = end_time
        self.modified_by = modified_by
        if not modified_time:
            self.modified_time = datetime.datetime.utcnow()
        else:
            self.modified_time = modified_time

    def to_index(self, sr, window_s, start_time_s):
        start_s = self.start_time.timestamp() - start_time_s
        end_s = self.end_time.timestamp() - start_time_s

        if start_s % window_s != 0:
            raise ValueError(f"Start time {start_s} is not a multiple of window size {window_s}")
            #start_s = start_s - (start_s % window_s)
            remainder = start_s % window_s
            if remainder > window_s / 2:
                start_s = start_s + (window_s - remainder)
            else:
                start_s = start_s - remainder

        if end_s % window_s != 0:
            raise ValueError(f"End time {end_s} is not a multiple of window size {window_s}")
            #end_s = end_s - (end_s % window_s)
            remainder = end_s % window_s
            if remainder > window_s / 2:
                end_s = end_s + (window_s - remainder)
            else:
                end_s = end_s - remainder

        start_idx = int(start_s * sr)
        end_idx = int(end_s * sr)

        return start_idx, end_idx

    @staticmethod
    def from_index(idx, sr, window_s, start_time_s):
        start_s = idx / sr
        end_s = start_s + window_s

        abs_start_s = start_time_s + start_s
        abs_end_s = start_time_s + end_s

        abs_start_time = datetime.datetime.fromtimestamp(abs_start_s, tz=datetime.timezone.utc)
        abs_end_time = datetime.datetime.fromtimestamp(abs_end_s, tz=datetime.timezone.utc)

        return Artefact(abs_start_time, abs_end_time)

    @staticmethod
    def from_artf_dict(artefact_dict, date_format):
        modified_by = artefact_dict["ModifiedBy"]
        modified_time = artefact_dict["ModifiedDate"]
        # Fill to 6 digits after dot to make it microseconds
        modified_time = str_time_fill_ms(modified_time)
        modified_time = datetime.datetime.strptime(f"{modified_time}", date_format)\
            .replace(tzinfo=datetime.timezone.utc)
        start_time = artefact_dict["StartTime"]
        # Fill to 6 digits after dot to make it microseconds
        start_time = str_time_fill_ms(start_time)
        start_time = datetime.datetime.strptime(f"{start_time}", date_format)\
            .replace(tzinfo=datetime.timezone.utc)
        # Fill to 6 digits after dot to make it microseconds
        end_time = artefact_dict["EndTime"]
        end_time = str_time_fill_ms(end_time)
        end_time = datetime.datetime.strptime(f"{end_time}", date_format)\
            .replace(tzinfo=datetime.timezone.utc)

        return Artefact(start_time, end_time, modified_time, modified_by)

    def __repr__(self):
        return f"Artefact {self.start_time} -> {self.end_time} [{self.modified_by}] ({self.modified_time})"

    def __str__(self):
        return repr(self)

    # Compare with other artefact
    def __eq__(self, other):
        if not isinstance(other, Artefact):
            return False
        return self.start_time == other.start_time and self.end_time == other.end_time

