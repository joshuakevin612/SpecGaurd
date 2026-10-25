"""Untrusted worker protocol. Contains inputs only; assertions stay outside."""
import contextlib
import importlib.util
import json
import sys


def main():
    requests = json.load(open('/work/inputs.json' if sys.platform != 'win32'
                              and __file__.startswith('/work/') else 'inputs.json'))
    # Printing cannot impersonate protocol output through normal Python print().
    with contextlib.redirect_stdout(sys.stderr):
        spec = importlib.util.spec_from_file_location('submission', 'submission.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        results = []
        for request in requests:
            try:
                result = getattr(module, request['function'])(*request['args'], **request['kwargs'])
            except Exception as exc:
                results.append({'kind': 'raise', 'type': type(exc).__name__})
            else:
                try:
                    # Serialization errors are infrastructure failures, not
                    # exceptions raised by the submitted function.
                    json.dumps(result, allow_nan=False)
                    results.append({'kind': 'return', 'value': result})
                except (TypeError, ValueError, RecursionError):
                    results.append({'kind': 'invalid'})
    sys.stdout.write(json.dumps(results, allow_nan=False))


if __name__ == '__main__':
    main()
