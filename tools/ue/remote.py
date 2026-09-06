"""Bridge to a running Unreal Editor via the engine's own remote-execution protocol.

Usage:
  py -3 Tools/remote.py --file Tools/some_script.py   # run a script inside UE
  py -3 Tools/remote.py --cmd "print('hi')"           # run one statement
"""
import argparse
import sys
import time

UE_PY = r"C:\Program Files\Epic Games\UE_5.8\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python"
sys.path.insert(0, UE_PY)
import remote_execution as ue_re  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file", help="python file to execute inside Unreal")
    p.add_argument("--cmd", help="single statement to execute inside Unreal")
    p.add_argument("--timeout", type=float, default=30.0, help="seconds to wait for an editor node")
    a = p.parse_args()
    if not a.file and not a.cmd:
        p.error("need --file or --cmd")

    r = ue_re.RemoteExecution()
    r.start()
    node = None
    deadline = time.time() + a.timeout
    while time.time() < deadline:
        nodes = r.remote_nodes
        if nodes:
            node = nodes[0]
            break
        time.sleep(0.5)
    if not node:
        print("NO_UNREAL_NODE_FOUND")
        r.stop()
        sys.exit(2)

    r.open_command_connection(node["node_id"])
    if a.file:
        import os
        with open(a.file, encoding="utf-8") as f:
            code = f.read()
        result = r.run_command(code, exec_mode=ue_re.MODE_EXEC_FILE, raise_on_failure=False)
        blob = str(result)
        if not result.get("success") and "Could not load Python file" in blob:
            # this UE build treats ExecuteFile commands as literal paths - send the path
            result = r.run_command(os.path.abspath(a.file), exec_mode=ue_re.MODE_EXEC_FILE, raise_on_failure=False)
    else:
        result = r.run_command(a.cmd, exec_mode=ue_re.MODE_EXEC_STATEMENT, raise_on_failure=False)
    r.stop()

    for line in result.get("output", []):
        print(f"[{line.get('type', '?')}] {line.get('output', '').rstrip()}")
    if result.get("result") not in (None, "", "None"):
        print(f"[result] {result.get('result')}")
    print("SUCCESS" if result.get("success") else "FAILED")
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
