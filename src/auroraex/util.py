import json
import datetime
from tabulate import tabulate


class Util:

    @staticmethod
    def datetime_handler(x):
        if isinstance(x, datetime.datetime) or isinstance(x, datetime.date):
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
    def print_tabulate(results, headers=[], strip_size=30):
        if not results:
            return
        rows = []
        headers = headers if headers else [v for v in results[0].keys()]
        for result in results:
            rows.append([str(result.get(key))[0:strip_size] for key in headers])

        print(tabulate(rows, headers=headers, tablefmt="simple"))
