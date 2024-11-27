from cytoolz import curry
from process import Process


class Augments:

    @classmethod
    def composed(cls, augs):
        def _composed(p):
            p1 = p
            for aug in augs:
                p1 = aug(p1)
            return p1
        return _composed

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

    def __init__(self, process, augments=None):
        self._process = process
        self.augments = augments or []

    def with_augment(self, augment, new_name=None):
        new_process = self._process.copy(new_name=new_name)
        new = type(self)(new_process, augments=self.augments + [augment])
        return new

    def _augmented(self):
        p = self._process
        for augment in self.augments:
            p = augment(p)
        return p

    def __getattr__(self, attr):
        proc = self._augmented()
        return getattr(proc, attr)

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
