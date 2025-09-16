# This file has intentional syntax errors and issues for testing

from fastapi import FastAPI
import sqlalchemy
import nonexistent_module  # This will cause an import error

app = FastAPI()

# Syntax error - missing colon
@app.get("/")
def hello_world()
    return {"message": "Hello World"}

# Another syntax error - undefined variable
@app.get("/users/{user_id}")
def get_user(user_id: int):
    user = get_user_from_db(user_id)  # This function doesn't exist
    return user

# Security issue - hardcoded credentials
DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"

# Performance issue - inefficient code
def slow_function():
    result = []
    for i in range(1000000):
        result.append(i * 2)
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
