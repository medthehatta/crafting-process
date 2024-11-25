import json
import re

from utils import curry

from graph import GraphBuilder
from process import Ingredients
from process import Process
from augment import Augments


def parse_process(s):
    stripped_lines = (line.strip() for line in s.splitlines())
    lines = [
        line for line in stripped_lines if line and not line.startswith("#")
    ]

    if len(lines) == 0:
        raise ValueError(f"No substantive lines in (next line):\n{s}")
    elif len(lines) == 1:
        return _parse_process_header(lines[0])
    elif len(lines) == 2:
        return {
            **_parse_process_header(lines[0]),
            "inputs": lines[1],
        }
    else:
        raise ValueError(f"Found too many lines in (next line):\n{s}")


def _parse_process_header(s):
    # 5 ingredient + 2 other ingredient | attribute1=foo bar | attribute2=3
    # 5 ingredient + 2 other ingredient | attribute1=foo bar attribute2=3
    # 5 ingredient + 2 other ingredient
    segments = re.split(r"\s*\|\s*", s)

    # Only the first segment mark `|` is important.  Others are for
    # legibility only.  We ignore the other segment marks by
    # re-joining the subsequent tokens.
    if len(segments) > 1:
        (product_raw, attributes_raw) = (segments[0], " ".join(segments[1:]))
    else:
        (product_raw, attributes_raw) = (segments[0], "")

    # Parse the attributes.
    #
    # They will generally be a space-free identifier followed
    # by an equals, then arbitrary data until another attr= or
    # end of line.
    # foo1=some data foo2=other foo3=8
    #
    # There is syntactic sugar though, and we expand that
    # first.
    attributes_raw = re.sub(r"^\s*(.+):", r"process=\1", attributes_raw)
    keys = [
        (m.group(1), m.span())
        for m in re.finditer(r"([A-Za-z_][A-Za-z_0-0]*)=", attributes_raw)
    ]
    end_pad = [(None, (None, None))]

    attributes = {}
    for (k, (_, start)), (_, (end, _)) in zip(keys, keys[1:] + end_pad):
        # Try to interpret each attribute as a valid JSON primitive; otherwise
        # take the literal string
        try:
            attributes[k] = json.loads(attributes_raw[start:end].strip())
        except json.decoder.JSONDecodeError:
            attributes[k] = attributes_raw[start:end].strip()

    return {
        "outputs": product_raw,
        **attributes,
    }


class Predicates:

    @classmethod
    @curry
    def and_(cls, pred1, pred2, process):
        return pred1(process) and pred2(process)

    @classmethod
    @curry
    def or_(cls, pred1, pred2, process):
        return pred1(process) or pred2(process)

    @classmethod
    @curry
    def not_(cls, predicate, process):
        return not predicate(process)

    @classmethod
    @curry
    def outputs_part(cls, part, process):
        return part in process.outputs.nonzero_components

    @classmethod
    @curry
    def requires_part(cls, part, process):
        return part in process.inputs.nonzero_components


def specs_from_lines(lines):
    found = False
    buf = ""

    for line in lines:

        if not line.strip() or line.strip().startswith("#"):
            if found:
                yield parse_process(buf)
                buf = ""
                found = False

        else:
            buf += line + "\n"
            found = True

    if buf:
        yield parse_process(buf)


def process_from_spec_dict(spec):
    inputs = (
        Ingredients.parse(spec["inputs"]) if spec.get("inputs")
        else Ingredients.zero()
    )
    outputs = (
        Ingredients.parse(spec["outputs"]) if spec.get("outputs")
        else Ingredients.zero()
    )

    kwargs = {
        k: v for (k, v) in spec.items()
        if k not in ["inputs", "outputs"]
    }

    return Process(outputs=outputs, inputs=inputs, **kwargs)


def parse_processes(lines):
    return [process_from_spec_dict(spec) for spec in specs_from_lines(lines)]


def augment_specs_from_lines(lines):
    arg_parsers = {
        "mul_duration": float,
        "mul_speed": float,
        "mul_inputs": float,
        "mul_outputs": float,
        "add_input": Ingredients.parse,
        "add_output": Ingredients.parse,
    }

    records = []

    record_in_progress = {}

    for line in lines:
        if (not line.strip() or line.startswith("---")) and record_in_progress:
            records.append(record_in_progress.copy())
            record_in_progress = {}

        elif not line.strip() or line.startswith("---"):
            continue

        elif not record_in_progress:
            name = line.strip()
            record_in_progress = {"name": name}

        elif "name" in record_in_progress:
            (func_name, rest) = re.split(r"\s+", line.strip(), 1)
            arg_parser = arg_parsers.get(func_name)
            record_in_progress["augments"] = (
                record_in_progress.get("augments", [])
                + [(func_name, arg_parser(rest))]
            )

    return records


def augments_from_records(records):
    result = {
        record["name"]: Augments.composed(
            [
                getattr(Augments, func_name)(input_arg)
                for (func_name, input_arg) in record["augments"]
            ]
        )
        for record in records
    }

    return result


def parse_augments(lines):
    return augments_from_records(augment_specs_from_lines(lines))
