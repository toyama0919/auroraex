import json
import datetime
from tabulate import tabulate

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

    @staticmethod
    def print_tabulate(results, strip_size = 30):
        if not results:
            return
        rows = []
        for result in results:
            rows.append([ str(v)[0:strip_size] for v in result.values() ])

        headers = [ v for v in results[0].keys() ]
        print(tabulate(rows, headers = headers, tablefmt="simple"))
