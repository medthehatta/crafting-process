import json
import re

from .utils import curry

from .graph import GraphBuilder
from .process import describe_process
from .process import Ingredients
from .process import Process
from .augment import Augments


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


def _is_augment_line(stripped):
    """Return True if every token on the line starts with '@'."""
    tokens = stripped.split()
    return bool(tokens) and all(t.startswith('@') for t in tokens)


def _parse_annotation_block(s):
    """Extract and remove a [key=val | key2=val2] block from s.

    Returns (cleaned_s, annotations_dict).  If no block is found, returns
    (s, {}).  Values are JSON-decoded (int/float/string); bare true/false are
    kept as strings to avoid bool footguns.
    """
    m = re.search(r'\[([^\]]*)\]', s)
    if not m:
        return s, {}

    interior = m.group(1)
    cleaned = s[:m.start()] + s[m.end():]

    annotations = {}
    for pair in re.split(r'\s*\|\s*', interior):
        pair = pair.strip()
        if not pair:
            continue
        if '=' not in pair:
            raise ValueError(f"Annotation '{pair}' is not in key=value format")
        key, _, raw_val = pair.partition('=')
        key = key.strip()
        raw_val = raw_val.strip()
        # Reject bare JSON booleans; keep them as strings
        if raw_val in ('true', 'false', 'null'):
            annotations[key] = raw_val
        else:
            try:
                annotations[key] = json.loads(raw_val)
            except json.decoder.JSONDecodeError:
                annotations[key] = raw_val

    return cleaned, annotations


def _parse_process_header(s):
    # Extract annotation block first, before any | splitting, so that
    # pipes inside [...] don't collide with the outer segment separator.
    s, annotations = _parse_annotation_block(s)

    # It can be valid to provide the entire recipe in the "header" by
    # separating inputs and outputs with " = ".
    #
    # However if an = is at the end of the line, it's assumed the next line is
    # the part "after" the equals anyway, i.e. the inputs, so we strip out
    # terminal =.
    cleaned = re.sub(r"=\s*$", "", s)

    # Then, split off anything after an intermediate " = " and call that the
    # inputs.
    equals = re.split(r"\s+=\s+", cleaned)

    match equals:
        case [h]:
            pre_equals = h
            inputs = None
        case [h, inp]:
            pre_equals = h
            inputs = inp
        case _:
            raise ValueError(f"Cannot parse: '{s}'")

    # 5 ingredient + 2 other ingredient | attribute1=foo bar | attribute2=3 = 2 thing + foo
    # 5 ingredient + 2 other ingredient | attribute1=foo bar | attribute2=3
    # 5 ingredient + 2 other ingredient | attribute1=foo bar attribute2=3
    # 5 ingredient + 2 other ingredient
    segments = re.split(r"\s*[|]\s*", pre_equals)

    # Only the first segment mark `|` is important.  Others are for
    # legibility only.  We ignore the other segment marks by
    # re-joining the subsequent tokens.
    if len(segments) > 1:
        (product_raw, attributes_raw) = (segments[0].strip(), " ".join(segments[1:]))
    else:
        (product_raw, attributes_raw) = (segments[0].strip(), "")

    # Extract inline @augment tokens before any other attribute parsing so they
    # don't bleed into the process name or other key=value pairs.
    inline_augment_tokens = re.findall(r'@[A-Za-z_][A-Za-z_0-9]*', attributes_raw)
    attributes_raw = re.sub(r'@[A-Za-z_][A-Za-z_0-9]*\s*', '', attributes_raw).strip()
    inline_augments = [t.lstrip('@') for t in inline_augment_tokens]

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
        for m in re.finditer(r"([A-Za-z_][A-Za-z_0-9]*)=", attributes_raw)
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

    input_dict = {"inputs": inputs} if inputs else {}

    return {
        "outputs": product_raw,
        **input_dict,
        **attributes,
        "annotations": annotations,
        "inline_augments": inline_augments,
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
    def any_(cls, predicates, process):
        return any(predicate(process) for predicate in predicates)

    @classmethod
    @curry
    def all_(cls, predicates, process):
        return all(predicate(process) for predicate in predicates)

    @classmethod
    @curry
    def outputs_any_of(cls, kinds):
        return cls.any_([cls.outputs_part(k) for k in kinds])

    @classmethod
    @curry
    def uses_any_of_processes(cls, process_names):
        return cls.any_([cls.uses_process(k) for k in process_names])

    @classmethod
    @curry
    def outputs_part(cls, part, x):
        raise NotImplementedError("Override me")

    @classmethod
    @curry
    def requires_part(cls, part, x):
        raise NotImplementedError("Override me")

    @classmethod
    @curry
    def uses_process(cls, process_name, x):
        raise NotImplementedError("Override me")


class ProcessPredicates(Predicates):

    @classmethod
    @curry
    def outputs_part(cls, part, process):
        return part in process.outputs.nonzero_components

    @classmethod
    @curry
    def requires_part(cls, part, process):
        return part in process.inputs.nonzero_components

    @classmethod
    @curry
    def uses_process(cls, process_name, process):
        return process.process == process_name

    @classmethod
    @curry
    def annotation_matches(cls, key, pred, process):
        v = process.annotations.get(key)
        return v is not None and pred(v)


class GraphPredicates(Predicates):

    @classmethod
    @curry
    def outputs_part(cls, part, graph):
        return graph.outputs_kind(part)

    @classmethod
    @curry
    def requires_part(cls, part, graph):
        return graph.requires_kind(part)

    @classmethod
    @curry
    def uses_process(cls, process_name, graph):
        return process_name in graph.processes


def specs_from_lines(lines):
    found = False
    buf = ""
    augment_block = []      # list[list[str]] — one inner list per @-line
    in_augment_section = True  # True while collecting consecutive @-lines

    for line in lines:
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            if found:
                spec = parse_process(buf)
                spec["augment_block"] = list(augment_block)
                yield spec
                buf = ""
                found = False

        elif _is_augment_line(stripped):
            if not in_augment_section:
                # New @-block after recipes: reset
                augment_block = []
                in_augment_section = True
            augment_block.append([t.lstrip('@') for t in stripped.split()])

        else:
            in_augment_section = False
            buf += line + "\n"
            found = True

    if buf:
        spec = parse_process(buf)
        spec["augment_block"] = list(augment_block)
        yield spec


def process_from_spec_dict(spec):
    inputs = (
        Ingredients.parse(spec["inputs"]) if spec.get("inputs")
        else Ingredients.zero()
    )
    outputs = (
        Ingredients.parse(spec["outputs"]) if spec.get("outputs")
        else Ingredients.zero()
    )

    annotations = spec.get("annotations", {})
    _excluded = {"inputs", "outputs", "annotations", "augment_block", "inline_augments"}
    kwargs = {k: v for (k, v) in spec.items() if k not in _excluded}

    return Process(outputs=outputs, inputs=inputs, annotations=annotations, **kwargs)


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
        "add_input_rate": Ingredients.parse,
        "add_output_rate": Ingredients.parse,
        "increase_energy_pct": float,
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
    result = {}
    for record in records:
        to_compose = [
            getattr(Augments, func_name)(input_arg)
            for (func_name, input_arg) in record["augments"]
        ]
        result[record["name"]] = Augments.composed(to_compose)

    return result


def parse_augments(lines):
    records = augment_specs_from_lines(lines)
    return augments_from_records(records)


class ProcessLibrary:

    def __init__(self, recipes=None):
        self.recipes = recipes or {}
        self.names = set(recipes.keys()) if recipes else set()
        self._augments = {}

    #
    # Add augments
    #

    def register_augment(self, name, fn):
        self._augments[name] = fn

    #
    # Add recipes
    #

    def add_from_text(self, text):
        for spec in specs_from_lines(text.splitlines()):
            inline_augments = spec.get("inline_augments", [])
            # augment_seqs is a list of lists; each inner list is one variant's augment names
            if inline_augments:
                augment_seqs = [inline_augments]
            else:
                augment_seqs = spec.get("augment_block", [])

            base = process_from_spec_dict(spec)
            base_name = self.mkname(base)
            self.recipes[base_name] = base

            for aug_names in augment_seqs:
                fns = [self._augments[n] for n in aug_names]
                augmented = Augments.composed(fns)(base)
                # Always create a fresh copy with the updated applied_augments so we
                # never mutate the base process (matters when the augment fn returns p
                # unchanged, e.g. mul_speed on a batch-only process with no duration).
                augmented = augmented.copy(
                    applied_augments=base.applied_augments + aug_names
                )
                suffix = " ".join(f"@{n}" for n in aug_names)
                aug_name = self._unique_name(f"{base_name} {suffix}")
                self.recipes[aug_name] = augmented

        return self

    def _unique_name(self, candidate):
        if candidate not in self.names:
            self.names.add(candidate)
            return candidate
        disambiguator = 2
        while f"{candidate} {disambiguator}" in self.names:
            disambiguator += 1
        name = f"{candidate} {disambiguator}"
        self.names.add(name)
        return name

    def mkname(self, recipe):
        candidate = describe_process(recipe.outputs.nonzero_components, recipe.process)
        return self._unique_name(candidate)

    #
    # Lookup
    #

    def filter(self, pred):
        return [(n, r) for (n, r) in self.recipes.items() if pred(r)]

    def producing(self, resource):
        return self.filter(ProcessPredicates.outputs_part(resource))

    def consuming(self, resource):
        return self.filter(ProcessPredicates.requires_part(resource))

    def using(self, process):
        return self.filter(ProcessPredicates.uses_process(process))

    def with_augment_filter(self, skip_augments=None, only_augments=None):
        skip_set = set(skip_augments or [])
        only_set = set(only_augments) if only_augments is not None else None

        def _keep(proc):
            aug_set = set(proc.applied_augments)
            if skip_set and aug_set & skip_set:
                return False
            if only_set is not None and not aug_set.issubset(only_set):
                return False
            return True

        filtered = {n: p for (n, p) in self.recipes.items() if _keep(p)}
        result = ProcessLibrary(recipes=filtered)
        result._augments = self._augments
        return result

