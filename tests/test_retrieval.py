"""第5回 宿題（実装）: 検索結果に前後のページを付ける処理のテスト。APIは呼ばない。"""

from app.retrieval import add_neighbor_pages


def _page(document_id, n):
    return {
        "page_id": f"{document_id}-p{n:03d}",
        "document_id": document_id,
        "page": n,
        "content": f"本文{n}",
    }


PAGES = [_page("lec01-main", n) for n in (1, 2, 3, 4, 5)] + [
    _page("lec02-main", n) for n in (1, 2)
]


def _hit(document_id, n, distance=0.1):
    return {**_page(document_id, n), "distance": distance}


def test_window_zero_returns_hits_unchanged():
    hits = [_hit("lec01-main", 3)]
    assert add_neighbor_pages(hits, 0, PAGES) == hits


def test_adds_previous_and_next_page_after_each_hit():
    results = add_neighbor_pages([_hit("lec01-main", 3)], 1, PAGES)
    assert [r["page_id"] for r in results] == [
        "lec01-main-p003",
        "lec01-main-p002",
        "lec01-main-p004",
    ]
    assert results[1]["neighbor_of"] == "lec01-main-p003"
    assert "distance" not in results[1]
    assert results[1]["content"] == "本文2"


def test_does_not_duplicate_pages_or_cross_documents():
    hits = [_hit("lec01-main", 5), _hit("lec01-main", 4, 0.2), _hit("lec02-main", 1)]
    results = add_neighbor_pages(hits, 1, PAGES)
    ids = [r["page_id"] for r in results]
    assert len(ids) == len(set(ids))
    # p005 の次（lec02-main-p001）は別資料なので隣として付けない。p004 は検索結果なので重複させない
    assert ids == [
        "lec01-main-p005",
        "lec01-main-p004",
        "lec01-main-p003",
        "lec02-main-p001",
        "lec02-main-p002",
    ]
    assert "neighbor_of" not in results[1]


def test_unknown_page_is_kept_without_neighbors():
    hit = {"page_id": "unknown", "content": "本文"}
    assert add_neighbor_pages([hit], 1, PAGES) == [hit]
