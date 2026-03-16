from cytoolz import curry


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
        if p.duration is None:
            return p
        return p.copy(duration=mul * p.duration)

    @classmethod
    @curry
    def mul_speed(cls, denom, p):
        if p.duration is None:
            return p
        return p.copy(duration=p.duration / denom)

    @classmethod
    @curry
    def mul_inputs(cls, mul, p):
        return p.copy(inputs=mul * p.inputs)

    @classmethod
    @curry
    def mul_outputs(cls, mul, p):
        return p.copy(outputs=mul * p.outputs)

    @classmethod
    @curry
    def add_input(cls, more_in, p):
        return p.copy(inputs=p.inputs + more_in)

    @classmethod
    @curry
    def add_input_rate(cls, more_in, p):
        return p.copy(inputs=p.inputs + p.duration * more_in)

    @classmethod
    @curry
    def add_output(cls, more_out, p):
        return p.copy(outputs=p.outputs + more_out)

    @classmethod
    @curry
    def add_output_rate(cls, more_out, p):
        return p.copy(outputs=p.outputs + p.duration * more_out)

    @classmethod
    @curry
    def increase_energy_pct(cls, kind, pct, p):
        if kind in p.inputs.nonzero_components:
            return p.copy(inputs=p.inputs + (pct / 100) * p.inputs.project(kind))
        return p
