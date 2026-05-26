import re


def split_top_level(spec: str) -> list[str]:
    """Return raw field strings, split on *top-level* commas."""
    fields: list[str] = []
    start = 0
    depth = 0
    quote_char: str | None = None
    i = 0
    ident_re = re.compile(r"[A-Za-z_]\w*")  # cheap identifier

    while i < len(spec):
        ch = spec[i]

        # ---------- string handling ----------
        if quote_char:
            if ch == "\\":
                i += 2  # skip escaped char
                continue
            if ch == quote_char:
                quote_char = None
            i += 1
            continue

        if ch in {"'", '"'}:
            prev = spec[i - 1] if i else " "
            if (
                depth or prev.isspace() or prev in "=([{,:"
            ):  # looks like a quote
                quote_char = ch
            i += 1
            continue

        # ---------- bracket / brace / paren ----------
        if ch in "([{":
            depth += 1
            i += 1
            continue
        if ch in ")]}":
            depth = max(depth - 1, 0)
            i += 1
            continue

        # ---------- field separators ----------
        if ch == "," and depth == 0:
            j = i + 1
            while j < len(spec) and spec[j].isspace():
                j += 1
            if j >= len(spec):  # comma at end – split
                fields.append(spec[start:i].strip())
                start = i + 1
                i += 1
                continue

            id_match = ident_re.match(spec, j)
            if id_match:
                k = id_match.end()
                while k < len(spec) and spec[k].isspace():
                    k += 1
                if k >= len(spec) or spec[k] in {":", "|", ","}:
                    # confirmed: comma separates two fields
                    fields.append(spec[start:i].strip())
                    start = i + 1
                    i += 1
                    continue

        i += 1

    fields.append(spec[start:].strip())
    return [f for f in fields if f]  # prune empties


def parse_schema(spec: str) -> list[tuple[str, str, str]]:
    """Turn *spec* into a list of (name, python_type, description)."""
    result: list[tuple[str, str, str]] = []

    for field in split_top_level(spec):
        name = ""
        type_str = "str"  # default type
        description = ""

        name_part, _, desc_part = field.partition("|")
        description = desc_part.strip()
        main_part = name_part.strip()

        if ":" in main_part:
            name, type_candidate = main_part.split(":", 1)
            name = name.strip()
            type_candidate = type_candidate.strip()
            if type_candidate:
                type_str = type_candidate
        else:
            name = main_part  # keeps default type

        if name:  # skip broken pieces
            result.append((name, type_str, description))

    return result


# ------------------------------ demo ------------------------------
if __name__ == "__main__":
    SAMPLE_1 = (
        " name: str | The character's full name,"
        "race: str | The character's fantasy race,"
        "class: Literal['mage','thief'] | The character's profession,"
        "background: str | A brief backstory for the character"
    )

    SAMPLE_2 = (
        "field_with_internal_quotes: Literal['type_A', "
        '"type_B_with_\'_apostrophe"] | A literal with mixed quotes,'
        " another_field :str| A field with a description"
    )

    SAMPLE_3 = (
        "field_with_internal_quotes: Literal['type_A', "
        '"type_B_with_\'_apostrophe"] | A literal with mixed quotes,'
        " another_field | A field with a description"
    )

    SAMPLE_4 = "input, query, output"

    SAMPLE_5 = (
        "name: str | The character's full name,"
        "race: str | The character's fantasy race,"
        "class: Literal['mage','thief'] | The character's profession, which can be either mage or thief,"
        "background: str | A brief backstory for the character"
    )

    SAMPLE_6 = (
        "summary: str | A short blurb, e.g. key:value pairs that appear in logs"
    )
    # ➜ [('summary', 'str',
    #     'A short blurb, e.g. key:value pairs that appear in logs')]

    SAMPLE_7 = "path: str | The literal string 'C:\\\\Program Files\\\\My,App'"

    # ➜ [('path', 'str',
    #     "The literal string 'C:\\Program Files\\My,App'")]

    SAMPLE_8 = (
        "transform: Callable[[int, str], bool] | Function that returns True on success,"
        "retries: int | How many times to retry"
    )
    # ➜ ('transform', 'Callable[[int, str], bool]', 'Function that returns True on success')
    #    ('retries',   'int',                         'How many times to retry')

    SAMPLE_9 = (
        r"regex: str | Pattern such as r'^[A-Z\|a-z]+$',"
        "flags: int | re flags to use"
    )
    # ➜ ('regex', 'str', "Pattern such as r'^[A-Z\\|a-z]+$'")
    #    ('flags', 'int', 're flags to use')

    SAMPLE_10 = "id:int, name:str,"  # note the final comma!
    # ➜ ('id', 'int', '')
    #    ('name', 'str', '')

    SAMPLE_11 = "id:int | Primary key\nname:str | Display name\nactive:bool"
    # ➜ should not work!

    SAMPLE_12 = (
        'comment:str | The text "done | failed" goes here,'
        'status:Literal["done","failed"]'
    )
    # ➜ ('comment', 'str',    'The text "done | failed" goes here')
    #    ('status',  'Literal["done","failed"]', '')

    SAMPLE_13 = "choice: Literal['He said \\'yes\\'', 'no'] | User response"
    # ➜ ('choice', "Literal['He said \\'yes\\'', 'no']", 'User response')

    SAMPLE_14 = ""
    # ➜ []

    SAMPLE_15 = "username"
    # ➜ [('username', 'str', '')]

    SAMPLE_16 = (
        "payload: dict[str, list[dict[str, tuple[int,str]]]] "
        "| Arbitrarily complex structure"
    )
    # ➜ ('payload', 'dict[str, list[dict[str, tuple[int,str]]]]',
    #     'Arbitrarily complex structure')

    SAMPLE_17 = "münze: str | Deutsche Münzbezeichnung, engl. 'coin'"


    SAMPLE_18 = "ticket_info : str, reasoning : str, search_queries : list[str], relevant_documents: dict[str, float] | dict of pdf_ids as keys and scores as values"


    SAMPLE_19 = "title, headings: list[str], entities_and_metadata: list[dict[str, str]], type:Literal['news', 'blog', 'opinion piece', 'tweet']"
    # ➜ [('münze', 'str', "Deutsche Münzbezeichnung, engl. 'coin'")]

    for title, spec in [
        ("Sample-1", SAMPLE_1),
        ("Sample-2", SAMPLE_2),
        ("Sample-3", SAMPLE_3),
        ("Sample-4", SAMPLE_4),
        ("Sample-5", SAMPLE_5),
        ("Sample-6", SAMPLE_6),
        ("Sample-7", SAMPLE_7),
        ("Sample-8", SAMPLE_8),
        ("Sample-9", SAMPLE_9),
        ("Sample-10", SAMPLE_10),
        ("Sample-11", SAMPLE_11),
        ("Sample-12", SAMPLE_12),
        ("Sample-13", SAMPLE_13),
        ("Sample-14", SAMPLE_14),
        ("Sample-15", SAMPLE_15),
        ("Sample-16", SAMPLE_16),
        ("Sample-17", SAMPLE_17),
        ("Sample-18", SAMPLE_18),
        ("Sample-19", SAMPLE_19),
    ]:
        print(f"\n{title}")
        for row in parse_schema(spec):
            print(row)
