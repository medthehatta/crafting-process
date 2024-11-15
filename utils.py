from cytoolz import curry


def only(seq):
    lst = list(seq)

    if len(lst) == 0:
        raise ValueError("List is empty")

    elif len(lst) > 1:
        raise ValueError(
            f"Found {len(lst)} values instead of unique value in: {lst}"
        )

    else:
        return lst[0]
