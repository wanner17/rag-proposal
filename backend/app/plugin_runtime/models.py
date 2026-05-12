from pydantic import BaseModel, Field, field_validator


class BackendRouteConfig(BaseModel):
    prefix: str
    module: str

    @field_validator("prefix")
    @classmethod
    def validate_prefix(cls, value: str) -> str:
        if not value.startswith("/api/"):
            raise ValueError("backend route prefix must start with /api/")
        if value.endswith("/"):
            raise ValueError("backend route prefix must not end with /")
        return value

    @field_validator("module")
    @classmethod
    def validate_module(cls, value: str) -> str:
        if not value.startswith("app.plugins."):
            raise ValueError("backend plugin module must be under app.plugins")
        if "/" in value or "\\" in value or ".." in value:
            raise ValueError("backend plugin module must be a dotted repo-local import")
        return value


class FrontendRouteConfig(BaseModel):
    path: str
    component: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("frontend route path must start with /")
        if value != "/" and value.endswith("/"):
            raise ValueError("frontend route path must not end with /")
        return value


class RouteConfig(BaseModel):
    backend: BackendRouteConfig | None = None
    frontend: FrontendRouteConfig | None = None


class NavigationConfig(BaseModel):
    label: str
    order: int = 100


class RetrievalConfig(BaseModel):
    top_k: int = Field(default=20, ge=1, le=50)
    top_n: int = Field(default=5, ge=1, le=10)


class OutputConfig(BaseModel):
    sections: list[str] = []


class PluginConfig(BaseModel):
    id: str
    name: str
    version: str
    enabled: bool = True
    routes: RouteConfig = Field(default_factory=RouteConfig)
    navigation: NavigationConfig | None = None
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    outputs: OutputConfig = Field(default_factory=OutputConfig)
