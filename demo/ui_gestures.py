"""Reusable pointer gestures shared by mouse and touch UI controls."""


class DragReleaseGesture:
    """Turn a press into either a short click or a thresholded drag."""

    def _init_drag_release(self) -> None:
        self._touch_uid = None
        self._touch_start = None
        self._dragging = False
        self._drag_blocked = False

    def on_touch_down(self, touch):
        if self._on_click and self.collide_point(*touch.pos):
            self._touch_uid = touch.uid
            self._touch_start = tuple(touch.pos)
            self._dragging = self._drag_blocked = False
            touch.grab(self)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.uid != self._touch_uid:
            return super().on_touch_move(touch)
        sx, sy = self._touch_start or touch.pos
        moved = ((touch.x - sx) ** 2 + (touch.y - sy) ** 2) ** 0.5
        threshold = max(12 * getattr(self, 'scale', 1.0), 8)
        if not self._dragging and not self._drag_blocked and moved >= threshold:
            accepted = bool(self._on_drag_start and
                            self._on_drag_start(self.code, tuple(touch.pos)))
            self._dragging, self._drag_blocked = accepted, not accepted
        if self._dragging and self._on_drag_move:
            self._on_drag_move(self.code, tuple(touch.pos))
        return True

    def on_touch_up(self, touch):
        if touch.uid != self._touch_uid:
            return super().on_touch_up(touch)
        dragging, blocked = self._dragging, self._drag_blocked
        if touch.grab_current is self:
            touch.ungrab(self)
        self._init_drag_release()
        if dragging and self._on_drag_end:
            self._on_drag_end(self.code, tuple(touch.pos))
        elif not dragging and not blocked and self.collide_point(*touch.pos):
            self._on_click(self.code)
        return True
