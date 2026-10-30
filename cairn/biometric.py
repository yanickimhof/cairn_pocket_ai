"""Touch ID on macOS, as a way to ask the system "is the owner here?" before the data key is read from the keychain.

Everything is optional: without the system library, without a sensor, or on another system, available() is False and the password
is the only way in. Nothing here can be reached while Cairn is locked except confirm(), which only asks the system."""
import base64
import sys
import threading

SERVICE = "Cairn data lock"
ACCOUNT = "data key"


def _context():
    if sys.platform != "darwin":
        return None
    try:
        from LocalAuthentication import LAContext, LAPolicyDeviceOwnerAuthenticationWithBiometrics
    except ImportError:
        return None
    context = LAContext.alloc().init()
    ok, _error = context.canEvaluatePolicy_error_(LAPolicyDeviceOwnerAuthenticationWithBiometrics, None)
    return (context, LAPolicyDeviceOwnerAuthenticationWithBiometrics) if ok else None


def status():
    """Why Touch ID can or cannot be offered: ok, no_system (not a Mac), no_package (the macOS component is not installed),
    no_keyring, or no_sensor (no Touch ID on this computer, or none enrolled)."""
    if sys.platform != "darwin":
        return "no_system"
    try:
        import keyring  # noqa: F401
    except ImportError:
        return "no_keyring"
    try:
        import LocalAuthentication  # noqa: F401
    except ImportError:
        return "no_package"
    return "ok" if _context() is not None else "no_sensor"


def available():
    return status() == "ok"


def confirm(reason):
    """Ask the system for a fingerprint. True only when it was given."""
    found = _context()
    if found is None:
        return False
    context, policy = found
    outcome, done = {"ok": False}, threading.Event()

    def reply(success, _error):
        outcome["ok"] = bool(success)
        done.set()

    context.evaluatePolicy_localizedReason_reply_(policy, reason, reply)
    done.wait(60)
    return outcome["ok"]


def remember(dek):
    try:
        import keyring

        keyring.set_password(SERVICE, ACCOUNT, base64.b64encode(dek).decode("ascii"))
        return True
    except Exception:  # noqa: BLE001 (no keychain: the password stays the way in)
        return False


def recall():
    try:
        import keyring

        value = keyring.get_password(SERVICE, ACCOUNT)
        return base64.b64decode(value.encode("ascii")) if value else None
    except Exception:  # noqa: BLE001
        return None


def forget():
    try:
        import keyring

        keyring.delete_password(SERVICE, ACCOUNT)
    except Exception:  # noqa: BLE001
        pass
