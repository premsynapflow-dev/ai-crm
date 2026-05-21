import uuid
from types import SimpleNamespace
from unittest.mock import patch

from app.db.models import AgentCorrection, AutomationRule, ChurnOutcome, Complaint, Customer, KnowledgeSnippet
from app.queue.backends import PostgresQueueBackend, RedisQueueBackend, queue_health
from app.services.feedback_learning import record_agent_correction, record_churn_outcome
from app.services.knowledge import create_snippet, retrieve_snippets
from app.services.model_orchestration import GeminiProvider, ModelOrchestrator
from app.services.workflow_dsl import evaluate_rule, validate_workflow_definition


def test_postgres_queue_backend_fallback(test_db):
    backend = PostgresQueueBackend()
    job = backend.enqueue(test_db, "send_email", {"to_email": "a@example.com"})
    fetched = backend.fetch(test_db)

    assert backend.name == "postgres"
    assert str(job.id) == fetched[0].id
    assert fetched[0].payload["to_email"] == "a@example.com"


def test_redis_queue_backend_with_mocked_client(test_db):
    store = []

    class FakeRedis:
        @classmethod
        def from_url(cls, url, decode_responses=True):
            return cls()

        def ping(self):
            return True

        def rpush(self, key, value):
            store.append(value)

        def lpop(self, key):
            return store.pop(0) if store else None

        def llen(self, key):
            return len(store)

    with patch.dict("sys.modules", {"redis": SimpleNamespace(Redis=FakeRedis)}):
        backend = RedisQueueBackend("redis://local")
        backend.enqueue(test_db, "send_slack", {"text": "hello"})
        assert backend.health(test_db)["pending"] == 1
        fetched = backend.fetch(test_db)

    assert fetched[0].job_type == "send_slack"
    assert fetched[0].payload["text"] == "hello"


def test_workflow_dsl_validation_and_legacy_compatibility(test_db, test_client_record):
    payload = {
        "trigger": {"type": "risk_updated"},
        "conditions": [{"field": "risk_score", "operator": ">", "value": 80}],
        "actions": [{"type": "mark_high_priority"}],
    }
    assert validate_workflow_definition(payload)["valid"] is True

    rule = AutomationRule(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        trigger_type="sentiment",
        trigger_value="-0.2",
        action_type="mark_high_priority",
        condition_definition=[{"field": "sentiment", "operator": "<", "value": -0.2}],
        action_definition=[{"type": "mark_high_priority"}],
    )
    assert evaluate_rule(rule, {"sentiment": -0.6}).matched is True
    assert evaluate_rule(rule, {"sentiment": 0.1}).matched is False


def test_feedback_learning_records_churn_and_correction(test_db, test_client_record):
    customer = Customer(
        id=uuid.uuid4(),
        client_id=test_client_record.id,
        primary_email="learn@example.com",
        emails=["learn@example.com"],
    )
    test_db.add(customer)
    test_db.commit()

    outcome = record_churn_outcome(
        test_db,
        client_id=test_client_record.id,
        customer_id=customer.id,
        outcome_type="retained",
        reason="Saved by outreach",
    )
    correction = record_agent_correction(
        test_db,
        client_id=test_client_record.id,
        correction_type="classification",
        corrected_value={"category": "billing"},
        customer_id=customer.id,
        feedback_score=5,
    )
    test_db.commit()

    assert test_db.query(ChurnOutcome).filter(ChurnOutcome.id == outcome.id).count() == 1
    assert test_db.query(AgentCorrection).filter(AgentCorrection.id == correction.id).count() == 1


def test_knowledge_snippet_keyword_retrieval(test_db, test_client_record):
    create_snippet(
        test_db,
        client_id=test_client_record.id,
        title="Refund policy",
        content="Refunds are reviewed within seven business days.",
        keywords=["refund", "policy"],
    )
    test_db.commit()

    results = retrieve_snippets(test_db, client_id=test_client_record.id, query="customer wants refund")

    assert results
    assert results[0].title == "Refund policy"


def test_model_orchestrator_uses_provider():
    class FakeProvider:
        provider_name = "fake"

        def generate_reply(self, prompt, **kwargs):
            return SimpleNamespace(text="ok", provider="fake", model="fake-model")

    orchestrator = ModelOrchestrator(provider=FakeProvider())
    result = orchestrator.generate_reply("hello")

    assert result.text == "ok"
    assert result.provider == "fake"
