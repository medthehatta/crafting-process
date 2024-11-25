from cytoolz import curry
from process import Process


class Augments:

    @classmethod
    @curry
    def composed(cls, augs, p):
        p1 = p
        for aug in augs:
            p1 = aug(p1)
        return p

    @classmethod
    @curry
    def mul_duration(cls, mul, p):
        return Process(
            p.outputs,
            inputs=p.inputs,
            duration=mul * p.duration,
            process=p.process,
        )

    @classmethod
    @curry
    def mul_speed(cls, denom, p):
        return Process(
            p.outputs,
            inputs=p.inputs,
            duration=p.duration / denom,
            process=p.process,
        )

    @classmethod
    @curry
    def mul_inputs(cls, mul, p):
        return Process(
            p.outputs,
            inputs=mul * p.inputs,
            duration=p.duration,
            process=p.process,
        )

    @classmethod
    @curry
    def mul_outputs(cls, mul, p):
        return Process(
            mul * p.outputs,
            inputs=p.inputs,
            duration=p.duration,
            process=p.process,
        )

    @classmethod
    @curry
    def add_input(cls, more_in, p):
        return Process(
            p.outputs,
            inputs=p.inputs + more_in,
            duration=p.duration,
            process=p.process,
        )

    @classmethod
    @curry
    def add_output(cls, more_out, p):
        return Process(
            p.outputs + more_out,
            inputs=p.inputs,
            duration=p.duration,
            process=p.process,
        )


class AugmentedProcess:

    def _init__(self, process, augments=None, tags=None):
        self.process = process
        self.augments = augments or []
        self.tags = tags or {}

    def _augmented(self):
        p = self.process
        for augment in self.augments:
            p = augment(p)
        return p

    @property
    def transfer(self):
        proc = self._augmented()
        return proc.outputs - proc.inputs

    @property
    def transfer_rate(self):
        proc = self._augmented()
        if proc.duration:
            return (1 / proc.duration) * proc.transfer
        else:
            raise ValueError(
                "Process which has no duration has no transfer rate"
            )

    def to_dict(self):
        proc = self._augmented()
        return {
            "outputs": [(n, c) for (n, c, _) in proc.outputs.triples()],
            "inputs": [(n, c) for (n, c, _) in proc.inputs.triples()],
            "duration": proc.duration,
            "transfer_summary": str(self.transfer),
        }

    def __repr__(self):
        proc = self._augmented()
        if proc.process:
            process = f"Aug_{proc.process}"
        else:
            process = "Aug_Process"

        if proc.duration:
            return f"{process}[{proc.transfer}]/{proc.duration}"
        else:
            return f"{process}[{proc.transfer}]"
