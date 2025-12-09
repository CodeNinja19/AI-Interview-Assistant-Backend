from fastapi import APIRouter
app = APIRouter()


@app.get("/hello")
def say_hello():
    return {"message": "Hello from routes!"}