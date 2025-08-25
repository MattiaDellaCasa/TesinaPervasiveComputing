from fastapi import FastAPI, Request, HTTPException
import base64, json

app = FastAPI()

@app.get("/")
def root():
    return {"status": "ok", "service": "mining-server"}

@app.post("/pubsub/push")
async def pubsub_push(request: Request):
    envelope = await request.json()
    if not envelope or "message" not in envelope:
        raise HTTPException(status_code=400, detail="no message")
    msg = envelope["message"]
    data_b64 = msg.get("data")
    if not data_b64:
        raise HTTPException(status_code=400, detail="no data")
    decoded = base64.b64decode(data_b64).decode("utf-8")
    try:
        payload = json.loads(decoded)
    except:
        payload = {"raw": decoded}
    print("📩 Messaggio ricevuto:", payload)
    return {"status": "ack"}