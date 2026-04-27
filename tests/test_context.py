from warhammer.context import EngagementContext


def test_engagement_context_marks_advanced_attackers_as_moved():
    context = EngagementContext(attacker_advanced=True)

    assert context.attacker_moved is True
    assert context.attacker_advanced is True


def test_engagement_context_discards_non_positive_target_model_count():
    zero = EngagementContext(target_model_count=0)
    negative = EngagementContext(target_model_count=-3)
    positive = EngagementContext(target_model_count=5)

    assert zero.target_model_count is None
    assert negative.target_model_count is None
    assert positive.target_model_count == 5
