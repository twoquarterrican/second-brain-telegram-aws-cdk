from openai import OpenAI
import os

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def embed_text(text: str) -> list[float]:
    """Generate a vector embedding for text using OpenAI."""
    resp = client.embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding
