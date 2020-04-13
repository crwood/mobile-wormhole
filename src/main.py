import os.path

from kivy.app import App
from kivy.core.window import Window
from kivy.factory import Factory
from kivy.properties import BooleanProperty, StringProperty
from kivy.support import install_twisted_reactor
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import NoTransition, Screen, ScreenManager
from plyer import filechooser

install_twisted_reactor()

from magic import Wormhole
from cross import ensure_storage_perms, get_downloads_dir


class ErrorPopup(Popup):
    error = StringProperty('Something bad happened!')

    @staticmethod
    def show(error):
        """
        Show a hopefully user-friendly error message.
        """
        Factory.ErrorPopup(error=str(error)).open()


class HomeScreen(Screen):
    pass


class SendScreen(Screen):
    code = StringProperty('')
    path = StringProperty('')
    send_button_text = StringProperty('send')
    send_button_disabled = BooleanProperty(False)

    def on_enter(self):
        """
        Called when the user enters this screen.
        """
        self.code = ''
        self.path = ''

        self.send_button_disabled = True
        self.send_button_text = 'waiting for code'

        self.wormhole = Wormhole()

        def update_code(code):
            self.code = code
            self.send_button_disabled = False
            self.send_button_text = 'send'

        deferred = self.wormhole.generate_code()
        deferred.addCallbacks(update_code, ErrorPopup.show)

    def open_file_chooser(self):
        """
        Called when the user releases the choose file button.
        """
        def update_path(selection):
            if selection:
                try:
                    path = os.path.normpath(selection[0])
                    assert os.path.exists(path) and os.path.isfile(path)
                except:
                    ErrorPopup.show(
                        'there is something wrong about the file you chose'
                    )
                    self.path = ''
                else:
                    self.path = path
            else:
                self.path = ''

        def show_error():
            ErrorPopup.show(
                'you cannot send a file if the app cannot access it'
            )

        @ensure_storage_perms(show_error)
        def open_file_chooser():
            filechooser.open_file(
                title='choose a file to send',
                on_selection=update_path
            )

        open_file_chooser()

    def send(self):
        """
        Called when the user releases the send button.
        """
        if not self.path:
            return ErrorPopup.show('please choose a file')
        else:
            file_path = self.path

        def exchange_keys():
            self.send_button_disabled = True
            self.send_button_text = 'exchanging keys'
            deferred = self.wormhole.exchange_keys()
            deferred.addCallbacks(send_file, ErrorPopup.show)

        def send_file(*args):
            self.send_button_disabled = True
            self.send_button_text = 'sending file'
            deferred = self.wormhole.send_file(file_path)
            deferred.addCallbacks(show_done, ErrorPopup.show)

        def show_done(*args):
            self.send_button_disabled = True
            self.send_button_text = 'done'

        exchange_keys()

    def on_leave(self):
        """
        Called when the user leaves this screen.
        """
        self.wormhole.close()


class ReceiveScreen(Screen):
    connect_button_disabled = BooleanProperty(False)
    connect_button_text = StringProperty('connect')

    accept_button_disabled = BooleanProperty(True)
    accept_button_text = StringProperty('waiting for offer')

    file_name = StringProperty('-')
    file_size = StringProperty('-')

    def on_enter(self):
        """
        Called when the user enters this screen.
        """
        self.connect_button_disabled = False
        self.connect_button_text = 'connect'

        self.accept_button_disabled = True
        self.accept_button_text = 'waiting for offer'

        self.file_name = '-'
        self.file_size = '-'

    def open_wormhole(self):
        """
        Called when the user releases the connect button.
        """
        code = self.ids.code_input.text.strip()
        if not code:
            return ErrorPopup.show('please enter a code')

        def connect():
            self.connect_button_disabled = True
            self.connect_button_text = 'connecting'

            self.wormhole = Wormhole()

            deferred = self.wormhole.connect(code)
            deferred.addCallbacks(exchange_keys, ErrorPopup.show)

        def exchange_keys(*args):
            self.connect_button_disabled = True
            self.connect_button_text = 'exchanging keys'

            deferred = self.wormhole.exchange_keys()
            deferred.addCallbacks(await_offer, ErrorPopup.show)

        def await_offer(*args):
            self.connect_button_disabled = True
            self.connect_button_text = 'connected'

            deferred = self.wormhole.await_offer()
            deferred.addCallbacks(show_offer, ErrorPopup.show)

        def show_offer(offer):
            self.file_name = str(offer['filename'])
            self.file_size = str(offer['filesize'])

            self.accept_button_disabled = False
            self.accept_button_text = 'accept'

        connect()

    def accept_offer(self):
        """
        Called when the user releases the accept button.
        """
        path = os.path.join(get_downloads_dir(), self.file_name)

        def accept_offer():
            self.accept_button_disabled = True
            self.accept_button_text = 'receiving'

            deferred = self.wormhole.accept_offer(path)
            deferred.addCallbacks(show_done, ErrorPopup.show)

        def show_done(hex_digest):
            self.accept_button_disabled = True
            self.accept_button_text = 'done'

        accept_offer()

    def on_leave(self):
        """
        Called when the user leaves this screen.
        """
        try:
            self.wormhole.close()
        except AttributeError:
            pass


class WormholeApp(App):

    def build(self):
        """
        Init and return the main widget, in our case the screen manager.

        Attach the on_keyboard event listener to the Window object.
        """
        self.screen_manager = ScreenManager(transition=NoTransition())

        for screen_cls in [HomeScreen, SendScreen, ReceiveScreen]:
            self.screen_manager.add_widget(screen_cls())

        Window.bind(on_keyboard=self.on_keyboard)

        return self.screen_manager

    def on_keyboard(self, window, key, *args):
        """
        Called when the keyboard is used for input.

        Handle the back button on Android (this equates to the escape key). If
        the user is not on the home screen, navigate them there; otherwise let
        them exit the app (the default behaviour).
        """
        if key == 27:
            if self.screen_manager.current != 'home_screen':
                self.screen_manager.current = 'home_screen'
                return True

        return False


if __name__ == '__main__':
    WormholeApp().run()
