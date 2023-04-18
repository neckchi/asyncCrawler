from pydantic import BaseModel, BaseSettings, Field, SecretStr


class Services(BaseModel):
    changeMode: str | None = None
    allianceID: str | None = None
    alliancePoolID: str | None = None
    tradeID: str | None = None
    oiServiceID: str = Field(default=...)
    carrierID: str = Field(default=...)
    serviceID: str = Field(default=...)
    service: str = Field(default=...)
    direction: str = Field(default=...)
    frequency: str = Field(default=...)
    startDay: str = Field(default=...)
    # portCode: str | None = Field(max_length=5, title="SeaPort", example='DEHAM', regex=r"[A-Z]{2}[A-Z0-9]{3}")
    portCode: str | None = Field(title="SeaPort", example='DEHAM')
    order: int = Field(default=..., ge=0)
    tt: int | str = Field(default=..., ge=0)
    locationType: str = Field(default=..., max_length=1, title="Either POL(L) or POD(D)", example='L',
                              regex=r"[A-Z]{1}")
    relatedID: int = Field(default=...)


class Settings(BaseSettings):
    mft_server: SecretStr
    mft_user: SecretStr
    mft_password: SecretStr

    class Config:
        env_file = ".env"