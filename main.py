from coolname import generate_slug
import numpy as np
from scipy.optimize import milp
from scipy.optimize import LinearConstraint
from scipy.optimize import Bounds

from formal_vector import FormalVector


class Ingredients(FormalVector):
    _ZERO = "Ingredients.NONE"


class Process:

    @classmethod
    def from_transfer(cls, transfer, **kwargs):
        outputs = []
        inputs = []
        for (name, component, basis) in transfer.triples():
            if component > 0:
                outputs.append((name, component, basis))
            elif component < 0:
                inputs.append((name, component, basis))
        return cls(
            Ingredients.from_triples(outputs),
            Ingredients.from_triples(inputs),
            **kwargs,
        )

    def __init__(self, outputs, inputs=None, extra_inputs=None, duration=None):
        self.outputs = outputs
        self.inputs = inputs or Ingredients.zero()
        self.extra_inputs = extra_inputs or Ingredients.zero()
        self.duration = duration

    @property
    def transfer(self):
        return self.outputs - self.inputs

    @property
    def transfer_rate(self):
        if self.duration:
            return (1 / self.duration) * self.transfer
        else:
            raise ValueError(
                "Process which has no duration has no transfer rate"
            )

    def __repr__(self):
        if self.duration:
            return f"Process[{self.transfer}]/{self.duration}"
        else:
            return f"Process[{self.transfer}]"


class GraphBuilder:

    def __init__(self):
        self.processes = {}
        self.pools = {}
        self.pool_aliases = {}

    def add_process(self, process, name=None):
        name = name or generate_slug(2)
        self.processes[name] = process
        outputs = list(process.outputs.nonzero_components)
        inputs = list(process.inputs.nonzero_components)
        return {
            "name": name,
            "outputs": outputs,
            "inputs": inputs,
            "process": process,
        }

    def _connect_process_to_process(self, kind, src_process, dest_process):
        # If they are both processes, create a new pool unless one already
        # exists.  If a pool exists for both processes, coalesce them.
        src_pools = self.find_pools_by_kind_and_process_name(
            kind,
            src_process,
        )
        if len(src_pools) > 1:
            raise ValueError(
                f"Somehow there are multiple pools for process "
                f"'{src_process}' and kind '{kind}'!"
            )
        dest_pools = self.find_pools_by_kind_and_process_name(
            kind,
            dest_process,
        )
        if len(dest_pools) > 1:
            raise ValueError(
                f"Somehow there are multiple pools for process "
                f"'{dest_process}' and kind '{kind}'!"
            )

        # No pools found for either src or dest: make a new one
        if not src_pools and not dest_pools:
            pool = self.add_pool(kind)
            self._to_pool(pool["name"], src_process)
            self._from_pool(pool["name"], dest_process)
            return pool

        # Pool found for src and not dest: connect to dest
        elif src_pools and not dest_pools:
            src_pool = src_pools[0]
            self._from_pool(src_pool["name"], dest_process)
            return src_pool

        # Pool found for dest and not src: connect to src
        elif not src_pools and dest_pools:
            dest_pool = dest_pools[0]
            self._to_pool(dest_pool["name"], src_process)
            return dest_pool

        # Both!  Coalesce the pools
        else:
            src_pool = src_pools[0]
            dest_pool = dest_pools[0]
            return self.coalesce_pools(src_pool, dest_pool)

    def connect(self, kind, src, dest):
        return self.connect_named(kind, src["name"], dest["name"])

    def connect_named(self, kind, src_process_or_pool, dest_process_or_pool):
        if src_process_or_pool in self.processes:
            src_kind = "process"
        elif src_process_or_pool in self.pools:
            src_kind = "pool"
        else:
            raise ValueError(f"No such process/pool: '{src_process_or_pool}'")

        if dest_process_or_pool in self.processes:
            dest_kind = "process"
        elif dest_process_or_pool in self.pools:
            dest_kind = "pool"
        else:
            raise ValueError(f"No such process/pool: '{dest_process_or_pool}'")

        match (src_kind, dest_kind):

            # If they are both pools, coalesce them to just the destination
            case ("pool", "pool"):
                return self.coalesce_pools(
                    src_process_or_pool,
                    dest_process_or_pool,
                )

            # If one is a pool and the other a process, connect
            case ("process", "pool"):
                return self._to_pool(
                    dest_process_or_pool,
                    src_process_or_pool,
                )

            case ("pool", "process"):
                return self._from_pool(
                    src_process_or_pool,
                    dest_process_or_pool,
                )

            case ("process", "process"):
                return self._connect_process_to_process(
                    kind,
                    src_process_or_pool,
                    dest_process_or_pool,
                )

    def coalesce_pools(self, pool1_name, pool2_name):
        pool1 = self.pools[pool1_name]
        pool2 = self.pools[pool2_name]
        if pool1["kind"] != pool2["kind"]:
            raise ValueError(
                f"Cannot coalesce pools, kinds "
                f"'{pool1['kind']}' != '{pool2['kind']}'"
            )
        kind = pool1["kind"]
        new_pool = self.add_pool(kind)
        src_pool = self.pools[pool1_name]
        dest_pool = self.pools[pool2_name]
        new_pool["inputs"] = src_pool["inputs"] + dest_pool["inputs"]
        new_pool["outputs"] = src_pool["outputs"] + dest_pool["outputs"]
        self.pool_aliases[pool1_name] = new_pool["name"]
        self.pool_aliases[pool2_name] = new_pool["name"]
        self.pools.pop(pool1_name)
        self.pools.pop(pool2_name)
        return new_pool

    def add_pool(self, kind, name=None):
        name = name or f"{kind}-{generate_slug(2)}"
        self.pools[name] = {
            "name": name,
            "kind": kind,
            "inputs": [],
            "outputs": [],
        }
        return self.pools[name]

    def _to_pool(self, pool_name, src_process_name):
        pool = self.pools[pool_name]
        src = self.processes[src_process_name]
        if pool["kind"] not in src.outputs.nonzero_components:
            raise ValueError(
                f"Cannot connect process '{src_process_name}' to pool "
                f"'{pool_name}': no '{pool['kind']}' output in {src}"
            )
        pool["inputs"].append(src_process_name)
        return pool

    def _from_pool(self, pool_name, dest_process_name):
        pool = self.pools[pool_name]
        dest = self.processes[dest_process_name]
        if pool["kind"] not in dest.inputs.nonzero_components:
            raise ValueError(
                f"Cannot connect process '{dest_process_name}' to pool "
                f"'{pool_name}': no '{pool['kind']}' input in {dest}"
            )
        pool["outputs"].append(dest_process_name)
        return pool

    def find_pools_by_kind(self, kind):
        return [pool for pool in self.pools.values() if pool["kind"] == kind]

    def find_pools_by_process_name(self, process_name):
        return [
            pool for pool in self.pools.values()
            if process_name in pool.get("inputs", [])
            or process_name in pool.get("outputs", [])
        ]

    def find_pools_by_kind_and_process_name(self, kind, process_name):
        return [
            pool for pool in self.find_pools_by_kind(kind)
            if process_name in pool.get("inputs", [])
            or process_name in pool.get("outputs", [])
        ]

    def build_matrix(self):
        matrix = []

        pool_items = list(self.pools.items())
        pools = [p for (p, _) in pool_items]
        process_items = list(self.processes.items())
        processes = [p for (p, _) in process_items]

        for (pool_name, pool) in pool_items:
            kind = pool["kind"]
            row = []

            for (process_name, process) in process_items:
                if process_name in pool["inputs"]:
                    rate = process.transfer_rate
                    row.append(rate[kind])
                elif process_name in pool["outputs"]:
                    rate = process.transfer_rate
                    row.append(rate[kind])
                else:
                    row.append(0)

            matrix.append(row)

        return {
            "matrix": matrix,
            "processes": processes,
            "pools": pools,
        }


def solve_milp(dense, keys, max_leak=0, max_repeat=180):
    c = np.ones(len(keys))
    A = np.array(dense)
    b_u = max_leak * np.ones(len(dense))
    b_l = np.zeros(len(dense))

    constraints = LinearConstraint(A, b_l, b_u)
    integrality = np.ones_like(c)
    bounds = Bounds(lb=np.ones_like(c), ub=max_repeat * np.ones_like(c))

    res = milp(
        c=c,
        constraints=constraints,
        integrality=integrality,
        bounds=bounds,
    )

    if res.success:
        return {
            "answer": dict(zip(keys, map(int, res.x))),
            "result": res,
        }
    else:
        raise ValueError("No solution found")


def best_milp_sequence(matrix, keys):
    max_leak = 10000
    max_repeat = 500
    last = None

    try:
        soln = solve_milp(
            matrix, keys, max_leak=max_leak, max_repeat=max_repeat
        )
    except ValueError:
        return
    else:
        last = soln["result"].x
        leaks = matrix @ soln["result"].x
        max_leak = 0.9 * max(leaks)
        yield (max_leak, soln["answer"])

    while True:
        try:
            soln = solve_milp(
                matrix,
                keys,
                max_leak=max_leak,
                max_repeat=max_repeat,
            )
        except ValueError:
            return
        else:
            if (soln["result"].x == last).all():
                return
            last = soln["result"].x
            leaks = matrix @ soln["result"].x
            max_leak = 0.9 * max(leaks)
            yield (max_leak, soln["answer"])
