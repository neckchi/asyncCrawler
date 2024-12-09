from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from uuid import UUID


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
    locationType: str = Field(default=..., max_length=1, title="Either POL(L) or POD(D)",
                              example='L', pattern=r"[A-Z]{1}")  # in order to pull out None/other invalid locationCode
    relatedID: UUID = Field(default=...)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8')
    mft_server: SecretStr
    mft_user: SecretStr
    mft_password: SecretStr
    cosu_service_url: str
    cosu_route_url: str
    cosu_ports_url: str
    cosu_unloc_url: str
    eglv_service_url: str
    eglv_location_url: str
    eglv_route_url: str
    ymlu_service_url: str
    ymlu_route_url: str
    hdmu_service_url: str
    hdmu_route_url: str
    cmdu_service_url: str
    cmdu_api_key: SecretStr
    cmdu_route_url: str
    hlcu_service_url: str
    hlcu_client_id: SecretStr
    hlcu_client_secret: SecretStr
    hlcu_token: SecretStr
    smlm_service_url: str
    smlm_route_url: str
    smlm_host: str
    smlm_origin: str
    smlm_referer: str
