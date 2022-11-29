import uvicorn
import fire
from utility import settings


def start_server(host="0.0.0.0", port=8000 if settings.PORT is None else settings.PORT):
    uvicorn.run("main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    fire.Fire(start_server)
