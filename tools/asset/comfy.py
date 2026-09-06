"""Small ComfyUI client + a UI-workflow → API-prompt converter.

The converter lets us drive the *official* workflow templates (UI JSON, as shipped in the
comfyui-workflow-templates package) headlessly: it asks the running server for /object_info,
walks each node's declared inputs in order, and fills them from the template's widgets_values
and links. Nodes not upstream of the requested output nodes are pruned (previews, notes).
"""
import copy
import json
import os
import time
import urllib.parse
import urllib.request
import uuid

BASE = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
COMFY_DIR = os.environ.get("COMFY_DIR", r"C:\Users\nickl\Documents\Agents\comfyui\ComfyUI")

WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO", "COLOR", "LOAD_3D", "COMFY_DYNAMICCOMBO_V3"}
FRONTEND_ONLY = {"Note", "MarkdownNote", "Reroute", "PrimitiveNode"}


def _get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def alive():
    try:
        _get("/system_stats")
        return True
    except Exception:
        return False


def object_info():
    return _get("/object_info")


def upload_image(path, subfolder="envlab"):
    """multipart upload → returns the name ComfyUI's LoadImage expects."""
    boundary = "----envlab" + uuid.uuid4().hex
    name = os.path.basename(path)
    with open(path, "rb") as f:
        blob = f.read()
    body = b""
    body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode() + blob + b"\r\n"
    body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"subfolder\"\r\n\r\n{subfolder}\r\n".encode()
    body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n".encode()
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(BASE + "/upload/image", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        res = json.loads(r.read().decode("utf-8"))
    sub = res.get("subfolder", "")
    return (sub + "/" if sub else "") + res["name"]


def queue(prompt):
    res = _post("/prompt", {"prompt": prompt, "client_id": "envlab"})
    if "error" in res:
        raise RuntimeError(json.dumps(res, indent=1)[:4000])
    return res["prompt_id"]


def wait(prompt_id, timeout=3600, poll=3.0, log=print):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        h = _get(f"/history/{prompt_id}")
        if prompt_id in h:
            entry = h[prompt_id]
            st = entry.get("status", {})
            if st.get("status_str") == "error" or not st.get("completed", True) and st.get("status_str") == "error":
                msgs = [m for m in st.get("messages", []) if m[0] == "execution_error"]
                raise RuntimeError("ComfyUI execution error: " + json.dumps(msgs)[:4000])
            return entry
        q = _get("/queue")
        running = len(q.get("queue_running", []))
        pending = len(q.get("queue_pending", []))
        s = f"  … running={running} pending={pending} {int(time.time() - t0)}s"
        if s != last:
            log(s)
            last = s
        time.sleep(poll)
    raise TimeoutError(prompt_id)


def output_files(history_entry):
    """Every {filename, subfolder, type} the run produced, as absolute paths under ComfyUI/output."""
    found = []
    for _nid, out in history_entry.get("outputs", {}).items():
        for _k, v in out.items():
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and "filename" in item:
                        base = os.path.join(COMFY_DIR, item.get("type", "output"))
                        found.append(os.path.join(base, item.get("subfolder", ""), item["filename"]))
    return found


# ----------------------------------------------------------------------------- converter


def ui_to_api(workflow, info, keep_outputs=None, overrides=None):
    """workflow: UI JSON (nodes/links). info: /object_info. keep_outputs: node ids whose upstream
    subgraph to keep (None = everything executable). overrides: {node_id: {input: value}}."""
    nodes = {n["id"]: n for n in workflow["nodes"]}
    links = {l[0]: l for l in workflow["links"]}  # id -> [id, from, from_slot, to, to_slot, type]
    overrides = {int(k): v for k, v in (overrides or {}).items()}

    api = {}
    for nid, n in nodes.items():
        t = n["type"]
        if t in FRONTEND_ONLY or t not in info:
            continue
        spec = info[t]["input"]
        ordered = list(spec.get("required", {}).items()) + list(spec.get("optional", {}).items())
        linked = {}
        for inp in n.get("inputs", []) or []:
            if inp.get("link") is not None:
                linked[inp["name"]] = inp["link"]
        widgets = list(n.get("widgets_values") or [])
        wi = 0
        inputs = {}
        def consume(name, s, prefix=""):
            nonlocal wi
            key = f"{prefix}{name}"
            typ = s[0] if isinstance(s, (list, tuple)) else s
            cfg = s[1] if isinstance(s, (list, tuple)) and len(s) > 1 and isinstance(s[1], dict) else {}
            has_widget = isinstance(typ, list) or typ in WIDGET_TYPES or cfg.get("widgetType") is not None
            val = None
            if has_widget and wi < len(widgets):
                val = widgets[wi]
                wi += 1
                if cfg.get("control_after_generate"):
                    wi += 1
                if cfg.get("image_upload"):
                    wi += 1
            if key in linked:
                l = links[linked[key]]
                inputs[key] = [str(l[1]), l[2]]
            elif has_widget:
                inputs[key] = val
            # dynamic combo: the chosen option exposes extra inputs that follow in widgets_values;
            # in API prompts they are keyed "<parent>.<child>" (ComfyUI v3 dynamic inputs)
            if typ == "COMFY_DYNAMICCOMBO_V3" and val is not None:
                for opt in cfg.get("options", []):
                    if opt.get("key") == val:
                        sub = opt.get("inputs", {})
                        for sec in ("required", "optional"):
                            for sname, sspec in sub.get(sec, {}).items():
                                consume(sname, sspec, prefix=f"{key}.")

        for name, s in ordered:
            consume(name, s)
        if nid in overrides:
            inputs.update(overrides[nid])
        api[str(nid)] = {"class_type": t, "inputs": inputs}

    if keep_outputs:
        keep = set()
        stack = [str(k) for k in keep_outputs]
        while stack:
            k = stack.pop()
            if k in keep or k not in api:
                continue
            keep.add(k)
            for v in api[k]["inputs"].values():
                if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] in api:
                    stack.append(v[0])
        api = {k: v for k, v in api.items() if k in keep}
    # drop dangling links (to pruned nodes)
    for k, node in api.items():
        for name in list(node["inputs"]):
            v = node["inputs"][name]
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] not in api:
                del node["inputs"][name]
    return api


def load_template(name):
    import comfyui_workflow_templates_json  # noqa: F401  (installed in the ComfyUI venv only)
    base = os.path.dirname(comfyui_workflow_templates_json.__file__)
    with open(os.path.join(base, "templates", name), encoding="utf-8") as f:
        return json.load(f)


def template_path(name):
    return os.path.join(COMFY_DIR, ".venv", "Lib", "site-packages", "comfyui_workflow_templates_json", "templates", name)
