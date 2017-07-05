import json
import datetime

class Util:

    @staticmethod
    def datetime_handler(x):
        if isinstance(x, datetime.datetime):
            return x.isoformat()
        raise TypeError("Unknown type")

    @staticmethod
    def print_json(data):
        print(
            json.dumps(
                data,
                indent=4,
                default=Util.datetime_handler
            )
        )
