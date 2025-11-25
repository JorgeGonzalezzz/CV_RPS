from src.states import StateFactory, StateID
from config.config_loader import ConfigLoader


class TerryRPS(object):
    def __init__(self, config_path="config/configs/config.json"):
        # Terry owns the configuration
        self.config = ConfigLoader(config_path)
        self.config.load()

        if not self.config.is_loaded():
            raise RuntimeError("Configuration could not be loaded")

        # Initial state
        self.state_id = StateID.INITIALIZE
        self.state = StateFactory(self.state_id)
        self.state.on_enter()

    def handle_input(self, input_data):
        """
        Send input to current state and perform the state transition.
        `input_data` could already be pre-processed using self.config.
        """
        next_id = self.state.next_state(input_data)

        if next_id != self.state_id:
            self.state.on_exit()
            self.state_id = next_id
            self.state = StateFactory(self.state_id)
            self.state.on_enter()

    def get_state_name(self):
        return str(self.state)
