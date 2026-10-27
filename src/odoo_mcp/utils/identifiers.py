from __future__ import annotations


def identifier_words(value: str, fallback: str = "owl_component") -> list[str]:
    words: list[str] = []
    current = ""
    for char in value:
        if char.isalnum():
            current += char.lower()
        elif current:
            words.append(current)
            current = ""
    if current:
        words.append(current)
    return words or [fallback]


def snake_identifier(value: str, fallback: str = "owl_component") -> str:
    return "_".join(identifier_words(value, fallback))


def pascal_identifier(value: str, fallback: str = "OwlComponent") -> str:
    words = identifier_words(value, fallback.lower())
    return "".join(word[:1].upper() + word[1:] for word in words)


def camel_identifier(value: str, fallback: str = "service") -> str:
    pascal = pascal_identifier(value, fallback.title())
    return pascal[:1].lower() + pascal[1:]
