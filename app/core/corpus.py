from __future__ import annotations

import random

ES = """el la los las un una unos unas de del que y o pero porque cuando donde como
para por con sin sobre entre hasta desde según durante casa tiempo persona año día
manera parte vida trabajo mundo mano lugar caso momento forma punto gobierno país
agua palabra hombre mujer ciudad número grupo problema historia programa noche
verdad ejemplo pueblo campo espacio proyecto sistema empresa nivel razón fuerza
grande pequeño nuevo viejo bueno malo primero último mismo alto bajo largo joven
hacer tener poder decir ver dar saber querer llegar pasar deber poner parecer quedar
creer hablar llevar dejar seguir encontrar llamar venir pensar salir volver tomar""".split()

EN = """the of and to in a is that it for on with as by at from or an be this which
have not are but was were has had they you all can will one time year people way day
man thing woman life child world school state family student group country problem
hand part place case week company system program question work government number
night point home water room mother area money story fact month right study book eye
job word business issue side kind head house service friend father power hour game""".split()


def _words(lang: str) -> list[str]:
    if lang == "es":
        return ES
    if lang == "en":
        return EN
    return ES + EN


def make_words(rng: random.Random, n: int, lang: str = "mixed") -> str:
    """A run of `n` random words, lightly punctuated so it reads like prose."""
    pool = _words(lang)
    n = max(1, n)
    out: list[str] = []
    sentence_len = rng.randint(6, 14)
    since_break = 0
    for i in range(n):
        word = rng.choice(pool)
        if since_break == 0:
            word = word.capitalize()
        out.append(word)
        since_break += 1
        if since_break >= sentence_len and i < n - 1:
            out[-1] += rng.choices([".", ".", ".", ",", ";", ":"], k=1)[0]
            if out[-1].endswith((".", ";", ":")):
                since_break = 0
                sentence_len = rng.randint(6, 14)
    if not out[-1].endswith("."):
        out[-1] += "."
    return " ".join(out)


def make_chars(rng: random.Random, n: int, alphabet: str) -> str:
    if not alphabet:
        raise ValueError("alphabet is empty")
    return "".join(rng.choice(alphabet) for _ in range(max(1, n)))


def make_word(rng: random.Random, lang: str = "mixed") -> str:
    return rng.choice(_words(lang))
