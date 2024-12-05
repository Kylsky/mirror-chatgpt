from dataclasses import dataclass, field


@dataclass
class Share:
    user_name: str = field(default="")

    access_token: str = field(default="")

    gpt_4_limit: int = -1
    gpt_4o_limit: int = -1
    gpt_4o_mini_limit: int = -1
    gpt_o1_mini_limit: int = -1
    gpto1_preview_limit: int = -1

    expire_at: int = -1

    gpt_limit_enable: bool = False

    temp_conversation_enable: bool = False
