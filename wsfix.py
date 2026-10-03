"""Make simple-websocket write whole frames.

simple-websocket 1.1.0 -- the newest release at the time of writing -- sends a
websocket frame with one call to ``socket.send()`` and ignores what it returns
(simple_websocket/ws.py, ``Base.send``). ``send()`` is allowed to write less
than it was given, and does so as soon as the kernel's send buffer is full.
The rest of the frame is dropped. Nothing raises, on either side: the browser
reads the start of the next frame where a header should be and reports
"Invalid frame header", the Socket.IO connection dies, and the game stops
updating until the page is reloaded.

It takes a real network to see. On loopback the buffer is large enough that a
multi-megabyte frame goes out in one syscall, so the whole test suite passes
and only a deployed server breaks. Measured against the real instance through
its proxy, a 33KB update arrived and a 330KB one killed the connection; with a
deliberately slow reader in front of a local server, send() wrote 2,807,808
bytes of a 7,134,709 byte frame and discarded the other four and a half
megabytes.

MUDFinder sends frames that size routinely: a token move broadcasts the whole
session, which carries every uploaded image as base64.

The fix is to finish the write. Rather than reimplement ``Base.send`` -- which
would mean copying its wsproto calls and keeping that copy in step with the
library -- this swaps the socket underneath it for one whose ``send`` is
``sendall``. The library keeps doing its own framing.

Delete this file when simple-websocket releases a version that loops, and drop
the call from mudfinder.py with it.
"""


class _WholeWriteSocket:
    """A socket whose send() writes everything, delegating all else."""

    __slots__ = ("_sock",)

    def __init__(self, sock):
        object.__setattr__(self, "_sock", sock)

    def send(self, data):
        self._sock.sendall(data)
        return len(data)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_sock"), name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, "_sock"), name, value)


def apply_whole_frame_writes():
    """Wrap simple-websocket's send so a frame is written in full.

    Returns True if the patch was applied, False if simple-websocket is not
    installed -- which is not an error. It is only used by the websocket
    transport in threading mode, and the Socket.IO server runs over polling
    without it.

    Safe to call more than once: the wrapper is marked, and a second call
    leaves the first in place.
    """
    try:
        from simple_websocket import ws as simple_websocket_ws
    except ImportError:
        return False

    base = simple_websocket_ws.Base
    original = base.send
    if getattr(original, "_mudfinder_whole_frame", False):
        return True

    def send(self, data):
        # Wrapped on first use rather than at construction: the socket is
        # attached during the handshake, by more than one code path, and this
        # is the one place every send goes through.
        if not isinstance(self.sock, _WholeWriteSocket):
            self.sock = _WholeWriteSocket(self.sock)
        return original(self, data)

    send._mudfinder_whole_frame = True
    # Kept so tests can still reach the library's own send and show what it
    # does, which is the only way a test of this can mean anything.
    send.__wrapped__ = original
    base.send = send
    return True
