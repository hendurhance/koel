from __future__ import annotations

from koel.db.repositories import CROSS_RATE_BATCH_SIZE, _chunks


class TestBatchSize:
    def test_batch_stays_under_postgres_param_cap(self):
        # 6 params per row today. Leave generous headroom for future columns.
        cols_per_row = 6
        assert CROSS_RATE_BATCH_SIZE * cols_per_row <= 65_000


class TestChunks:
    def test_exact_multiple(self):
        rows = [{"i": i} for i in range(30_000)]
        batches = list(_chunks(rows, 10_000))
        assert len(batches) == 3
        assert all(len(b) == 10_000 for b in batches)

    def test_partial_last_batch(self):
        rows = [{"i": i} for i in range(23_716)]
        batches = list(_chunks(rows, 10_000))
        assert [len(b) for b in batches] == [10_000, 10_000, 3_716]
        # Ensure no row dropped or duplicated.
        flat = [r for b in batches for r in b]
        assert flat == rows

    def test_smaller_than_batch_fits_single_chunk(self):
        rows = [{"i": i} for i in range(12)]
        batches = list(_chunks(rows, 10_000))
        assert len(batches) == 1
        assert batches[0] == rows

    def test_empty_input_yields_nothing(self):
        assert list(_chunks([], 10_000)) == []
