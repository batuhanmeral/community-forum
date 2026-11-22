from contextlib import contextmanager

import pytest
from django.core.cache import cache
from django.db.models.signals import post_init


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """DRF throttles use the default cache; clear it between tests so counters reset."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def rows_loaded():
    """Count model instances built from DB rows while the context manager is active."""

    @contextmanager
    def counter(*models):
        loaded = dict.fromkeys(models, 0)
        receivers = []
        for model in models:

            def receiver(sender, _model=model, **kwargs):
                loaded[_model] += 1

            post_init.connect(receiver, sender=model, weak=False)
            receivers.append((receiver, model))
        try:
            yield loaded
        finally:
            for receiver, model in receivers:
                post_init.disconnect(receiver, sender=model)

    return counter


@pytest.fixture
def task_command():
    """Run task commands without leaking process-global worker state into tests."""
    import logging
    import signal

    from django.core.management import call_command

    def run(name, **options):
        signals = [signal.SIGINT, signal.SIGTERM]
        if hasattr(signal, "SIGQUIT"):
            signals.append(signal.SIGQUIT)
        handlers = {sig: signal.getsignal(sig) for sig in signals}
        loggers = [
            logging.getLogger(logger_name)
            for logger_name in [
                "django.tasks",
                "django_tasks_db",
                "django_tasks_db.prune_db_task_results",
            ]
        ]
        logger_states = [(logger, logger.level, logger.handlers[:]) for logger in loggers]
        defaults = {"verbosity": 0}
        if name == "db_worker":
            defaults.update(batch=True, startup_delay=False)
        try:
            return call_command(name, **{**defaults, **options})
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
            for logger, level, original_handlers in logger_states:
                for handler in logger.handlers[:]:
                    if handler not in original_handlers:
                        logger.removeHandler(handler)
                        handler.close()
                logger.handlers = original_handlers
                logger.setLevel(level)

    return run
