from src.terryrps import TerryRPS

if __name__ == "__main__":
    terry = TerryRPS()
    print("Current state:", terry.get_state_name())
    terry.handle_input(True)
    print("Current state:", terry.state)
    terry.handle_input(True)
    print("Current state:", terry.state)

    print(terry.config.color_ranges_hsv["red"])
