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
