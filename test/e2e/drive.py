"""Drives real key events into fcitx5 over its D-Bus frontend and checks what
the client would end up with. Mirrors a real client: keys fcitx does not accept
are typed by the client itself."""
import os, sys, time
import dbus, dbus.mainloop.glib
from gi.repository import GLib

IM = os.environ.get('MULGA_IM', 'mulga')

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SessionBus()
ctx = GLib.MainContext.default()

def pump():
    for _ in range(20):
        while ctx.iteration(False):
            pass
        time.sleep(0.005)

obj = None
for _ in range(200):
    try:
        obj = bus.get_object('org.fcitx.Fcitx5', '/org/freedesktop/portal/inputmethod')
        obj.Introspect(dbus_interface='org.freedesktop.DBus.Introspectable')
        break
    except dbus.DBusException:
        time.sleep(0.05)
if obj is None:
    print("fcitx5 never showed up on the bus"); sys.exit(2)

im = dbus.Interface(obj, 'org.fcitx.Fcitx.InputMethod1')
path, _uuid = im.CreateInputContext([('program', 'mulga-test')])
ic = dbus.Interface(bus.get_object('org.fcitx.Fcitx5', path),
                    'org.fcitx.Fcitx.InputContext1')

commits, preedits = [], []
bus.add_signal_receiver(lambda s: commits.append(str(s)),
                        signal_name='CommitString',
                        dbus_interface='org.fcitx.Fcitx.InputContext1', path=path)
bus.add_signal_receiver(lambda strs, cur: preedits.append(''.join(str(t) for t, _ in strs)),
                        signal_name='UpdateFormattedPreedit',
                        dbus_interface='org.fcitx.Fcitx.InputContext1', path=path)

PREEDIT, FORMATTED = 1 << 1, 1 << 4
print("input method: %s" % IM)
ic.SetCapability(dbus.UInt64(PREEDIT | FORMATTED))
ic.FocusIn()
pump()

SHIFT = 1

def type_text(text, end='reset'):
    """Returns (text the client ends up with, last preedit seen).

    `end` is how the typing session finishes: 'reset' is the client dropping
    its buffer, 'focusout' is the user clicking away, 'none' is still typing.
    """
    del commits[:], preedits[:]
    out = []
    for ch in text:
        sym = ord(ch) if ord(ch) < 0x100 else (0x01000000 | ord(ch))
        state = SHIFT if ch.isupper() else 0
        before = len(commits)
        handled = bool(ic.ProcessKeyEvent(dbus.UInt32(sym), dbus.UInt32(0),
                                          dbus.UInt32(state), False,
                                          dbus.UInt32(0)))
        pump()
        out.extend(commits[before:])
        if not handled:
            out.append(ch)
    tail = list(preedits)
    # A real client also receives whatever the ending flushes out.
    before = len(commits)
    if end == 'reset':
        ic.Reset()
    elif end == 'focusout':
        ic.FocusOut()
    elif end == 'invokeaction':
        # Clicking inside the preedit.
        ic.InvokeAction(dbus.UInt32(0), dbus.Int32(0))
    pump()
    out.extend(commits[before:])
    if end == 'focusout':
        ic.FocusIn()
        pump()
    return ''.join(out), (tail[-1] if tail else '')

failures = 0
def check(sent, want, end='reset', label=''):
    global failures
    got, _ = type_text(sent, end)
    ok = got == want
    print(("ok   " if ok else "FAIL ") + repr(sent) + (label and " " + label) +
          " -> " + repr(got) + ("" if ok else "   want " + repr(want)))
    if not ok:
        failures += 1

# The shared corpus, the same file the macOS layout is checked against.
corpus = os.environ.get('MULGA_CORPUS')
if not corpus:
    print("MULGA_CORPUS is not set")
    sys.exit(2)
rows = 0
with open(corpus, encoding='utf-8') as fp:
    for line in fp:
        if not line.strip() or line.startswith('#'):
            continue
        sent, want = line.rstrip('\n').split('\t')
        check(sent, want, 'focusout')
        rows += 1
print("corpus: %d rows" % rows)

# A word ending on a letter that could have started a digraph. The trailing `g`
# is still held when the typing stops, so these three say where it ends up.
check("ming ", "ming ", 'none', label='[still typing]')
check("ming", "ming", 'focusout', label='[clicked away]')
# The one place the two Linux routes differ. fcitx5-m17n's M17NEngine::reset
# commits nothing, so a client-initiated reset drops the held character; our
# addon hands it back. That is upstream behaviour and no rule in the .mim can
# change it, so it is recorded here rather than papered over.
if IM.startswith('m17n'):
    check("ming", "min", 'reset', label='[client reset: m17n drops it]')
else:
    check("ming", "ming", 'reset', label='[client reset]')
check("ming", "ming", 'invokeaction', label='[clicked in preedit]')

# A held character has to show up as preedit, not vanish.
del preedits[:]
ic.ProcessKeyEvent(dbus.UInt32(ord('o')), dbus.UInt32(0), dbus.UInt32(0), False, dbus.UInt32(0))
pump()
seen = preedits[-1] if preedits else ''
print(("ok   " if seen == 'o' else "FAIL ") + "held character shows as preedit -> " + repr(seen))
if seen != 'o':
    failures += 1
ic.Reset(); pump()

# Escape must reach the client rather than being swallowed.
ESCAPE = 0xff1b
handled = bool(ic.ProcessKeyEvent(dbus.UInt32(ESCAPE), dbus.UInt32(0), dbus.UInt32(0), False, dbus.UInt32(0)))
print(("ok   " if not handled else "FAIL ") + "Escape passes through to the client -> handled=" + str(handled))
if handled:
    failures += 1

ic.FocusOut(); pump()
print("FAILURES=%d" % failures)
sys.exit(1 if failures else 0)
