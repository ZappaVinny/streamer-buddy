"""
API key storage, backed by the OS credential store.

keyring finds its backends through entry points, which PyInstaller
strips out of a frozen app — so the backend is selected explicitly by
platform here rather than left to discovery. A frozen build also needs
the matching --hidden-import (keyring.backends.Windows,
keyring.backends.macOS, keyring.backends.SecretService).

If no store is usable — a locked session, a headless box, keyring not
installed — everything degrades to the OPENAI_API_KEY environment
variable and says so, rather than failing at connect time.
"""

import os
import sys

from core import constants


SERVICE = constants.APP_SLUG
USERNAME = "openai_api_key"

_backend_error = None


def _keyring():
    """
    Returns a usable keyring module, or None. The explicit backend
    selection is what keeps this working once packaged.
    """

    global _backend_error

    try:
        import keyring
    except ImportError:
        _backend_error = "keyring is not installed"
        return None

    try:
        if sys.platform == "win32":
            from keyring.backends import Windows

            if not Windows.WinVaultKeyring.priority:
                raise RuntimeError("Windows credential store unavailable")

            keyring.set_keyring(Windows.WinVaultKeyring())

        elif sys.platform == "darwin":
            from keyring.backends import macOS

            keyring.set_keyring(macOS.Keyring())

        else:
            from keyring.backends import SecretService

            keyring.set_keyring(SecretService.Keyring())

    except Exception as error:
        _backend_error = str(error)
        return None

    _backend_error = None
    return keyring


def backend_available():
    """True if a credential store can be used on this machine."""

    return _keyring() is not None


def backend_status():
    """One-line description of where keys are being stored."""

    if _keyring() is not None:
        return "Stored in your system credential manager."

    reason = _backend_error or "unavailable"

    return (
        f"System credential manager unavailable ({reason}). "
        "Falling back to the OPENAI_API_KEY environment variable."
    )


def get_api_key():
    """
    The key to connect with. A stored key wins; otherwise the
    environment variable, which is also the only option when no
    credential store is available.
    """

    keyring = _keyring()

    if keyring is not None:
        try:
            stored = keyring.get_password(SERVICE, USERNAME)

            if stored:
                return stored
        except Exception:
            pass

    return os.environ.get("OPENAI_API_KEY", "")


def set_api_key(key):
    """
    Saves the key. Returns True if it went into the credential store,
    False if there's nowhere to put it (caller should tell the user to
    use the environment variable instead).
    """

    keyring = _keyring()

    if keyring is None:
        return False

    keyring.set_password(SERVICE, USERNAME, key)
    return True


def clear_api_key():
    keyring = _keyring()

    if keyring is None:
        return False

    try:
        keyring.delete_password(SERVICE, USERNAME)
    except Exception:
        return False

    return True


def has_stored_key():
    keyring = _keyring()

    if keyring is None:
        return False

    try:
        return bool(keyring.get_password(SERVICE, USERNAME))
    except Exception:
        return False
