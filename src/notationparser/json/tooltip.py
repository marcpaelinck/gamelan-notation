from typing import cast

from src.notationparser.json.types import (
    DynamicsItem,
    ExecutionItem,
    GotoItem,
    LoopItem,
)


def toOrdinal(val: int) -> str:
    return "1st" if val == 1 else "2nd" if val == 2 else "3rd" if val == 3 else f"${val}th"


def toText(values: list[int] | None, ordinal: bool = False) -> str:
    if values:
        value_list = [f"{val}" for val in values]
        if ordinal:
            value_list = [toOrdinal(val) for val in values]
        if len(value_list) > 1:
            return ", ".join(value_list[0:-1]) + " & " + value_list[-1]
        else:
            return "".join(value_list)  # also takes care of empty array
    else:
        return ""


def executionItemTooltip(item: ExecutionItem, length: str) -> str:
    nbrOfPasses = len(item.passes) if item.passes else 0
    # maxPassNr = not item.passes ? 0 : Math.max(...item.passes)
    sortedPasses = sorted(item.passes) if item.passes else []
    # Create components for the values to return.
    instruction: str = ""
    passcondition: str = ""
    shortTooltip: str = ""
    match item.type:
        case "goto":
            item = cast(GotoItem, item)
            shortTooltip = item.targetname
            instruction = f"go to {item.targetname}"
            passcondition = "after"
        case "loop":
            item = cast(LoopItem, item)
            shortTooltip = f"{item.count}X"
            instruction = f"play {item.count}X"
            passcondition = "on"
        case "tempo" | "dynamics":
            item = cast(DynamicsItem, item)
            current = "current " if length == "long" else ""
            itemtype = f"{item.type} " if length == "long" else ""
            if item.type == "tempo":
                isGradual = item.isGradual and item.fromValue != item.toValue
                shortTooltip = f"{itemtype}{(f'{current}→' if not item.fromValue else f'{item.fromValue}→') if isGradual else ''}{int(item.toValue)} BPM"
            else:
                isGradual = item.isGradual and item.fromDynamics != item.toDynamics
                shortTooltip = f"{itemtype}{(f'{current}→' if not item.fromDynamics else f'{item.fromDynamics}→') if isGradual else ''}{item.toDynamics}"

            multipleSections = item.isGradual and item.fromSection != item.toSection
            instruction = (
                shortTooltip
                + f" beat {('1→' if not item.fromSection else f'{item.fromSection}→') if multipleSections else ''}{item.toSection}"
            )
            passcondition = "on"

    if length == "short":
        return shortTooltip

    # Compose the long tooltip version
    if not nbrOfPasses:
        return instruction
    if nbrOfPasses and not item.each:
        return f"{instruction} {passcondition} {'passes' if nbrOfPasses > 1  else  'pass'} {toText(item.passes)}"
    if nbrOfPasses and item.each:
        return f"{instruction} {passcondition} every {toText(sortedPasses, True)} {'passes' if nbrOfPasses > 1 else 'pass'}"
    return "Invalid combination: missing one or more pass numbers."
