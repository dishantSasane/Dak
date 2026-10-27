from app.rag.embeddings import DIMENSIONS, _encode


def test_encode_uses_small_onnx_batches_and_returns_valid_vectors(monkeypatch) -> None:
    class FakeModel:
        def embed(self, texts: list[str], *, batch_size: int, parallel: int):
            assert texts == ["policy clause", "customer question"]
            assert batch_size == 1
            assert parallel == 1
            for _ in texts:
                yield [3.0, 4.0] + [0.0] * (DIMENSIONS - 2)

    monkeypatch.setattr("app.rag.embeddings._model", lambda: FakeModel())

    result = _encode(["policy clause", "customer question"])

    assert len(result) == 2
    assert all(len(vector) == DIMENSIONS for vector in result)
    assert result[0][:2] == [0.6, 0.8]
