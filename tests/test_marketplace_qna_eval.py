from __future__ import annotations


def test_marketplace_qna_sources_have_expected_shape():
    from tests.rag_eval.marketplace_qna_fixture_builder import build_fixture_bundle

    bundle = build_fixture_bundle()

    assert len(bundle.sources) == 18
    assert sum(source.language == "zh-CN" for source in bundle.sources) == 9
    assert sum(source.language == "en" for source in bundle.sources) == 9
    assert sum(len(source.questions) for source in bundle.sources) == 114
    assert {len(source.questions) for source in bundle.sources if source.order == 4} == {16}
