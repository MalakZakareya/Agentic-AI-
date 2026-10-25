from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.v1 import upload
from api.v1 import analysis
from api.v1 import design_analysis
from api.v1 import draft
from api.v1 import legal_research

from core.config import settings


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.DESCRIPTION,
        version=settings.VERSION,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Upload endpoint
    application.include_router(
        upload.router,
        prefix="/api/v1/upload",
        tags=["Upload"],
    )

    # Document analysis endpoint
    application.include_router(
        analysis.router
    )

    # Design analysis endpoint
    application.include_router(
        design_analysis.router
    )

    # Draft creation endpoint
    application.include_router(
        draft.router
    )

    # Legal research endpoint
    application.include_router(
        legal_research.router
    )


    # Compatibility fallback for environments where
    # FastAPI include_router does not register routes.
    from fastapi.routing import APIRoute

    registered_paths = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in application.routes
        if isinstance(route, APIRoute)
    }

    for source_router in (
        upload.router,
        analysis.router,
        design_analysis.router,
        draft.router,
        legal_research.router,
    ):
        for route in source_router.routes:
            if not isinstance(route, APIRoute):
                continue

            route_key = (
                route.path,
                tuple(sorted(route.methods or [])),
            )

            if route_key not in registered_paths:
                application.router.routes.append(route)
                registered_paths.add(route_key)

    return application


app = create_application()


templates = Jinja2Templates(
    directory="templates"
)


app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)


@app.get(
    "/",
    include_in_schema=False,
)
def homepage(
    request: Request
):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )