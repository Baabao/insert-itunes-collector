import functools
import hashlib
import random
import time

try:
    _random = random.SystemRandom()
    using_sysrandom = True
except NotImplementedError:
    import warnings

    warnings.warn(
        "A secure pseudo-random number generator is not available "
        "on your system. Falling back to Mersenne Twister."
    )
    using_sysrandom = False


def get_random_string(
    length=12,
    allowed_chars="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
):
    if not using_sysrandom:
        secret_key = "=_epdw8ef%4k*vtlhq*#k4c=hn!1&h(=7_k)tp7+p(&56eg6q!"
        # hank 2to3 note: here, encode() no necessary modify for 2to3 upgrading
        _random.seed(
            hashlib.sha256(
                ("%s%s%s" % (_random.getstate(), time.time(), secret_key)).encode(
                    "utf-8"
                )
            ).digest()
        )
    return "".join(_random.choice(allowed_chars) for i in range(length))
