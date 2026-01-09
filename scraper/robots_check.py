from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser


@dataclass
class RobotsCheck:
    parser: Optional[RobotFileParser]
    user_agent: str

    def can_fetch(self, url: str) -> bool:
        if not self.parser:
            return True
        return self.parser.can_fetch(self.user_agent, url)


def load_robots_parser(base_url: str, user_agent: str) -> RobotsCheck:
    robots_url = urljoin(base_url, "/robots.txt")
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
    except Exception:
        parser = None
    return RobotsCheck(parser=parser, user_agent=user_agent)
