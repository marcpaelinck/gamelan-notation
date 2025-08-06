import tkinter as tk
from enum import StrEnum, auto
from itertools import count
from tkinter import ttk

from src.settings.classes import RunType
from src.settings.settings import Settings


class ItemType(StrEnum):
    BOOL = auto()
    DROPDOWN = auto()


def update_parts(part: ttk.Combobox, var, index, mode):
    print(f"part={part.keys()} var={var} index={index} mode={mode}")
    part.delete(0, tk.END)
    part.set("")


def create_menu():

    counter = count(1)

    def add_item(itemtype: ItemType, label: str, value, values: list[str] = None, trace: callable = None):
        row = next(counter)
        if itemtype is ItemType.BOOL:
            variable = tk.BooleanVar()
            variable.set(value)
            item = ttk.Checkbutton(frame, onvalue=True, offvalue=False, variable=variable, text=label)
            item.grid(row=row, column=3, columnspan=1, padx=10, pady=10, sticky=tk.W)
            item
        elif itemtype is ItemType.DROPDOWN:
            label = tk.Label(frame, text=label)
            label.grid(row=row, column=1, columnspan=2, padx=10, pady=10, sticky=tk.W)
            selector_id = values.index(value)
            variable = tk.StringVar()
            if trace:
                variable.trace_add("write", trace)
            variable.set(values[selector_id])  # Set default value
            item = ttk.Combobox(frame, textvariable=variable, values=values)
            item.grid(row=row, column=3, columnspan=3, padx=10, pady=10, sticky=tk.W)
        return item, variable

    # Create the main window
    root = tk.Tk()
    root.title("JSON Viewer")
    root.geometry("600x400")
    run_settings = Settings.get()
    # Add a Frame for the Treeview
    frame = tk.Frame(root)
    frame.pack(fill=tk.BOTH, expand=True)

    # Create a menu bar
    menu_bar = tk.Menu(root)
    root.config(menu=menu_bar)

    # Create a menu
    file_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label="File", menu=file_menu)
    file_menu.add_command(label="Exit", command=root.quit)

    # Add items
    notations = list(run_settings.notations.keys())
    part_combo, part = add_item(
        ItemType.DROPDOWN,
        label="Part",
        value=run_settings.notation_settings.part_id,
        values=list(run_settings.notations[run_settings.notation_settings.notation_id].parts.keys()),
    )
    _, notation = add_item(
        ItemType.DROPDOWN,
        label="Notation",
        value=run_settings.notation_settings.notation_id,
        values=notations,
        trace=lambda *args: update_parts(part_combo, *args),
    )

    _, runtype = add_item(
        ItemType.DROPDOWN,
        label="Runtype",
        value=run_settings.options.notation_to_midi.runtype,
        values=[item.value for item in RunType],
    )
    _, production = add_item(
        ItemType.BOOL, label="Production", value=run_settings.options.notation_to_midi.is_production_run
    )

    _, save_pdf = add_item(
        ItemType.BOOL, label="create pdf notation", value=run_settings.options.notation_to_midi.save_pdf_notation
    )
    _, save_midifile = add_item(
        ItemType.BOOL, label="create midifile", value=run_settings.options.notation_to_midi.save_midifile
    )
    _, save_corrected = add_item(
        ItemType.BOOL,
        label="save corrected notation",
        value=run_settings.options.notation_to_midi.save_corrected_to_file,
    )
    _, detailed_val_logging = add_item(
        ItemType.BOOL,
        label="detailed validation logging",
        value=run_settings.options.notation_to_midi.detailed_validation_logging,
    )
    _, autocorrect = add_item(
        ItemType.BOOL, label="autocorrect", value=run_settings.options.notation_to_midi.autocorrect
    )

    # Run the application
    root.mainloop()
    print(notation.get())
    print(part.get())
    print(runtype.get())
    print(f"production: {production.get()}")
    print(f"save_pdf: {save_pdf.get()}")
    print(f"save_midifile: {save_midifile.get()}")
    print(f"save_corrected: {save_corrected.get()}")
    print(f"detailed_val_logging: {detailed_val_logging.get()}")
    print(f"autocorrect notation: {autocorrect.get()}")


if __name__ == "__main__":
    create_menu()
