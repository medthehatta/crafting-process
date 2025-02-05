from fastapi import FastAPI
import uvicorn

from ops import CraftingContext


cc = CraftingContext()
app = FastAPI()


@app.get("/")
async def index():
    return {"ok": True}


@app.post("/recipes")
async def post_recipes(recipe):
    pass


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9090)
