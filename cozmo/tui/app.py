from textual.app import App
from .screens.main import MainScreen
from .screens.settings import SettingsScreen
from .themes import cozmo


class CozmoApp(App):
    SCREENS = {
        "main": MainScreen,
        "settings": SettingsScreen,
    }

    def on_mount(self) -> None:
        self.register_theme(cozmo)
        self.theme = "cozmo"
        self.push_screen("main")

    def on_key(self, event):
        if event.key == "q":
            exit()


if __name__ == "__main__":
    CozmoApp().run()
