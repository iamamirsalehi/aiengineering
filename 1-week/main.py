from chat_application import ChatApplication
from chat_config import ChatConfig
from environment_loader import EnvironmentLoader


def main() -> None:
    EnvironmentLoader().load()
    app = ChatApplication(ChatConfig.from_environment())
    app.run()


if __name__ == "__main__":
    main()
