import time

try:
    import pyttsx3
except Exception:
    pyttsx3 = None


class Voice:
    """
    Non-blocking TTS using pyttsx3 in the MAIN thread.
    - call say(text) to enqueue speech
    - call tick() frequently (e.g. every frame)
    - call wait_done(game_tick_fn) to wait until the queue finishes
    """
    def __init__(self, enabled: bool = True, rate: int = 170):
        self.enabled = enabled and (pyttsx3 is not None)
        self._queue = []
        self._speaking = False
        self._engine = None

        if not self.enabled:
            return

        try:
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", rate)

            def on_end(name, completed):
                self._speaking = False

            self._engine.connect("finished-utterance", on_end)
            self._engine.startLoop(False)
        except Exception:
            self.enabled = False
            self._engine = None

    def say(self, text: str):
        print(f"[VOICE] {text}")
        if not self.enabled:
            return
        self._queue.append(text)

    def tick(self):
        if not self.enabled or self._engine is None:
            return
        try:
            if (not self._speaking) and self._queue:
                text = self._queue.pop(0)
                self._speaking = True
                self._engine.say(text)
            self._engine.iterate()
        except Exception:
            self.enabled = False
            self._engine = None

    def is_busy(self) -> bool:
        if not self.enabled:
            return False
        return self._speaking or bool(self._queue)

    def wait_done(self, game_tick_fn=None, timeout_s: float = 3.0):
        """
        Wait until all queued speech finishes.
        `game_tick_fn` should be a callable that keeps your UI responsive
        (e.g. calling _read_and_render once).
        """
        t0 = time.time()
        while self.is_busy():
            if game_tick_fn is not None:
                ok = game_tick_fn()
                if ok is False:
                    return False
            else:
                # minimal keep-alive
                self.tick()
                time.sleep(0.01)

            if (time.time() - t0) > timeout_s:
                # don't hang forever
                return True
        return True

    def close(self):
        if not self.enabled or self._engine is None:
            return
        try:
            self._engine.endLoop()
        except Exception:
            pass
