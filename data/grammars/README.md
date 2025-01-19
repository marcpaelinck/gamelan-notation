# Grammar files

These grammar files are used by the Tatsu module to parse the notation files. A parser model can be pre-compiled and saved as a pickled object in this folder. After each modification of one of the grammar (.ebnf) files, this pickle file needs to be renewed. See `create_notation_grammar_model` in module `notation_parser_tatsu.py`.