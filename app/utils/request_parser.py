from fastapi import Request


async def parse_request(request: Request) -> dict:
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        return await request.json()

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        return dict(form)

    return {}
