from unittest.mock import MagicMock

import pytest

from procedurewriter.agents.meta_analysis.orchestrator import (
    MetaAnalysisOrchestrator,
    OrchestratorInput,
)
from procedurewriter.agents.meta_analysis.screener_agent import PICOQuery


@pytest.mark.asyncio
async def test_full_meta_analysis_flow_with_extraction():
    # Mock LLM
    mock_llm = MagicMock()
    mock_llm.provider_type = "openai"
    
    # Mock responses
    pico_resp = MagicMock()
    pico_resp.content = '{"population": "P", "intervention": "I", "comparison": "C", "outcome": "O", "confidence": 0.95}'
    pico_resp.input_tokens = 10
    pico_resp.output_tokens = 10
    
    screen_resp = MagicMock()
    screen_resp.content = '{"decision": "Include", "reason": "Relevant", "confidence": 0.9}'
    screen_resp.input_tokens = 10
    screen_resp.output_tokens = 10
    
    bias_resp = MagicMock()
    bias_resp.content = """{
        "randomization": "low", "deviations": "low", "missing_data": "low", 
        "measurement": "low", "selection": "low"
    }"""
    bias_resp.input_tokens = 10
    bias_resp.output_tokens = 10
    
    stats_resp = MagicMock()
    stats_resp.content = """{
        "outcome_found": true,
        "effect_size": 0.5,
        "effect_type": "OR",
        "ci_lower": 0.2,
        "ci_upper": 0.8,
        "sample_size": 100
    }"""
    stats_resp.input_tokens = 10
    stats_resp.output_tokens = 10
    
    grade_resp = MagicMock()
    grade_resp.content = '{"grade_summary": "High certainty", "certainty_level": "High"}'
    grade_resp.input_tokens = 10
    grade_resp.output_tokens = 10
    
    def chat_side_effect(messages, **kwargs):
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "").lower()
        
        # Robust matching
        if "extract pico" in system_msg:
            return pico_resp
        elif "methodologist" in system_msg: # Screener says "You are an expert systematic review methodologist"
            return screen_resp
        elif "risk of bias" in system_msg:
            return bias_resp
        elif "statistical extraction" in system_msg:
            return stats_resp
        elif "grade" in system_msg:
            return grade_resp
        else:
            # PICO fallback if "extract pico" isn't unique enough (Pico prompt: "You are an expert medical literature analyst...")
            if "medical literature analyst" in system_msg and "pico" in system_msg:
                return pico_resp
            
            # Default fallback
            return pico_resp 
            
    mock_llm.chat_completion.side_effect = chat_side_effect
    
    # Input Data
    input_data = OrchestratorInput(
        query=PICOQuery(population="Patients", intervention="Drug", comparison="Placebo", outcome="Cure"),
        study_sources=[
            {"study_id": "S1", "title": "T1", "abstract": "A1"},
            {"study_id": "S2", "title": "T2", "abstract": "A2"}
        ],
        outcome_of_interest="Cure"
    )
    
    orchestrator = MetaAnalysisOrchestrator(llm=mock_llm)
    
    # Execute
    result = orchestrator.execute(input_data)
    
    # Assertions
    output = result.output
    
    # Verify both studies were included
    assert len(output.included_study_ids) == 2, f"Studies excluded: {output.exclusion_reasons}"
    
    # Verify synthesis
    # Since both have OR=0.5, pooled should be 0.5
    assert output.synthesis.pooled_estimate.pooled_effect > 0
    assert abs(output.synthesis.pooled_estimate.pooled_effect - 0.5) < 0.05
