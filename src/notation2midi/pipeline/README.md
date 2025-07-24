These modules each perform a step in the notation-to-midi process. The classe in each module is a subclass of the `Agent` class. It contains information about the expected input and the class's output, and it contains a _main method that executes the step's process. The pipeline steps are executed in sequence by the Pipeline class which is created in `src.notation2mid.main`. The sequence should be such that the expected input of each step is available from the output of previous steps in the sequence. Each step tries to complete its process even if errors are encountered. Errors are logged in order to give meaningful information on how to correct them. Errors encountered in a step will cause the entire pipeline to be aborted after the step has completed.

| **module** | **class** | **description** | **expected input** | **output**|
|------------|-----------|-----------------|--------------------|-----------|
| setting_validation | SettingsValidationAgent | Checks the configuration and settings files for inconsistencies. | `RunSettings` | `None` |
| parse_notation | NotationParserAgent | Parses the notation file into a Notation object which reflects the notation's structure. | `RunSettings` | `Notation` |
| notation_to_score | ScoreCreatorAgent | Converts the Notation object into a Score object which is more suited for further processing. | `RunSettings`, `Notation` | GENERIC* `Score` |
| apply_rules | RulesAgent |  Applies transformations such as creating separate staves from a single stave containing multiple instrument positions. | GENERIC* `Score` | BOUND* `Score` |
| create_note_patterns | NotePatternGeneratorAgent |  Creates sequences of Note objects to emulate patterns such as tremolo or norot. | BOUND* `Score` | PATTERN* `Score` |
| score_postprocessing | ScorePostprocessAgent |  Fills empty and shorthand beats + applies metadata. | PATTERN* `Score` | COMPLETE* `Score` |
| score_validation | ScoreValidationAgent |  Validates the score and performs corrections if required. | COMPLETE* `Score` | `None` |
| create_execution | ExecutionCreatorAgent |  Creates a score Execution: the flow (gongan sequence), tempi and dynamics. | COMPLETE* `Score` | `Execution` |
| score_to_midi | MidiGeneratorAgent |  Generates MIDI output. | `RunSettings`, `Execution` | `PART` |
| score_to_pdf | PDFGeneratorAgent |  Generates a human-readable PDF score. | GENERIC* `Score` | `str` (PDF file name) |
| score_to_notation | ScoreToNotationAgent |  Generates a corrected and standardized input file. | GENERIC* `Score` | `None` |
| export_to_midiplayer | MidiPlayerUpdatePartAgent, MidiPlayerUpdatePdfAgent |  Updates the JSON settings file of the Front End application. | `RunSettings`, `Part`, `str` (PDF file name) | `None` |

|*||
|-|-|
| GENERIC `Score` |  `Score` object containing GenericNote objects. These are notes that have not yet been converted to the corresponding notes of specific instrument positions. (see BOUND `Score`) |
| BOUND `Score` |  GENERIC `Score` object containing (bound) Note objects which are linked to a specific instrument position. E.g. generic DENG1 (deng with octave 1) translates to bound DENG0 for reyong position 1, to DENG1 for reyong position 2 and to DENG2 for reyong position 4. |
| PATTERN `Score` |  BOUND `Score` object where shorthand notation for patterns such as tremolo and norot have been elaborated to individual Note objects. |
| COMPLETE `Score` |  PATTERN `Score` object in which all instruments occur in each beat (which includes 'empty' measures for instruments that have no notation for that beat), and in which all metadata has been applied. |