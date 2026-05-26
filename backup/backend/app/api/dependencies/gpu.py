from fastapi import Request


def get_gpu_limit(request: Request):
    return request.app.state.gpu_limit
