"""
Minimal in-process SIMULATION of the parts of the GenVM SDK that MilestoneJudge
uses. It exists only so the contract's own Python logic (validation, state
machine, leader/validator functions, prompt construction) can be exercised
without a GenLayer node.

IMPORTANT: this is a simulation, not GenLayer. `run_nondet_default` below runs
the leader function on one fake node and the validator function on the other
fake nodes, then counts votes. It proves that MilestoneJudge's leader/validator
code behaves as designed under scripted web/LLM responses. It does NOT prove
anything about real validators, real LLMs, real web fetching or the real
consensus protocol - those must be checked in GenLayer Studio / on a network
(see docs/USAGE.md).
"""

import json
import sys
import types


class UserError(Exception):
    def __init__(self, message=""):
        super().__init__(message)
        self.message = message


class VMError(Exception):
    pass


class Return:
    def __init__(self, calldata):
        self.calldata = calldata


class Address:
    def __init__(self, value):
        if isinstance(value, Address):
            value = value.as_hex
        value = str(value).lower()
        if not (value.startswith("0x") and len(value) == 42):
            raise ValueError(f"bad address {value}")
        self._hex = value

    @property
    def as_hex(self):
        return self._hex

    def __eq__(self, other):
        return isinstance(other, Address) and other._hex == self._hex

    def __hash__(self):
        return hash(self._hex)

    def __repr__(self):
        return f"Address({self._hex})"


class u32(int):
    pass


class u64(int):
    pass


class u256(int):
    pass


class i32(int):
    pass


bigint = int


class _Arr(list):
    pass


class _Map(dict):
    pass


class DynArray:
    def __class_getitem__(cls, item):
        return _Arr


class TreeMap:
    def __class_getitem__(cls, item):
        return _Map


def allow_storage(cls):
    return cls


def _zero(tp):
    if tp is _Arr:
        return _Arr()
    if tp is _Map:
        return _Map()
    if tp is bool:
        return False
    if tp is str:
        return ""
    if isinstance(tp, type) and issubclass(tp, int):
        return tp(0)
    return None


class Contract:
    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls)
        for name, tp in getattr(cls, "__annotations__", {}).items():
            object.__setattr__(obj, name, _zero(tp))
        return obj


# --------------------------- simulated network ----------------------------- #

class Node:
    """One simulated node: its own view of the web and its own 'LLM'."""

    def __init__(self, web=None, llm=None):
        self.web = web if web is not None else {}
        self.llm = llm
        self.prompts = []
        self.web_calls = []

    def fetch(self, url):
        self.web_calls.append(url)
        handler = self.web
        spec = handler(url) if callable(handler) else handler.get(url)
        if spec is None:
            raise RuntimeError(f"connection failed for {url}")
        status, body = spec
        return types.SimpleNamespace(status_code=status, body=body.encode("utf-8"))

    def prompt(self, text, response_format=None):
        self.prompts.append(text)
        out = self.llm(text)
        if response_format == "json" and isinstance(out, str):
            out = json.loads(out)  # real runtime guarantees parsable JSON
        return out


class _Sim:
    nodes = []
    current = None


sim = _Sim()


def run_nondet_unsafe(leader_fn, validator_fn):
    nodes = sim.nodes
    assert len(nodes) >= 1, "configure sim.nodes first"
    prev = sim.current
    try:
        sim.current = nodes[0]
        try:
            leader_res = Return(leader_fn())
        except UserError as e:
            leader_res = e
        except Exception as e:  # noqa: BLE001
            leader_res = VMError(str(e))
        votes = [True]  # the leader implicitly backs its own result
        for node in nodes[1:]:
            sim.current = node
            try:
                votes.append(bool(validator_fn(leader_res)))
            except Exception:  # noqa: BLE001  (unhandled validator error == Disagree)
                votes.append(False)
    finally:
        sim.current = prev
    if sum(votes) * 2 > len(nodes):
        if isinstance(leader_res, Return):
            return json.loads(json.dumps(leader_res.calldata))  # calldata round trip
        raise leader_res
    raise UserError("[CONSENSUS] no majority: transaction undetermined, state unchanged")


def _web_request(url, method="GET", **kwargs):
    return sim.current.fetch(url)


def _exec_prompt(prompt, response_format=None, **kwargs):
    return sim.current.prompt(prompt, response_format)


gl = types.SimpleNamespace(
    contract=types.SimpleNamespace(Contract=Contract),
    storage=types.SimpleNamespace(allow=allow_storage, DynArray=DynArray, TreeMap=TreeMap),
    public=types.SimpleNamespace(view=lambda f: f, write=types.SimpleNamespace()),
    vm=types.SimpleNamespace(
        UserError=UserError, VMError=VMError, Return=Return,
        run_nondet_default=run_nondet_unsafe,  # v0.3 name; run_nondet_unsafe deliberately absent
    ),
    nondet=types.SimpleNamespace(
        web=types.SimpleNamespace(request=_web_request),
        exec_prompt=_exec_prompt,
    ),
    message=types.SimpleNamespace(sender_address=None),
)


class _Write:
    """gl.public.write must be usable as a plain decorator."""

    def __call__(self, f):
        return f


gl.public.write = _Write()


def install():
    """Mimic the GenVM v0.3 layout: `import genlayer as gl` and
    `from genlayer.types import *` (the star-import no longer binds `gl`)."""
    root = types.ModuleType("genlayer")
    for name, value in vars(gl).items():
        setattr(root, name, value)
    types_mod = types.ModuleType("genlayer.types")
    for name in ("Address", "u32", "u64", "u256", "i32", "bigint"):
        setattr(types_mod, name, globals()[name])
    root.types = types_mod
    storage_mod = types.ModuleType("genlayer.storage")
    storage_mod.TreeMap = TreeMap
    storage_mod.DynArray = DynArray
    root.storage = types.SimpleNamespace(allow=allow_storage, DynArray=DynArray, TreeMap=TreeMap)
    sys.modules["genlayer"] = root
    sys.modules["genlayer.types"] = types_mod
    sys.modules["genlayer.storage"] = storage_mod
    return root
