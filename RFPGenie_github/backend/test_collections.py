import pytest
from fastapi.testclient import TestClient
from RFPGenie_github.backend.main import app  # Assuming main.py is where the FastAPI app is created

client = TestClient(app)

def test_upload_document():
    # Test uploading a valid document
    with open("test_document.txt", "w") as f:
        f.write("This is a test document.")
    with open("test_document.txt", "rb") as f:
        response = client.post("/collections/upload", files={"file": f})
    assert response.status_code == 200

    # Test uploading a document with an unsupported file type
    with open("test_document.unsupported", "w") as f:
        f.write("This is a test document.")
    with open("test_document.unsupported", "rb") as f:
        response = client.post("/collections/upload", files={"file": f})
    assert response.status_code == 400

    # Test uploading a document that already exists
    with open("test_document.txt", "rb") as f:
        response = client.post("/collections/upload", files={"file": f})
    assert response.status_code == 409

def test_get_chunks():
    # Test retrieving chunks for a valid source and collection
    response = client.get("/collections/source1/collection1")
    assert response.status_code == 200

    # Test retrieving chunks for a non-existent source or collection
    response = client.get("/collections/nonexistent_source/nonexistent_collection")
    assert response.status_code == 200
    assert response.json() == []

def test_get_collection_categories():
    response = client.get("/collections/categories")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_collections_by_source():
    response = client.get("/collections")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_delete_source():
    # Test deleting a source that exists
    response = client.delete("/collections/source/source1")
    assert response.status_code == 200

    # Test deleting a source that does not exist
    response = client.delete("/collections/source/nonexistent_source")
    assert response.status_code == 200
