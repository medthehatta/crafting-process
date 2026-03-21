import re

from formal_vector import FormalVector


class Ingredients(FormalVector):
    _ZERO = "Ingredients.NONE"

    @classmethod
    def parse(cls, s, **kwargs):
        # Collapse runs of spaces and tabs to a single space so that ingredient
        # names like "iron  ore" and "iron ore" are treated identically.
        # Newlines are intentionally left alone — they are meaningful at the
        # recipe level but should never appear inside an ingredient string.
        normalized = re.sub(r"[ \t]+", " ", s).strip()
        return super().parse(normalized, **kwargs)


def describe_process(output_names, process=None):
    base = " + ".join(output_names)
    return base + f" via {process}" if process else base


class Process:

    @classmethod
    def from_transfer(cls, transfer, **kwargs):
        outputs = []
        inputs = []
        for name, component, basis in transfer.triples():
            if component > 0:
                outputs.append((name, component, basis))
            elif component < 0:
                inputs.append((name, -component, basis))
        return cls(
            Ingredients.from_triples(outputs),
            Ingredients.from_triples(inputs),
            **kwargs,
        )

    def __init__(
        self,
        outputs,
        inputs=None,
        duration=None,
        process=None,
        annotations=None,
        applied_augments=None,
    ):
        # This is just metadata saying what kind of process it is
        self.process = process
        self.outputs = outputs
        self.inputs = inputs or Ingredients.zero()
        self.duration = duration
        self.annotations = annotations if annotations is not None else {}
        self.applied_augments = list(applied_augments) if applied_augments else []

    def copy(self, new_name=None, **overrides):
        return type(self)(
            outputs=overrides.get("outputs", self.outputs),
            inputs=overrides.get("inputs", self.inputs),
            duration=overrides.get("duration", self.duration),
            process=new_name or overrides.get("process", self.process),
            annotations={**self.annotations, **overrides.get("annotations", {})},
            applied_augments=overrides.get(
                "applied_augments", list(self.applied_augments)
            ),
        )

    @property
    def transfer(self):
        return self.outputs - self.inputs

    @property
    def transfer_rate(self):
        if self.duration:
            return (1 / self.duration) * self.transfer
        else:
            raise ValueError("Process which has no duration has no transfer rate")

    def transfer_quantity(self, batch=False):
        if batch:
            return self.transfer
        else:
            return self.transfer_rate

    def describe(self):
        return describe_process(self.outputs.nonzero_components, self.process)

    def to_dict(self):
        return {
            "outputs": [(n, c) for (n, c, _) in self.outputs.triples()],
            "inputs": [(n, c) for (n, c, _) in self.inputs.triples()],
            "duration": self.duration,
            "transfer_summary": str(self.transfer),
            "process": self.process,
            "annotations": self.annotations,
            "applied_augments": self.applied_augments,
        }

    def __repr__(self):
        if self.process:
            process = self.process
        else:
            process = "Process"

        if self.duration:
            return f"{process}[{self.transfer}]/{self.duration}"
        else:
            return f"{process}[{self.transfer}]"
