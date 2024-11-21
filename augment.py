from cytoolz import curry
from process import Process


class Augments:

    @classmethod
    def compose_all(cls, augments):

        def _composed(p):
            acc = p

            for augment in augments:
                acc = augment(acc)

            return acc

        return _composed

    @classmethod
    def compose(cls, *augments):
        return cls.compose_all(augments)

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
