from unittest.mock import MagicMock

from procedurewriter.agents.meta_analysis.stats_extractor import (
    StatisticsExtractorAgent,
    StatsExtractionInput,
)


def test_stats_extractor_happy_path():
    # Mock LLM
    mock_llm = MagicMock()
    mock_llm.provider_type = "openai" # Needed for BaseAgent init
    
    # Mock a "perfect" JSON response from LLM
    mock_response = MagicMock()
    mock_response.content = """
    {
        "outcome_found": true,
        "effect_size": 2.5,
        "effect_type": "OR",
        "ci_lower": 1.5,
        "ci_upper": 4.5,
        "sample_size": 100,
        "p_value": 0.001,
        "reported_as_text": "OR 2.5 (95% CI 1.5-4.5)"
    }
    """
    mock_response.input_tokens = 10
    mock_response.output_tokens = 10
    mock_response.total_tokens = 20
    mock_response.cost_usd = 0.001
    
    mock_llm.chat_completion.return_value = mock_response
    
    agent = StatisticsExtractorAgent(llm=mock_llm)
    
    inp = StatsExtractionInput(
        study_id="TEST01",
        title="Test Study",
        abstract="We found significant improvement.",
        outcome_of_interest="Improvement"
    )
    
    result = agent.execute(inp)
    
    # Assertions
    stats = result.output
    assert stats.effect_size == 2.5
    assert stats.effect_size_type == "OR"
    assert stats.confidence_interval_lower == 1.5
    assert stats.confidence_interval_upper == 4.5
    
    # Verify variance calculation
    # SE ~ (4.5 - 1.5) / 3.92 = 3.0 / 3.92 = 0.765306
    # Var = 0.765306^2 = 0.58569
    expected_se = (4.5 - 1.5) / 3.92
    expected_var = expected_se ** 2
    assert abs(stats.variance - expected_var) < 0.001

def test_stats_extractor_not_found():
    # Mock LLM
    mock_llm = MagicMock()
    mock_llm.provider_type = "openai"
    
    mock_response = MagicMock()
    mock_response.content = '{"outcome_found": false}'
    mock_response.input_tokens = 10
    mock_response.output_tokens = 10
    mock_response.total_tokens = 20
    mock_response.cost_usd = 0.001
    
    mock_llm.chat_completion.return_value = mock_response
    
    agent = StatisticsExtractorAgent(llm=mock_llm)
    
    inp = StatsExtractionInput(
        study_id="TEST02",
        title="Irrelevant Study",
        abstract="Nothing related here.",
        outcome_of_interest="Death"
    )
    
    result = agent.execute(inp)
    
    # Should return placeholder high variance
    stats = result.output
    assert stats.variance >= 10.0
    assert stats.weight == 0.0