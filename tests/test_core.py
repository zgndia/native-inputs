import time
import unittest

from native_keyboard_inputs import InputController, InvalidInputError


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.controller = InputController("fake")
        self.backend = self.controller.backend

    def tearDown(self):
        self.controller.close()

    def test_aliases_and_case_normalization(self):
        self.controller.keyboard.tap("ESC")
        self.assertEqual(self.backend.events[:2], [("key_down", "escape"), ("key_up", "escape")])

    def test_numpad_alias(self):
        self.controller.keyboard.press("np2")
        self.controller.keyboard.release("numpad_2")
        self.assertEqual(self.backend.events[:2], [("key_down", "numpad_2"), ("key_up", "numpad_2")])

    def test_custom_alias(self):
        self.controller.keyboard.register_alias("jump", "space")
        self.controller.keyboard.tap("jump")
        self.assertEqual(self.backend.events[:2], [("key_down", "space"), ("key_up", "space")])

    def test_unknown_key_raises(self):
        with self.assertRaises(InvalidInputError):
            self.controller.keyboard.press("not_a_real_key")

    def test_direct_press_is_idempotent(self):
        self.controller.keyboard.press("a")
        self.controller.keyboard.press("a")
        self.controller.keyboard.release("a")
        self.assertEqual(self.backend.events, [("key_down", "a"), ("key_up", "a")])

    def test_overlapping_holds_do_not_release_early(self):
        first = self.controller.keyboard.hold("shift", 0.08, blocking=False)
        second = self.controller.keyboard.hold("shift", 0.20, blocking=False)
        time.sleep(0.12)
        self.assertIn("left_shift", self.backend.held_keys)
        second.cancel()
        first.wait()
        second.wait()
        self.assertNotIn("left_shift", self.backend.held_keys)
        self.assertEqual(
            [event for event in self.backend.events if event[0] in ("key_down", "key_up")],
            [("key_down", "left_shift"), ("key_up", "left_shift")],
        )

    def test_mouse_alias_and_movement(self):
        self.controller.mouse.click("lmb")
        self.controller.mouse.move_relative(4, -2)
        self.controller.mouse.scroll(vertical=2, horizontal=-1)
        self.assertEqual(self.backend.events[0:2], [("mouse_down", "left"), ("mouse_up", "left")])
        self.assertIn(("move_relative", 4, -2), self.backend.events)
        self.assertIn(("scroll", -1, 2), self.backend.events)

    def test_async_type_sends_text_characters(self):
        import asyncio
        asyncio.run(self.controller.keyboard.type("Hello ;)" , interval=0))
        self.assertEqual(
            [event for event in self.backend.events if event[0] == "type_text"],
            [("type_text", character) for character in "Hello ;)"] ,
        )

    def test_async_type_normalizes_newlines(self):
        import asyncio
        asyncio.run(self.controller.keyboard.type("a\r\nb", interval=0))
        self.assertEqual(
            [event[1] for event in self.backend.events if event[0] == "type_text"],
            ["a", "\n", "b"],
        )

    def test_type_rejects_non_string(self):
        import asyncio
        with self.assertRaises(TypeError):
            asyncio.run(self.controller.keyboard.type(123, interval=0))

    def test_hotkey_releases_in_reverse_order(self):
        self.controller.keyboard.hotkey("ctrl", "c", interval=0)
        self.assertEqual(self.backend.events, [
            ("key_down", "left_ctrl"), ("key_down", "c"),
            ("key_up", "c"), ("key_up", "left_ctrl"),
        ])

    def test_context_manager_releases_after_exception(self):
        with self.assertRaises(RuntimeError):
            with self.controller.keyboard.held("space"):
                raise RuntimeError("test")
        self.assertNotIn("space", self.backend.held_keys)

    def test_release_all_cancels_timed_hold(self):
        task = self.controller.keyboard.hold("space", 5, blocking=False)
        self.controller.release_all()
        self.assertTrue(task.wait(0.2))
        self.assertFalse(self.backend.held_keys)


if __name__ == "__main__":
    unittest.main()
